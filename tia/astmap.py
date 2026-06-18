"""Map source lines to the qualified name of their enclosing function.

`line_to_qualname("...source...")` returns ``{lineno: "Class.method"}``.
Lines that belong to no function (module-level statements, imports,
class-body lines between methods) are simply absent from the dict — the
caller treats those as "module-level".

Decorator lines count as part of the function they decorate: changing a
decorator changes the function's behaviour.
"""

import ast


def line_to_qualname(source: str) -> dict[int, str]:
    tree = ast.parse(source)
    mapping: dict[int, str] = {}

    def visit(node: ast.AST, stack: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual = ".".join(stack + [child.name])
                start = min(
                    [child.lineno] + [d.lineno for d in child.decorator_list]
                )
                end = child.end_lineno or child.lineno
                for ln in range(start, end + 1):
                    mapping[ln] = qual  # outer assigned first...
                visit(child, stack + [child.name])  # ...inner overwrites
            else:
                visit(child, stack)

    visit(tree, [])
    return mapping


def line_to_qualname_from_file(path: str) -> dict[int, str]:
    with open(path, encoding="utf-8") as fh:
        return line_to_qualname(fh.read())
