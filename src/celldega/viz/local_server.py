"""
Local server module for handling HTTP requests with CORS support.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer, SimpleHTTPRequestHandler
import ipaddress
import socket
from socketserver import ThreadingMixIn
import threading as thr
from typing import ClassVar
from urllib.parse import unquote, urlparse

import requests


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in a new thread."""

    daemon_threads = True


class CORSHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Custom HTTP request handler with CORS support."""

    def end_headers(self) -> None:
        """Add CORS headers to the response."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Range, X-Requested-With, Content-Type, Authorization",
        )
        self.send_header(
            "Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, Content-Length"
        )
        self.send_header("Access-Control-Allow-Credentials", "true")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        """Handle OPTIONS requests for CORS preflight."""
        self.send_response(200)
        self.end_headers()

    def log_message(self, format_str: str, *args) -> None:
        """Override log_message to prevent logging to the console."""


def _is_private_ip(ip_str: str) -> bool:
    """
    Check if an IP address is private, loopback, or otherwise internal.

    Blocks RFC1918 private ranges, loopback, link-local, and other non-public IPs.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        # If we can't parse it, reject it
        return True


class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler that proxies requests to remote URLs.

    Handles requests like:
        /proxy/https://example.com/path/to/file.parquet

    Supports Range requests for partial content fetching.

    Security: URLs are validated to prevent SSRF attacks:
    - Only http/https schemes allowed
    - Private/loopback IPs are blocked
    - When remote_base_url is set, /proxy/ requests are constrained to that host
    """

    # Class variables
    remote_base_url = None
    # Shared session for connection pooling (reuses TCP connections)
    _session = None
    # Cache for small responses (footers, metadata) - keyed by (url, range_header)
    _cache: ClassVar[dict] = {}
    _cache_max_size = 100  # Max cached items
    _cache_max_bytes = 65536  # Only cache responses < 64KB

    @classmethod
    def get_session(cls):
        """Get or create a shared requests session for connection pooling."""
        if cls._session is None:
            cls._session = requests.Session()
            # Increase pool size for concurrent requests
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=20, pool_maxsize=50, max_retries=3
            )
            cls._session.mount("http://", adapter)
            cls._session.mount("https://", adapter)
        return cls._session

    @classmethod
    def get_cached(cls, cache_key):
        """Get a cached response if available."""
        return cls._cache.get(cache_key)

    @classmethod
    def set_cached(cls, cache_key, data, headers):
        """Cache a small response."""
        if len(cls._cache) >= cls._cache_max_size:
            # Simple eviction: clear oldest half
            keys = list(cls._cache.keys())
            for k in keys[: len(keys) // 2]:
                del cls._cache[k]
        cls._cache[cache_key] = (data, headers)

    def _validate_remote_url(self, remote_url: str) -> str | None:
        """
        Validate a remote URL to prevent SSRF attacks.

        Returns a reconstructed safe URL if valid, or None if the URL should be rejected.

        Security checks:
        1. Scheme must be http or https
        2. Hostname must resolve to a public (non-private) IP
        3. If remote_base_url is configured and using /proxy/ path,
           the requested host must match the configured base URL host
        """
        try:
            parsed = urlparse(remote_url)
        except Exception:
            return None

        # Check scheme - must be http or https
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return None

        # Check hostname exists
        hostname = parsed.hostname
        if not parsed.netloc or not hostname:
            return None

        # If remote_base_url is configured, enforce host matching for /proxy/ requests
        # This prevents using /proxy/ to escape to arbitrary hosts
        if self.remote_base_url and self.path.startswith("/proxy/"):
            try:
                base_parsed = urlparse(self.remote_base_url)
                if hostname != base_parsed.hostname:
                    # Reject requests to hosts different from configured base
                    return None
            except Exception:
                return None

        # Resolve hostname and check if IP is private/internal
        try:
            # Get all IP addresses for the hostname
            port = parsed.port or (443 if scheme == "https" else 80)
            addr_info = socket.getaddrinfo(hostname, port)
            for _family, _socktype, _proto, _canonname, sockaddr in addr_info:
                ip_str = sockaddr[0]
                if _is_private_ip(ip_str):
                    return None
        except socket.gaierror:
            # DNS resolution failed
            return None

        # Reconstruct URL from validated components to break taint chain
        # This ensures CodeQL sees this as a "clean" URL
        safe_netloc = hostname
        if parsed.port:
            safe_netloc = f"{hostname}:{parsed.port}"
        safe_path = parsed.path if parsed.path else "/"
        safe_query = f"?{parsed.query}" if parsed.query else ""
        safe_fragment = f"#{parsed.fragment}" if parsed.fragment else ""

        return f"{scheme}://{safe_netloc}{safe_path}{safe_query}{safe_fragment}"

    def _send_cors_headers(self):
        """Add CORS headers to allow cross-origin requests."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Range, X-Requested-With, Content-Type, Authorization",
        )
        self.send_header(
            "Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, Content-Length"
        )
        self.send_header("Access-Control-Allow-Credentials", "true")

    def do_OPTIONS(self) -> None:
        """Handle OPTIONS requests for CORS preflight."""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_HEAD(self) -> None:
        """Handle HEAD requests."""
        self._proxy_request(method="HEAD")

    def do_GET(self) -> None:
        """Handle GET requests by proxying to the remote URL."""
        self._proxy_request(method="GET")

    def _proxy_request(self, method="GET") -> None:
        """
        Proxy the request to the remote server.

        Passes through Range headers for partial content requests.
        Caches small responses (< 64KB) like Parquet footers for performance.
        """
        # Parse the request path
        path = self.path

        # Check if this is a proxy request
        if path.startswith("/proxy/"):
            # Extract the remote URL from the path
            remote_url = unquote(path[7:])  # Remove "/proxy/" prefix
        elif self.remote_base_url:
            # Use the configured base URL + path
            # Remove leading slash from path
            clean_path = path.lstrip("/")
            remote_url = f"{self.remote_base_url.rstrip('/')}/{clean_path}"
        else:
            self.send_error(400, "No remote URL configured")
            return

        # Validate URL to prevent SSRF
        validated_url = self._validate_remote_url(remote_url)
        if validated_url is None:
            self.send_error(400, "Invalid or disallowed URL")
            return
        remote_url = validated_url

        # Build headers to forward (especially Range for partial content)
        forward_headers = {}

        # Forward Range header if present
        range_header = self.headers.get("Range")
        if range_header:
            forward_headers["Range"] = range_header

        # Check cache for small Range requests (like footer reads)
        cache_key = (remote_url, range_header) if range_header else None
        if cache_key and method == "GET":
            cached = self.get_cached(cache_key)
            if cached:
                data, headers = cached
                self.send_response(206 if range_header else 200)
                self._send_cors_headers()
                for k, v in headers.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)
                return

        try:
            # Use shared session for connection pooling
            session = self.get_session()

            # Make the request to the remote server
            if method == "HEAD":
                response = session.head(
                    remote_url,
                    headers=forward_headers,
                    allow_redirects=True,
                    timeout=30,
                )
            else:
                response = session.get(
                    remote_url,
                    headers=forward_headers,
                    allow_redirects=True,
                    timeout=60,
                    stream=True,
                )

            # Send the response status
            self.send_response(response.status_code)

            # Add CORS headers
            self._send_cors_headers()

            # Collect headers to forward (sanitize to prevent HTTP response splitting)
            response_headers = {}
            for header_name in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                if header_name in response.headers:
                    # Sanitize header value to prevent HTTP response splitting
                    # Remove any CR/LF characters that could inject new headers
                    raw_value = response.headers[header_name]
                    safe_value = str(raw_value).replace("\r", "").replace("\n", "")
                    response_headers[header_name] = safe_value

            for k, v in response_headers.items():
                self.send_header(k, v)

            self.end_headers()

            # Send the response body (for GET requests)
            if method == "GET":
                # Check if this is a small response we should cache
                content_length = int(response.headers.get("Content-Length", 0))
                if cache_key and content_length > 0 and content_length <= self._cache_max_bytes:
                    # Small response - read entirely and cache
                    data = response.content
                    self.set_cached(cache_key, data, response_headers)
                    self.wfile.write(data)
                else:
                    # Large response - stream in chunks
                    for chunk in response.iter_content(chunk_size=1048576):  # 1MB chunks
                        if chunk:
                            self.wfile.write(chunk)

        except requests.exceptions.Timeout:
            self.send_error(504, "Gateway Timeout")
        except requests.exceptions.RequestException as e:
            self.send_error(502, f"Bad Gateway: {e!s}")
        except Exception as e:
            self.send_error(500, f"Internal Server Error: {e!s}")

    def log_message(self, format_str: str, *args) -> None:
        """Override log_message to prevent logging to the console."""


def get_local_server() -> int:
    """
    Start a local HTTP server with CORS support and return the port number.

    Returns:
        int: The port number on which the server is running.
    """
    server = ThreadedHTTPServer(("", 0), CORSHTTPRequestHandler)

    service = thr.Thread(target=server.serve_forever, daemon=True)
    service.start()

    return server.server_address[1]


def get_proxy_server(remote_base_url: str | None = None, verbose: bool = False) -> int:
    """
    Start a local proxy server that forwards requests to a remote URL.

    This is useful for bypassing CORS restrictions when the remote server
    (like Hugging Face) doesn't support CORS for Range requests.

    Security: The proxy validates all URLs to prevent SSRF attacks:
    - Only http/https schemes are allowed
    - Private/loopback IP addresses are blocked
    - When remote_base_url is set, /proxy/ requests are constrained to that host

    Args:
        remote_base_url: Optional base URL for the remote server.
            If provided, requests to the proxy will be forwarded to this URL.
            If not provided, use /proxy/FULL_URL format.
        verbose: If True, print log messages.

    Returns:
        int: The port number on which the proxy server is running.

    Example:
        >>> port = get_proxy_server("https://huggingface.co/datasets/user/repo/resolve/main/folder")
        >>> # Now use http://localhost:{port}/file.parquet
        >>> # Or use http://localhost:{port}/proxy/https://huggingface.co/.../other/file.parquet
    """

    # Create a custom handler class with the remote URL configured
    class ConfiguredProxyHandler(ProxyHTTPRequestHandler):
        pass

    ConfiguredProxyHandler.remote_base_url = remote_base_url

    if verbose:
        # Override log_message to print
        def log_message(self, format_str, *args):
            print(f"[Proxy] {format_str % args}")

        ConfiguredProxyHandler.log_message = log_message

    server = ThreadedHTTPServer(("", 0), ConfiguredProxyHandler)

    service = thr.Thread(target=server.serve_forever, daemon=True)
    service.start()

    port = server.server_address[1]

    if verbose:
        print(f"[Proxy] Server started on port {port}")
        if remote_base_url:
            print(f"[Proxy] Proxying requests to: {remote_base_url}")

    return port
