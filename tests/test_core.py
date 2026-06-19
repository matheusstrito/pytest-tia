"""Unit tests for tia's pure logic (no git / no pytest subprocess)."""

from tia import astmap, remotestore, resolve, select

SOURCE = '''\
import os


CONST = 1


def top():
    return CONST


class Calc:
    def add(self, a, b):
        return a + b

    @staticmethod
    def helper():
        x = 1
        return x
'''


def test_qualname_module_level_lines_absent():
    m = astmap.line_to_qualname(SOURCE)
    assert 1 not in m          # import
    assert 4 not in m          # CONST assignment


def test_qualname_function_and_method():
    m = astmap.line_to_qualname(SOURCE)
    assert m[8] == "top"
    assert m[13] == "Calc.add"          # return a + b
    assert m[17] == "Calc.helper"       # x = 1
    assert m[18] == "Calc.helper"       # return x


def test_qualname_decorator_belongs_to_function():
    m = astmap.line_to_qualname(SOURCE)
    assert m[16] == "Calc.helper"       # the @staticmethod line


MAP = {
    "t_add": {"calc.py": {"add"}, "test_calc.py": {"t_add"}},
    "t_mul": {"calc.py": {"mul"}, "test_calc.py": {"t_mul"}},
}


def test_select_function_hit():
    sel = select.select_tests(MAP, {"calc.py": {"mul"}}, set(), {"t_add", "t_mul"})
    assert set(sel) == {"t_mul"}


def test_select_module_fallback_runs_all_touching_file():
    sel = select.select_tests(MAP, {}, {"calc.py"}, {"t_add", "t_mul"})
    assert set(sel) == {"t_add", "t_mul"}


def test_select_new_test_always_runs():
    sel = select.select_tests(MAP, {}, set(), {"t_add", "t_mul", "t_brand_new"})
    assert set(sel) == {"t_brand_new"}


def test_select_unrelated_change_runs_nothing():
    sel = select.select_tests(MAP, {"calc.py": {"sub"}}, set(), {"t_add", "t_mul"})
    assert sel == {}


READS = {
    "t_tax": {"tax.json"},
    "t_other": {"other.yaml"},
}


def test_select_data_dep_picks_only_readers():
    sel = select.select_tests(
        {"t_tax": {}, "t_other": {}}, {}, set(), {"t_tax", "t_other"},
        data_changes={"tax.json"}, reads=READS,
    )
    assert set(sel) == {"t_tax"}
    assert sel["t_tax"] == "reads tax.json"


def test_select_unread_data_file_runs_nothing():
    sel = select.select_tests(
        {"t_tax": {}, "t_other": {}}, {}, set(), {"t_tax", "t_other"},
        data_changes={"nobody_reads_this.json"}, reads=READS,
    )
    assert sel == {}


# --- ③ shallow-clone-safe resolution: baked funcmaps, no git needed -------

FUNCMAPS = {"calc.py": {12: "mul", 13: "mul"}}


def test_resolve_uses_baked_funcmaps_without_git():
    # cwd points nowhere: if this needed `git show`, it would fail.
    changes = {"calc.py": {"mod": {13}, "ins": set()}}
    fc, mf = resolve.changed_functions(
        changes, ref="deadbeef", cwd="/no/such/dir", funcmaps=FUNCMAPS)
    assert fc == {"calc.py": {"mul"}}
    assert mf == set()


def test_resolve_baked_module_level_mod_falls_back_to_file():
    changes = {"calc.py": {"mod": {1}, "ins": set()}}  # line 1 not in any func
    fc, mf = resolve.changed_functions(
        changes, ref="deadbeef", cwd="/no/such/dir", funcmaps=FUNCMAPS)
    assert fc == {}
    assert mf == {"calc.py"}


# --- ③ remote store roundtrip --------------------------------------------

def test_remote_push_pull_by_ref(tmp_path):
    local = tmp_path / "map.json"
    local.write_text('{"ref":"abc123"}', encoding="utf-8")
    remote = str(tmp_path / "remote")
    remotestore.push(str(local), remote, "abc123")

    dest = tmp_path / "pulled.json"
    got = remotestore.pull(remote, "abc123", str(dest))
    assert got is not None
    assert dest.read_text(encoding="utf-8") == '{"ref":"abc123"}'


def test_remote_pull_falls_back_to_latest(tmp_path):
    local = tmp_path / "map.json"
    local.write_text('{"ref":"abc123"}', encoding="utf-8")
    remote = str(tmp_path / "remote")
    remotestore.push(str(local), remote, "abc123")

    dest = tmp_path / "out.json"
    got = remotestore.pull(remote, "a-ref-nobody-recorded", str(dest))
    assert got is not None  # fell back to latest.json
    assert dest.read_text(encoding="utf-8") == '{"ref":"abc123"}'
