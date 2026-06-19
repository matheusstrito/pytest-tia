"""A minimal 'remote' for sharing impact maps across CI runners.

Local maps under ``.tia/`` are per-checkout. In CI the runner that builds
the map (on the base branch) is almost never the runner that consumes it
(on a PR), so the map has to live somewhere shared.

Maps are addressed by the **git ref they were recorded at**, so a PR job
can pull the exact map built for its base. A ``latest.json`` pointer is
also kept as a fallback when the consumer doesn't know the precise ref.

Two backends, picked from the remote string:

* ``http://`` / ``https://`` — talk to ``tia.server`` (or any store that
  answers GET/PUT on ``/maps/<name>``). This is the zero-friction CI path.
* anything else — a plain directory (a mounted cache volume, an artifact
  dir synced to/from S3, a checked-out cache repo).

The surface stays tiny (`push`/`pull` by ref) so a real S3/GCS backend can
slot in the same way later.
"""

import os
import shutil
import urllib.error
import urllib.request

LATEST = "latest.json"


def _key(ref: str | None) -> str:
    """Safe object name for a ref. None/unknown collapses to latest."""
    if not ref:
        return LATEST
    safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in ref)
    return f"{safe}.json"


def _is_http(remote: str) -> bool:
    return remote.startswith(("http://", "https://"))


def _http_put(url: str, data: bytes) -> None:
    req = urllib.request.Request(url, data=data, method="PUT")
    with urllib.request.urlopen(req, timeout=30):
        pass


def _http_get(url: str) -> bytes | None:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _write(dest: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(data)


def push(local_map_path: str, remote: str, ref: str | None) -> str:
    """Publish the local map under its ref, and update the latest pointer."""
    key = _key(ref)
    if _is_http(remote):
        base = remote.rstrip("/")
        with open(local_map_path, "rb") as fh:
            data = fh.read()
        _http_put(f"{base}/maps/{key}", data)
        _http_put(f"{base}/maps/{LATEST}", data)
        return f"{base}/maps/{key}"

    os.makedirs(remote, exist_ok=True)
    dst = os.path.join(remote, key)
    shutil.copyfile(local_map_path, dst)
    shutil.copyfile(local_map_path, os.path.join(remote, LATEST))
    return dst


def pull(remote: str, ref: str | None, dest: str) -> str | None:
    """Fetch the map for ``ref`` (else latest) into ``dest``. None if absent."""
    candidates = [_key(ref), LATEST] if ref else [LATEST]

    if _is_http(remote):
        base = remote.rstrip("/")
        for name in candidates:
            data = _http_get(f"{base}/maps/{name}")
            if data is not None:
                _write(dest, data)
                return f"{base}/maps/{name}"
        return None

    for name in candidates:
        src = os.path.join(remote, name)
        if os.path.exists(src):
            with open(src, "rb") as fh:
                _write(dest, fh.read())
            return src
    return None
