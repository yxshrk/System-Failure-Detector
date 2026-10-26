"""Differential tests: the symbolic executor must agree with real Python."""

import random

import pytest

from premortem.sp1 import domain as D
from premortem.sp1.benchmarks import BENCHMARKS
from premortem.sp1.concrete import run
from premortem.sp1.solve import concretize, diff_check, evaluate_outcome, unwind_possible
from premortem.sp1.symexec import concrete as known


def _sources(b):
    return [("reference", b.reference)] + b.hand_mutants()


@pytest.mark.parametrize("b", BENCHMARKS, ids=lambda b: b.name)
def test_symbolic_matches_concrete(b):
    rng = random.Random(b.name)
    for label, src in _sources(b):
        for _ in range(25):
            values = {n: D.sample(t, rng) for n, t in b.params}
            args = [values[n] for n, _ in b.params]
            c = run(src, b.name, args)
            assert c.kind != "timeout", (label, values)
            o = evaluate_outcome(src, b.name, b.params, b.loop_bound, values)
            exc = known(o.exc) if not isinstance(o.exc, bool) else o.exc
            if exc is None:
                import z3
                exc = z3.is_true(z3.simplify(o.exc))
            assert exc == (c.kind == "exception"), (label, values, c)
            if c.kind == "ok":
                assert concretize(o.value) == c.value, (label, values, c.value)


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
