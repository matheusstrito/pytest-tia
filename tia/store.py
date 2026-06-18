"""Load/save the test->lines impact map as JSON under .tia/map.json."""

import datetime
import json
import os

TIA_DIR = ".tia"
MAP_NAME = "map.json"


def tia_dir(root: str) -> str:
    return os.path.join(root, TIA_DIR)


def map_path(root: str) -> str:
    return os.path.join(tia_dir(root), MAP_NAME)


def save_map(root: str, result: dict[str, dict[str, set[int]]]) -> str:
    os.makedirs(tia_dir(root), exist_ok=True)
    data = {
        "version": 1,
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "tests": {
            nodeid: {f: sorted(lines) for f, lines in files.items()}
            for nodeid, files in sorted(result.items())
        },
    }
    path = map_path(root)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    return path


def load_map(root: str) -> dict:
    with open(map_path(root), encoding="utf-8") as fh:
        data = json.load(fh)
    for nodeid, files in data["tests"].items():
        data["tests"][nodeid] = {f: set(lines) for f, lines in files.items()}
    return data
