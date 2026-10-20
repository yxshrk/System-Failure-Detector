"""Gold-model properties of the SP2 design families."""

import math

import pytest

from premortem.planning import gbfs, ground, parse_domain, parse_problem, satplan
from premortem.sp2.families import FAMILIES, VARIANTS, design_predicates
from premortem.sp2.score import outcome, translation_scores


def _task(fam, variant, size):
    dom = parse_domain(fam.domain)
    return ground(dom, parse_problem(fam.problem(variant, size), dom))


@pytest.mark.parametrize("name", list(FAMILIES))
@pytest.mark.parametrize("variant", VARIANTS)
def test_variant_semantics(name, variant):
    fam = FAMILIES[name]
    for size in (1, 2):
        task = _task(fam, variant, size)
        r = gbfs(task)
        if variant == "fixed":
            assert r.status == "unsolvable"
            assert math.isfinite(r.h_init), "fix must not be provable by the delete relaxation alone"
        else:
            assert r.status == "solved"
            assert satplan(task, 30).length <= r.length


@pytest.mark.parametrize("name", list(FAMILIES))
def test_variants_differ_only_in_design_facts(name):
    fam = FAMILIES[name]
    dom = parse_domain(fam.domain)
    inits = {}
    for v in VARIANTS:
        prob = parse_problem(fam.problem(v, 2), dom)
        inits[v] = {a.fact for a in prob.init}
    dp = design_predicates(name)
    stripped = [{f for f in s if f not in dp} for s in inits.values()]
    assert all(s == stripped[0] for s in stripped)
    for v in VARIANTS:
        assert {f for f in inits[v] if f in dp} == set(fam.design_facts[v])


def test_scoring_replays_on_gold():
    fam = FAMILIES["payments"]
    inst = {"family": "payments", "problem": fam.problem("flawed", 1), "violation": True}
    plan = satplan(_task(fam, "flawed", 1), 20).plan
    assert outcome({"verdict": "violation", "trace": plan}, inst)[0] == "valid_trace"
    assert outcome({"verdict": "violation", "trace": plan[:-1]}, inst)[0] == "invalid_trace"
    assert outcome({"verdict": "safe"}, inst)[0] == "miss"
    fixed = {"family": "payments", "problem": fam.problem("fixed", 1), "violation": False}
    assert outcome({"verdict": "violation", "trace": plan}, fixed)[0] == "false_alarm"
    s = translation_scores(inst, fam.problem("subtle", 1))
    assert s["parsed"] and not s["design_exact"] and s["design_model"] == ["dedup-racy"]
