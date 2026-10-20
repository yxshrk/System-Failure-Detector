"""Exact scoring of SP1 answers against the gold reference.

A claimed failing input is *valid* iff it lies in the stated domain and the
code under review behaves differently from the unmutated reference on it
(different return value, or one raises and the other does not). Outcomes:

    bug instance:      valid_witness | invalid_witness (fabricated) | miss
    control instance:  correct_no_bug | false_alarm (fabricated)
    either:            no_answer (unparseable / specification never accepted)
"""

from __future__ import annotations

from . import domain as D
from .concrete import run


def check_witness(witness, params, code: str, reference: str, fname: str) -> tuple[bool, str]:
    if not isinstance(witness, dict):
        return False, "no failing input given"
    missing = [n for n, _ in params if n not in witness]
    if missing:
        return False, f"missing argument(s) {missing}"
    args = []
    for n, t in params:
        v = witness[n]
        if isinstance(t, D.IntT) and isinstance(v, float) and v.is_integer():
            v = int(v)
        why = D.check_value(t, v)
        if why:
            return False, f"out of domain: {n}: {why}"
        args.append(v)
    got = run(code, fname, args)
    want = run(reference, fname, args)
    if got.kind == "timeout":
        return False, "code under review did not terminate"
    if got.same_as(want):
        return False, f"code behaves as specified on this input (returns {got.value!r})" if got.kind == "ok" \
            else "both raise on this input"
    def show(r):
        return repr(r.value) if r.kind == "ok" else r.error

    return True, f"reference: {show(want)}; code: {show(got)}"


def outcome(result: dict, inst: dict, params, reference: str, fname: str) -> tuple[str, str]:
    verdict = result["verdict"]
    if verdict == "invalid":
        return "no_answer", "; ".join(map(str, result.get("errors", [])))[:300]
    if verdict == "no_bug":
        if result.get("tool_status") == "timeout":
            return "tool_timeout", result.get("tool_detail", "")
        return ("miss", "") if inst["kind"] == "bug" else ("correct_no_bug", "")
    ok, why = check_witness(result.get("witness"), params, inst["source"], reference, fname)
    if inst["kind"] == "control":
        return "false_alarm", why
    return ("valid_witness", why) if ok else ("invalid_witness", why)
