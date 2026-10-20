"""Planning as satisfiability (Kautz & Selman 1992; R&N 4th ed., Ch. 11).

For a horizon ``T`` the encoding has fluent variables ``f@t`` (t = 0..T) and
action variables ``a@t`` (t = 0..T-1) with

* the initial state fully specified (closed world) and the goal at ``T``;
* precondition axioms ``a@t -> p@t`` (``-> not p@t`` for negative ones);
* effect axioms ``a@t -> add@t+1`` and ``a@t -> not del@t+1``;
* explanatory frame axioms
  ``(f@t & ~f@t+1) -> OR{a@t : f in del(a)}`` and
  ``(~f@t & f@t+1) -> OR{a@t : f in add(a)}``;
* exactly one action per step (sequential plans), via a sequential counter.

Horizons are tried in order T = 0, 1, ..., so the first satisfiable one gives a
shortest plan. Planning-graph style reachability layers fix variables that
cannot vary: a fact that cannot yet be true (or cannot yet be false) at step
``t`` becomes a constant, and an action whose preconditions cannot hold at
``t`` gets no variable. Clauses for step ``t`` do not depend on ``T``, so one
incremental solver is reused and the goal is passed as assumptions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from pysat.card import CardEnc, EncType
from pysat.formula import IDPool
from pysat.solvers import Solver

from .ground import Task
from .validate import validate_plan

Lit = int | bool


@dataclass
class HorizonStats:
    """Formula size and solver time for one horizon (``sat`` is None on timeout)."""

    T: int
    n_vars: int
    n_clauses: int
    solve_seconds: float
    sat: bool | None


@dataclass
class SatPlanResult:
    plan: list[str] | None
    length: int | None
    status: str  # "solved" | "no_plan_within_bound" | "timeout"
    stats: list[HorizonStats] = field(default_factory=list)
    seconds: float = 0.0


class _Layers:
    """Relaxed reachability per step: facts possibly true/false, actions possible."""

    def __init__(self, task: Task, index: dict[str, int]) -> None:
        self.pre = [[index[f] for f in a.pre_pos] for a in task.actions]
        self.neg = [[index[f] for f in a.pre_neg] for a in task.actions]
        self.add = [[index[f] for f in a.add] for a in task.actions]
        self.dele = [[index[f] for f in a.delete] for a in task.actions]
        init = {index[f] for f in task.init}
        self.true: list[frozenset[int]] = [frozenset(init)]
        self.false: list[frozenset[int]] = [frozenset(set(range(len(index))) - init)]
        self.acts: list[list[int]] = []

    def facts_at(self, t: int) -> tuple[frozenset[int], frozenset[int]]:
        while len(self.true) <= t:
            self._grow()
        return self.true[t], self.false[t]

    def actions_at(self, t: int) -> list[int]:
        while len(self.acts) <= t:
            self._grow()
        return self.acts[t]

    def _grow(self) -> None:
        t = len(self.acts)
        tr, fa = self.true[t], self.false[t]
        acts = [i for i in range(len(self.pre))
                if all(p in tr for p in self.pre[i]) and all(p in fa for p in self.neg[i])]
        self.acts.append(acts)
        self.true.append(tr.union(*(self.add[i] for i in acts)))
        self.false.append(fa.union(*(self.dele[i] for i in acts)))


class _Encoder:
    """Builds the clauses of each transition step incrementally."""

    def __init__(self, task: Task) -> None:
        self.task = task
        self.index = {f: i for i, f in enumerate(task.facts)}
        self.layers = _Layers(task, self.index)
        self.pool = IDPool()
        self.n_clauses = 0
        self.unsat_from: int | None = None  # every horizon > this step is UNSAT
        n = len(task.facts)
        self.adders: list[list[int]] = [[] for _ in range(n)]
        self.deleters: list[list[int]] = [[] for _ in range(n)]
        for i, (adds, dels) in enumerate(zip(self.layers.add, self.layers.dele)):
            for f in adds:
                self.adders[f].append(i)
            for f in dels:
                self.deleters[f].append(i)

    def fact(self, f: int, t: int) -> Lit:
        tr, fa = self.layers.facts_at(t)
        if f in tr and f in fa:
            return self.pool.id(("f", f, t))
        return f in tr

    def act(self, a: int, t: int) -> int:
        return self.pool.id(("a", a, t))

    def goal_assumptions(self, T: int) -> list[int] | None:
        """Goal literals at ``T``; ``None`` if some goal literal is constantly false."""
        lits: list[int] = []
        goals = [(self.index[g], True) for g in self.task.goal_pos] + [(self.index[g], False) for g in self.task.goal_neg]
        for f, positive in goals:
            lit = _neg(self.fact(f, T)) if not positive else self.fact(f, T)
            if lit is False:
                return None
            if lit is not True:
                lits.append(lit)
        return lits

    def step(self, t: int) -> list[list[int]]:
        """Clauses linking step ``t`` to ``t + 1``."""
        L = self.layers
        acts = L.actions_at(t)
        out: list[list[int]] = []

        def clause(*lits: Lit) -> None:
            c: list[int] = []
            for lit in lits:
                if lit is True:
                    return
                if lit is not False:
                    c.append(lit)
            if not c:
                self.unsat_from = t if self.unsat_from is None else min(self.unsat_from, t)
            out.append(c)

        avars = {a: self.act(a, t) for a in acts}
        for a, v in avars.items():
            for p in L.pre[a]:
                clause(-v, self.fact(p, t))
            for p in L.neg[a]:
                clause(-v, _neg(self.fact(p, t)))
            for f in L.add[a]:
                clause(-v, self.fact(f, t + 1))
            for f in L.dele[a]:
                clause(-v, _neg(self.fact(f, t + 1)))
        for f in range(len(self.task.facts)):
            now, nxt = self.fact(f, t), self.fact(f, t + 1)
            if now is not False and nxt is not True:
                clause(_neg(now), nxt, *(avars[a] for a in self.deleters[f] if a in avars))
            if now is not True and nxt is not False:
                clause(now, _neg(nxt), *(avars[a] for a in self.adders[f] if a in avars))
        if avars:
            card = CardEnc.equals(lits=list(avars.values()), bound=1, vpool=self.pool, encoding=EncType.seqcounter)
            out.extend(card.clauses)
        else:
            clause()  # no action can occur at step t
        out = [c for c in out if c]
        self.n_clauses += len(out)
        return out


def _neg(lit: Lit) -> Lit:
    return (not lit) if isinstance(lit, bool) else -lit


def _solve(solver: Solver, assumptions: list[int], deadline: float | None) -> bool | None:
    """Solve under assumptions; ``None`` if the deadline passes first."""
    if deadline is None:
        return solver.solve(assumptions=assumptions)
    budget = 1000
    while True:
        if time.perf_counter() >= deadline:
            return None
        solver.conf_budget(budget)
        result = solver.solve_limited(assumptions=assumptions)
        if result is not None:
            return result
        budget = min(2 * budget, 200_000)


def satplan(task: Task, t_max: int, solver_name: str = "cd19", time_limit: float | None = None) -> SatPlanResult:
    """Find a shortest plan of length <= ``t_max`` by iterating horizons T = 0..t_max.

    ``time_limit`` (seconds) bounds the whole call. The decoded plan is replayed
    with :func:`validate_plan` and an ``AssertionError`` is raised if it fails.
    """
    if t_max < 0:
        raise ValueError("t_max must be non-negative")
    start = time.perf_counter()
    deadline = None if time_limit is None else start + time_limit
    enc = _Encoder(task)
    stats: list[HorizonStats] = []

    def result(status: str, plan: list[str] | None = None) -> SatPlanResult:
        length = None if plan is None else len(plan)
        return SatPlanResult(plan, length, status, stats, time.perf_counter() - start)

    with Solver(name=solver_name) as solver:
        for T in range(t_max + 1):
            if T > 0:
                solver.append_formula(enc.step(T - 1))
            if deadline is not None and time.perf_counter() >= deadline:
                return result("timeout")
            goal = enc.goal_assumptions(T)
            n_vars = enc.pool.top
            n_clauses = enc.n_clauses + (len(goal) if goal else 0)
            if goal is None or (enc.unsat_from is not None and T > enc.unsat_from):
                stats.append(HorizonStats(T, n_vars, n_clauses, 0.0, False))
                continue
            t0 = time.perf_counter()
            sat = _solve(solver, goal, deadline)
            stats.append(HorizonStats(T, n_vars, n_clauses, time.perf_counter() - t0, sat))
            if sat is None:
                return result("timeout")
            if sat:
                plan = _decode(enc, solver.get_model(), T)
                check = validate_plan(task, plan)
                if not check.valid:
                    raise AssertionError(f"SATPlan decoded an invalid plan {plan}: {check.message}")
                return result("solved", plan)
    return result("no_plan_within_bound")


def _decode(enc: _Encoder, model: list[int] | None, T: int) -> list[str]:
    true = {lit for lit in (model or []) if lit > 0}
    plan: list[str] = []
    for t in range(T):
        chosen = [a for a in enc.layers.actions_at(t) if enc.pool.obj2id[("a", a, t)] in true]
        if len(chosen) != 1:
            raise AssertionError(f"SATPlan model has {len(chosen)} actions at step {t}")
        plan.append(enc.task.actions[chosen[0]].name)
    return plan
