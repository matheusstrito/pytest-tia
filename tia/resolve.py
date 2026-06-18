"""Resolve changed lines to changed qualnames, at the recorded ref.

The impact map stores qualnames captured against a git ref. To turn the
diff's old-side line numbers into the *same* qualnames, we parse each
file as it existed at that ref (``git show ref:path``) and look up the
enclosing function of every changed line.

Returns:
    func_changes: {path: {qualname, ...}}  — functions whose body changed
    module_files: {path, ...}              — files with a module-level
                                             *modification* (fallback)
"""

import subprocess

from tia import astmap


def _git_show(ref: str, path: str, cwd: str) -> str | None:
    out = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return out.stdout if out.returncode == 0 else None


def changed_functions(
    changes: dict[str, dict[str, set[int]]],
    ref: str,
    cwd: str,
) -> tuple[dict[str, set[str]], set[str]]:
    func_changes: dict[str, set[str]] = {}
    module_files: set[str] = set()

    for path, kinds in changes.items():
        if not path.endswith(".py"):
            continue  # non-Python deps are handled separately (silent deps)
        src = _git_show(ref, path, cwd)
        if src is None:
            continue  # file is new at this ref — its new tests run anyway
        try:
            l2q = astmap.line_to_qualname(src)
        except SyntaxError:
            module_files.add(path)  # can't parse: be conservative
            continue

        funcs: set[str] = set()
        for ln in kinds["mod"]:
            qual = l2q.get(ln)
            if qual is None:
                module_files.add(path)  # module-level modification
            else:
                funcs.add(qual)
        for ln in kinds["ins"]:
            qual = l2q.get(ln)
            if qual is not None:
                funcs.add(qual)  # insertion inside an existing function
            # module-level insertion (new func/test) deliberately ignored

        if funcs:
            func_changes[path] = funcs

    return func_changes, module_files
