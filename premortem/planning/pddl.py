"""Parser and pretty-printer for a STRIPS subset of PDDL.

Supported requirements: ``:strips``, ``:typing`` (type hierarchies),
``:negative-preconditions`` and ``:equality``. Every syntax or validation
problem raises :class:`PDDLError` with a message precise enough to be fed back
to whoever (or whatever) wrote the file, e.g.
``predicate 'holds' expects 2 arguments, got 1 in (holds c1)``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Union

OBJECT = "object"
SUPPORTED_REQUIREMENTS = (":strips", ":typing", ":negative-preconditions", ":equality")
_UNSUPPORTED_CONSTRUCTS = {
    "or", "imply", "forall", "exists", "when", "either",
    "increase", "decrease", "assign", "scale-up", "scale-down",
}
_TOKEN = re.compile(r"[()]|[^\s()]+")

SExpr = Union[str, list["SExpr"]]
TypedList = tuple[tuple[str, str], ...]


class PDDLError(Exception):
    """A syntax or validation error in a PDDL domain, problem or plan."""


@dataclass(frozen=True)
class Atom:
    """A (possibly lifted) atom such as ``(holds ?c ?l)`` or ``(holds c1 l1)``."""

    predicate: str
    args: tuple[str, ...] = ()

    def __str__(self) -> str:
        return f"({self.fact})"

    @property
    def fact(self) -> str:
        """The atom without parentheses, e.g. ``"holds c1 l1"``."""
        return " ".join((self.predicate, *self.args))


@dataclass(frozen=True)
class ActionSchema:
    """A lifted STRIPS operator. Equality tests use the predicate ``=``."""

    name: str
    parameters: TypedList = ()
    pre_pos: tuple[Atom, ...] = ()
    pre_neg: tuple[Atom, ...] = ()
    add: tuple[Atom, ...] = ()
    delete: tuple[Atom, ...] = ()

    def signature(self) -> str:
        """Human-readable signature, e.g. ``(pay ?c - client ?o - order)``."""
        return "(" + " ".join([self.name, *(f"{v} - {t}" for v, t in self.parameters)]) + ")"


@dataclass
class Domain:
    """A parsed domain. ``types`` maps each declared type to its parent type."""

    name: str
    requirements: tuple[str, ...] = ()
    types: dict[str, str] = field(default_factory=dict)
    constants: dict[str, str] = field(default_factory=dict)
    predicates: dict[str, TypedList] = field(default_factory=dict)
    actions: dict[str, ActionSchema] = field(default_factory=dict)

    def is_subtype(self, t: str, ancestor: str) -> bool:
        """True iff type ``t`` equals ``ancestor`` or inherits from it."""
        for _ in range(len(self.types) + 2):
            if t == ancestor:
                return True
            if t == OBJECT:
                return False
            t = self.types.get(t, OBJECT)
        raise PDDLError(f"cyclic type hierarchy involving '{t}'")

    def known_types(self) -> list[str]:
        return [OBJECT, *self.types]

    def predicate_signature(self, name: str) -> str:
        params = self.predicates[name]
        return "(" + " ".join([name, *(f"{v} - {t}" for v, t in params)]) + ")"


@dataclass
class Problem:
    """A parsed problem. ``objects`` maps object names to their types."""

    name: str
    domain_name: str
    objects: dict[str, str] = field(default_factory=dict)
    init: frozenset[Atom] = frozenset()
    goal_pos: tuple[Atom, ...] = ()
    goal_neg: tuple[Atom, ...] = ()


# ---------------------------------------------------------------------------
# S-expressions
# ---------------------------------------------------------------------------

def _parse_sexpr(text: str, what: str) -> list[SExpr]:
    """Tokenize (lower-casing, stripping ``;`` comments) and build the tree."""
    stack: list[list[SExpr]] = [[]]
    opened: list[int] = []
    for lineno, line in enumerate(text.lower().splitlines(), 1):
        for tok in _TOKEN.findall(line.split(";", 1)[0]):
            if tok == "(":
                stack.append([])
                opened.append(lineno)
            elif tok == ")":
                if len(stack) == 1:
                    raise PDDLError(f"unexpected ')' on line {lineno} of the {what} (too many closing parentheses)")
                done = stack.pop()
                opened.pop()
                stack[-1].append(done)
            else:
                stack[-1].append(tok)
    if len(stack) > 1:
        missing = len(stack) - 1
        raise PDDLError(
            f"unbalanced parentheses in the {what}: {missing} '(' never closed "
            f"(innermost unclosed '(' opened on line {opened[-1]})"
        )
    top = stack[0]
    if not top:
        raise PDDLError(f"the {what} is empty")
    if len(top) > 1 or not isinstance(top[0], list):
        extra = _fmt(top[1]) if len(top) > 1 else _fmt(top[0])
        raise PDDLError(f"the {what} must be a single (define ...) form; unexpected {_short(extra)}")
    return top[0]


def _fmt(x: SExpr) -> str:
    if isinstance(x, str):
        return x
    return "(" + " ".join(_fmt(y) for y in x) + ")"


def _short(s: str, limit: int = 80) -> str:
    return s if len(s) <= limit else s[: limit - 3] + "..."


def _names(items: object, limit: int = 30) -> str:
    items = sorted(items)  # type: ignore[arg-type]
    if not items:
        return "none"
    shown = ", ".join(items[:limit])
    return shown + (f", ... ({len(items) - limit} more)" if len(items) > limit else "")


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _split_define(tree: list[SExpr], kind: str) -> tuple[str, list[list[SExpr]]]:
    """Check ``(define (KIND NAME) section...)`` and return ``(NAME, sections)``."""
    if not tree or tree[0] != "define":
        raise PDDLError(f"expected (define ({kind} NAME) ...) but got {_short(_fmt(tree))}")
    if len(tree) < 2 or not isinstance(tree[1], list) or len(tree[1]) != 2 or tree[1][0] != kind \
            or not isinstance(tree[1][1], str):
        got = _fmt(tree[1]) if len(tree) > 1 else "nothing"
        raise PDDLError(f"expected ({kind} NAME) after define but got {_short(got)}")
    sections: list[list[SExpr]] = []
    for sec in tree[2:]:
        if not isinstance(sec, list) or not sec or not isinstance(sec[0], str) or not sec[0].startswith(":"):
            raise PDDLError(f"expected a section like (:keyword ...) in the {kind} but got {_short(_fmt(sec))}")
        sections.append(sec)
    return tree[1][1], sections


def _typed_list(items: list[SExpr], ctx: str, *, variables: bool) -> list[tuple[str, str]]:
    """Parse ``a b - t c`` into ``[(a, t), (b, t), (c, object)]``."""
    result: list[tuple[str, str]] = []
    pending: list[str] = []
    i = 0
    while i < len(items):
        tok = items[i]
        if isinstance(tok, list):
            raise PDDLError(f"unexpected {_short(_fmt(tok))} in {ctx}")
        if tok == "-":
            if not pending:
                raise PDDLError(f"'-' without preceding names in {ctx}")
            if i + 1 >= len(items):
                raise PDDLError(f"missing type after '-' in {ctx}")
            t = items[i + 1]
            if isinstance(t, list):
                raise PDDLError(f"unsupported type {_fmt(t)} in {ctx}: (either ...) types are not supported")
            result.extend((n, t) for n in pending)
            pending = []
            i += 2
            continue
        if variables and not tok.startswith("?"):
            raise PDDLError(f"expected a variable like ?x but got '{tok}' in {ctx}")
        if not variables and (tok.startswith("?") or tok.startswith(":")):
            raise PDDLError(f"expected a name but got '{tok}' in {ctx}")
        pending.append(tok)
        i += 1
    result.extend((n, OBJECT) for n in pending)
    return result


def _check_requirements(items: list[SExpr], where: str) -> tuple[str, ...]:
    reqs: list[str] = []
    for r in items:
        if not isinstance(r, str) or r not in SUPPORTED_REQUIREMENTS:
            raise PDDLError(
                f"unsupported requirement '{_fmt(r)}' in {where} (supported: {', '.join(SUPPORTED_REQUIREMENTS)})"
            )
        if r not in reqs:
            reqs.append(r)
    return tuple(reqs)


def _literals(node: SExpr, ctx: str) -> list[tuple[bool, list[SExpr]]]:
    """Flatten a conjunction into ``(positive, atom-sexpr)`` pairs."""
    if node == []:
        return []
    if not isinstance(node, list):
        raise PDDLError(f"expected a parenthesised formula in {ctx} but got '{node}'")
    head = node[0]
    if not isinstance(head, str):
        raise PDDLError(f"malformed formula {_short(_fmt(node))} in {ctx}")
    if head == "and":
        out: list[tuple[bool, list[SExpr]]] = []
        for sub in node[1:]:
            out.extend(_literals(sub, ctx))
        return out
    if head == "not":
        if len(node) != 2 or not isinstance(node[1], list) or not node[1]:
            raise PDDLError(f"malformed negation {_short(_fmt(node))} in {ctx}: expected (not (predicate ...))")
        inner = node[1]
        if inner[0] in ("and", "not") or inner[0] in _UNSUPPORTED_CONSTRUCTS:
            raise PDDLError(f"unsupported formula {_short(_fmt(node))} in {ctx}: only atoms can be negated")
        return [(False, inner)]
    if head in _UNSUPPORTED_CONSTRUCTS:
        raise PDDLError(
            f"unsupported construct '{head}' in {ctx}: {_short(_fmt(node))} (only and, not and atoms are supported)"
        )
    return [(True, node)]


def _atom_parts(node: list[SExpr], ctx: str) -> tuple[str, list[str]]:
    for x in node:
        if not isinstance(x, str):
            raise PDDLError(f"malformed atom {_short(_fmt(node))} in {ctx}: arguments must be names or variables")
    pred, args = node[0], node[1:]
    assert isinstance(pred, str)
    return pred, [a for a in args if isinstance(a, str)]


def _check_arity(domain: Domain, pred: str, args: list[str], node: list[SExpr], ctx: str) -> None:
    if pred not in domain.predicates:
        raise PDDLError(f"unknown predicate '{pred}' in {ctx} (known: {_names(domain.predicates)})")
    expected = len(domain.predicates[pred])
    if len(args) != expected:
        raise PDDLError(
            f"predicate '{pred}' expects {_plural(expected, 'argument')}, got {len(args)} in {_fmt(node)} "
            f"(in {ctx}); declared as {domain.predicate_signature(pred)}"
        )


# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------

def parse_domain(text: str) -> Domain:
    """Parse and validate a PDDL domain."""
    name, sections = _split_define(_parse_sexpr(text, "domain"), "domain")
    single: dict[str, list[SExpr]] = {}
    action_nodes: list[list[SExpr]] = []
    for sec in sections:
        key = sec[0]
        assert isinstance(key, str)
        if key == ":action":
            action_nodes.append(sec)
        elif key in (":requirements", ":types", ":constants", ":predicates"):
            if key in single:
                raise PDDLError(f"duplicate {key} section in domain")
            single[key] = sec[1:]
        else:
            raise PDDLError(
                f"unsupported domain section '{key}' (supported: :requirements, :types, :constants, :predicates, :action)"
            )

    dom = Domain(name=name, requirements=_check_requirements(single.get(":requirements", []), "domain"))
    _parse_types(dom, single.get(":types", []))

    for cname, ctype in _typed_list(single.get(":constants", []), ":constants", variables=False):
        if ctype not in dom.known_types():
            raise PDDLError(f"unknown type '{ctype}' for constant '{cname}' (known types: {_names(dom.known_types())})")
        if cname in dom.constants and dom.constants[cname] != ctype:
            raise PDDLError(f"constant '{cname}' declared twice (types {dom.constants[cname]} and {ctype})")
        dom.constants[cname] = ctype

    for pnode in single.get(":predicates", []):
        if not isinstance(pnode, list) or not pnode or not isinstance(pnode[0], str) \
                or pnode[0].startswith(("?", ":", "-")) or pnode[0] in ("=", "and", "not"):
            raise PDDLError(f"malformed predicate declaration {_short(_fmt(pnode))} in :predicates")
        pname = pnode[0]
        ctx = f"declaration of predicate '{pname}'"
        params = _typed_list(pnode[1:], ctx, variables=True)
        _check_params(dom, params, ctx)
        if pname in dom.predicates:
            raise PDDLError(f"predicate '{pname}' declared twice in :predicates")
        dom.predicates[pname] = tuple(params)

    for anode in action_nodes:
        schema = _parse_action(anode, dom)
        if schema.name in dom.actions:
            raise PDDLError(f"action '{schema.name}' defined twice")
        dom.actions[schema.name] = schema
    return dom


def _parse_types(dom: Domain, items: list[SExpr]) -> None:
    for tname, parent in _typed_list(items, ":types", variables=False):
        if tname == OBJECT:
            if parent != OBJECT:
                raise PDDLError("the built-in type 'object' cannot have a parent type")
            continue
        if tname in dom.types and dom.types[tname] != parent:
            raise PDDLError(f"type '{tname}' declared twice (parents {dom.types[tname]} and {parent})")
        dom.types[tname] = parent
    for parent in list(dom.types.values()):
        if parent != OBJECT and parent not in dom.types:
            dom.types[parent] = OBJECT  # parents are implicitly declared
    for t in dom.types:
        seen = {t}
        cur = dom.types[t]
        while cur != OBJECT:
            if cur in seen:
                raise PDDLError(f"cyclic type hierarchy involving '{t}'")
            seen.add(cur)
            cur = dom.types[cur]


def _check_params(dom: Domain, params: list[tuple[str, str]], ctx: str) -> None:
    seen: set[str] = set()
    for var, vtype in params:
        if vtype not in dom.known_types():
            raise PDDLError(f"unknown type '{vtype}' for {var} in {ctx} (known types: {_names(dom.known_types())})")
        if var in seen:
            raise PDDLError(f"duplicate parameter {var} in {ctx}")
        seen.add(var)


def _parse_action(node: list[SExpr], dom: Domain) -> ActionSchema:
    if len(node) < 2 or not isinstance(node[1], str) or node[1].startswith((":", "?")):
        raise PDDLError(f"action without a name: {_short(_fmt(node))}")
    name = node[1]
    fields: dict[str, SExpr] = {}
    rest = node[2:]
    i = 0
    while i < len(rest):
        key = rest[i]
        if key not in (":parameters", ":precondition", ":effect"):
            raise PDDLError(
                f"unexpected {_short(_fmt(key))} in action {name} (expected :parameters, :precondition or :effect)"
            )
        assert isinstance(key, str)
        if key in fields:
            raise PDDLError(f"duplicate {key} in action {name}")
        if i + 1 >= len(rest):
            raise PDDLError(f"missing value after {key} in action {name}")
        fields[key] = rest[i + 1]
        i += 2

    raw_params = fields.get(":parameters", [])
    if not isinstance(raw_params, list):
        raise PDDLError(f":parameters of action {name} must be a list like (?x - type), got '{raw_params}'")
    params = _typed_list(raw_params, f"parameters of action {name}", variables=True)
    _check_params(dom, params, f"action {name}")
    scope = dict(params)

    pre_pos: list[Atom] = []
    pre_neg: list[Atom] = []
    ctx = f"precondition of action {name}"
    for positive, anode in _literals(fields.get(":precondition", []), ctx):
        atom = _lifted_atom(anode, dom, scope, ctx, allow_equality=True)
        if not positive and atom.predicate != "=" and ":negative-preconditions" not in dom.requirements:
            raise PDDLError(
                f"negative precondition (not {atom}) in action {name} requires :negative-preconditions "
                "in the domain's :requirements"
            )
        (pre_pos if positive else pre_neg).append(atom)

    add: list[Atom] = []
    delete: list[Atom] = []
    ctx = f"effect of action {name}"
    for positive, anode in _literals(fields.get(":effect", []), ctx):
        atom = _lifted_atom(anode, dom, scope, ctx, allow_equality=False)
        (add if positive else delete).append(atom)

    return ActionSchema(name, tuple(params), tuple(pre_pos), tuple(pre_neg), tuple(add), tuple(delete))


def _lifted_atom(node: list[SExpr], dom: Domain, scope: dict[str, str], ctx: str, *, allow_equality: bool) -> Atom:
    pred, args = _atom_parts(node, ctx)
    if pred == "=":
        if not allow_equality:
            raise PDDLError(f"equality {_fmt(node)} is not allowed in {ctx}")
        if ":equality" not in dom.requirements:
            raise PDDLError(f"equality {_fmt(node)} in {ctx} requires :equality in the domain's :requirements")
        if len(args) != 2:
            raise PDDLError(f"equality expects 2 arguments, got {len(args)} in {_fmt(node)} ({ctx})")
        slots: list[tuple[str, str]] = [("?a", OBJECT), ("?b", OBJECT)]
    else:
        _check_arity(dom, pred, args, node, ctx)
        slots = list(dom.predicates[pred])
    for arg, (slot, slot_type) in zip(args, slots):
        if arg.startswith("?"):
            if arg not in scope:
                raise PDDLError(
                    f"unknown variable '{arg}' in {_fmt(node)} ({ctx}); parameters are: {_names(scope) if scope else 'none'}"
                )
            kind, arg_type = "variable", scope[arg]
        else:
            if arg not in dom.constants:
                raise PDDLError(
                    f"unknown constant '{arg}' in {_fmt(node)} ({ctx}); actions may only use parameters "
                    f"or declared :constants (constants: {_names(dom.constants)})"
                )
            kind, arg_type = "constant", dom.constants[arg]
        if not (dom.is_subtype(arg_type, slot_type) or dom.is_subtype(slot_type, arg_type)):
            raise PDDLError(
                f"{kind} {arg} has type {arg_type} but parameter {slot} of predicate {pred} needs {slot_type} "
                f"in {_fmt(node)} ({ctx})"
            )
    return Atom(pred, tuple(args))


# ---------------------------------------------------------------------------
# Problem
# ---------------------------------------------------------------------------

def parse_problem(text: str, domain: Domain) -> Problem:
    """Parse a PDDL problem and validate it against ``domain``."""
    name, sections = _split_define(_parse_sexpr(text, "problem"), "problem")
    single: dict[str, list[SExpr]] = {}
    allowed = (":domain", ":requirements", ":objects", ":init", ":goal")
    for sec in sections:
        key = sec[0]
        assert isinstance(key, str)
        if key not in allowed:
            raise PDDLError(f"unsupported problem section '{key}' (supported: {', '.join(allowed)})")
        if key in single:
            raise PDDLError(f"duplicate {key} section in problem")
        single[key] = sec[1:]

    if ":domain" not in single:
        raise PDDLError("problem is missing the (:domain NAME) section")
    dpart = single[":domain"]
    if len(dpart) != 1 or not isinstance(dpart[0], str):
        raise PDDLError(f"malformed (:domain ...) section: expected (:domain NAME), got {_short(_fmt([':domain', *dpart]))}")
    if dpart[0] != domain.name:
        raise PDDLError(f"problem refers to domain '{dpart[0]}' but the given domain is named '{domain.name}'")
    _check_requirements(single.get(":requirements", []), "problem")

    objects: dict[str, str] = {}
    for oname, otype in _typed_list(single.get(":objects", []), ":objects", variables=False):
        if otype not in domain.known_types():
            raise PDDLError(
                f"unknown type '{otype}' for object '{oname}' in :objects (known types: {_names(domain.known_types())})"
            )
        previous = objects.get(oname, domain.constants.get(oname))
        if previous is not None and previous != otype:
            what = "object" if oname in objects else "domain constant"
            raise PDDLError(f"object '{oname}' declared with type {otype} but it is already a {what} of type {previous}")
        objects[oname] = otype
    universe = {**domain.constants, **objects}

    init: set[Atom] = set()
    for fnode in single.get(":init", []):
        if not isinstance(fnode, list) or not fnode:
            raise PDDLError(f"expected a fact like (predicate obj ...) in :init but got {_short(_fmt(fnode))}")
        if fnode[0] == "not":
            raise PDDLError(
                f"negative literal {_short(_fmt(fnode))} in :init: the initial state is closed-world, "
                "so simply omit facts that are false"
            )
        if fnode[0] == "=" or fnode[0] in _UNSUPPORTED_CONSTRUCTS or fnode[0] == "and":
            raise PDDLError(f"unsupported entry {_short(_fmt(fnode))} in :init: only ground atoms are allowed")
        init.add(_ground_atom(fnode, domain, universe, ":init"))

    if ":goal" not in single:
        raise PDDLError("problem is missing the (:goal ...) section")
    gpart = single[":goal"]
    if len(gpart) > 1:
        raise PDDLError("(:goal ...) must contain a single formula; wrap several goals in (and ...)")
    goal_pos: list[Atom] = []
    goal_neg: list[Atom] = []
    for positive, gnode in _literals(gpart[0] if gpart else [], ":goal"):
        if gnode and gnode[0] == "=":
            raise PDDLError(f"equality {_fmt(gnode)} is not allowed in :goal")
        atom = _ground_atom(gnode, domain, universe, ":goal")
        if not positive and ":negative-preconditions" not in domain.requirements:
            raise PDDLError(
                f"negative goal (not {atom}) requires :negative-preconditions in the domain's :requirements"
            )
        target = goal_pos if positive else goal_neg
        if atom not in target:
            target.append(atom)
    return Problem(name, domain.name, objects, frozenset(init), tuple(goal_pos), tuple(goal_neg))


def _ground_atom(node: list[SExpr], dom: Domain, universe: dict[str, str], ctx: str) -> Atom:
    pred, args = _atom_parts(node, ctx)
    _check_arity(dom, pred, args, node, ctx)
    for arg, (slot, slot_type) in zip(args, dom.predicates[pred]):
        if arg.startswith("?"):
            raise PDDLError(f"variable '{arg}' in {ctx} fact {_fmt(node)}: facts must be ground (use object names)")
        if arg not in universe:
            raise PDDLError(f"unknown object '{arg}' in {ctx} fact {_fmt(node)} (declared objects: {_names(universe)})")
        if not dom.is_subtype(universe[arg], slot_type):
            raise PDDLError(
                f"object '{arg}' has type {universe[arg]} but parameter {slot} of predicate {pred} needs "
                f"{slot_type} in {ctx} fact {_fmt(node)}"
            )
    return Atom(pred, tuple(args))


# ---------------------------------------------------------------------------
# Pretty-printing
# ---------------------------------------------------------------------------

def _typed_str(pairs: list[tuple[str, str]] | TypedList, typed: bool) -> str:
    if not typed:
        return " ".join(n for n, _ in pairs)
    chunks: list[str] = []
    group: list[str] = []
    current: str | None = None
    for n, t in pairs:
        if t != current and group:
            chunks.append(" ".join(group) + f" - {current}")
            group = []
        current = t
        group.append(n)
    if group:
        chunks.append(" ".join(group) + f" - {current}")
    return " ".join(chunks)


def _conjunction(pos: tuple[Atom, ...], neg: tuple[Atom, ...]) -> str:
    lits = [str(a) for a in pos] + [f"(not {a})" for a in neg]
    if not lits:
        return "()"
    if len(lits) == 1:
        return lits[0]
    return "(and " + " ".join(lits) + ")"


def domain_to_pddl(domain: Domain) -> str:
    """Render a :class:`Domain` as PDDL text that parses back to an equal domain."""
    typed = bool(domain.types) or ":typing" in domain.requirements
    lines = [f"(define (domain {domain.name})"]
    if domain.requirements:
        lines.append(f"  (:requirements {' '.join(domain.requirements)})")
    if domain.types:
        by_parent: dict[str, list[str]] = {}
        for t, parent in domain.types.items():
            by_parent.setdefault(parent, []).append(t)
        lines.append("  (:types " + " ".join(f"{' '.join(ts)} - {p}" for p, ts in by_parent.items()) + ")")
    if domain.constants:
        lines.append(f"  (:constants {_typed_str(list(domain.constants.items()), typed)})")
    lines.append("  (:predicates")
    for pname, params in domain.predicates.items():
        inner = _typed_str(params, typed)
        lines.append(f"    ({pname}{' ' + inner if inner else ''})")
    lines.append("  )")
    for a in domain.actions.values():
        lines.append(f"  (:action {a.name}")
        lines.append(f"    :parameters ({_typed_str(a.parameters, typed)})")
        lines.append(f"    :precondition {_conjunction(a.pre_pos, a.pre_neg)}")
        lines.append(f"    :effect {_conjunction(a.add, a.delete)})")
    lines.append(")")
    return "\n".join(lines) + "\n"


def problem_to_pddl(problem: Problem) -> str:
    """Render a :class:`Problem` as PDDL text that parses back to an equal problem."""
    typed = any(t != OBJECT for t in problem.objects.values())
    objs = sorted(problem.objects.items(), key=lambda kv: (kv[1], kv[0]))
    lines = [f"(define (problem {problem.name})", f"  (:domain {problem.domain_name})"]
    if objs:
        lines.append(f"  (:objects {_typed_str(objs, typed)})")
    lines.append("  (:init")
    for atom in sorted(problem.init, key=lambda a: (a.predicate, a.args)):
        lines.append(f"    {atom}")
    lines.append("  )")
    lines.append(f"  (:goal {_conjunction(problem.goal_pos, problem.goal_neg)})")
    lines.append(")")
    return "\n".join(lines) + "\n"
