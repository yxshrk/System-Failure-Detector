"""Exact scoring of SP2 answers: replay every trace on the gold problem.

    violating design:  valid_trace | invalid_trace (fabricated) | miss
    fixed design:      correct_safe | false_alarm (fabricated)
    either:            no_answer

SP3 (translation quality) compares the model's initial state with the gold one,
separately for the design facts that distinguish the variants.
"""

from __future__ import annotations

from functools import lru_cache

from ..planning import ground, parse_domain, parse_problem, validate_plan
from .families import FAMILIES, design_predicates


@lru_cache(maxsize=None)
def gold_task(domain: str, problem: str):
    dom = parse_domain(domain)
    return ground(dom, parse_problem(problem, dom))


def _domain(inst: dict) -> str:
    return inst.get("domain") or FAMILIES[inst["family"]].domain


def replay(inst: dict, trace) -> tuple[bool, str, int | None]:
    task = gold_task(_domain(inst), inst["problem"])
    try:
        v = validate_plan(task, trace)
    except Exception as e:  # malformed step text
        return False, f"unparseable trace: {e}", None
    # A trace counts once the violation has been reached; trailing steps after that do not matter.
    return v.goal_reached_at is not None, v.message, v.goal_reached_at


def outcome(result: dict, inst: dict) -> tuple[str, str]:
    if result["verdict"] == "invalid":
        return "no_answer", "; ".join(map(str, result.get("errors", [])))[:300]
    if result["verdict"] == "safe":
        return ("miss", "") if inst["violation"] else ("correct_safe", "")
    trace = result.get("trace") or []
    if not trace:
        return ("invalid_trace" if inst["violation"] else "false_alarm"), "no trace given"
    ok, msg, at = replay(inst, trace)
    if not inst["violation"]:
        return "false_alarm", msg
    return ("valid_trace", f"violation reached after {at} steps") if ok else ("invalid_trace", msg)


def translation_scores(inst: dict, problem_text: str | None) -> dict:
    if not problem_text:
        return {}
    dom = parse_domain(_domain(inst))
    try:
        mine = parse_problem(problem_text, dom)
    except Exception:
        return {"parsed": False}
    gold = parse_problem(inst["problem"], dom)
    m_init = {a.fact for a in mine.init}
    g_init = {a.fact for a in gold.init}
    dp = set(inst.get("design_predicates") or design_predicates(inst["family"]))
    m_design = {f for f in m_init if f in dp}
    g_design = {f for f in g_init if f in dp}
    tp = len(m_init & g_init)
    return {
        "parsed": True,
        "design_exact": m_design == g_design,
        "design_model": sorted(m_design), "design_gold": sorted(g_design),
        "init_precision": tp / len(m_init) if m_init else 0.0,
        "init_recall": tp / len(g_init) if g_init else 0.0,
        "init_exact": m_init == g_init,
        "objects_exact": dict(mine.objects) == dict(gold.objects),
        "missing": sorted(g_init - m_init)[:12], "extra": sorted(m_init - g_init)[:12],
    }
