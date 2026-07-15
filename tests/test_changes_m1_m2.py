"""Tests for the two behavioural changes.

M1: select_tests tolerates None for func_changes / module_files, matching
    the already-optional data_changes / reads.
M2: dynscan flags globals()/locals() as dynamic-namespace access.
"""

from tia import dynscan, select


# --- M1: None-tolerant selection -----------------------------------------

def test_select_tests_accepts_none_func_and_module():
    # Previously raised AttributeError on None.items() / iteration.
    sel = select.select_tests(
        {"t_a": {"m.py": {"f"}}}, None, None, {"t_a"})
    assert sel == {}          # nothing changed -> nothing selected


def test_select_tests_none_still_runs_new_tests():
    sel = select.select_tests(
        {"t_a": {"m.py": {"f"}}}, None, None, {"t_a", "t_brand_new"})
    assert set(sel) == {"t_brand_new"}


# --- M2: globals()/locals() detection ------------------------------------

def test_dynscan_flags_globals():
    src = "def f():\n    return globals()['x']\n"
    markers = dynscan.find_markers(src)
    assert any("globals" in m for m in markers)


def test_dynscan_flags_locals():
    src = "def f():\n    return locals()\n"
    markers = dynscan.find_markers(src)
    assert any("locals" in m for m in markers)


def test_dynscan_static_file_still_clean():
    # regression: an ordinary function must stay unflagged
    src = "def add(a, b):\n    return a + b\n"
    assert dynscan.find_markers(src) == []
