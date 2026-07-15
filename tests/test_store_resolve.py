"""Round-trip tests for the on-disk map (store) and git-fallback resolution.

These cover the paths test_core.py leaves out: save/load with the reads,
funcmaps and dynamic sections populated, and the resolve branches that fall
back to `git show` instead of the baked funcmaps.
"""

import subprocess

from tia import resolve, store


# --- store: full save -> load round-trip ---------------------------------

def test_save_map_writes_file_and_returns_path(tmp_path):
    root = str(tmp_path)
    result = {"t_add": {"calc.py": {"add"}}}
    path = store.save_map(root, result, "abc123")
    assert path == store.map_path(root)
    assert (tmp_path / ".tia" / "map.json").exists()


def test_roundtrip_preserves_tests_reads_funcmaps_dynamic(tmp_path):
    root = str(tmp_path)
    result = {"t_add": {"calc.py": {"add", "helper"}}}
    reads = {"t_add": {"fixtures/data.json"}}
    funcmaps = {"calc.py": {12: "add", 13: "add"}}
    dynamic = {"calc.py": ["getattr"]}

    store.save_map(root, result, "ref42", reads=reads,
                   funcmaps=funcmaps, dynamic=dynamic)
    data = store.load_map(root)

    assert data["version"] == 5
    assert data["ref"] == "ref42"
    # sets come back as sets, not sorted lists
    assert data["tests"]["t_add"]["calc.py"] == {"add", "helper"}
    assert data["reads"]["t_add"] == {"fixtures/data.json"}
    # funcmap line numbers come back as ints, not the on-disk string keys
    assert data["funcmaps"]["calc.py"] == {12: "add", 13: "add"}
    assert data["dynamic"]["calc.py"] == ["getattr"]


def test_load_map_defaults_missing_optional_sections(tmp_path):
    # A minimal v-any map with no reads/funcmaps/dynamic still loads clean.
    root = str(tmp_path)
    store.save_map(root, {"t_x": {"m.py": {"f"}}}, None)
    data = store.load_map(root)
    assert data["reads"] == {}
    assert data["funcmaps"] == {}
    assert data["dynamic"] == {}


# --- resolve: the git-show fallback (no baked funcmap for the file) -------

def _init_repo(tmp_path, filename, source):
    cwd = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=cwd, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=cwd, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=cwd, check=True)
    (tmp_path / filename).write_text(source, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=cwd, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=cwd, check=True)
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd,
                         capture_output=True, text=True, check=True)
    return cwd, rev.stdout.strip()


def test_resolve_falls_back_to_git_show_when_not_in_funcmaps(tmp_path):
    src = "def top():\n    return 1\n"
    cwd, ref = _init_repo(tmp_path, "m.py", src)
    changes = {"m.py": {"mod": {2}, "ins": set()}}
    # no funcmaps -> must read the blob at `ref` via git show
    fc, mf = resolve.changed_functions(changes, ref=ref, cwd=cwd, funcmaps={})
    assert fc == {"m.py": {"top"}}
    assert mf == set()


def test_resolve_unparseable_blob_is_conservative(tmp_path):
    src = "def broken(:\n    pass\n"  # syntax error on purpose
    cwd, ref = _init_repo(tmp_path, "bad.py", src)
    changes = {"bad.py": {"mod": {1}, "ins": set()}}
    fc, mf = resolve.changed_functions(changes, ref=ref, cwd=cwd, funcmaps={})
    assert fc == {}
    assert mf == {"bad.py"}          # unparseable -> whole file is impacted


def test_resolve_missing_blob_at_ref_is_skipped(tmp_path):
    cwd, ref = _init_repo(tmp_path, "m.py", "def top():\n    return 1\n")
    # file never existed at this ref, not in funcmaps -> silently skipped
    changes = {"ghost.py": {"mod": {1}, "ins": set()}}
    fc, mf = resolve.changed_functions(changes, ref=ref, cwd=cwd, funcmaps={})
    assert fc == {}
    assert mf == set()


def test_resolve_non_python_file_ignored():
    changes = {"config.yaml": {"mod": {1}, "ins": set()}}
    fc, mf = resolve.changed_functions(changes, ref="x", cwd=".", funcmaps={})
    assert fc == {}
    assert mf == set()


def test_resolve_insertion_inside_function_selected(tmp_path):
    changes = {"m.py": {"mod": set(), "ins": {2}}}
    funcmaps = {"m.py": {1: "top", 2: "top"}}
    fc, mf = resolve.changed_functions(changes, ref="x", cwd=".", funcmaps=funcmaps)
    assert fc == {"m.py": {"top"}}
    assert mf == set()
