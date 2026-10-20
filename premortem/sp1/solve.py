"""Z3 queries for SP1.

Two queries share one shape, ``domain AND bounds AND violation``:

* ``diff_check``  -- gold: does the code under review ever behave differently
  from the reference? (violation = outcomes differ). Used to build and label
  instances and to measure how rare each bug's trigger is.
* ``spec_check``  -- the Translate arm's tool: does some input satisfy the
  model-written precondition while the code raises or breaks the model-written
  postcondition?

A model of the formula is the witness; UNSAT means "no failure within the
bounds" -- list capacities from the domain and loops unrolled ``loop_bound``
times (paths needing more iterations are excluded, not checked).
"""

from __future__ import annotations

import functools
import threading
import time
from dataclasses import dataclass, field

import z3

from . import domain as D
from .symexec import NONE, Opt, SymError, SymbolicExecutor, conj, disj, eq, neg, truthy


_Z3_LOCK = threading.RLock()  # the default Z3 context is not thread-safe
SPEC_CHECK_SECONDS = 120


class ToolTimeout(Exception):
    pass


class _deadline:
    """Wall-clock limit for symbolic execution + solving (only in a process's main thread)."""

    def __init__(self, seconds: float):
        self.seconds = seconds
        self.active = threading.current_thread() is threading.main_thread()

    def __enter__(self):
        if self.active:
            import signal
            self.old = signal.signal(signal.SIGALRM, self._fire)
            signal.setitimer(signal.ITIMER_REAL, self.seconds)
        return self

    @staticmethod
    def _fire(signum, frame):
        raise ToolTimeout()

    def __exit__(self, *exc):
        if self.active:
            import signal
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, self.old)
        return False


def _serialized(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _Z3_LOCK:
            return fn(*args, **kwargs)
    return wrapper


@dataclass
class SolveResult:
    status: str  # "witness" | "no_witness" | "unknown" | "error"
    witness: dict | None = None
    seconds: float = 0.0
    detail: str = ""
    stats: dict = field(default_factory=dict)


def symbolic_inputs(params):
    syms, cons = {}, []
    for name, t in params:
        v, c = D.make_symbolic(name, t)
        syms[name] = v
        cons += c
    return syms, cons


def outcomes_differ(a, b):
    """The two calls raise differently, or both return normally with different values."""
    exc_differs = a.exc != b.exc if isinstance(a.exc, bool) and isinstance(b.exc, bool) else _b(a.exc) != _b(b.exc)
    return disj(exc_differs, conj(neg(a.exc), neg(b.exc), neg(eq(a.value, b.value))))


def _b(c):
    return z3.BoolVal(c) if isinstance(c, bool) else c


def _solve(constraints, params, syms, timeout_ms):
    s = z3.Solver()
    s.set("timeout", timeout_ms)
    for c in constraints:
        if isinstance(c, bool):
            if not c:
                return "no_witness", None
            continue
        s.add(c)
    r = s.check()
    if r == z3.sat:
        m = s.model()
        return "witness", {name: D.from_model(t, syms[name], m) for name, t in params}
    if r == z3.unsat:
        return "no_witness", None
    return "unknown", None


@_serialized
def diff_check(src_ref: str, src_mut: str, fname: str, params, loop_bound: int, timeout_ms: int = 60_000) -> SolveResult:
    t0 = time.perf_counter()
    syms, cons = symbolic_inputs(params)
    args = [syms[n] for n, _ in params]
    try:
        o_ref = SymbolicExecutor(src_ref, loop_bound).run(fname, args)
        o_mut = SymbolicExecutor(src_mut, loop_bound).run(fname, args)
    except SymError as e:
        return SolveResult("error", detail=str(e), seconds=time.perf_counter() - t0)
    formula = cons + [neg(o_ref.unwind), neg(o_mut.unwind), outcomes_differ(o_ref, o_mut)]
    status, wit = _solve(formula, params, syms, timeout_ms)
    return SolveResult(status, wit, time.perf_counter() - t0)


@_serialized
def unwind_possible(src: str, fname: str, params, loop_bound: int) -> bool:
    """Whether some in-domain input needs more than ``loop_bound`` iterations."""
    syms, cons = symbolic_inputs(params)
    o = SymbolicExecutor(src, loop_bound).run(fname, [syms[n] for n, _ in params])
    status, _ = _solve(cons + [o.unwind], params, syms, 30_000)
    return status != "no_witness"


HARD_LIMIT_SECONDS = 150


def spec_check(code_src: str, fname: str, spec_src: str, params, loop_bound: int,
               timeout_ms: int = 60_000) -> SolveResult:
    """Search for an in-domain input with pre(x) true where the code raises or post(x, f(x)) is false.

    Runs in a child process that is killed after ``HARD_LIMIT_SECONDS``: a model-written spec can make
    term construction or Z3 run far past Z3's own timeout, and native code ignores Python signals.
    A timeout is reported as status "timeout", separately from any verdict."""
    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    recv, send = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_spec_check_child, args=(send, code_src, fname, spec_src, params, loop_bound, timeout_ms))
    t0 = time.perf_counter()
    proc.start()
    send.close()
    if recv.poll(HARD_LIMIT_SECONDS):
        try:
            result = recv.recv()
        except EOFError:
            result = SolveResult("error", detail="(tool limitation) the checker process died", stats={"tool_error": True})
    else:
        proc.kill()
        result = SolveResult("timeout", detail=f"symbolic execution and solving exceeded {HARD_LIMIT_SECONDS} s",
                             seconds=time.perf_counter() - t0)
    proc.join()
    return result


def _spec_check_child(conn, *args):
    try:
        conn.send(spec_check_inprocess(*args))
    except BaseException as e:  # report rather than hang the parent
        conn.send(SolveResult("error", detail=f"(tool limitation) checker crashed: {e!r}", stats={"tool_error": True}))
    conn.close()


@_serialized
def spec_check_inprocess(code_src: str, fname: str, spec_src: str, params, loop_bound: int,
                         timeout_ms: int = 60_000) -> SolveResult:
    t0 = time.perf_counter()
    try:
        with _deadline(SPEC_CHECK_SECONDS):
            return _spec_check(code_src, fname, spec_src, params, loop_bound, timeout_ms, t0)
    except ToolTimeout:
        return SolveResult("timeout", detail=f"symbolic execution and solving exceeded {SPEC_CHECK_SECONDS} s",
                           seconds=time.perf_counter() - t0)


def _spec_check(code_src, fname, spec_src, params, loop_bound, timeout_ms, t0) -> SolveResult:
    syms, cons = symbolic_inputs(params)
    args = [syms[n] for n, _ in params]
    try:
        spec = SymbolicExecutor(spec_src, loop_bound)
    except SymError as e:
        return SolveResult("error", detail=f"in your specification: {e}", seconds=time.perf_counter() - t0)
    if "post" not in spec.functions:
        return SolveResult("error", detail="the specification must define a function named post", seconds=time.perf_counter() - t0)
    n_post = len(spec.functions["post"].args.args)
    if n_post != len(params) + 1:
        names = ", ".join([n for n, _ in params] + ["result"])
        return SolveResult("error", detail=f"post must take exactly {len(params) + 1} parameters ({names}), "
                                           f"but it takes {n_post}", seconds=time.perf_counter() - t0)
    try:
        code_out = SymbolicExecutor(code_src, loop_bound).run(fname, args)
    except SymError as e:
        return SolveResult("error", detail=f"(tool limitation) the code under review could not be encoded: {e}",
                           seconds=time.perf_counter() - t0, stats={"tool_error": True})
    try:
        pre_ok, pre_unwind = True, False
        if "pre" in spec.functions:
            n_pre = len(spec.functions["pre"].args.args)
            if n_pre != len(params):
                return SolveResult("error", detail=f"pre must take exactly {len(params)} parameters, but it takes {n_pre}",
                                   seconds=time.perf_counter() - t0)
            pre_out = spec.run("pre", args)
            pre_ok = conj(pre_out.normal, truthy(pre_out.value))
            pre_unwind = pre_out.unwind
        result = code_out.value
        post_out = spec.run("post", args + [result])
        post_ok = conj(post_out.normal, truthy(post_out.value))
    except SymError as e:
        return SolveResult("error", detail=f"in your specification: {e}", seconds=time.perf_counter() - t0)

    # A precondition that excludes the whole domain makes every check vacuous.
    vac_status, _ = _solve(cons + [pre_ok, neg(pre_unwind)], params, syms, timeout_ms)
    if vac_status == "no_witness":
        return SolveResult("error", detail="your precondition pre(...) is false for every input in the stated domain, "
                                           "so nothing would be checked", seconds=time.perf_counter() - t0)
    violation = conj(pre_ok, disj(code_out.exc, neg(post_ok)))
    formula = cons + [neg(code_out.unwind), neg(post_out.unwind), neg(pre_unwind), violation]
    status, wit = _solve(formula, params, syms, timeout_ms)
    return SolveResult(status, wit, time.perf_counter() - t0)


def evaluate_outcome(src: str, fname: str, params, loop_bound: int, values: dict):
    """Symbolically execute on concrete inputs and simplify (for executor self-tests)."""
    args = [D.to_symbolic_constant(t, values[n]) for n, t in params]
    o = SymbolicExecutor(src, loop_bound).run(fname, args)
    return o


def concretize(v):
    """Turn a fully-simplified executor value into a Python value."""
    from .symexec import SymList, concrete, is_z3
    if v is NONE:
        return None
    if isinstance(v, Opt):
        isn = z3.simplify(v.is_none) if is_z3(v.is_none) else v.is_none
        if concrete(isn):
            return None
        return concretize(v.val)
    if isinstance(v, SymList):
        n = v.length if not is_z3(v.length) else z3.simplify(v.length).as_long()
        return [concretize(e) for e in v.elems[:n]]
    if isinstance(v, tuple):
        return tuple(concretize(x) for x in v)
    if is_z3(v):
        s = z3.simplify(v)
        if z3.is_bool(s):
            return z3.is_true(s)
        return s.as_long()
    return v
