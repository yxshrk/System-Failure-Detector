"""Concrete (real Python) execution with a step budget.

Used for exact scoring: a claimed failing input is run on the code under review
and on the unmutated reference, and the two outcomes are compared.
"""

from __future__ import annotations

import ast
import copy
import sys
from dataclasses import dataclass
from functools import lru_cache

STEP_LIMIT = 200_000

_ALLOWED_BUILTINS = ["len", "abs", "min", "max", "sum", "sorted", "reversed", "range", "list", "all", "any",
                     "int", "bool", "enumerate", "zip", "divmod", "pow", "tuple", "True", "False", "None",
                     "ValueError", "IndexError", "ZeroDivisionError", "TypeError", "AssertionError", "Exception"]


def _restricted_import(name, *args, **kwargs):
    if name not in ("typing", "__future__"):
        raise ImportError(f"import of {name} is not allowed")
    import importlib
    return importlib.import_module(name)


def _builtins() -> dict:
    import builtins
    b = {n: getattr(builtins, n) for n in _ALLOWED_BUILTINS if hasattr(builtins, n)}
    b["__import__"] = _restricted_import
    return b


class StepLimit(Exception):
    pass


@dataclass(frozen=True)
class Run:
    kind: str  # "ok" | "exception" | "timeout"
    value: object = None
    error: str = ""

    def same_as(self, other: "Run") -> bool:
        if self.kind != other.kind:
            return False
        if self.kind == "ok":
            return _strict_eq(self.value, other.value)
        return True


def _strict_eq(a, b) -> bool:
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return type(a) is type(b) and len(a) == len(b) and all(_strict_eq(x, y) for x, y in zip(a, b))
    return a == b


@lru_cache(maxsize=4096)
def _compile(source: str):
    return compile(source, "<function>", "exec")


def load(source: str) -> dict:
    ns = {"__builtins__": _builtins()}
    exec(_compile(source), ns)  # trusted benchmark code or AST-whitelisted spec code (see check_safe)
    return ns


def run(source: str, fname: str, args: list, step_limit: int = STEP_LIMIT) -> Run:
    ns = load(source)
    fn = ns.get(fname)
    if fn is None:
        return Run("exception", error=f"function {fname} not defined")
    return call(fn, args, step_limit)


def call(fn, args: list, step_limit: int = STEP_LIMIT) -> Run:
    steps = 0

    def tracer(frame, event, arg):
        nonlocal steps
        if frame.f_code.co_filename != "<function>":
            return None

        def local(frame, event, arg):
            nonlocal steps
            if event == "line":
                steps += 1
                if steps > step_limit:
                    raise StepLimit()
            return local

        return local

    old = sys.gettrace()
    sys.settrace(tracer)
    try:
        value = fn(*copy.deepcopy(args))
        return Run("ok", value)
    except StepLimit:
        return Run("timeout", error=f"exceeded {step_limit} steps")
    except RecursionError:
        return Run("timeout", error="recursion limit")
    except Exception as e:  # the program under test raised
        return Run("exception", error=f"{type(e).__name__}: {e}")
    finally:
        sys.settrace(old)


_ALLOWED_NODES = (
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Assign, ast.AugAssign, ast.AnnAssign,
    ast.For, ast.While, ast.If, ast.Expr, ast.Pass, ast.Break, ast.Continue, ast.Assert,
    ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.IfExp, ast.Compare, ast.Call, ast.Constant, ast.Name, ast.Load,
    ast.Store, ast.Subscript, ast.Slice, ast.List, ast.Tuple, ast.ListComp, ast.GeneratorExp, ast.comprehension,
    ast.Attribute, ast.keyword, ast.operator, ast.unaryop, ast.cmpop, ast.boolop, ast.expr_context,
    ast.Import, ast.ImportFrom, ast.alias,
)


def check_safe(source: str) -> str | None:
    """Reject model-written code that could do anything beyond pure computation."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return f"syntax error on line {e.lineno}: {e.msg}"
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return f"construct {type(node).__name__} is not allowed"
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            return f"name {node.id} is not allowed"
        if isinstance(node, ast.Attribute) and (node.attr.startswith("_") or node.attr not in {
                "append", "extend", "pop", "insert", "remove", "sort", "reverse", "count", "index", "copy"}):
            return f"attribute .{node.attr} is not allowed"
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
            if mod not in ("typing", "__future__"):
                return f"import of {mod} is not allowed"
    return None
