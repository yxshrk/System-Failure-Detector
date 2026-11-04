"""How a model-written specification pins down the result (SP3 analysis).

    constructive  -- ``post`` computes the expected answer itself and compares (a part of) ``result``
                     with it by ``==`` / ``!=``: in effect a second implementation of the function, so
                     the Z3 query becomes a differential check between two programs;
    declarative   -- ``post`` only states properties of ``result`` (ordering, membership, a permutation
                     of the input, ...) without computing the answer.

A part of ``result`` is ``result`` itself, a name unpacked or copied from it, an index into one of
those, or ``len`` of one. Whole-value transformations such as ``sorted(result)`` are properties.
"""

from __future__ import annotations

import ast


def _post(tree: ast.Module) -> ast.FunctionDef | None:
    return next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "post"), None)


def _result_names(post: ast.FunctionDef) -> set[str]:
    """``result`` plus every name assigned directly from (an index of) it, e.g. ``a, b = result``."""
    names = {post.args.args[-1].arg}
    changed = True
    while changed:
        changed = False
        for n in ast.walk(post):
            if isinstance(n, ast.Assign) and _is_part(n.value, names):
                for t in n.targets:
                    for leaf in ast.walk(t):
                        if isinstance(leaf, ast.Name) and isinstance(leaf.ctx, ast.Store) and leaf.id not in names:
                            names.add(leaf.id)
                            changed = True
    return names


def _is_part(node: ast.AST, names: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Subscript):
        return _is_part(node.value, names)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "len" and len(node.args) == 1:
        return _is_part(node.args[0], names)
    return False


def _mentions(node: ast.AST, names: set[str]) -> bool:
    return any(isinstance(n, ast.Name) and n.id in names for n in ast.walk(node))


def spec_style(spec: str) -> str:
    """``"constructive"``, ``"declarative"`` or ``"unparsable"`` (no ``post`` with a result parameter)."""
    try:
        tree = ast.parse(spec)
    except SyntaxError:
        return "unparsable"
    post = _post(tree)
    if post is None or not post.args.args:
        return "unparsable"
    names = _result_names(post)
    for n in ast.walk(post):
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and isinstance(n.ops[0], (ast.Eq, ast.NotEq)):
            left, right = n.left, n.comparators[0]
            for part, other in ((left, right), (right, left)):
                if _is_part(part, names) and not _mentions(other, names):
                    return "constructive"
    return "declarative"
