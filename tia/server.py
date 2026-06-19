"""A minimal, zero-dependency HTTP backend for sharing tia maps.

    GET  /maps/<name>   -> map bytes (404 if absent)
    PUT  /maps/<name>   -> store map bytes
    GET  /  or /health  -> liveness check

Backed by a directory; run one per team or inside CI. Stdlib only — no
FastAPI, no external deps — so

    python -m tia.server --dir ./tia-maps --port 8000

just works. Put nginx / an auth proxy / S3 in front later; the client
(`tia push/pull --... <url>`) only needs GET and PUT on ``/maps/<name>``.

This is deliberately not a general file server: only ``/maps/<flat-name>``
is reachable and path separators are rejected, so it can't be walked out
of its directory.
"""

import argparse
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PREFIX = "/maps/"


def _resolve(root: str, path: str) -> str | None:
    """Map a request path to a file under root, or None if illegal."""
    if not path.startswith(PREFIX):
        return None
    name = path[len(PREFIX):]
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        return None
    return os.path.join(root, name)


def make_handler(root: str):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes = b"") -> None:
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/health"):
                return self._send(200, b"tia-server ok\n")
            fp = _resolve(root, self.path)
            if fp and os.path.isfile(fp):
                with open(fp, "rb") as fh:
                    return self._send(200, fh.read())
            return self._send(404, b"not found\n")

        def do_PUT(self):
            fp = _resolve(root, self.path)
            if not fp:
                return self._send(400, b"bad path\n")
            length = int(self.headers.get("Content-Length", 0))
            data = self.rfile.read(length)
            os.makedirs(root, exist_ok=True)
            with open(fp, "wb") as fh:
                fh.write(data)
            return self._send(201, b"stored\n")

        def log_message(self, *args):  # keep CI logs quiet
            pass

    return Handler


def serve(root: str, host: str, port: int) -> None:
    os.makedirs(root, exist_ok=True)
    httpd = ThreadingHTTPServer((host, port), make_handler(root))
    print(f"[tia-server] serving {os.path.abspath(root)} "
          f"on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="tia-server",
                                description="Shared store for tia impact maps")
    p.add_argument("--dir", default="./tia-maps", help="directory to store maps in")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args(argv)
    serve(a.dir, a.host, a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
