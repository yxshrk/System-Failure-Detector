"""Finite input domains for SP1 functions.

Every benchmark function takes arguments from a bounded domain (integer
ranges, lists up to a maximum length). The domain is what makes the CSP finite,
and it is stated verbatim to the model in both arms so that "does a failing
input exist?" has one well-defined answer.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import z3

from .symexec import SymList, mk_list


@dataclass(frozen=True)
class IntT:
    lo: int
    hi: int


@dataclass(frozen=True)
class BoolT:
    pass


@dataclass(frozen=True)
class ListT:
    elem: IntT
    max_len: int
    min_len: int = 0
    sorted: bool = False
    distinct: bool = False


Type = IntT | BoolT | ListT


def describe(name: str, t: Type) -> str:
    if isinstance(t, IntT):
        return f"`{name}` is an integer with {t.lo} <= {name} <= {t.hi}"
    if isinstance(t, BoolT):
        return f"`{name}` is a bool"
    extra = []
    if t.sorted:
        extra.append("sorted in strictly increasing order" if t.distinct else "sorted in non-decreasing order")
    elif t.distinct:
        extra.append("with no repeated values")
    tail = (", " + ", ".join(extra)) if extra else ""
    return (f"`{name}` is a list of {t.min_len} to {t.max_len} integers, each between "
            f"{t.elem.lo} and {t.elem.hi} inclusive{tail}")


def type_name(t: Type) -> str:
    return "int" if isinstance(t, IntT) else "bool" if isinstance(t, BoolT) else "list[int]"


def make_symbolic(name: str, t: Type):
    """Return (symbolic value, list of domain constraints)."""
    if isinstance(t, IntT):
        v = z3.Int(name)
        return v, [v >= t.lo, v <= t.hi]
    if isinstance(t, BoolT):
        return z3.Bool(name), []
    n = z3.Int(f"{name}__len")
    elems = [z3.Int(f"{name}__{k}") for k in range(t.max_len)]
    cons = [n >= t.min_len, n <= t.max_len]
    for e in elems:
        cons += [e >= t.elem.lo, e <= t.elem.hi]
    for k in range(t.max_len - 1):
        inside = k + 1 < n
        if t.sorted:
            cons.append(z3.Implies(inside, elems[k] < elems[k + 1] if t.distinct else elems[k] <= elems[k + 1]))
    if t.distinct and not t.sorted:
        for i in range(t.max_len):
            for j in range(i + 1, t.max_len):
                cons.append(z3.Implies(j < n, elems[i] != elems[j]))
    return SymList(n, tuple(elems)), cons


def from_model(t: Type, sym, model: z3.ModelRef):
    if isinstance(t, IntT):
        return model.eval(sym, model_completion=True).as_long()
    if isinstance(t, BoolT):
        return z3.is_true(model.eval(sym, model_completion=True))
    n = model.eval(sym.length, model_completion=True).as_long()
    return [model.eval(e, model_completion=True).as_long() for e in sym.elems[:n]]


def substitution(t: Type, sym, value) -> list[tuple]:
    """Pairs (z3 var, z3 value) binding a symbolic input to a concrete one."""
    if isinstance(t, IntT):
        return [(sym, z3.IntVal(value))]
    if isinstance(t, BoolT):
        return [(sym, z3.BoolVal(value))]
    pairs = [(sym.length, z3.IntVal(len(value)))]
    for k, e in enumerate(sym.elems):
        pairs.append((e, z3.IntVal(value[k] if k < len(value) else 0)))
    return pairs


def sample(t: Type, rng: random.Random):
    if isinstance(t, IntT):
        return rng.randint(t.lo, t.hi)
    if isinstance(t, BoolT):
        return rng.random() < 0.5
    n = rng.randint(t.min_len, t.max_len)
    if t.distinct:
        pool = range(t.elem.lo, t.elem.hi + 1)
        xs = rng.sample(pool, n)
    else:
        xs = [rng.randint(t.elem.lo, t.elem.hi) for _ in range(n)]
    return sorted(xs) if t.sorted else xs


def domain_size(t: Type) -> int:
    if isinstance(t, IntT):
        return t.hi - t.lo + 1
    if isinstance(t, BoolT):
        return 2
    if t.sorted or t.distinct:
        return -1  # not needed exactly; sampling is used
    m = t.elem.hi - t.elem.lo + 1
    return sum(m ** n for n in range(t.min_len, t.max_len + 1))


def enumerate_values(t: Type):
    if isinstance(t, IntT):
        return list(range(t.lo, t.hi + 1))
    if isinstance(t, BoolT):
        return [False, True]
    raise ValueError("lists are sampled, not enumerated")


def check_value(t: Type, v) -> str | None:
    """None if ``v`` is in the domain, else a reason."""
    if isinstance(t, IntT):
        if isinstance(v, bool) or not isinstance(v, int):
            return f"expected an integer, got {v!r}"
        if not t.lo <= v <= t.hi:
            return f"{v} is outside [{t.lo}, {t.hi}]"
        return None
    if isinstance(t, BoolT):
        return None if isinstance(v, bool) else f"expected a bool, got {v!r}"
    if not isinstance(v, list):
        return f"expected a list, got {v!r}"
    if not t.min_len <= len(v) <= t.max_len:
        return f"list length {len(v)} is outside [{t.min_len}, {t.max_len}]"
    for x in v:
        r = check_value(t.elem, x)
        if r:
            return f"element {r}"
    if t.sorted:
        ok = all(a < b for a, b in zip(v, v[1:])) if t.distinct else all(a <= b for a, b in zip(v, v[1:]))
        if not ok:
            return "list is not sorted as required"
    elif t.distinct and len(set(v)) != len(v):
        return "list has repeated values"
    return None


def to_symbolic_constant(t: Type, v):
    """A concrete value as an executor value (used to replay inputs symbolically)."""
    if isinstance(t, ListT):
        return mk_list(len(v), tuple(v))
    return v
