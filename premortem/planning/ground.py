"""Grounding a lifted PDDL task into a propositional STRIPS task.

Facts are strings without parentheses (``"holds c1 l1"``); ground action names
are the lower-case action name followed by its arguments (``"pay c1 o1"``).
Grounding joins action preconditions against the facts reachable in the
delete relaxation, so static predicates prune bindings as soon as they are
bound and only relaxed-reachable actions are ever instantiated.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from .pddl import OBJECT, ActionSchema, Atom, Domain, Problem

State = frozenset[str]


@dataclass(frozen=True)
class GroundAction:
    """A ground STRIPS action. ``delete`` never overlaps ``add`` (add wins)."""

    name: str
    pre_pos: frozenset[str]
    pre_neg: frozenset[str]
    add: frozenset[str]
    delete: frozenset[str]

    def __str__(self) -> str:
        return f"({self.name})"


@dataclass
class Task:
    """A ground STRIPS task under the closed-world assumption.

    ``domain``/``problem`` are kept (when available) so that plan validation
    can explain type and arity errors in terms of the original action schemas.
    """

    name: str
    facts: tuple[str, ...]
    init: State
    goal_pos: frozenset[str]
    goal_neg: frozenset[str]
    actions: list[GroundAction]
    domain: Domain | None = field(default=None, repr=False, compare=False)
    problem: Problem | None = field(default=None, repr=False, compare=False)
    _cache: dict[str, Any] = field(default_factory=dict, init=False, repr=False, compare=False)

    def action(self, name: str) -> GroundAction | None:
        """Look up a ground action by its name (e.g. ``"pay c1 o1"``)."""
        table = self._cache.get("by_name")
        if table is None:
            table = self._cache["by_name"] = {a.name: a for a in self.actions}
        return table.get(name)

    def goal_satisfied(self, state: State) -> bool:
        return self.goal_pos <= state and self.goal_neg.isdisjoint(state)

    def unsatisfied_goals(self, state: State) -> list[str]:
        """Goal literals false in ``state``, formatted like ``(p a)`` / ``(not (p a))``."""
        missing = [f"({g})" for g in sorted(self.goal_pos - state)]
        return missing + [f"(not ({g}))" for g in sorted(self.goal_neg & state)]

    def goal_str(self) -> str:
        lits = [f"({g})" for g in sorted(self.goal_pos)] + [f"(not ({g}))" for g in sorted(self.goal_neg)]
        return lits[0] if len(lits) == 1 else "(and " + " ".join(lits) + ")"


def applicable(state: State, action: GroundAction) -> bool:
    """True iff all positive preconditions hold and no negative one does."""
    return action.pre_pos <= state and action.pre_neg.isdisjoint(state)


def apply(state: State, action: GroundAction) -> State:
    """Successor state: apply deletes, then adds."""
    return (state - action.delete) | action.add


def _fact(pred: str, args: tuple[str, ...]) -> str:
    return " ".join((pred, *args))


def _substitute(atom: Atom, binding: dict[str, str]) -> tuple[str, ...]:
    return tuple(binding.get(a, a) for a in atom.args)


def instantiate(schema: ActionSchema, args: Iterable[str]) -> GroundAction:
    """Ground ``schema`` with ``args`` (no type or equality checking)."""
    args = tuple(args)
    binding = {var: obj for (var, _), obj in zip(schema.parameters, args)}

    def facts(atoms: tuple[Atom, ...]) -> frozenset[str]:
        return frozenset(_fact(a.predicate, _substitute(a, binding)) for a in atoms if a.predicate != "=")

    add = facts(schema.add)
    return GroundAction(
        name=" ".join((schema.name, *args)),
        pre_pos=facts(schema.pre_pos),
        pre_neg=facts(schema.pre_neg),
        add=add,
        delete=facts(schema.delete) - add,
    )


def equality_violations(schema: ActionSchema, args: Iterable[str]) -> list[str]:
    """Equality preconditions of ``schema`` that are false for ``args``."""
    binding = {var: obj for (var, _), obj in zip(schema.parameters, tuple(args))}
    bad = []
    for positive, atoms in ((True, schema.pre_pos), (False, schema.pre_neg)):
        for atom in atoms:
            if atom.predicate == "=":
                x, y = _substitute(atom, binding)
                if (x == y) != positive:
                    lit = f"(= {x} {y})"
                    bad.append(lit if positive else f"(not {lit})")
    return bad


class _FactIndex:
    """Reachable facts per predicate, indexed by argument position for joins."""

    def __init__(self) -> None:
        self.by_pred: dict[str, set[tuple[str, ...]]] = {}
        self.by_arg: dict[tuple[str, int, str], list[tuple[str, ...]]] = {}

    def add(self, pred: str, args: tuple[str, ...]) -> bool:
        bucket = self.by_pred.setdefault(pred, set())
        if args in bucket:
            return False
        bucket.add(args)
        for i, a in enumerate(args):
            self.by_arg.setdefault((pred, i, a), []).append(args)
        return True

    def count(self, pred: str) -> int:
        return len(self.by_pred.get(pred, ()))

    def matches(self, pred: str, pattern: tuple[str | None, ...]) -> Iterator[tuple[str, ...]]:
        """Facts of ``pred`` agreeing with the non-``None`` entries of ``pattern``.

        The index must not be modified while the iterator is being consumed.
        """
        bound = [(i, v) for i, v in enumerate(pattern) if v is not None]
        if not bound:
            yield from self.by_pred.get(pred, ())
            return
        smallest = min((self.by_arg.get((pred, i, v), []) for i, v in bound), key=len)
        for args in smallest:
            if all(args[i] == v for i, v in bound):
                yield args


class _SchemaGrounder:
    """Enumerates bindings of one schema consistent with the reachable facts."""

    def __init__(self, schema: ActionSchema, objects_by_type: dict[str, list[str]],
                 fluents: set[str], static_init: set[tuple[str, tuple[str, ...]]]) -> None:
        self.schema = schema
        self.params = [v for v, _ in schema.parameters]
        self.domains = {v: objects_by_type[t] for v, t in schema.parameters}
        self.domain_sets = {v: set(objs) for v, objs in self.domains.items()}
        self.atoms = [a for a in schema.pre_pos if a.predicate != "="]
        self.fluents = fluents
        self.static_init = static_init
        # Constraints checked as soon as all their variables are bound.
        self.constraints: list[tuple[str, Atom]] = (
            [("eq", a) for a in schema.pre_pos if a.predicate == "="]
            + [("neq", a) for a in schema.pre_neg if a.predicate == "="]
            + [("static-neg", a) for a in schema.pre_neg if a.predicate != "=" and a.predicate not in fluents]
        )
        self.trigger_preds = {a.predicate for a in self.atoms}

    def _ok(self, binding: dict[str, str]) -> bool:
        for kind, atom in self.constraints:
            if any(a.startswith("?") and a not in binding for a in atom.args):
                continue
            args = _substitute(atom, binding)
            if kind == "eq" and args[0] != args[1]:
                return False
            if kind == "neq" and args[0] == args[1]:
                return False
            if kind == "static-neg" and (atom.predicate, args) in self.static_init:
                return False
        return True

    def _order(self, index: _FactIndex) -> list[Atom]:
        """Greedy join order: most-bound atoms first, static before fluent, then smallest."""
        remaining = list(self.atoms)
        bound: set[str] = set()
        order: list[Atom] = []
        while remaining:
            def key(a: Atom) -> tuple[int, int, int]:
                n_bound = sum(1 for x in a.args if not x.startswith("?") or x in bound)
                return (-n_bound, a.predicate in self.fluents, index.count(a.predicate))
            best = min(remaining, key=key)
            remaining.remove(best)
            order.append(best)
            bound.update(x for x in best.args if x.startswith("?"))
        return order

    def bindings(self, index: _FactIndex) -> Iterator[tuple[str, ...]]:
        order = self._order(index)

        def join(i: int, binding: dict[str, str]) -> Iterator[dict[str, str]]:
            if i == len(order):
                yield from free(binding, [p for p in self.params if p not in binding])
                return
            atom = order[i]
            pattern = tuple(
                (binding.get(x) if x.startswith("?") else x) for x in atom.args
            )
            for args in index.matches(atom.predicate, pattern):
                new = dict(binding)
                for var, val in zip(atom.args, args):
                    if not var.startswith("?"):
                        continue
                    if var in new:
                        if new[var] != val:
                            break
                    elif val in self.domain_sets[var]:
                        new[var] = val
                    else:
                        break
                else:
                    if self._ok(new):
                        yield from join(i + 1, new)

        def free(binding: dict[str, str], todo: list[str]) -> Iterator[dict[str, str]]:
            if not todo:
                yield binding
                return
            var, rest = todo[0], todo[1:]
            for obj in self.domains[var]:
                new = {**binding, var: obj}
                if self._ok(new):
                    yield from free(new, rest)

        for binding in join(0, {}):
            yield tuple(binding[p] for p in self.params)


def ground(domain: Domain, problem: Problem) -> Task:
    """Ground ``problem`` into a :class:`Task`, keeping only relaxed-reachable actions."""
    objects = {**domain.constants, **problem.objects}
    objects_by_type = {
        t: sorted(o for o, ot in objects.items() if domain.is_subtype(ot, t))
        for t in [OBJECT, *domain.types]
    }
    fluents = {a.predicate for s in domain.actions.values() for a in (*s.add, *s.delete)}
    static_init = {(a.predicate, a.args) for a in problem.init if a.predicate not in fluents}

    index = _FactIndex()
    for atom in problem.init:
        index.add(atom.predicate, atom.args)

    grounders = [_SchemaGrounder(s, objects_by_type, fluents, static_init) for s in domain.actions.values()]
    last_seen: dict[str, tuple[int, ...]] = {}
    instances: dict[tuple[str, tuple[str, ...]], GroundAction] = {}
    changed = True
    while changed:
        changed = False
        for g in grounders:
            snapshot = tuple(index.count(p) for p in sorted(g.trigger_preds))
            if last_seen.get(g.schema.name) == snapshot:
                continue
            last_seen[g.schema.name] = snapshot
            new_facts: list[tuple[str, tuple[str, ...]]] = []
            for args in g.bindings(index):
                key = (g.schema.name, args)
                if key in instances:
                    continue
                action = instantiate(g.schema, args)
                if not action.pre_pos.isdisjoint(action.pre_neg):
                    continue  # contradictory preconditions: never applicable
                instances[key] = action
                binding = dict(zip(g.params, args))
                new_facts.extend((a.predicate, _substitute(a, binding)) for a in g.schema.add)
            for pred, args in new_facts:
                if index.add(pred, args):
                    changed = True

    actions = sorted(instances.values(), key=lambda a: a.name)
    init = frozenset(a.fact for a in problem.init)
    goal_pos = frozenset(a.fact for a in problem.goal_pos)
    goal_neg = frozenset(a.fact for a in problem.goal_neg)
    facts: set[str] = set(init) | goal_pos | goal_neg
    for a in actions:
        facts.update(itertools.chain(a.pre_pos, a.pre_neg, a.add, a.delete))
    return Task(
        name=problem.name,
        facts=tuple(sorted(facts)),
        init=init,
        goal_pos=goal_pos,
        goal_neg=goal_neg,
        actions=actions,
        domain=domain,
        problem=problem,
    )
