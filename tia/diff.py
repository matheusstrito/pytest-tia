"""Turn a git diff into a set of changed line numbers per file.

We diff against a ref (default HEAD, which includes both staged and
unstaged work) using ``--unified=0`` so each hunk header pins down the
exact new-side line range that changed.
"""

import subprocess
from collections import defaultdict


def changed_lines(ref: str = "HEAD", cwd: str = ".") -> dict[str, set[int]]:
    out = subprocess.run(
        ["git", "diff", "--unified=0", "--no-color", "--relative", ref],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    result: dict[str, set[int]] = defaultdict(set)
    current: str | None = None
    for line in out.stdout.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path == "/dev/null":
                current = None
            else:
                current = path[2:] if path.startswith("b/") else path
        elif line.startswith("@@") and current:
            # Format: @@ -a,b +c,d @@   (the "+c,d" is the new side)
            try:
                plus = line.split("+", 1)[1].split(" ", 1)[0]
            except IndexError:
                continue
            if "," in plus:
                start_s, count_s = plus.split(",")
                start, count = int(start_s), int(count_s)
            else:
                start, count = int(plus), 1
            if count == 0:
                # Pure deletion: nothing on the new side, so flag the two
                # lines straddling where the code was removed.
                result[current].update({start, start + 1})
            else:
                result[current].update(range(start, start + count))
    return dict(result)
