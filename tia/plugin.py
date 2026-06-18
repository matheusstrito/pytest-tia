"""Pytest plugin that records a per-test line-coverage map.

We wrap each test's *call* phase and switch coverage.py's dynamic
context to the test's nodeid. After the session we read the coverage
data back and invert it into ``{nodeid: {file: {lines...}}}``.
"""

import os

import coverage
import pytest

import tia


class RecordPlugin:
    def __init__(self, root: str, data_file: str, source: str):
        self.root = root
        # Don't measure tia's own code — our wrapper frame is live during
        # each test's context and would otherwise leak into the map.
        tia_glob = os.path.join(os.path.dirname(tia.__file__), "*")
        self.cov = coverage.Coverage(
            data_file=data_file,
            branch=False,
            source=[source],
            omit=[tia_glob],
            config_file=False,
        )
        self.cov.erase()
        self.cov.start()
        # nodeid -> {relpath -> set(line numbers)}
        self.result: dict[str, dict[str, set[int]]] = {}

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_call(self, item):
        # Everything executed between these switches is attributed to
        # this test's nodeid. Setup/teardown stay in the empty context.
        self.cov.switch_context(item.nodeid)
        try:
            return (yield)
        finally:
            self.cov.switch_context("")

    def pytest_sessionfinish(self, session, exitstatus):
        self.cov.stop()
        self.cov.save()
        data = self.cov.get_data()
        result: dict[str, dict[str, set[int]]] = {}
        for abs_path in data.measured_files():
            rel = os.path.relpath(abs_path, self.root).replace(os.sep, "/")
            for lineno, contexts in data.contexts_by_lineno(abs_path).items():
                for ctx in contexts:
                    if not ctx:  # empty context = import-time / setup
                        continue
                    result.setdefault(ctx, {}).setdefault(rel, set()).add(lineno)
        self.result = result
