"""
Local server module for handling HTTP requests with CORS support.
"""

from functools import lru_cache
from http.server import HTTPServer, SimpleHTTPRequestHandler, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import threading as thr
from urllib.parse import urlparse, unquote
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
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, Content-Length")
        self.send_header("Access-Control-Allow-Credentials", "true")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        """Handle OPTIONS requests for CORS preflight."""
        self.send_response(200)
        self.end_headers()

    def log_message(self, format_str: str, *args) -> None:
        """Override log_message to prevent logging to the console."""


class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler that proxies requests to remote URLs.

    Handles requests like:
        /proxy/https://example.com/path/to/file.parquet

    Supports Range requests for partial content fetching.
    """

    # Class variables
    remote_base_url = None
    # Shared session for connection pooling (reuses TCP connections)
    _session = None
    # Cache for small responses (footers, metadata) - keyed by (url, range_header)
    _cache = {}
    _cache_max_size = 100  # Max cached items
    _cache_max_bytes = 65536  # Only cache responses < 64KB

    @classmethod
    def get_session(cls):
        """Get or create a shared requests session for connection pooling."""
        if cls._session is None:
            cls._session = requests.Session()
            # Increase pool size for concurrent requests
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=20,
                pool_maxsize=50,
                max_retries=3
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
            for k in keys[:len(keys) // 2]:
                del cls._cache[k]
        cls._cache[cache_key] = (data, headers)

    def _send_cors_headers(self):
        """Add CORS headers to allow cross-origin requests."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Range, X-Requested-With, Content-Type, Authorization",
        )
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, Content-Length")
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

            # Collect headers to forward
            response_headers = {}
            if "Content-Type" in response.headers:
                response_headers["Content-Type"] = response.headers["Content-Type"]
            if "Content-Length" in response.headers:
                response_headers["Content-Length"] = response.headers["Content-Length"]
            if "Content-Range" in response.headers:
                response_headers["Content-Range"] = response.headers["Content-Range"]
            if "Accept-Ranges" in response.headers:
                response_headers["Accept-Ranges"] = response.headers["Accept-Ranges"]

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
            self.send_error(502, f"Bad Gateway: {str(e)}")
        except Exception as e:
            self.send_error(500, f"Internal Server Error: {str(e)}")

    def log_message(self, format_str: str, *args) -> None:
        """Override log_message to prevent logging to the console."""
        pass


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


def get_proxy_server(remote_base_url: str = None, verbose: bool = False) -> int:
    """
    Start a local proxy server that forwards requests to a remote URL.

    This is useful for bypassing CORS restrictions when the remote server
    (like Hugging Face) doesn't support CORS for Range requests.

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
        >>> # Or use http://localhost:{port}/proxy/https://example.com/other/file.parquet
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
