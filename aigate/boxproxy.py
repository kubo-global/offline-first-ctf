#!/usr/bin/env python3
"""
The only way out of the player boxes: a small HTTP proxy with a fixed allowlist.

The boxes sit on an internal Docker network with no route anywhere, so even when the
server has internet (for the AI helper), a box does not. Tools in the box (curl, wget,
python) are pointed here by http_proxy, and this proxy forwards only requests for the
server's own address to the room's services, by name on the inside network:

    http://<SERVER_ADDR>:8000   -> ctfd:8000          the game
    http://<SERVER_ADDR>:8080   -> tutorials:80       tutorials and CyberChef
    http://<SERVER_ADDR>:8081   -> webchallenge:8081  the web challenges
    http://<SERVER_ADDR>:8083   -> aigate:8083        the AI helper

Anything else (another host, another port, HTTPS tunnels) gets a plain refusal.
"""
import http.client, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

SERVER = os.environ.get("SERVER_ADDR", "10.0.0.1")
ROUTES = {8000: ("ctfd", 8000), 8080: ("tutorials", 80), 8081: ("webchallenge", 8081), 8083: ("aigate", 8083)}
HOP = {"connection", "keep-alive", "proxy-connection", "proxy-authorization", "te", "trailer",
       "transfer-encoding", "upgrade"}


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"   # one request per connection, the end is the close
    server_version = "ctf-boxproxy"
    sys_version = ""

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def refuse(self, why):
        b = (f"Not reachable from your box: {why}\n"
             f"From here you can reach the game, the tutorials, the web challenges and the AI helper,\n"
             f"all at http://{SERVER}:<port>. Everything else stays outside the CTF.\n").encode()
        self.send_response(403)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_CONNECT(self):
        self.refuse("HTTPS and tunnels are off")

    def handle_any(self):
        u = urlsplit(self.path)
        if u.scheme != "http" or not u.hostname:
            return self.refuse("send the full address, like http://%s:8000/" % SERVER)
        port = u.port or 80
        if u.hostname != SERVER or port not in ROUTES:
            return self.refuse(f"{u.hostname}:{port}")
        host, tport = ROUTES[port]
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        path = (u.path or "/") + ("?" + u.query if u.query else "")
        try:
            c = http.client.HTTPConnection(host, tport, timeout=150)
            c.request(self.command, path, body=body, headers=headers)
            r = c.getresponse()
        except OSError as e:
            return self.refuse(f"the service did not answer ({e.__class__.__name__})")
        self.send_response(r.status, r.reason)
        for k, v in r.getheaders():
            if k.lower() not in HOP and k.lower() != "content-length":
                self.send_header(k, v)
        length = r.getheader("Content-Length")
        if length and not r.getheader("Transfer-Encoding"):
            self.send_header("Content-Length", length)
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
        c.close()

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = handle_any


if __name__ == "__main__":
    print(f"boxproxy: boxes may reach {SERVER} on ports {sorted(ROUTES)}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 3128), Proxy).serve_forever()
