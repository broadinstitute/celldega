from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading as thr


class CORSHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Custom HTTP request handler with CORS support."""

    def end_headers(self) -> None:
        """Add CORS headers to the response."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers", "X-Requested-With, content-type, Authorization"
        )
        self.send_header("Access-Control-Allow-Credentials", "true")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        """Handle OPTIONS requests for CORS preflight."""
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:
        """Override log_message to prevent logging to the console."""
        pass


def get_local_server() -> int:
    """Start a local HTTP server with CORS support and return the port number.

    Returns:
        int: The port number on which the server is running.
    """
    server = HTTPServer(("", 0), CORSHTTPRequestHandler)
    print(f"Server running on port {server.server_address[1]}")

    service = thr.Thread(target=server.serve_forever)
    service.start()

    return server.server_address[1]