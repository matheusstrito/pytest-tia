"""Decide which tests to run given a coverage map and a set of changes.

Three rules, in order of precision:

1. Line-level hit: a changed line is one a test actually executed.
   This is the precise, ideal case.
2. Module-level fallback: a changed line in a covered file that no
   test executed (e.g. a module-level constant, a `def` signature, an
   import). We can't pin it to one test, so we conservatively select
   every test that touches that file. Keeps us *sound* for top-level
   edits without giving up precision for in-function edits.
3. New tests: any currently-collected test not in the map has never
   been measured, so we always run it.
"""


def select_tests(
    tia_map: dict,
    changed: dict[str, set[int]],
    all_nodeids: set[str],
) -> dict[str, str]:
    """Return ``{nodeid: human-readable reason}`` for tests to run."""
    map_tests: dict[str, dict[str, set[int]]] = tia_map["tests"]
    selected: dict[str, str] = {}

    for path, lines in changed.items():
        tests_touching_file = [t for t, files in map_tests.items() if path in files]
        for lineno in sorted(lines):
            hit = False
            for t in tests_touching_file:
                if lineno in map_tests[t][path]:
                    selected.setdefault(t, f"executes {path}:{lineno}")
                    hit = True
            if not hit and tests_touching_file:
                for t in tests_touching_file:
                    selected.setdefault(
                        t, f"imports {path} (module-level change near line {lineno})"
                    )

    known = set(map_tests)
    for nodeid in all_nodeids:
        if nodeid not in known:
            selected.setdefault(nodeid, "new test (never measured)")

    return selected
