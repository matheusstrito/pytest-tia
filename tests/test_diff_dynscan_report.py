"""Tests for diff parsing, dynamic-marker scanning and the CI report.

diff.changed_lines is driven through a real temp git repo (so the hunk
header parsing is exercised end to end); dynscan and report are pure
string in / string out.
"""

import subprocess

from tia import diff, dynscan, report


# --- diff: real hunk headers from a temp repo ----------------------------

def _repo(tmp_path):
    cwd = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=cwd, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=cwd, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=cwd, check=True)
    return cwd


def _commit(cwd, name, text):
    from pathlib import Path
    Path(cwd, name).write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=cwd, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "c"], cwd=cwd, check=True)


def test_diff_detects_modified_line(tmp_path):
    cwd = _repo(tmp_path)
    _commit(cwd, "m.py", "a = 1\nb = 2\nc = 3\n")
    from pathlib import Path
    Path(cwd, "m.py").write_text("a = 1\nb = 99\nc = 3\n", encoding="utf-8")
    changes = diff.changed_lines("HEAD", cwd=cwd)
    assert 2 in changes["m.py"]["mod"]


def test_diff_detects_pure_insertion(tmp_path):
    cwd = _repo(tmp_path)
    _commit(cwd, "m.py", "a = 1\nb = 2\n")
    from pathlib import Path
    Path(cwd, "m.py").write_text("a = 1\nNEW = 0\nb = 2\n", encoding="utf-8")
    changes = diff.changed_lines("HEAD", cwd=cwd)
    # a pure insertion records anchor lines under "ins", not "mod"
    assert changes["m.py"]["ins"]
    assert not changes["m.py"]["mod"]


def test_diff_ignores_deleted_file_target(tmp_path):
    cwd = _repo(tmp_path)
    _commit(cwd, "gone.py", "x = 1\n")
    subprocess.run(["git", "rm", "-q", "gone.py"], cwd=cwd, check=True)
    changes = diff.changed_lines("HEAD", cwd=cwd)
    # +++ /dev/null means the new side is nothing; no entry is created for it
    assert "gone.py" not in changes or changes == {}


# --- dynscan: reflection markers -----------------------------------------

def test_dynscan_flags_computed_getattr():
    src = "def f(o, n):\n    return getattr(o, n)\n"
    markers = dynscan.find_markers(src)
    assert any("getattr" in m for m in markers)


def test_dynscan_ignores_literal_getattr():
    src = "def f(o):\n    return getattr(o, 'x')\n"
    assert dynscan.find_markers(src) == []


def test_dynscan_flags_eval_and_getattr_hook():
    src = "def f(s):\n    return eval(s)\n\n\nclass C:\n    def __getattr__(self, n):\n        return 1\n"
    markers = dynscan.find_markers(src)
    assert any("eval" in m for m in markers)
    assert any("__getattr__" in m for m in markers)


def test_dynscan_flags_importlib_import_module():
    src = "import importlib\n\n\ndef f(n):\n    return importlib.import_module(n)\n"
    markers = dynscan.find_markers(src)
    assert any("import_module" in m for m in markers)


def test_dynscan_syntax_error_returns_empty():
    assert dynscan.find_markers("def broken(:\n") == []


# --- report: impact_tag reasons and markdown escalation block ------------

def test_impact_tag_reports_changed_functions():
    tag = report.impact_tag(
        "calc.py", {"calc.py": {"add", "mul"}}, set(), {}, set(), {})
    assert tag == "add, mul"


def test_impact_tag_escalated_to_file_level():
    tag = report.impact_tag(
        "calc.py", {"calc.py": {"add"}}, set(), {"calc.py": ["getattr"]},
        set(), {})
    assert "file-level (dynamic)" in tag


def test_impact_tag_data_dependency_counts_readers():
    tag = report.impact_tag(
        "tax.json", {}, set(), {}, {"tax.json"},
        {"t_a": {"tax.json"}, "t_b": {"tax.json"}})
    assert "2 readers" in tag


def test_render_markdown_includes_escalated_section():
    md = report.render_markdown(
        ref="abcdef1234", changed=["calc.py"],
        func_changes={"calc.py": {"add"}}, module_files=set(),
        escalated={"calc.py": ["getattr() @L5"]},
        data_changes=set(), reads={}, cosmetic=set(),
        selected={"t_add": "add"}, total=10)
    assert "Widened to file-level" in md
    assert "getattr() @L5" in md


def test_render_markdown_no_tests_selected_says_all_skipped():
    md = report.render_markdown(
        ref="abcdef1234", changed=[], func_changes={}, module_files=set(),
        escalated={}, data_changes=set(), reads={}, cosmetic=set(),
        selected={}, total=8)
    assert "skipping all 8" in md
