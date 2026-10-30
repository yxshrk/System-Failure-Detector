"""The two SP1 arms.

(A) Direct     -- the model reads the code and its docstring and outputs a
                  verdict plus a concrete failing input.
(B) Translate  -- the model writes pre/postconditions from the docstring; the
                  bounded verifier (symbolic execution + Z3) searches for a
                  violating input. Verifier errors are fed back for repair.

Both arms receive identical information: the code under review (whose
docstring is the specification) and the input domain.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..parsing import code_blocks, last_json_object
from . import domain as D
from .solve import spec_check

MAX_REPAIRS = 2

SYSTEM_DIRECT = (
    "You are a meticulous senior software engineer running a pre-mortem code review. "
    "You analyse code by reading and reasoning about it; you cannot execute it."
)

SYSTEM_TRANSLATE = (
    "You are a formal-methods engineer. You translate informal specifications into precise, "
    "machine-checkable pre- and postconditions for an automatic verifier."
)


def domain_text(params) -> str:
    return "\n".join(f"- {D.describe(n, t)}" for n, t in params)


def direct_prompt(code: str, params) -> str:
    names = ", ".join(f'"{n}": ...' for n, _ in params)
    return f"""Below is a Python function. Its docstring is the specification: it states exactly what the function must return for every valid input.

Valid inputs:
{domain_text(params)}

```python
{code.strip()}
```

Question: is there a valid input for which the function does NOT behave as its docstring specifies (it returns a different value, or raises an exception)?

- If yes, give one concrete such input.
- If you are confident the function meets its docstring for every valid input, say so.

Think it through, then end your answer with a JSON object in a ```json block, either
{{"verdict": "bug", "failing_input": {{{names}}}, "expected": <what the docstring requires>, "actual": <what the code returns, or "exception">}}
or
{{"verdict": "no_bug"}}"""


def translate_prompt(code: str, fname: str, params, loop_bound: int) -> str:
    args = ", ".join(n for n, _ in params)
    return f"""Below is a Python function whose docstring is its specification. Do NOT judge the code yourself. Instead, translate the docstring into a formal specification that an automatic bounded verifier will check the code against.

Valid inputs:
{domain_text(params)}

```python
{code.strip()}
```

Write two Python functions:

    def pre({args}):            # -> bool: True for inputs the docstring's contract covers (you may just return True)
    def post({args}, result):   # -> bool: True exactly when `result` is what the docstring requires for these inputs

How the verifier works: it symbolically executes `{fname}` on every valid input (lists up to their maximum length; loops unrolled up to {loop_bound} iterations) and asks the Z3 SMT solver for an input where pre(...) is True but `{fname}` raises an exception or post(...) is False. Any such input is reported as a failure.

The verifier understands only this subset of Python, for pre, post and any helper functions you define:
- values: ints, bools, None, lists of ints, tuples (no strings, floats, dicts, sets, lambdas, classes, imports, recursion)
- statements: assignment, augmented assignment, if/elif/else, for over range(...)/lists/enumerate(...)/zip(...), while, break, continue, return, assert
- built-ins: len, abs, min, max, sum, sorted, reversed, range, list, all, any, enumerate, zip, divmod; list methods append, pop, insert, count, index, copy, extend, remove, sort, reverse
- integer arithmetic only: use // and %, never /
Guidance:
- Specify the docstring's intended behaviour, not what the code happens to do.
- Computing the required answer independently (for example with a simple loop) and comparing it with `result` is a good strategy.
- `post` receives the original, unmodified inputs.

Answer with one ```python block containing pre, post and any helpers."""


def repair_prompt(original: str, previous: str, feedback: str) -> str:
    return (f"{original}\n\n--- Your previous answer ---\n{previous.strip()}\n\n--- Verifier feedback ---\n{feedback}\n\n"
            "Please send a corrected specification: the complete code in one ```python block.")


@dataclass
class ArmResult:
    instance: str
    arm: str
    model: str
    verdict: str  # "bug" | "no_bug" | "invalid" (no usable answer)
    witness: dict | None = None
    attempts: int = 1
    spec: str | None = None
    tool_status: str | None = None
    tool_detail: str = ""
    tool_seconds: float = 0.0
    errors: list = field(default_factory=list)
    llm_cost: float = 0.0
    llm_seconds: float = 0.0
    output_tokens: int = 0
    raw: str = ""

    def to_dict(self):
        return asdict(self)


def run_direct(llm, inst: dict, params) -> ArmResult:
    prompt = direct_prompt(inst["source"], params)
    c = llm.complete(SYSTEM_DIRECT, prompt, tag=f"sp1-direct:{inst['id']}")
    res = ArmResult(inst["id"], "direct", llm.alias, "invalid", llm_cost=c.cost_usd, llm_seconds=c.seconds,
                    output_tokens=c.output_tokens, raw=c.text)
    if c.error:
        res.errors.append(c.error)
        return res
    obj = last_json_object(c.text, "verdict")
    if obj is None:
        res.errors.append("no JSON verdict found")
        return res
    v = str(obj.get("verdict", "")).lower().replace("-", "_").strip()
    if v in ("bug", "failure", "fail"):
        res.verdict = "bug"
        wit = obj.get("failing_input")
        res.witness = wit if isinstance(wit, dict) else None
    elif v in ("no_bug", "nobug", "correct", "no_failure"):
        res.verdict = "no_bug"
    else:
        res.errors.append(f"unrecognised verdict {v!r}")
    return res


def run_translate(llm, inst: dict, params, fname: str, loop_bound: int) -> ArmResult:
    original = translate_prompt(inst["source"], fname, params, loop_bound)
    prompt = original
    res = ArmResult(inst["id"], "translate", llm.alias, "invalid")
    for attempt in range(1 + MAX_REPAIRS):
        c = llm.complete(SYSTEM_TRANSLATE, prompt, tag=f"sp1-translate:{inst['id']}:{attempt}")
        res.attempts = attempt + 1
        res.llm_cost += c.cost_usd
        res.llm_seconds += c.seconds
        res.output_tokens += c.output_tokens
        res.raw = c.text
        if c.error:
            res.errors.append(c.error)
            return res
        blocks = code_blocks(c.text, "python")
        if not blocks:
            feedback = "No ```python code block was found in your answer."
        else:
            spec = max(blocks, key=len)
            res.spec = spec
            r = spec_check(inst["source"], fname, spec, params, loop_bound)
            res.tool_status, res.tool_detail, res.tool_seconds = r.status, r.detail, res.tool_seconds + r.seconds
            if r.status == "witness":
                res.verdict, res.witness = "bug", r.witness
                return res
            if r.status in ("no_witness", "unknown", "timeout", "incomplete"):
                res.verdict = "no_bug"  # scored as undecided unless the status is a real "no_witness"
                return res
            feedback = r.detail
        res.errors.append(feedback)
        prompt = repair_prompt(original, c.text, feedback)
    return res
