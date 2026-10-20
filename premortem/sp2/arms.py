"""The two SP2 arms.

(A) Direct     -- the model reads the design document and the family's event
                  vocabulary (the PDDL domain) and outputs a verdict plus an
                  event trace.
(B) Translate  -- the model writes the PDDL problem (objects, initial state with
                  the design facts, goal); the planners search it. Complete
                  greedy best-first search with h_FF either finds a trace or
                  proves the violation unreachable *in the model's problem*;
                  when a trace exists SATPlan then shortens it to an optimal one.
                  Parser/validator errors are fed back for repair.

Every trace, from either arm, is finally replayed on the gold problem.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from ..parsing import code_blocks, last_json_object
from ..planning import PDDLError, gbfs, ground, parse_domain, parse_problem, satplan
from .families import FAMILIES

MAX_REPAIRS = 2
SEARCH_LIMIT = 3_000_000
SEARCH_SECONDS = 300
SAT_TIME_LIMIT = 120.0

SYSTEM_DIRECT = (
    "You are a principal engineer running a pre-mortem on a distributed-system design: you look for "
    "concrete event sequences that make the system violate its safety requirement. You reason "
    "carefully and step by step; you have no tools."
)
SYSTEM_TRANSLATE = (
    "You are a formal-methods engineer. You translate design documents into precise PDDL planning "
    "problems that a classical planner can analyse."
)


def domain_of(inst: dict) -> str:
    return inst.get("domain") or FAMILIES[inst["family"]].domain


def _context(inst: dict) -> str:
    return f"""--- Design document ---
{inst['design'].strip()}

--- Event model ---
The possible events in this system are modelled by the following STRIPS planning domain. Each action
is one event; it can happen only when its precondition holds, and its effect updates the state
(closed world: facts not stated are false).

```pddl
{domain_of(inst).strip()}
```

{inst['naming']}"""


def direct_prompt(inst: dict) -> str:
    fam = FAMILIES[inst["family"]]
    goal = gold_goal_text(inst)
    return f"""{_context(inst)}

Question: {fam.question} In the event model this means reaching a state where {goal} holds.

If it can happen, give a complete event sequence, starting from the initial situation described in
the design document, that ends in such a state: a list of ground actions such as "(action arg1 arg2)".
Every action's precondition must hold at the moment it occurs. If it cannot happen under this design,
say so.

End your answer with a JSON object in a ```json block, either
{{"verdict": "violation", "trace": ["(action arg ...)", ...]}}
or
{{"verdict": "safe"}}"""


def translate_prompt(inst: dict) -> str:
    fam = FAMILIES[inst["family"]]
    goal = gold_goal_text(inst)
    dom_name = parse_domain(domain_of(inst)).name
    return f"""{_context(inst)}

Question: {fam.question} In the event model this means reaching a state where {goal} holds.

Do NOT try to answer the question yourself. Instead, write the PDDL problem file that encodes this
particular design: its objects, its complete initial state, and the goal. A classical planner will then
search it: complete forward search with the FF heuristic decides whether the goal is reachable, and
SATPlan returns the shortest event sequence that reaches it.

Requirements:
- use (:domain {dom_name}) and the object names given above, each declared with its type;
- :init must list every fact that is true initially, including the design facts that describe this
  design and static facts such as counter successors (closed world: anything not listed is false);
- :goal must be {goal}.

Answer with the problem in one ```pddl block."""


def repair_prompt(original: str, previous: str, feedback: str) -> str:
    return (f"{original}\n\n--- Your previous answer ---\n{previous.strip()}\n\n--- Planner feedback ---\n{feedback}\n\n"
            "Please send the corrected problem file, complete, in one ```pddl block.")


def gold_goal_text(inst: dict) -> str:
    dom = parse_domain(domain_of(inst))
    prob = parse_problem(inst["problem"], dom)
    atoms = [str(a) for a in prob.goal_pos]
    return atoms[0] if len(atoms) == 1 else "(and " + " ".join(sorted(atoms)) + ")"


@dataclass
class ArmResult:
    instance: str
    arm: str
    model: str
    verdict: str  # "violation" | "safe" | "invalid"
    trace: list | None = None
    attempts: int = 1
    problem: str | None = None
    solver: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    llm_cost: float = 0.0
    llm_seconds: float = 0.0
    output_tokens: int = 0
    raw: str = ""

    def to_dict(self):
        return asdict(self)


def run_direct(llm, inst: dict) -> ArmResult:
    c = llm.complete(SYSTEM_DIRECT, direct_prompt(inst), tag=f"sp2-direct:{inst['id']}")
    res = ArmResult(inst["id"], "direct", llm.alias, "invalid", llm_cost=c.cost_usd, llm_seconds=c.seconds,
                    output_tokens=c.output_tokens, raw=c.text)
    if c.error:
        res.errors.append(c.error)
        return res
    obj = last_json_object(c.text, "verdict")
    if obj is None:
        res.errors.append("no JSON verdict found")
        return res
    v = str(obj.get("verdict", "")).lower().strip()
    if v.startswith("viol") or v in ("unsafe", "bug", "failure"):
        res.verdict = "violation"
        tr = obj.get("trace")
        res.trace = [str(x) for x in tr] if isinstance(tr, list) else None
    elif v in ("safe", "no_violation", "no violation"):
        res.verdict = "safe"
    else:
        res.errors.append(f"unrecognised verdict {v!r}")
    return res


def check_problem(inst: dict, text: str):
    """Parse, validate and ground a model-written problem; return (task, error message)."""
    dom = parse_domain(domain_of(inst))
    try:
        prob = parse_problem(text, dom)
    except PDDLError as e:
        return None, None, str(e)
    gold = parse_problem(inst["problem"], dom)
    if set(map(str, prob.goal_pos)) != set(map(str, gold.goal_pos)) or prob.goal_neg:
        return None, prob, f"the goal must be exactly {gold_goal_text(inst)}"
    try:
        task = ground(dom, prob)
    except PDDLError as e:
        return None, prob, str(e)
    return task, prob, ""


def plan_for(task) -> dict:
    """Complete search first (decides reachability), then SATPlan for the shortest trace."""
    t0 = time.perf_counter()
    g = gbfs(task, max_expansions=SEARCH_LIMIT, time_limit=SEARCH_SECONDS)
    out = {"gbfs_status": g.status, "gbfs_expanded": g.expanded, "gbfs_seconds": round(time.perf_counter() - t0, 3),
           "gbfs_length": g.length, "h_init": g.h_init if g.h_init != float("inf") else None}
    if g.status != "solved":
        out["plan"] = None
        return out
    sp = satplan(task, g.length, time_limit=SAT_TIME_LIMIT)
    out.update({"satplan_status": sp.status, "satplan_length": sp.length, "satplan_seconds": round(sp.seconds, 3)})
    out["plan"] = sp.plan if sp.status == "solved" else g.plan
    return out


def run_translate(llm, inst: dict) -> ArmResult:
    original = translate_prompt(inst)
    prompt = original
    res = ArmResult(inst["id"], "translate", llm.alias, "invalid")
    for attempt in range(1 + MAX_REPAIRS):
        c = llm.complete(SYSTEM_TRANSLATE, prompt, tag=f"sp2-translate:{inst['id']}:{attempt}")
        res.attempts = attempt + 1
        res.llm_cost += c.cost_usd
        res.llm_seconds += c.seconds
        res.output_tokens += c.output_tokens
        res.raw = c.text
        if c.error:
            res.errors.append(c.error)
            return res
        blocks = code_blocks(c.text, "pddl") or code_blocks(c.text, "lisp") or code_blocks(c.text, None)
        blocks = [b for b in blocks if "define" in b and "problem" in b]
        if not blocks:
            feedback = "No ```pddl block containing a (define (problem ...)) was found in your answer."
        else:
            text = max(blocks, key=len)
            res.problem = text
            task, _, err = check_problem(inst, text)
            if task is not None:
                res.solver = plan_for(task)
                if res.solver["gbfs_status"] == "solved":
                    res.verdict, res.trace = "violation", res.solver["plan"]
                elif res.solver["gbfs_status"] == "unsolvable":
                    res.verdict = "safe"
                else:
                    res.verdict = "safe"  # search limit hit without finding a trace
                    res.errors.append("search limit reached")
                return res
            feedback = err
        res.errors.append(feedback)
        prompt = repair_prompt(original, c.text, feedback)
    return res
