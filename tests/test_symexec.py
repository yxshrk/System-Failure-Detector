"""Differential tests: the symbolic executor must agree with real Python."""

import random

import pytest

from premortem.sp1 import domain as D
from premortem.sp1.benchmarks import BENCHMARKS
from premortem.sp1.concrete import run
from premortem.sp1.solve import (concretize, diff_check, spec_check_inprocess, symbolic_then_substitute,
                                 unwind_possible)
from premortem.sp1.symexec import concrete as known


def _sources(b):
    return [("reference", b.reference)] + b.hand_mutants()


@pytest.mark.parametrize("b", BENCHMARKS, ids=lambda b: b.name)
def test_symbolic_matches_concrete(b):
    """Lemma 1, checked on the Z3 encoding itself: execute ONCE on symbolic inputs, then substitute
    concrete inputs into the resulting terms and compare with real Python."""
    rng = random.Random(b.name)
    for label, src in _sources(b):
        at = symbolic_then_substitute(src, b.name, b.params, b.loop_bound)
        for _ in range(25):
            values = {n: D.sample(t, rng) for n, t in b.params}
            c = run(src, b.name, [values[n] for n, _ in b.params])
            assert c.kind != "timeout", (label, values)
            exc, value, unwind = at(values)
            assert known(unwind) is not True, (label, values)  # references fit their bound
            assert known(exc) == (c.kind == "exception"), (label, values, c)
            if c.kind == "ok":
                assert concretize(value) == c.value, (label, values, c.value)


@pytest.mark.parametrize("b", [b for b in BENCHMARKS if b.hand], ids=lambda b: b.name)
def test_hand_mutants_have_confirmed_witnesses(b):
    for label, src in b.hand_mutants():
        r = diff_check(b.reference, src, b.name, b.params, b.loop_bound)
        assert r.status == "witness", (label, r)
        args = [r.witness[n] for n, _ in b.params]
        assert not run(src, b.name, args).same_as(run(b.reference, b.name, args)), (label, r.witness)


@pytest.mark.parametrize("b", BENCHMARKS, ids=lambda b: b.name)
def test_reference_equivalent_to_itself(b):
    r = diff_check(b.reference, b.reference, b.name, b.params, b.loop_bound)
    assert r.status == "no_witness", r


@pytest.mark.parametrize("b", BENCHMARKS, ids=lambda b: b.name)
def test_reference_loops_fit_the_unroll_bound(b):
    """Theorem 1's bounded completeness is only meaningful if the reference never needs more than k iterations."""
    assert not unwind_possible(b.reference, b.name, b.params, b.loop_bound)


def test_spec_check_deepens_the_spec_unrolling_or_reports_incomplete():
    """Theorem 1 needs the coverage query to be UNSAT: deepen the spec's unrolling, never answer "no failure" early."""
    params = [("xs", D.ListT(D.IntT(0, 3), 3))]
    code = "def f(xs):\n    return 2 * len(xs)\n"
    # loops over a list twice as long as xs: 6 iterations, more than the first spec bound max(k, L + 1) = 4
    doubled = ("def post(xs, result):\n    ys = []\n    for x in xs:\n        ys.append(x)\n        ys.append(x)\n"
               "    n = 0\n    for y in ys:\n        n += 1\n    return n == result\n")
    assert spec_check_inprocess(code, "f", doubled, params, 2).status == "no_witness"
    endless = "def post(xs, result):\n    i = 0\n    while i < 1000:\n        i += 1\n    return True\n"
    assert spec_check_inprocess(code, "f", endless, params, 2).status == "incomplete"
