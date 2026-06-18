"""Decide which tests to run, at method-level granularity.

Three rules:

1. Function hit — a test executed a function whose body changed.
   Immune to line shifts elsewhere in the file.
2. Module-level fallback — a file had a module-level *modification*
   (constant, import, class body). Run every test touching that file.
3. New test — any collected test not in the map has never been measured.
"""


def select_tests(
    map_tests: dict[str, dict[str, set[str]]],
    func_changes: dict[str, set[str]],
    module_files: set[str],
    all_nodeids: set[str],
) -> dict[str, str]:
    """Return ``{nodeid: human-readable reason}`` for tests to run."""
    selected: dict[str, str] = {}

    for path, changed_funcs in func_changes.items():
        for nodeid, files in map_tests.items():
            executed = files.get(path)
            if executed:
                hit = changed_funcs & executed
                if hit:
                    selected.setdefault(nodeid, f"{path}: {', '.join(sorted(hit))}")

    for path in module_files:
        for nodeid, files in map_tests.items():
            if path in files:
                selected.setdefault(nodeid, f"module-level change in {path}")

    known = set(map_tests)
    for nodeid in all_nodeids:
        if nodeid not in known:
            selected.setdefault(nodeid, "new test (never measured)")

    return selected
