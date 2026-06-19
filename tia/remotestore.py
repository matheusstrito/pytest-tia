"""A minimal 'remote' for sharing impact maps across CI runners.

Local maps under ``.tia/`` are per-checkout. In CI the runner that builds
the map (on the base branch) is almost never the runner that consumes it
(on a PR), so the map has to live somewhere shared.

Maps are addressed by the **git ref they were recorded at**, so a PR job
can pull the exact map built for its base. A ``latest.json`` pointer is
also kept as a fallback when the consumer doesn't know the precise ref.

The backend here is a plain directory — which already models the common
CI cases: a mounted cache volume, an artifact directory synced to/from
S3, or a checked-out cache repo. The surface is deliberately tiny
(`push`/`pull` by ref) so an S3/HTTP backend can slot in behind it later.
"""

import os
import shutil

LATEST = "latest.json"


def _key(ref: str | None) -> str:
    """Filesystem-safe name for a ref. None/unknown collapses to latest."""
    if not ref:
        return LATEST
    safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in ref)
    return f"{safe}.json"


def push(local_map_path: str, remote: str, ref: str | None) -> str:
    """Copy the local map into the remote under its ref, update latest."""
    os.makedirs(remote, exist_ok=True)
    dst = os.path.join(remote, _key(ref))
    shutil.copyfile(local_map_path, dst)
    shutil.copyfile(local_map_path, os.path.join(remote, LATEST))
    return dst


def pull(remote: str, ref: str | None, dest: str) -> str | None:
    """Fetch the map for ``ref`` (else latest) into ``dest``. None if absent."""
    candidates = [_key(ref), LATEST] if ref else [LATEST]
    for name in candidates:
        src = os.path.join(remote, name)
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            shutil.copyfile(src, dest)
            return src
    return None
