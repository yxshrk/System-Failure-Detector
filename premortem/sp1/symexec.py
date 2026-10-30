"""Bounded symbolic execution of a small Python subset into Z3 terms.

This is the "code semantics" half of the SP1 formulation: a function body is
compiled into constraints over its symbolic inputs so that

    domain(x) AND NOT spec(x, f(x))

can be handed to Z3. A model of that formula is a failure witness; UNSAT means
no failure exists *within the bounds* (list capacities, loop unrolling depth).

Execution is path-merging rather than path-forking: both sides of a symbolic
branch are executed and the variable environments are joined with
``If(cond, then, else)``. Each program point carries an ``alive`` condition (the
path condition under which control reaches it), so ``return``/``break``/
``continue`` and exceptions just shrink ``alive``. This keeps the formula
linear in program size times unrolling depth, avoiding the exponential path
explosion of classic forking symbolic execution.

Supported values: ints (unbounded, like Python), bools, lists of ints/bools
with symbolic length and bounded capacity, tuples, and ``None`` (including
values that are None only on some paths). Loops over symbolic ranges and
``while`` loops are unrolled ``loop_bound`` times; paths that would need more
iterations are recorded in ``unwind`` and assumed away by callers, which is
what makes any "no failure" verdict a bounded one.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

import z3


class SymError(Exception):
    """The program uses a construct the bounded symbolic executor cannot handle."""


class _Undef:
    def __repr__(self) -> str:
        return "<undef>"


class _NoneVal:
    def __repr__(self) -> str:
        return "None"


UNDEF = _Undef()
NONE = _NoneVal()

MAX_CONCRETE_UNROLL = 5000


@dataclass(frozen=True)
class Opt:
    """A value that is None exactly when ``is_none`` holds."""

    is_none: object
    val: object


@dataclass(frozen=True)
class Partial:
    """A variable that is bound only where ``defined`` holds (reading it elsewhere raises)."""

    defined: object
    val: object


@dataclass(frozen=True)
class SymList:
    """A list with possibly symbolic length; entries at index >= length are junk."""

    length: object
    elems: tuple

    @property
    def cap(self) -> int:
        return len(self.elems)


@dataclass(frozen=True)
class RangeVal:
    start: object
    stop: object
    step: int


# --------------------------------------------------------------------------
# Small helpers over "python constant or z3 term" values
# --------------------------------------------------------------------------


def is_z3(v) -> bool:
    return isinstance(v, z3.ExprRef)


def is_boolish(v) -> bool:
    return isinstance(v, bool) or (is_z3(v) and z3.is_bool(v))


def is_intish(v) -> bool:
    return (isinstance(v, int) and not isinstance(v, bool)) or (is_z3(v) and z3.is_int(v))


def is_numeric(v) -> bool:
    return is_boolish(v) or is_intish(v)


def as_bool(v):
    if isinstance(v, bool):
        return z3.BoolVal(v)
    return v


def as_int(v):
    if isinstance(v, bool):
        return z3.IntVal(int(v))
    if isinstance(v, int):
        return z3.IntVal(v)
    if is_z3(v) and z3.is_bool(v):
        return z3.If(v, z3.IntVal(1), z3.IntVal(0))
    return v


def concrete(c):
    """Python bool if ``c`` is a known truth value, else None."""
    if isinstance(c, bool):
        return c
    if is_z3(c):
        if z3.is_true(c):
            return True
        if z3.is_false(c):
            return False
    return None


def conj(*cs):
    out = []
    for c in cs:
        k = concrete(c)
        if k is True:
            continue
        if k is False:
            return False
        out.append(c)
    if not out:
        return True
    return out[0] if len(out) == 1 else z3.And(*out)


def disj(*cs):
    out = []
    for c in cs:
        k = concrete(c)
        if k is False:
            continue
        if k is True:
            return True
        out.append(c)
    if not out:
        return False
    return out[0] if len(out) == 1 else z3.Or(*out)


def neg(c):
    k = concrete(c)
    if k is not None:
        return not k
    return z3.Not(c)


def kind(v) -> str:
    if v is NONE:
        return "None"
    if isinstance(v, Opt):
        return f"Optional[{kind(v.val)}]"
    if isinstance(v, SymList):
        return "list"
    if isinstance(v, tuple):
        return "tuple"
    if is_boolish(v):
        return "bool"
    if is_intish(v):
        return "int"
    if isinstance(v, RangeVal):
        return "range"
    return type(v).__name__


def _opt_parts(v):
    if v is NONE:
        return True, UNDEF
    if isinstance(v, Opt):
        return v.is_none, v.val
    return False, v


def _partial_parts(v):
    if v is UNDEF:
        return False, UNDEF
    if isinstance(v, Partial):
        return v.defined, v.val
    return True, v


def join_return(c, v, prev):
    """Accumulate a return value; ``prev`` is UNDEF until some path has returned."""
    return v if prev is UNDEF else ite(c, v, prev)


def mk_list(length, elems) -> SymList:
    elems = tuple(elems)
    if isinstance(length, int) and not isinstance(length, bool):
        elems = elems[:length]
    return SymList(length, elems)


def ite(c, a, b):
    """Join two values: ``a`` where ``c`` holds, ``b`` elsewhere."""
    k = concrete(c)
    if k is True:
        return a
    if k is False:
        return b
    if a is b:
        return a
    if a is UNDEF or b is UNDEF or isinstance(a, Partial) or isinstance(b, Partial):
        ad, av = _partial_parts(a)
        bd, bv = _partial_parts(b)
        val = bv if av is UNDEF else av if bv is UNDEF else ite(c, av, bv)
        defined = ite(c, ad, bd)
        if concrete(defined) is True:
            return val
        return Partial(defined, val)
    if a is NONE and b is NONE:
        return NONE
    if a is NONE or b is NONE or isinstance(a, Opt) or isinstance(b, Opt):
        an, av = _opt_parts(a)
        bn, bv = _opt_parts(b)
        val = bv if av is UNDEF else av if bv is UNDEF else ite(c, av, bv)
        is_none = ite(c, an, bn)
        if concrete(is_none) is False:
            return val
        if val is UNDEF:
            return NONE
        return Opt(is_none, val)
    if isinstance(a, SymList) or isinstance(b, SymList):
        if not (isinstance(a, SymList) and isinstance(b, SymList)):
            raise SymError(f"a variable holds a list on one path and a {kind(b) if isinstance(a, SymList) else kind(a)} on another")
        return _merge_lists(c, a, b)
    if isinstance(a, tuple) or isinstance(b, tuple):
        if not (isinstance(a, tuple) and isinstance(b, tuple)) or len(a) != len(b):
            raise SymError(f"cannot join {kind(a)} and {kind(b)} values at a branch join")
        return tuple(ite(c, x, y) for x, y in zip(a, b))
    if is_boolish(a) and is_boolish(b):
        if isinstance(a, bool) and isinstance(b, bool) and a == b:
            return a
        return z3.If(c, as_bool(a), as_bool(b))
    if is_numeric(a) and is_numeric(b):
        if isinstance(a, int) and isinstance(b, int) and not isinstance(a, bool) and not isinstance(b, bool) and a == b:
            return a
        return z3.If(c, as_int(a), as_int(b))
    raise SymError(f"cannot join {kind(a)} and {kind(b)} values at a branch join")


def _merge_lists(c, a: SymList, b: SymList) -> SymList:
    cap = max(a.cap, b.cap)
    pa = [a.elems[k] if k < a.cap else b.elems[k] for k in range(cap)]
    pb = [b.elems[k] if k < b.cap else a.elems[k] for k in range(cap)]
    return mk_list(ite(c, a.length, b.length), [ite(c, x, y) for x, y in zip(pa, pb)])


def eq(a, b):
    """Python ``==`` as a (possibly symbolic) bool."""
    if a is NONE or b is NONE or isinstance(a, Opt) or isinstance(b, Opt):
        an, av = _opt_parts(a)
        bn, bv = _opt_parts(b)
        if av is UNDEF and bv is UNDEF:
            return True
        if av is UNDEF:
            return bn
        if bv is UNDEF:
            return an
        same_none = conj(disj(neg(an), bn), disj(neg(bn), an))
        return conj(same_none, disj(an, eq(av, bv)))
    if isinstance(a, SymList) or isinstance(b, SymList):
        if not (isinstance(a, SymList) and isinstance(b, SymList)):
            return False
        parts = [_num_eq(a.length, b.length)]
        for k in range(min(a.cap, b.cap)):
            parts.append(disj(_num_lt_eq(a.length, k), eq(a.elems[k], b.elems[k])))
        return conj(*parts)
    if isinstance(a, tuple) or isinstance(b, tuple):
        if not (isinstance(a, tuple) and isinstance(b, tuple)) or len(a) != len(b):
            return False
        return conj(*(eq(x, y) for x, y in zip(a, b)))
    if is_numeric(a) and is_numeric(b):
        return _num_eq(a, b)
    raise SymError(f"cannot compare {kind(a)} with {kind(b)}")


def _num_eq(a, b):
    if not is_z3(a) and not is_z3(b):
        return a == b
    if is_boolish(a) and is_boolish(b):
        return as_bool(a) == as_bool(b)
    return as_int(a) == as_int(b)


def _num_lt_eq(n, k):
    """n <= k (used for 'index k is past the end')."""
    if not is_z3(n):
        return n <= k
    return n <= k


def truthy(v):
    if is_boolish(v):
        return v
    if is_intish(v):
        return v != 0 if not is_z3(v) else v != 0
    if isinstance(v, SymList):
        return v.length > 0 if not is_z3(v.length) else v.length > 0
    if v is NONE:
        return False
    if isinstance(v, Opt):
        return conj(neg(v.is_none), truthy(v.val))
    if isinstance(v, tuple):
        return len(v) > 0
    raise SymError(f"cannot use a {kind(v)} value as a condition")


def num(v):
    """Coerce to something usable in arithmetic."""
    if isinstance(v, bool):
        return int(v)
    if is_z3(v) and z3.is_bool(v):
        return as_int(v)
    if is_intish(v):
        return v
    raise SymError(f"expected a number, got {kind(v)}")


def _ite_chain_get(elems, idx):
    """elems[idx] for a symbolic idx known (by the caller) to be in range."""
    if not elems:
        return 0
    if not is_z3(idx):
        return elems[idx] if 0 <= idx < len(elems) else elems[-1]
    v = elems[-1]
    for k in range(len(elems) - 2, -1, -1):
        v = ite(idx == k, elems[k], v)
    return v


# --------------------------------------------------------------------------
# List primitives. Each returns (result, bad) where bad is the condition
# under which Python would raise.
# --------------------------------------------------------------------------


def _norm_index(lst: SymList, idx):
    n = lst.length
    if not is_z3(idx) and not is_z3(n):
        j = idx + n if idx < 0 else idx
        return j, not (0 <= j < n)
    if not is_z3(idx) and idx >= 0:
        return idx, idx >= n
    i = as_int(idx)
    j = z3.If(i < 0, i + n, i)
    return j, z3.Or(j < 0, j >= n)


def list_get(lst: SymList, idx):
    idx = num(idx)
    j, bad = _norm_index(lst, idx)
    if concrete(bad) is True:
        return 0, True
    if not is_z3(j):
        return (lst.elems[j] if j < lst.cap else 0), bad
    return _ite_chain_get(lst.elems, j), bad


def list_set(lst: SymList, idx, val):
    idx = num(idx)
    j, bad = _norm_index(lst, idx)
    if concrete(bad) is True:
        return lst, True
    if not is_z3(j):
        if j >= lst.cap:
            return lst, bad
        elems = list(lst.elems)
        elems[j] = val
        return mk_list(lst.length, elems), bad
    return mk_list(lst.length, [ite(j == k, val, e) for k, e in enumerate(lst.elems)]), bad


def list_append(lst: SymList, val) -> SymList:
    n = lst.length
    if not is_z3(n):
        return mk_list(n + 1, lst.elems + (val,))
    elems = [ite(n == k, val, e) for k, e in enumerate(lst.elems)] + [val]
    return mk_list(n + 1, elems)


def list_concat(a: SymList, b: SymList) -> SymList:
    if not is_z3(a.length):
        out = a
        for k in range(b.cap):
            appended = list_append(out, b.elems[k])
            out = appended if not is_z3(b.length) else ite(k < b.length, appended, out)
        return out
    cap = a.cap + b.cap
    elems = []
    for k in range(cap):
        from_b, _ = list_get(b, k - a.length) if b.cap else (0, True)
        from_a = a.elems[k] if k < a.cap else from_b
        elems.append(ite(k < a.length, from_a, from_b))
    return mk_list(a.length + b.length, elems)


def list_slice(lst: SymList, lo, hi, step) -> SymList:
    n = lst.length
    if step not in (None, 1, -1):
        raise SymError("slices with a step other than 1 or -1 are not supported")
    if step == -1:
        if lo is not None or hi is not None:
            raise SymError("only the full reversal slice xs[::-1] is supported with step -1")
        return list_reversed(lst)
    if not is_z3(n) and (lo is None or not is_z3(lo)) and (hi is None or not is_z3(hi)):
        elems = lst.elems[slice(lo, hi)]
        return mk_list(len(elems), elems)

    def norm(v, default):
        if v is None:
            return default
        v = as_int(num(v))
        v = z3.If(v < 0, v + n, v)
        return z3.If(v < 0, 0, z3.If(v > n, n, v))

    a = norm(lo, 0)
    b = norm(hi, n)
    length = z3.If(b > a, b - a, 0)
    elems = [_ite_chain_get(lst.elems, a + k) for k in range(lst.cap)]
    return mk_list(length, elems)


def list_reversed(lst: SymList) -> SymList:
    n = lst.length
    if not is_z3(n):
        return mk_list(n, tuple(reversed(lst.elems)))
    return mk_list(n, [_ite_chain_get(lst.elems, n - 1 - k) for k in range(lst.cap)])


def list_contains(lst: SymList, val):
    return disj(*(conj(_lt(k, lst.length), eq(e, val)) for k, e in enumerate(lst.elems)))


def list_count(lst: SymList, val):
    total = 0
    for k, e in enumerate(lst.elems):
        total = _add(total, ite(conj(_lt(k, lst.length), eq(e, val)), 1, 0))
    return total


def list_sum(lst: SymList, start=0):
    total = start
    for k, e in enumerate(lst.elems):
        total = _add(total, ite(_lt(k, lst.length), num(e), 0))
    return total


def list_index(lst: SymList, val):
    r = -1
    for k in range(lst.cap - 1, -1, -1):
        r = ite(conj(_lt(k, lst.length), eq(lst.elems[k], val)), k, r)
    return r, _num_eq(r, -1)


def list_minmax(lst: SymList, want_max: bool):
    if lst.cap == 0:
        return 0, True
    best = lst.elems[0]
    for k in range(1, lst.cap):
        e = lst.elems[k]
        better = _gt(e, best) if want_max else _lt(e, best)
        best = ite(conj(_lt(k, lst.length), better), e, best)
    return best, _num_eq(lst.length, 0) if is_z3(lst.length) else lst.length == 0


def list_sorted(lst: SymList, reverse: bool = False) -> SymList:
    for e in lst.elems:
        if not is_numeric(e):
            raise SymError("sorted() is only supported on lists of numbers")
    if not is_z3(lst.length) and not any(is_z3(e) for e in lst.elems):
        return mk_list(lst.length, sorted(lst.elems, reverse=reverse))
    e = list(lst.elems)
    n = lst.length
    for i in range(len(e)):
        for j in range(len(e) - 1 - i):
            out_of_order = _gt(e[j + 1], e[j]) if reverse else _lt(e[j + 1], e[j])
            swap = conj(_lt(j + 1, n), out_of_order)
            e[j], e[j + 1] = ite(swap, e[j + 1], e[j]), ite(swap, e[j], e[j + 1])
    return mk_list(n, e)


def list_pop(lst: SymList, idx=None):
    if idx is None:
        idx = -1
    j, bad = _norm_index(lst, num(idx))
    if concrete(bad) is True:
        return 0, lst, True
    val = (lst.elems[j] if j < lst.cap else 0) if not is_z3(j) else _ite_chain_get(lst.elems, j)
    n = lst.length
    if not is_z3(j) and not is_z3(n):
        elems = lst.elems[:j] + lst.elems[j + 1:]
        return val, mk_list(n - 1, elems), bad
    elems = []
    for k in range(lst.cap):
        nxt = lst.elems[k + 1] if k + 1 < lst.cap else lst.elems[k]
        elems.append(ite(_lt(k, j), lst.elems[k], nxt))
    return val, mk_list(n - 1, elems), bad


def list_insert(lst: SymList, idx, val) -> SymList:
    n = lst.length
    i = as_int(num(idx))
    i = z3.If(i < 0, i + n, i)
    i = z3.If(i < 0, 0, z3.If(i > n, n, i))
    elems = []
    for k in range(lst.cap + 1):
        prev = lst.elems[k - 1] if k >= 1 else val
        cur = lst.elems[k] if k < lst.cap else val
        elems.append(ite(k < i, cur, ite(i == k, val, prev)))
    return mk_list(n + 1, elems)


def _lt(a, b):
    if not is_z3(a) and not is_z3(b):
        return num(a) < num(b)
    return as_int(num(a)) < as_int(num(b))


def _gt(a, b):
    return _lt(b, a)


def _add(a, b):
    a, b = num(a), num(b)
    if not is_z3(a) and not is_z3(b):
        return a + b
    return as_int(a) + as_int(b)


# --------------------------------------------------------------------------
# Interpreter
# --------------------------------------------------------------------------


@dataclass
class Frame:
    env: dict
    alive: object = True


@dataclass
class _Call:
    ret: object = UNDEF
    returned: object = False


@dataclass
class _Loop:
    brk: list = field(default_factory=list)
    cont: list = field(default_factory=list)


@dataclass
class Outcome:
    """Result of symbolically executing one call.

    value    -- the return value (meaningful where ``normal`` holds)
    normal   -- condition under which the call returns without raising
    exc      -- condition under which the call raises
    unwind   -- condition under which a loop needed more than ``loop_bound``
                iterations (callers assume this is false)
    """

    value: object
    normal: object
    exc: object
    unwind: object


_BUILTINS = {"len", "abs", "min", "max", "sum", "sorted", "reversed", "range", "list", "all", "any",
             "int", "bool", "enumerate", "zip", "divmod", "pow", "tuple"}
_LIST_METHODS = {"append", "extend", "pop", "insert", "remove", "sort", "reverse", "count", "index", "copy"}


def merge_frames(frames: list[Frame]) -> Frame:
    live = [f for f in frames if concrete(f.alive) is not False]
    if not live:
        return Frame(dict(frames[0].env) if frames else {}, False)
    if len(live) == 1:
        return Frame(dict(live[0].env), live[0].alive)
    keys = set().union(*(f.env.keys() for f in live))
    env = {}
    for name in keys:
        v = live[-1].env.get(name, UNDEF)
        for f in reversed(live[:-1]):
            v = ite(f.alive, f.env.get(name, UNDEF), v)
        env[name] = v
    return Frame(env, disj(*(f.alive for f in live)))


class SymbolicExecutor:
    """Executes functions of one module symbolically. One instance per module."""

    def __init__(self, source: str, loop_bound: int = 8, max_depth: int = 6):
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            raise SymError(f"syntax error on line {e.lineno}: {e.msg}") from None
        self.loop_bound = loop_bound
        self.max_depth = max_depth
        self.functions: dict[str, ast.FunctionDef] = {}
        self.globals: dict[str, object] = {}
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                self.functions[node.name] = node
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                continue
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                try:
                    self.globals[node.targets[0].id] = ast.literal_eval(node.value)
                except ValueError:
                    raise SymError(f"line {node.lineno}: module-level assignments must be constants") from None
            else:
                raise SymError(f"line {node.lineno}: only function definitions and constants are allowed at module level")
        self._fresh = 0

    # ---- public API ---------------------------------------------------

    def run(self, fname: str, args: list) -> Outcome:
        if fname not in self.functions:
            raise SymError(f"function '{fname}' is not defined (defined: {', '.join(self.functions) or 'none'})")
        self.exc = False
        self.unwind = False
        self.loops: list[_Loop] = []
        self.stack: list[str] = []
        self.local_names: list[set] = []
        value, normal = self._call_user(fname, list(args), {}, True)
        return Outcome(value, normal, self.exc, self.unwind)

    # ---- function calls -----------------------------------------------

    def _call_user(self, fname, args, kwargs, alive):
        fdef = self.functions[fname]
        if fname in self.stack:
            raise SymError(f"recursive call to '{fname}' is not supported; use a loop")
        if len(self.stack) >= self.max_depth:
            raise SymError("function calls nested too deeply")
        a = fdef.args
        if a.vararg or a.kwarg or a.kwonlyargs or a.posonlyargs:
            raise SymError(f"function '{fname}': only plain positional parameters are supported")
        params = [p.arg for p in a.args]
        if len(args) > len(params):
            raise SymError(f"'{fname}' takes {len(params)} arguments but {len(args)} were given")
        env = dict(zip(params, args))
        for k, v in kwargs.items():
            if k not in params:
                raise SymError(f"'{fname}' got an unexpected keyword argument '{k}'")
            env[k] = v
        defaults = dict(zip(params[len(params) - len(a.defaults):], a.defaults))
        for p in params:
            if p not in env:
                if p not in defaults:
                    raise SymError(f"'{fname}' missing argument '{p}'")
                env[p] = self._const(defaults[p])
        self.stack.append(fname)
        self.local_names.append(_assigned_names(fdef))
        call = _Call()
        saved_loops, self.loops = self.loops, []
        frame = self.exec_block(fdef.body, Frame(env, alive), call)
        self.loops = saved_loops
        self.stack.pop()
        self.local_names.pop()
        if concrete(frame.alive) is False:
            ret = NONE if call.ret is UNDEF else call.ret
        else:
            ret = join_return(frame.alive, NONE, call.ret)
        return ret, disj(call.returned, frame.alive)

    def _const(self, node):
        try:
            v = ast.literal_eval(node)
        except ValueError:
            raise SymError(f"line {node.lineno}: default values must be constants") from None
        return self._lift(v)

    def _lift(self, v):
        if v is None:
            return NONE
        if isinstance(v, (bool, int)):
            return v
        if isinstance(v, (list, tuple)):
            items = [self._lift(x) for x in v]
            return mk_list(len(items), items) if isinstance(v, list) else tuple(items)
        if isinstance(v, str):
            raise SymError("strings are not supported")
        raise SymError(f"constants of type {type(v).__name__} are not supported")

    # ---- statements ---------------------------------------------------

    def fail(self, frame: Frame, bad):
        """Record that the current statement raises where ``bad`` holds."""
        if concrete(bad) is False:
            return
        self.exc = disj(self.exc, conj(frame.alive, bad))
        frame.alive = conj(frame.alive, neg(bad))

    def exec_block(self, stmts, frame: Frame, call: _Call) -> Frame:
        for stmt in stmts:
            if concrete(frame.alive) is False:
                break
            frame = self.exec_stmt(stmt, frame, call)
        return frame

    def exec_stmt(self, node, frame: Frame, call: _Call) -> Frame:
        try:
            return self._exec_stmt(node, frame, call)
        except SymError as e:
            if not getattr(e, "located", False) and hasattr(node, "lineno"):
                e.args = (f"line {node.lineno}: {e.args[0]}",)
                e.located = True
            raise

    def _exec_stmt(self, node, frame: Frame, call: _Call) -> Frame:
        if isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return frame
            self.eval(node.value, frame)
            return frame
        if isinstance(node, ast.Assign):
            value = self.eval(node.value, frame)
            for t in node.targets:
                self.assign(t, value, frame)
            return frame
        if isinstance(node, ast.AnnAssign):
            if node.value is not None:
                self.assign(node.target, self.eval(node.value, frame), frame)
            return frame
        if isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name):
                cur = self.lookup(node.target.id, frame)
                self.assign(node.target, self.binop(node.op, cur, self.eval(node.value, frame), frame), frame)
            elif isinstance(node.target, ast.Subscript):
                base = self.eval(node.target.value, frame)
                idx = self.eval(node.target.slice, frame)
                if not isinstance(base, SymList):
                    raise SymError(f"cannot index into {kind(base)}")
                cur, bad = list_get(base, idx)
                self.fail(frame, bad)
                self.assign(node.target, self.binop(node.op, cur, self.eval(node.value, frame), frame), frame)
            else:
                raise SymError("unsupported augmented assignment target")
            return frame
        if isinstance(node, ast.If):
            c = truthy(self.eval(node.test, frame))
            k = concrete(c)
            if k is True:
                return self.exec_block(node.body, frame, call)
            if k is False:
                return self.exec_block(node.orelse, frame, call)
            then_f = self.exec_block(node.body, Frame(dict(frame.env), conj(frame.alive, c)), call)
            else_f = self.exec_block(node.orelse, Frame(dict(frame.env), conj(frame.alive, neg(c))), call)
            return merge_frames([then_f, else_f])
        if isinstance(node, ast.For):
            return self.exec_for(node, frame, call)
        if isinstance(node, ast.While):
            return self.exec_while(node, frame, call)
        if isinstance(node, ast.Return):
            v = NONE if node.value is None else self.eval(node.value, frame)
            call.ret = join_return(frame.alive, v, call.ret)
            call.returned = disj(call.returned, frame.alive)
            frame.alive = False
            return frame
        if isinstance(node, (ast.Break, ast.Continue)):
            if not self.loops:
                raise SymError("'break'/'continue' outside a loop")
            loop = self.loops[-1]
            (loop.brk if isinstance(node, ast.Break) else loop.cont).append(Frame(dict(frame.env), frame.alive))
            frame.alive = False
            return frame
        if isinstance(node, ast.Pass):
            return frame
        if isinstance(node, ast.Assert):
            self.fail(frame, neg(truthy(self.eval(node.test, frame))))
            return frame
        if isinstance(node, ast.Raise):
            self.fail(frame, True)
            return frame
        raise SymError(f"unsupported statement: {type(node).__name__}")

    def assign(self, target, value, frame: Frame):
        if isinstance(target, ast.Name):
            frame.env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            if isinstance(value, SymList):
                if is_z3(value.length):
                    raise SymError("cannot unpack a list whose length is not fixed")
                value = value.elems
            if not isinstance(value, tuple):
                raise SymError(f"cannot unpack a {kind(value)}")
            if len(value) != len(target.elts):
                raise SymError(f"cannot unpack {len(value)} values into {len(target.elts)} targets")
            for t, v in zip(target.elts, value):
                self.assign(t, v, frame)
        elif isinstance(target, ast.Subscript):
            if not isinstance(target.value, ast.Name):
                raise SymError("only assignments of the form name[index] = value are supported")
            base = self.lookup(target.value.id, frame)
            if not isinstance(base, SymList):
                raise SymError(f"cannot assign into a {kind(base)}")
            if isinstance(target.slice, ast.Slice):
                raise SymError("slice assignment is not supported")
            new, bad = list_set(base, self.eval(target.slice, frame), value)
            self.fail(frame, bad)
            frame.env[target.value.id] = new
        else:
            raise SymError(f"unsupported assignment target {type(target).__name__}")

    def _iteration(self, iter_node, frame: Frame):
        """Return (count, cond(j), item(j), exceed_cond) describing a for loop."""
        if isinstance(iter_node, ast.Call) and isinstance(iter_node.func, ast.Name) and iter_node.func.id in ("enumerate", "zip") \
                and iter_node.func.id not in frame.env:
            name = iter_node.func.id
            vals = [self.eval(a, frame) for a in iter_node.args]
            if name == "enumerate":
                start = 0
                if len(vals) == 2:
                    start = vals[1]
                for kw in iter_node.keywords:
                    if kw.arg == "start":
                        start = self.eval(kw.value, frame)
                n, cond, item, exceed = self._iteration_of_value(vals[0])
                return n, cond, (lambda j: (_add(start, j), item(j))), exceed
            seqs = [self._iteration_of_value(v) for v in vals]
            n = min(s[0] for s in seqs)
            return (n, lambda j: conj(*(s[1](j) for s in seqs)), lambda j: tuple(s[2](j) for s in seqs),
                    conj(*(s[1](n) if s[0] > n else s[3] for s in seqs)))
        return self._iteration_of_value(self.eval(iter_node, frame))

    def _iteration_of_value(self, v):
        if isinstance(v, RangeVal):
            start, stop, step = v.start, v.stop, v.step
            if not is_z3(start) and not is_z3(stop):
                items = list(range(start, stop, step))
                if len(items) > MAX_CONCRETE_UNROLL:
                    raise SymError("loop with too many iterations")
                return len(items), (lambda j: True), (lambda j: items[j]), False
            K = self.loop_bound

            def item(j):
                return _add(start, j * step)

            def cond(j):
                return _lt(item(j), stop) if step > 0 else _gt(item(j), stop)

            return K, cond, item, cond(K)
        if isinstance(v, SymList):
            n = v.length
            if not is_z3(n):
                return n, (lambda j: True), (lambda j: v.elems[j]), False
            return v.cap, (lambda j: j < n), (lambda j: v.elems[j]), False
        if isinstance(v, tuple):
            return len(v), (lambda j: True), (lambda j: v[j]), False
        raise SymError(f"cannot iterate over a {kind(v)}")

    def exec_for(self, node: ast.For, frame: Frame, call: _Call) -> Frame:
        if node.orelse:
            raise SymError("for ... else is not supported")
        n, cond, item, exceed = self._iteration(node.iter, frame)
        loop = _Loop()
        self.loops.append(loop)
        exits = []
        completed = True
        for j in range(n):
            c = cond(j)
            stay_out = conj(frame.alive, neg(c))
            if concrete(stay_out) is not False:
                exits.append(Frame(dict(frame.env), stay_out))
            enter = conj(frame.alive, c)
            if concrete(enter) is False:
                frame = Frame(frame.env, False)
                completed = False
                break
            body = Frame(dict(frame.env), enter)
            self.assign(node.target, item(j), body)
            loop.cont = []
            body = self.exec_block(node.body, body, call)
            if loop.cont:
                body = merge_frames([body] + loop.cont)
            frame = body
        if completed and concrete(exceed) is not False:
            self.unwind = disj(self.unwind, conj(frame.alive, exceed))
            frame = Frame(frame.env, conj(frame.alive, neg(exceed)))
        self.loops.pop()
        return merge_frames(exits + [frame] + loop.brk)

    def exec_while(self, node: ast.While, frame: Frame, call: _Call) -> Frame:
        if node.orelse:
            raise SymError("while ... else is not supported")
        loop = _Loop()
        self.loops.append(loop)
        exits = []
        for j in range(self.loop_bound + 1):
            c = truthy(self.eval(node.test, frame))
            stay_out = conj(frame.alive, neg(c))
            if concrete(stay_out) is not False:
                exits.append(Frame(dict(frame.env), stay_out))
            enter = conj(frame.alive, c)
            if j == self.loop_bound:
                self.unwind = disj(self.unwind, enter)
                break
            if concrete(enter) is False:
                break
            body = Frame(dict(frame.env), enter)
            loop.cont = []
            body = self.exec_block(node.body, body, call)
            if loop.cont:
                body = merge_frames([body] + loop.cont)
            frame = body
        self.loops.pop()
        return merge_frames(exits + loop.brk) if (exits or loop.brk) else Frame(frame.env, False)

    # ---- expressions --------------------------------------------------

    def lookup(self, name, frame: Frame):
        if name in frame.env:
            v = frame.env[name]
            if v is UNDEF:
                self.fail(frame, True)  # UnboundLocalError on every path reaching here
                return 0
            if isinstance(v, Partial):
                self.fail(frame, neg(v.defined))
                return v.val
            return v
        if self.local_names and name in self.local_names[-1]:
            self.fail(frame, True)  # a local read before any assignment
            return 0
        if name in self.globals:
            return self._lift(self.globals[name])
        if name in ("True", "False", "None"):
            return {"True": True, "False": False, "None": NONE}[name]
        raise SymError(f"name '{name}' is not defined")

    def eval(self, node, frame: Frame):
        if isinstance(node, ast.Constant):
            return self._lift(node.value)
        if isinstance(node, ast.Name):
            return self.lookup(node.id, frame)
        if isinstance(node, ast.BinOp):
            left = self.eval(node.left, frame)
            right = self.eval(node.right, frame)
            return self.binop(node.op, left, right, frame)
        if isinstance(node, ast.UnaryOp):
            v = self.eval(node.operand, frame)
            if isinstance(node.op, ast.Not):
                return neg(truthy(v))
            if isinstance(node.op, ast.USub):
                v = self._strip_opt(v, frame)
                v = num(v)
                return -v
            if isinstance(node.op, ast.UAdd):
                return num(self._strip_opt(v, frame))
            raise SymError(f"unsupported unary operator {type(node.op).__name__}")
        if isinstance(node, ast.BoolOp):
            return self.eval_boolop(node, frame)
        if isinstance(node, ast.Compare):
            return self.eval_compare(node, frame)
        if isinstance(node, ast.IfExp):
            c = truthy(self.eval(node.test, frame))
            k = concrete(c)
            if k is not None:
                return self.eval(node.body if k else node.orelse, frame)
            ft = Frame(dict(frame.env), conj(frame.alive, c))
            vt = self.eval(node.body, ft)
            fe = Frame(dict(frame.env), conj(frame.alive, neg(c)))
            ve = self.eval(node.orelse, fe)
            merged = merge_frames([ft, fe])
            frame.env, frame.alive = merged.env, merged.alive
            return ite(c, vt, ve)
        if isinstance(node, ast.Call):
            return self.eval_call(node, frame)
        if isinstance(node, ast.Subscript):
            base = self.eval(node.value, frame)
            if isinstance(node.slice, ast.Slice):
                if not isinstance(base, SymList):
                    raise SymError(f"cannot slice a {kind(base)}")
                s = node.slice
                lo = None if s.lower is None else self.eval(s.lower, frame)
                hi = None if s.upper is None else self.eval(s.upper, frame)
                step = None if s.step is None else self.eval(s.step, frame)
                if step is not None and is_z3(step):
                    raise SymError("slice step must be a constant")
                return list_slice(base, lo, hi, step)
            idx = self.eval(node.slice, frame)
            if isinstance(base, tuple):
                if is_z3(idx):
                    raise SymError("tuple index must be a constant")
                if not -len(base) <= idx < len(base):
                    self.fail(frame, True)
                    return 0
                return base[idx]
            if not isinstance(base, SymList):
                raise SymError(f"cannot index into a {kind(base)}")
            v, bad = list_get(base, idx)
            self.fail(frame, bad)
            return v
        if isinstance(node, ast.List):
            items = [self.eval(e, frame) for e in node.elts]
            return mk_list(len(items), items)
        if isinstance(node, ast.Tuple):
            return tuple(self.eval(e, frame) for e in node.elts)
        if isinstance(node, ast.ListComp):
            return self.eval_listcomp(node.elt, node.generators, frame)
        if isinstance(node, ast.GeneratorExp):
            return self.eval_listcomp(node.elt, node.generators, frame)
        if isinstance(node, (ast.Dict, ast.Set, ast.DictComp, ast.SetComp)):
            raise SymError("dicts and sets are not supported; use lists")
        if isinstance(node, ast.JoinedStr):
            raise SymError("strings are not supported")
        if isinstance(node, ast.Lambda):
            raise SymError("lambda is not supported")
        if isinstance(node, ast.Attribute):
            raise SymError(f"attribute access '.{node.attr}' is not supported")
        raise SymError(f"unsupported expression: {type(node).__name__}")

    def _strip_opt(self, v, frame: Frame):
        """Using a maybe-None value as a number raises TypeError where it is None."""
        if v is NONE:
            self.fail(frame, True)
            return 0
        if isinstance(v, Opt):
            self.fail(frame, v.is_none)
            return v.val
        return v

    def binop(self, op, a, b, frame: Frame):
        a = self._strip_opt(a, frame)
        b = self._strip_opt(b, frame)
        if isinstance(op, ast.Add):
            if isinstance(a, SymList) and isinstance(b, SymList):
                return list_concat(a, b)
            if isinstance(a, tuple) and isinstance(b, tuple):
                return a + b
            return _add(a, b)
        if isinstance(op, ast.Mult) and (isinstance(a, SymList) or isinstance(b, SymList)):
            lst, cnt = (a, b) if isinstance(a, SymList) else (b, a)
            cnt = num(cnt)
            if not is_z3(cnt):
                out = mk_list(0, ())
                for _ in range(max(cnt, 0)):
                    out = list_concat(out, lst)
                return out
            if is_z3(lst.length) or lst.length != 1:
                raise SymError("list repetition by a symbolic count is only supported for one-element lists like [0] * n")
            K = self.loop_bound
            self.unwind = disj(self.unwind, conj(frame.alive, cnt > K))
            return mk_list(z3.If(cnt > 0, cnt, 0), [lst.elems[0]] * K)
        a, b = num(a), num(b)
        both_concrete = not is_z3(a) and not is_z3(b)
        if isinstance(op, ast.Sub):
            return a - b if both_concrete else as_int(a) - as_int(b)
        if isinstance(op, ast.Mult):
            return a * b if both_concrete else as_int(a) * as_int(b)
        if isinstance(op, (ast.FloorDiv, ast.Mod)):
            is_div = isinstance(op, ast.FloorDiv)
            if both_concrete:
                if b == 0:
                    self.fail(frame, True)
                    return 0
                return a // b if is_div else a % b
            self.fail(frame, _num_eq(b, 0))
            return _py_divmod(as_int(a), b, is_div)
        if isinstance(op, ast.Pow):
            if is_z3(b) or b < 0 or b > 12:
                raise SymError("exponent must be a constant between 0 and 12")
            out = 1
            for _ in range(b):
                out = out * a if not is_z3(out) and not is_z3(a) else as_int(out) * as_int(a)
            return out
        if isinstance(op, ast.Div):
            raise SymError("true division '/' produces floats, which are not supported; use '//'")
        raise SymError(f"unsupported operator {type(op).__name__}")

    def eval_boolop(self, node: ast.BoolOp, frame: Frame):
        """Python value semantics: `a or b` is a if a is truthy, else b; `a and b` is b if a is truthy, else a.
        The right operand is evaluated only on the paths where Python would evaluate it."""
        is_and = isinstance(node.op, ast.And)
        acc = self.eval(node.values[0], frame)
        for sub in node.values[1:]:
            c = truthy(acc)
            k = concrete(c)
            if k is not None:
                if k is not is_and:  # short-circuit: `and` with falsy left, `or` with truthy left
                    return acc
                acc = self.eval(sub, frame)
                continue
            guard = c if is_and else neg(c)
            fb = Frame(dict(frame.env), conj(frame.alive, guard))
            vb = self.eval(sub, fb)
            fskip = Frame(dict(frame.env), conj(frame.alive, neg(guard)))
            merged = merge_frames([fb, fskip])
            frame.env, frame.alive = merged.env, merged.alive
            try:
                acc = ite(guard, vb, acc)
            except SymError:
                raise SymError(f"`{'and' if is_and else 'or'}` whose operands have different types "
                               f"({kind(acc)} and {kind(vb)}) is not supported") from None
        return acc

    def eval_compare(self, node: ast.Compare, frame: Frame):
        """Chained comparisons short-circuit: `a < b < c` evaluates c only where a < b holds."""
        left = self.eval(node.left, frame)
        acc = True
        for op, rnode in zip(node.ops, node.comparators):
            k = concrete(acc)
            if k is False:
                return False
            if k is True:
                right = self.eval(rnode, frame)
                acc = self.compare(op, left, right, frame)
            else:
                fb = Frame(dict(frame.env), conj(frame.alive, acc))
                right = self.eval(rnode, fb)
                part = self.compare(op, left, right, fb)
                fskip = Frame(dict(frame.env), conj(frame.alive, neg(acc)))
                merged = merge_frames([fb, fskip])
                frame.env, frame.alive = merged.env, merged.alive
                acc = conj(acc, part)
            left = right
        return acc

    def compare(self, op, a, b, frame: Frame):
        if isinstance(op, (ast.Is, ast.IsNot)):
            if b is not NONE:
                raise SymError("'is' is only supported for comparisons with None")
            isn, _ = _opt_parts(a)
            return isn if isinstance(op, ast.Is) else neg(isn)
        if isinstance(op, ast.Eq):
            return eq(a, b)
        if isinstance(op, ast.NotEq):
            return neg(eq(a, b))
        if isinstance(op, (ast.In, ast.NotIn)):
            if isinstance(b, SymList):
                r = list_contains(b, a)
            elif isinstance(b, tuple):
                r = disj(*(eq(a, x) for x in b))
            elif isinstance(b, RangeVal):
                if b.step != 1:
                    raise SymError("'in range(...)' is only supported with step 1")
                x = num(self._strip_opt(a, frame))
                r = conj(_lt(x, b.stop), neg(_lt(x, b.start)))
            else:
                raise SymError(f"'in' is not supported on a {kind(b)}")
            return r if isinstance(op, ast.In) else neg(r)
        a = self._strip_opt(a, frame)
        b = self._strip_opt(b, frame)
        if isinstance(a, (SymList, tuple)) or isinstance(b, (SymList, tuple)):
            raise SymError("ordering comparisons (<, <=, >, >=) are only supported on numbers")
        if isinstance(op, ast.Lt):
            return _lt(a, b)
        if isinstance(op, ast.Gt):
            return _gt(a, b)
        if isinstance(op, ast.LtE):
            return neg(_gt(a, b))
        if isinstance(op, ast.GtE):
            return neg(_lt(a, b))
        raise SymError(f"unsupported comparison {type(op).__name__}")

    def eval_listcomp(self, elt, generators, frame: Frame):
        self._fresh += 1
        acc = f"__acc{self._fresh}"
        inner = ast.Expr(ast.Call(ast.Attribute(ast.Name(acc, ast.Load()), "append", ast.Load()), [elt], []))
        for gen in reversed(generators):
            if gen.is_async:
                raise SymError("async comprehensions are not supported")
            for cond in reversed(gen.ifs):
                inner = ast.If(cond, [inner], [])
            inner = ast.For(gen.target, gen.iter, [inner], [])
        child = Frame(dict(frame.env), frame.alive)
        child.env[acc] = mk_list(0, ())
        saved_loops, self.loops = self.loops, []
        child = self.exec_block([inner], child, _Call())
        self.loops = saved_loops
        frame.alive = child.alive
        return child.env[acc]

    def _quantifier(self, gen: ast.GeneratorExp, frame: Frame, is_all: bool):
        """all()/any() over a single-generator expression, with Python's short-circuiting."""
        self._fresh += 1
        res = f"__q{self._fresh}"
        g = gen.generators[0]
        test = gen.elt if not is_all else ast.UnaryOp(ast.Not(), gen.elt)
        inner = ast.If(test, [ast.Assign([ast.Name(res, ast.Store())], ast.Constant(not is_all)), ast.Break()], [])
        for cond in reversed(g.ifs):
            inner = ast.If(cond, [inner], [])
        loop = ast.For(g.target, g.iter, [inner], [])
        child = Frame(dict(frame.env), frame.alive)
        child.env[res] = is_all
        saved_loops, self.loops = self.loops, []
        child = self.exec_block([loop], child, _Call())
        self.loops = saved_loops
        frame.alive = child.alive
        return child.env[res]

    def eval_call(self, node: ast.Call, frame: Frame):
        func = node.func
        if isinstance(func, ast.Attribute):
            return self.eval_method(node, frame)
        if not isinstance(func, ast.Name):
            raise SymError("only calls to named functions are supported")
        name = func.id
        if name in frame.env:
            raise SymError(f"'{name}' is a variable here; calling a variable is not supported")
        if name in self.functions:
            args = [self.eval(a, frame) for a in node.args]
            kwargs = {kw.arg: self.eval(kw.value, frame) for kw in node.keywords}
            # Run the callee from path condition True and guard its effects by the caller's condition once.
            # Starting it from frame.alive would repeat that condition once per return statement; the DAG
            # stays small, but Z3's preprocessing expands shared sub-terms and blows up exponentially in
            # the number of calls. Arguments are passed by value, so the callee has no other effects.
            saved_exc, saved_unwind = self.exc, self.unwind
            self.exc = self.unwind = False
            value, normal = self._call_user(name, args, kwargs, True)
            self.exc = disj(saved_exc, conj(frame.alive, self.exc))
            self.unwind = disj(saved_unwind, conj(frame.alive, self.unwind))
            frame.alive = conj(frame.alive, normal)
            return value
        if name not in _BUILTINS:
            raise SymError(f"call to unsupported function '{name}'")
        if name in ("all", "any") and len(node.args) == 1 and isinstance(node.args[0], ast.GeneratorExp) \
                and len(node.args[0].generators) == 1:
            return self._quantifier(node.args[0], frame, name == "all")
        if any(isinstance(a, ast.Starred) for a in node.args):
            raise SymError("*args in calls is not supported")
        args = [self.eval(a, frame) for a in node.args]
        kwargs = {kw.arg: self.eval(kw.value, frame) for kw in node.keywords}
        return self.builtin(name, args, kwargs, frame)

    def builtin(self, name, args, kwargs, frame: Frame):
        def need_list(v):
            if isinstance(v, RangeVal):
                return self._range_list(v, frame)
            if isinstance(v, tuple):
                return mk_list(len(v), v)
            if not isinstance(v, SymList):
                raise SymError(f"{name}() expects a list, got {kind(v)}")
            return v

        allowed_kwargs = {"sorted": {"reverse"}, "min": {"default"}, "max": {"default"}, "sum": {"start"}}
        for k in kwargs:
            if k not in allowed_kwargs.get(name, set()):
                raise SymError(f"{name}() keyword argument '{k}' is not supported")
        if name == "len":
            v = args[0]
            if isinstance(v, tuple):
                return len(v)
            if isinstance(v, RangeVal):
                return self._range_list(v, frame).length
            return need_list(v).length
        if name == "abs":
            v = num(self._strip_opt(args[0], frame))
            return abs(v) if not is_z3(v) else z3.If(v < 0, -v, v)
        if name in ("min", "max"):
            want_max = name == "max"
            if len(args) == 1:
                lst = need_list(args[0])
                best, empty = list_minmax(lst, want_max)
                if "default" in kwargs:
                    return ite(empty, kwargs["default"], best)
                self.fail(frame, empty)
                return best
            if len(args) < 1:
                raise SymError(f"{name}() expects at least one argument")
            best = num(self._strip_opt(args[0], frame))
            for v in args[1:]:
                v = num(self._strip_opt(v, frame))
                best = ite(_gt(v, best) if want_max else _lt(v, best), v, best)
            return best
        if name == "sum":
            start = args[1] if len(args) > 1 else kwargs.get("start", 0)
            return list_sum(need_list(args[0]), start)
        if name == "sorted":
            rev = kwargs.get("reverse", False)
            if is_z3(rev):
                raise SymError("sorted(reverse=...) must be a constant")
            return list_sorted(need_list(args[0]), bool(rev))
        if name == "reversed":
            return list_reversed(need_list(args[0]))
        if name == "range":
            if not 1 <= len(args) <= 3:
                raise SymError("range() takes 1 to 3 arguments")
            vals = [num(self._strip_opt(a, frame)) for a in args]
            if len(vals) == 1:
                start, stop, step = 0, vals[0], 1
            else:
                start, stop = vals[0], vals[1]
                step = vals[2] if len(vals) == 3 else 1
            if is_z3(step) or step == 0:
                raise SymError("range() step must be a non-zero constant")
            return RangeVal(start, stop, step)
        if name in ("list", "tuple"):
            if not args:
                return mk_list(0, ()) if name == "list" else ()
            lst = need_list(args[0])
            if name == "tuple":
                if is_z3(lst.length):
                    raise SymError("tuple() of a variable-length list is not supported")
                return lst.elems
            return lst
        if name in ("all", "any"):
            lst = need_list(args[0])
            terms = [disj(neg(_lt(k, lst.length)), truthy(e)) if name == "all" else conj(_lt(k, lst.length), truthy(e))
                     for k, e in enumerate(lst.elems)]
            return conj(*terms) if name == "all" else disj(*terms)
        if name == "int":
            return num(self._strip_opt(args[0], frame))
        if name == "bool":
            return truthy(args[0])
        if name == "divmod":
            a, b = (num(self._strip_opt(x, frame)) for x in args)
            q = self.binop(ast.FloorDiv(), a, b, frame)
            r = self.binop(ast.Mod(), a, b, frame)
            return (q, r)
        if name == "pow":
            if len(args) != 2:
                raise SymError("pow() with a modulus argument is not supported; use (a ** b) % m")
            return self.binop(ast.Pow(), args[0], args[1], frame)
        if name in ("enumerate", "zip"):
            raise SymError(f"{name}() is only supported directly in a for loop")
        raise SymError(f"call to unsupported function '{name}'")

    def _range_list(self, r: RangeVal, frame: Frame) -> SymList:
        n, cond, item, exceed = self._iteration_of_value(r)
        if concrete(exceed) is not False:
            self.unwind = disj(self.unwind, conj(frame.alive, exceed))
        out = mk_list(0, ())
        for j in range(n):
            c = cond(j)
            appended = list_append(out, item(j))
            out = ite(c, appended, out)
        return out

    def eval_method(self, node: ast.Call, frame: Frame):
        func = node.func
        meth = func.attr
        if meth not in _LIST_METHODS:
            raise SymError(f"method '.{meth}()' is not supported")
        recv = self.eval(func.value, frame)
        if not isinstance(recv, SymList):
            raise SymError(f"'.{meth}()' called on a {kind(recv)}; only list methods are supported")
        args = [self.eval(a, frame) for a in node.args]
        kwargs = {kw.arg: self.eval(kw.value, frame) for kw in node.keywords}
        mutating = meth in ("append", "extend", "pop", "insert", "remove", "sort", "reverse")
        if mutating and not isinstance(func.value, ast.Name):
            raise SymError(f"'.{meth}()' must be called on a variable")

        def store(v):
            frame.env[func.value.id] = v

        if meth == "append":
            store(list_append(recv, args[0]))
            return NONE
        if meth == "extend":
            other = args[0]
            if not isinstance(other, SymList):
                raise SymError("extend() expects a list")
            store(list_concat(recv, other))
            return NONE
        if meth == "pop":
            val, new, bad = list_pop(recv, args[0] if args else None)
            self.fail(frame, bad)
            store(new)
            return val
        if meth == "insert":
            store(list_insert(recv, args[0], args[1]))
            return NONE
        if meth == "remove":
            idx, missing = list_index(recv, args[0])
            self.fail(frame, missing)
            _, new, _ = list_pop(recv, idx)
            store(new)
            return NONE
        if meth == "sort":
            rev = kwargs.get("reverse", False)
            store(list_sorted(recv, bool(rev)))
            return NONE
        if meth == "reverse":
            store(list_reversed(recv))
            return NONE
        if meth == "count":
            return list_count(recv, args[0])
        if meth == "index":
            idx, missing = list_index(recv, args[0])
            self.fail(frame, missing)
            return idx
        if meth == "copy":
            return recv
        raise SymError(f"method '.{meth}()' is not supported")


def _assigned_names(fdef: ast.FunctionDef) -> set:
    names = {a.arg for a in fdef.args.args}
    for node in ast.walk(fdef):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    return names


def _py_divmod(a, b, is_div: bool):
    """Python floor division / modulo on Z3 ints (Z3's own are Euclidean)."""
    if not is_z3(b):
        bz = z3.IntVal(b)
        q, r = a / bz, a % bz
        if b > 0:
            return q if is_div else r
        adj = r != 0
        return z3.If(adj, q - 1, q) if is_div else z3.If(adj, r + b, r)
    q, r = a / b, a % b
    adj = z3.And(b < 0, r != 0)
    return z3.If(adj, q - 1, q) if is_div else z3.If(adj, r + b, r)
