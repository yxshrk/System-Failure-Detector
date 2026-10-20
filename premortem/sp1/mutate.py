"""First-order mutation operators (the classic mutation-testing set).

ROR  relational operator replacement      (<  ->  <=, == -> !=, ...)
AOR  arithmetic operator replacement      (+ <-> -, * -> +, // <-> %)
CRP  integer constant replacement         (c -> c+1, c-1)
LCR  logical connector replacement        (and <-> or)
NEG  condition negation                    (if c -> if not c)
RNG  range-bound off-by-one                (range(a, b) -> range(a, b+-1), range(a+1, b))
SDL  statement deletion                    (drop an assignment / augmented assignment)

Docstrings are never mutated.
"""

from __future__ import annotations

import ast
import copy
from dataclasses import dataclass

_ROR = {
    ast.Lt: [ast.LtE, ast.Gt], ast.LtE: [ast.Lt, ast.GtE], ast.Gt: [ast.GtE, ast.Lt], ast.GtE: [ast.Gt, ast.LtE],
    ast.Eq: [ast.NotEq], ast.NotEq: [ast.Eq],
}
_AOR = {ast.Add: [ast.Sub], ast.Sub: [ast.Add], ast.Mult: [ast.Add], ast.FloorDiv: [ast.Mod], ast.Mod: [ast.FloorDiv]}
_SYM = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!=",
        ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.FloorDiv: "//", ast.Mod: "%"}


@dataclass(frozen=True)
class Mutant:
    op: str
    description: str
    source: str


def _is_docstring(node, parents) -> bool:
    p = parents.get(node)
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and isinstance(p, ast.Expr)


def _all_nodes(tree):
    out = []
    for node in ast.walk(tree):
        out.append(node)
    return out


def mutants(source: str) -> list[Mutant]:
    tree = ast.parse(source)
    nodes = _all_nodes(tree)
    parents = {}
    for n in nodes:
        for c in ast.iter_child_nodes(n):
            parents[c] = n
    found: list[Mutant] = []
    seen = {ast.unparse(tree)}

    def emit(op, desc, mutated_tree):
        src = ast.unparse(ast.fix_missing_locations(mutated_tree)) + "\n"
        if src.strip() in seen:
            return
        try:
            compile(src, "<mutant>", "exec")
        except SyntaxError:
            return
        seen.add(src.strip())
        found.append(Mutant(op, desc, src))

    for idx, node in enumerate(nodes):
        line = getattr(node, "lineno", "?")
        if isinstance(node, ast.Compare):
            for k, op in enumerate(node.ops):
                for repl in _ROR.get(type(op), []):
                    t = copy.deepcopy(tree)
                    tn = _all_nodes(t)[idx]
                    tn.ops[k] = repl()
                    emit("ROR", f"line {line}: '{_SYM[type(op)]}' -> '{_SYM[repl]}'", t)
        elif isinstance(node, ast.BinOp) and type(node.op) in _AOR:
            for repl in _AOR[type(node.op)]:
                t = copy.deepcopy(tree)
                _all_nodes(t)[idx].op = repl()
                emit("AOR", f"line {line}: '{_SYM[type(node.op)]}' -> '{_SYM[repl]}'", t)
        elif isinstance(node, ast.AugAssign) and type(node.op) in _AOR:
            for repl in _AOR[type(node.op)]:
                t = copy.deepcopy(tree)
                _all_nodes(t)[idx].op = repl()
                emit("AOR", f"line {line}: '{_SYM[type(node.op)]}=' -> '{_SYM[repl]}='", t)
        elif isinstance(node, ast.Constant) and type(node.value) is int and not _is_docstring(node, parents):
            for delta in (1, -1):
                t = copy.deepcopy(tree)
                _all_nodes(t)[idx].value = node.value + delta
                emit("CRP", f"line {line}: constant {node.value} -> {node.value + delta}", t)
        elif isinstance(node, ast.BoolOp):
            t = copy.deepcopy(tree)
            tn = _all_nodes(t)[idx]
            tn.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            emit("LCR", f"line {line}: '{'and' if isinstance(node.op, ast.And) else 'or'}' -> "
                        f"'{'or' if isinstance(node.op, ast.And) else 'and'}'", t)
        elif isinstance(node, (ast.If, ast.While)):
            t = copy.deepcopy(tree)
            tn = _all_nodes(t)[idx]
            tn.test = ast.UnaryOp(ast.Not(), tn.test)
            emit("NEG", f"line {line}: condition negated", t)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
            n_args = len(node.args)
            stop_pos = 0 if n_args == 1 else 1
            for delta in (1, -1):
                t = copy.deepcopy(tree)
                tn = _all_nodes(t)[idx]
                tn.args[stop_pos] = ast.BinOp(tn.args[stop_pos], ast.Add() if delta > 0 else ast.Sub(), ast.Constant(1))
                emit("RNG", f"line {line}: range stop {'+' if delta > 0 else '-'} 1", t)
            t = copy.deepcopy(tree)
            tn = _all_nodes(t)[idx]
            if n_args == 1:
                tn.args = [ast.Constant(1), tn.args[0]]
            else:
                tn.args[0] = ast.BinOp(tn.args[0], ast.Add(), ast.Constant(1))
            emit("RNG", f"line {line}: range start + 1", t)
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            parent = parents.get(node)
            if parent is not None and not isinstance(parent, ast.Module):
                for field_name in ("body", "orelse"):
                    block = getattr(parent, field_name, None)
                    if isinstance(block, list) and node in block and len(block) > 1:
                        pos = block.index(node)
                        t = copy.deepcopy(tree)
                        tp = _all_nodes(t)[nodes.index(parent)]
                        del getattr(tp, field_name)[pos]
                        emit("SDL", f"line {line}: statement '{ast.unparse(node)}' deleted", t)
    return found
