"""
webhook_receiver.py
Minimal HTTP server for integration testing webhook delivery.
Stores received POST bodies in memory; exposes GET /webhooks to retrieve them.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

_received: list[dict] = []


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            _received.append(json.loads(body))
        except Exception:
            pass
        self.send_response(200)
        self.end_headers()

    def do_GET(self):  # noqa: N802
        payload = json.dumps(_received).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):  # noqa: A002
        pass  # suppress access logs


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), WebhookHandler)
    server.serve_forever()
