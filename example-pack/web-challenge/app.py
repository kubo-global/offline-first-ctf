"""The web target of the example pack: one page with a flag in its source."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = b"""<!doctype html><meta charset="utf-8"><title>Nothing to see</title>
<h1>Nothing to see here</h1>
<p>This page has no secrets. Honestly.</p>
<!-- FLAG{view_source_first} -->
"""


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *a):
        pass


ThreadingHTTPServer(("0.0.0.0", 8081), H).serve_forever()
