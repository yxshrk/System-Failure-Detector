"""Forward state-space search with delete-relaxation heuristics.

States are Python ints used as bitsets over ``task.facts``. ``gbfs`` is complete
on finite state spaces: dead ends are pruned only when the relaxed goal is
unreachable (which is sound), so an empty open list proves the goal is
unreachable from the initial state.
"""

from __future__ import annotations

import heapq
import math
import time
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from .ground import State, Task

Heuristic = Callable[[Task, "State | int"], float]


@dataclass
class SearchResult:
    plan: list[str] | None
    status: str  # "solved" | "unsolvable" | "limit"
    expanded: int
    generated: int
    seconds: float
    evaluated: int = 0
    dead_ends: int = 0
    h_init: float | None = None

    @property
    def length(self) -> int | None:
        return None if self.plan is None else len(self.plan)


class CompiledTask:
    """Bitset view of a :class:`Task` with precomputed masks and relaxation tables."""

    def __init__(self, task: Task) -> None:
        self.task = task
        self.facts = task.facts
        self.index = {f: i for i, f in enumerate(task.facts)}
        idx = self.index
        acts = task.actions
        self.names = [a.name for a in acts]
        self.pre_idx = [tuple(idx[f] for f in a.pre_pos) for a in acts]
        self.add_idx = [tuple(idx[f] for f in a.add) for a in acts]
        self.pre = [_mask(p) for p in self.pre_idx]
        self.neg = [_mask(idx[f] for f in a.pre_neg) for a in acts]
        self.add = [_mask(a) for a in self.add_idx]
        self.keep = [~_mask(idx[f] for f in a.delete) for a in acts]
        self.init = self.encode(task.init)
        self.goal_pos = self.encode(task.goal_pos)
        self.goal_neg = self.encode(task.goal_neg)
        self.goal_idx = tuple(idx[f] for f in sorted(task.goal_pos))

        self.consumers: list[list[int]] = [[] for _ in task.facts]
        for a, pre in enumerate(self.pre_idx):
            for f in pre:
                self.consumers[f].append(a)
        self.free_actions = [a for a, pre in enumerate(self.pre_idx) if not pre]
        # Successor generator: bucket actions by their rarest positive precondition.
        groups: dict[int, list[int]] = {}
        for a, pre in enumerate(self.pre_idx):
            if pre:
                key = min(pre, key=lambda f: len(self.consumers[f]))
                groups.setdefault(key, []).append(a)
        self.groups = [(1 << f, members) for f, members in sorted(groups.items())]

    def encode(self, facts: Iterable[str]) -> int:
        """Bitset of ``facts`` (facts unknown to the task are irrelevant and dropped)."""
        return _mask(self.index[f] for f in facts if f in self.index)

    def decode(self, mask: int) -> State:
        return frozenset(self.facts[i] for i in _bits(mask))

    def is_goal(self, s: int) -> bool:
        return (s & self.goal_pos) == self.goal_pos and not (s & self.goal_neg)

    def successors(self, s: int) -> Iterator[tuple[int, int]]:
        """Yield ``(action_index, successor_state)`` for every applicable action."""
        pre, neg, add, keep = self.pre, self.neg, self.add, self.keep
        for a in self.free_actions:
            if not (s & neg[a]):
                yield a, (s & keep[a]) | add[a]
        for bit, members in self.groups:
            if s & bit:
                for a in members:
                    if (s & pre[a]) == pre[a] and not (s & neg[a]):
                        yield a, (s & keep[a]) | add[a]


def _mask(indices: Iterable[int]) -> int:
    m = 0
    for i in indices:
        m |= 1 << i
    return m


def _bits(mask: int) -> Iterator[int]:
    while mask:
        low = mask & -mask
        yield low.bit_length() - 1
        mask ^= low


def compile_task(task: Task) -> CompiledTask:
    """Return the (per-task cached) bitset compilation of ``task``."""
    ct = task._cache.get("compiled")
    if ct is None:
        ct = task._cache["compiled"] = CompiledTask(task)
    return ct


# ---------------------------------------------------------------------------
# Heuristics (delete relaxation; negative preconditions/goals count as satisfied)
# ---------------------------------------------------------------------------

def _relaxed_levels(ct: CompiledTask, s: int) -> tuple[list[float], list[int]]:
    """Layered relaxed planning graph from ``s``, stopping once all goals appear.

    Returns the first level of each fact (``inf`` if unreached) and, for each
    reached non-initial fact, the first achiever found (a min-level achiever).
    """
    n = len(ct.facts)
    level: list[float] = [math.inf] * n
    supporter = [-1] * n
    counter = [len(p) for p in ct.pre_idx]
    frontier = list(_bits(s))
    for f in frontier:
        level[f] = 0
    goals_left = sum(1 for g in ct.goal_idx if level[g] != 0)
    ready = list(ct.free_actions)
    depth = 0
    while goals_left:
        for f in frontier:
            for a in ct.consumers[f]:
                counter[a] -= 1
                if counter[a] == 0:
                    ready.append(a)
        if not ready:
            break
        frontier = []
        for a in ready:
            for f in ct.add_idx[a]:
                if level[f] == math.inf:
                    level[f] = depth + 1
                    supporter[f] = a
                    frontier.append(f)
        ready = []
        depth += 1
        goals_left = sum(1 for g in ct.goal_idx if level[g] == math.inf)
    return level, supporter


def _h_max(ct: CompiledTask, s: int) -> float:
    level, _ = _relaxed_levels(ct, s)
    return max((level[g] for g in ct.goal_idx), default=0)


def _h_ff(ct: CompiledTask, s: int) -> float:
    level, supporter = _relaxed_levels(ct, s)
    if any(level[g] == math.inf for g in ct.goal_idx):
        return math.inf
    plan: set[int] = set()
    marked: set[int] = set()
    stack = [g for g in ct.goal_idx if level[g] > 0]
    while stack:
        f = stack.pop()
        if f in marked:
            continue
        marked.add(f)
        a = supporter[f]
        if a in plan:
            continue
        plan.add(a)
        stack.extend(p for p in ct.pre_idx[a] if level[p] > 0 and p not in marked)
    return len(plan)


def _h_add(ct: CompiledTask, s: int) -> float:
    n = len(ct.facts)
    cost: list[float] = [math.inf] * n
    heap: list[tuple[float, int]] = []
    for f in _bits(s):
        cost[f] = 0
        heap.append((0, f))
    for a in ct.free_actions:
        for f in ct.add_idx[a]:
            if 1 < cost[f]:
                cost[f] = 1
                heap.append((1, f))
    heapq.heapify(heap)
    counter = [len(p) for p in ct.pre_idx]
    acc = [0.0] * len(counter)
    goals = set(ct.goal_idx)
    done: set[int] = set()
    while heap and len(done) < len(goals):
        c, f = heapq.heappop(heap)
        if c > cost[f]:
            continue
        if f in goals:
            done.add(f)
        for a in ct.consumers[f]:
            acc[a] += c
            counter[a] -= 1
            if counter[a] == 0:
                ac = acc[a] + 1
                for g in ct.add_idx[a]:
                    if ac < cost[g]:
                        cost[g] = ac
                        heapq.heappush(heap, (ac, g))
    return sum(cost[g] for g in ct.goal_idx)


def _h_zero(ct: CompiledTask, s: int) -> float:
    return 0


def _prepare(task: Task, state: State | int) -> tuple[CompiledTask, int]:
    ct = compile_task(task)
    return ct, state if isinstance(state, int) else ct.encode(state)


def h_ff(task: Task, state: State | int) -> float:
    """FF heuristic (Hoffmann & Nebel 2001): size of a relaxed plan; inf if relaxed-unreachable."""
    return _h_ff(*_prepare(task, state))


def h_add(task: Task, state: State | int) -> float:
    """Additive heuristic: sum of relaxed goal costs (inadmissible)."""
    return _h_add(*_prepare(task, state))


def h_max(task: Task, state: State | int) -> float:
    """Max heuristic: relaxed planning-graph level of the goal (admissible and consistent)."""
    return _h_max(*_prepare(task, state))


def h_zero(task: Task, state: State | int) -> float:
    """Blind heuristic (always 0)."""
    return 0


_FAST: dict[Callable[..., float], Callable[[CompiledTask, int], float]] = {
    h_ff: _h_ff, h_add: _h_add, h_max: _h_max, h_zero: _h_zero,
}


def _evaluator(task: Task, ct: CompiledTask, h: Heuristic) -> Callable[[int], float]:
    """Built-in heuristics run on bitsets; custom ones receive a frozenset of facts."""
    fast = _FAST.get(h)
    if fast is not None:
        return lambda s: fast(ct, s)
    return lambda s: h(task, ct.decode(s))


# ---------------------------------------------------------------------------
# Search algorithms
# ---------------------------------------------------------------------------

def _extract(ct: CompiledTask, parent: dict[int, tuple[int, int] | None], s: int) -> list[str]:
    plan: list[str] = []
    while (link := parent[s]) is not None:
        s, a = link
        plan.append(ct.names[a])
    plan.reverse()
    return plan


def gbfs(task: Task, h: Heuristic = h_ff, max_expansions: int = 1_000_000,
         time_limit: float | None = None) -> SearchResult:
    """Greedy best-first search on h (ties broken by lower g) with duplicate detection.

    Returns ``"unsolvable"`` when the open list empties (goal unreachable),
    ``"limit"`` when ``max_expansions`` or ``time_limit`` is hit.
    """
    start = time.perf_counter()
    ct = compile_task(task)
    evaluate = _evaluator(task, ct, h)
    expanded = generated = dead = 0
    s0 = ct.init
    h0 = evaluate(s0)
    evaluated = 1

    def result(status: str, plan: list[str] | None = None) -> SearchResult:
        return SearchResult(plan, status, expanded, generated, time.perf_counter() - start, evaluated, dead, h0)

    parent: dict[int, tuple[int, int] | None] = {s0: None}
    if ct.is_goal(s0):
        return result("solved", [])
    if h0 == math.inf:
        dead = 1
        return result("unsolvable")
    tie = 0
    open_list: list[tuple[float, int, int, int]] = [(h0, 0, tie, s0)]
    while open_list:
        if expanded >= max_expansions or (time_limit is not None and time.perf_counter() - start > time_limit):
            return result("limit")
        _, g, _, s = heapq.heappop(open_list)
        expanded += 1
        for a, t in ct.successors(s):
            generated += 1
            if t in parent:
                continue
            parent[t] = (s, a)
            if ct.is_goal(t):
                return result("solved", _extract(ct, parent, t))
            ht = evaluate(t)
            evaluated += 1
            if ht == math.inf:
                dead += 1
                continue
            tie += 1
            heapq.heappush(open_list, (ht, g + 1, tie, t))
    return result("unsolvable")


def bfs(task: Task, max_expansions: int = 1_000_000, time_limit: float | None = None) -> SearchResult:
    """Blind breadth-first search: a shortest plan, or ``"unsolvable"`` if none exists."""
    start = time.perf_counter()
    ct = compile_task(task)
    expanded = generated = 0

    def result(status: str, plan: list[str] | None = None) -> SearchResult:
        return SearchResult(plan, status, expanded, generated, time.perf_counter() - start)

    s0 = ct.init
    parent: dict[int, tuple[int, int] | None] = {s0: None}
    if ct.is_goal(s0):
        return result("solved", [])
    queue = deque([s0])
    while queue:
        if expanded >= max_expansions or (time_limit is not None and time.perf_counter() - start > time_limit):
            return result("limit")
        s = queue.popleft()
        expanded += 1
        for a, t in ct.successors(s):
            generated += 1
            if t in parent:
                continue
            parent[t] = (s, a)
            if ct.is_goal(t):
                return result("solved", _extract(ct, parent, t))
            queue.append(t)
    return result("unsolvable")


def astar(task: Task, h: Heuristic = h_max, max_expansions: int = 1_000_000,
          time_limit: float | None = None) -> SearchResult:
    """A* search; optimal (shortest) plans with an admissible h such as ``h_max``."""
    start = time.perf_counter()
    ct = compile_task(task)
    evaluate = _evaluator(task, ct, h)
    expanded = generated = dead = 0
    s0 = ct.init
    h0 = evaluate(s0)
    evaluated = 1

    def result(status: str, plan: list[str] | None = None) -> SearchResult:
        return SearchResult(plan, status, expanded, generated, time.perf_counter() - start, evaluated, dead, h0)

    if h0 == math.inf:
        return result("solved", []) if ct.is_goal(s0) else result("unsolvable")
    parent: dict[int, tuple[int, int] | None] = {s0: None}
    best_g = {s0: 0}
    h_cache = {s0: h0}
    closed: set[int] = set()
    tie = 0
    open_list: list[tuple[float, float, int, int]] = [(h0, h0, tie, s0)]
    while open_list:
        if expanded >= max_expansions or (time_limit is not None and time.perf_counter() - start > time_limit):
            return result("limit")
        _, _, _, s = heapq.heappop(open_list)
        if s in closed:
            continue
        if ct.is_goal(s):
            return result("solved", _extract(ct, parent, s))
        closed.add(s)
        expanded += 1
        g = best_g[s]
        for a, t in ct.successors(s):
            generated += 1
            if t in closed or best_g.get(t, math.inf) <= g + 1:
                continue
            ht = h_cache.get(t)
            if ht is None:
                ht = h_cache[t] = evaluate(t)
                evaluated += 1
                if ht == math.inf:
                    dead += 1
            if ht == math.inf:
                continue
            best_g[t] = g + 1
            parent[t] = (s, a)
            tie += 1
            heapq.heappush(open_list, (g + 1 + ht, ht, tie, t))
    return result("unsolvable")
