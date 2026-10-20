"""Plan parsing and replay against a ground task (in the spirit of VAL).

Steps are 1-based in all results and messages: ``failed_step == 3`` means the
third action could not be applied, and ``goal_reached_at == k`` means the goal
first holds after the first ``k`` actions (``0`` = already in the initial state).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from .ground import GroundAction, State, Task, apply, equality_violations, instantiate
from .pddl import PDDLError, _names, _plural

_NUMBERING = re.compile(r"^(?:step\s*)?\d+(?:\.\d+)?\s*[.:)\]]?\s*")
_BULLET = re.compile(r"^[-*•]\s+")
_DURATION = re.compile(r"\[[^\]]*\]\s*$")
_GROUP = re.compile(r"\(([^()]*)\)")
_CALL = re.compile(r"([^\s(),]+)\s*\((.*)\)")
_BAD_TOKEN = re.compile(r"[\"'`\[\]{}()]")


@dataclass
class ValidationResult:
    """Outcome of replaying a plan; see the module docstring for step numbering."""

    valid: bool
    executable: bool
    goal_reached: bool
    failed_step: int | None
    message: str
    goal_reached_at: int | None = None
    plan: list[str] = field(default_factory=list)
    states_visited: list[State] = field(default_factory=list, repr=False)


def _canonical(body: str, raw: str, where: str) -> str:
    tokens = body.replace(",", " ").split()
    if not tokens or any(_BAD_TOKEN.search(t) for t in tokens):
        raise PDDLError(f"cannot parse plan {where}: {raw.strip()!r}")
    return " ".join(tokens)


def _parse_line(raw: str, where: str) -> list[str]:
    s = re.split(r"[;#]", raw, maxsplit=1)[0].strip().lower()
    s = s.strip("\"'`, ")
    s = _DURATION.sub("", s).strip()
    s = _BULLET.sub("", s)
    s = _NUMBERING.sub("", s, count=1).strip().strip("\"'`, ")
    if not s:
        return []
    if s.startswith("("):
        groups = _GROUP.findall(s)
        if not groups or _GROUP.sub(" ", s).strip(" ,"):
            raise PDDLError(f"cannot parse plan {where}: {raw.strip()!r}")
        return [_canonical(g, raw, where) for g in groups]
    call = _CALL.fullmatch(s)
    if call:
        return [_canonical(f"{call.group(1)} {call.group(2)}", raw, where)]
    return [_canonical(s, raw, where)]


def parse_plan(plan: str | Iterable[str | Sequence[str]]) -> list[str]:
    """Normalise a plan into steps like ``"pay c1 o1"``.

    Accepts a list of steps or a text (one step per line, or a JSON list).
    Each step may be written ``(pay c1 o1)``, ``pay c1 o1`` or ``pay(c1, o1)``,
    optionally numbered (``1.``, ``0:``, ``step 2:``) and followed by a
    ``;`` comment or a ``[duration]``. Blank lines are ignored.
    """
    where = "entry"
    items: list[object]
    if isinstance(plan, str):
        text = plan.strip()
        items, where = text.splitlines(), "line"
        if text.startswith("["):
            try:
                data = json.loads(text)
            except ValueError:
                quoted = re.findall(r'"((?:[^"\\]|\\.)*)"', text)
                if quoted:
                    items, where = list(quoted), "entry"
                else:
                    items = text[1:].rstrip().removesuffix("]").splitlines()
            else:
                if not isinstance(data, list):
                    raise PDDLError("a JSON plan must be a list of steps")
                items, where = data, "entry"
    else:
        items = list(plan)

    steps: list[str] = []
    for i, item in enumerate(items, 1):
        if isinstance(item, (list, tuple)):
            item = " ".join(str(x) for x in item)
        if not isinstance(item, str):
            raise PDDLError(f"cannot parse plan {where} {i}: expected a string, got {item!r}")
        steps.extend(_parse_line(item, f"{where} {i}"))
    return steps


def _resolve(task: Task, step: str) -> tuple[GroundAction | None, list[str], str]:
    """Find or instantiate the ground action for ``step``.

    Returns ``(action, false_equalities, error)``; ``error`` is non-empty when
    the step does not denote a well-typed action at all.
    """
    action = task.action(step)
    if action is not None:
        return action, [], ""
    name, *args = step.split()
    dom = task.domain
    if dom is None:
        known = {a.name.split()[0] for a in task.actions}
        if name not in known:
            return None, [], f"unknown action '{name}' (known action names: {_names(known)})"
        return None, [], f"'{step}' is not an action of the grounded task (ill-typed or never applicable)"
    schema = dom.actions.get(name)
    if schema is None:
        return None, [], f"unknown action '{name}' (known action names: {_names(dom.actions)})"
    if len(args) != len(schema.parameters):
        return None, [], (
            f"action '{name}' expects {_plural(len(schema.parameters), 'argument')} "
            f"{schema.signature()}, got {len(args)}"
        )
    universe = {**dom.constants, **(task.problem.objects if task.problem else {})}
    for arg, (var, vtype) in zip(args, schema.parameters):
        if arg not in universe:
            return None, [], f"unknown object '{arg}' (declared objects: {_names(universe)})"
        if not dom.is_subtype(universe[arg], vtype):
            return None, [], f"object '{arg}' has type {universe[arg]} but parameter {var} of action {name} needs {vtype}"
    return instantiate(schema, args), equality_violations(schema, args), ""


def validate_plan(task: Task, plan: str | Iterable[str | Sequence[str]]) -> ValidationResult:
    """Replay ``plan`` from ``task.init`` and report the first failure, if any."""
    try:
        steps = parse_plan(plan)
    except PDDLError as e:
        return ValidationResult(False, False, False, None, str(e))

    state = task.init
    states = [state]
    goal_at: int | None = 0 if task.goal_satisfied(state) else None

    def failure(i: int, msg: str) -> ValidationResult:
        if goal_at is not None:
            msg += f"; note: the goal was already reached after step {goal_at}"
        return ValidationResult(False, False, task.goal_satisfied(state), i, msg, goal_at, steps, states)

    for i, step in enumerate(steps, 1):
        action, false_eq, error = _resolve(task, step)
        if action is None:
            return failure(i, f"step {i} ({step}): {error}")
        false = [f"({f})" for f in sorted(action.pre_pos - state)]
        false += [f"(not ({f}))" for f in sorted(action.pre_neg & state)]
        false += false_eq
        if false:
            what = f"precondition {false[0]} is" if len(false) == 1 else f"preconditions {', '.join(false)} are"
            return failure(i, f"step {i} ({step}): {what} false")
        state = apply(state, action)
        states.append(state)
        if goal_at is None and task.goal_satisfied(state):
            goal_at = i

    if not task.goal_satisfied(state):
        missing = task.unsatisfied_goals(state)
        what = f"goal {missing[0]}" if len(missing) == 1 else f"goals {', '.join(missing)}"
        msg = f"plan executed but {what} not reached"
        if goal_at is not None:
            msg += f" at the end (it held after step {goal_at} but later steps undid it)"
        return ValidationResult(False, True, False, None, msg, goal_at, steps, states)

    if not steps:
        msg = "plan valid: the goal already holds in the initial state"
    elif goal_at == len(steps):
        msg = f"plan valid: goal {task.goal_str()} reached after step {goal_at}"
    else:
        msg = f"plan valid: goal {task.goal_str()} first reached after step {goal_at} of {len(steps)}"
    return ValidationResult(True, True, True, None, msg, goal_at, steps, states)
