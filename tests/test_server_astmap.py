"""Direct HTTP tests for the map server and astmap edge cases.

test_core.py already drives the server through remotestore; here we hit the
health check, the 404 path and the bad-PUT path directly so those branches
are covered without going through the client.
"""

import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

from tia import astmap, server


def _serve(root):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(str(root)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def _get(url):
    with urllib.request.urlopen(url) as r:
        return r.status, r.read()


def test_health_endpoint_ok(tmp_path):
    httpd, base = _serve(tmp_path)
    try:
        status, body = _get(base + "/health")
        assert status == 200
        assert b"ok" in body
        # bare root works too
        status2, _ = _get(base + "/")
        assert status2 == 200
    finally:
        httpd.shutdown()


def test_get_missing_map_is_404(tmp_path):
    httpd, base = _serve(tmp_path)
    try:
        try:
            _get(base + "/maps/nope.json")
            assert False, "expected 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        httpd.shutdown()


def test_put_then_get_roundtrip(tmp_path):
    httpd, base = _serve(tmp_path)
    try:
        req = urllib.request.Request(
            base + "/maps/m.json", data=b'{"ref":"z"}', method="PUT")
        with urllib.request.urlopen(req) as r:
            assert r.status == 201
        status, body = _get(base + "/maps/m.json")
        assert status == 200
        assert body == b'{"ref":"z"}'
    finally:
        httpd.shutdown()


def test_put_bad_path_is_400(tmp_path):
    httpd, base = _serve(tmp_path)
    try:
        req = urllib.request.Request(
            base + "/maps/../evil", data=b"x", method="PUT")
        try:
            urllib.request.urlopen(req)
            assert False, "expected 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        httpd.shutdown()


# --- astmap: nested functions and empty source ---------------------------

def test_astmap_nested_function_inner_wins():
    src = "def outer():\n    def inner():\n        return 1\n    return inner\n"
    m = astmap.line_to_qualname(src)
    assert m[3] == "outer.inner"      # inner body maps to the inner qualname
    assert m[4] == "outer"            # back out at outer's return


def test_astmap_empty_source_is_empty_map():
    assert astmap.line_to_qualname("") == {}


def test_astmap_from_file(tmp_path):
    p = tmp_path / "s.py"
    p.write_text("def f():\n    return 1\n", encoding="utf-8")
    m = astmap.line_to_qualname_from_file(str(p))
    assert m[2] == "f"
