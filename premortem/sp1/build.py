"""Build the SP1 instance set: mutants with gold labels and trigger rarity.

For every benchmark we pool hand-written mutants, automatic first-order
mutants and hand-written equivalent rewrites, then for each candidate:

1. estimate trigger rarity = Pr[mutant(x) != reference(x)] for x drawn from
   the input distribution (exhaustive for small integer domains, otherwise
   ``N_SAMPLES`` random inputs; length uniform, then elements uniform);
2. ask Z3 (``diff_check``) whether any in-domain input exposes a difference,
   and confirm every Z3 witness by real execution;
3. label it a bug (witness exists) or a control (provably equivalent within
   the bounds).

The selection then keeps, per function, all hand mutants plus automatic
mutants stratified over rarity buckets, and two controls (the clean reference
and, when one exists, an equivalent mutant that looks like a bug).

Run:  python -m premortem.sp1.build
"""

from __future__ import annotations

import json
import math
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path

from . import domain as D
from .benchmarks import BENCHMARKS, BY_NAME
from .concrete import call, load
from .mutate import mutants
from .solve import diff_check, unwind_possible

N_SAMPLES = 5000
EXHAUSTIVE_LIMIT = 70_000
SEED = 3263
BUCKETS = [("common", 0.1), ("uncommon", 0.01), ("rare", 0.001), ("very_rare", 0.0)]
DATA = Path(__file__).resolve().parents[2] / "data" / "sp1"


def bucket(rarity: float) -> str:
    for name, lo in BUCKETS:
        if rarity >= lo and (rarity > 0 or name == "very_rare"):
            return name
    return "very_rare"


@lru_cache(maxsize=None)
def inputs_for(name: str):
    b = BY_NAME[name]
    if all(not isinstance(t, D.ListT) for _, t in b.params):
        size = math.prod(D.domain_size(t) for _, t in b.params)
        if size <= EXHAUSTIVE_LIMIT:
            import itertools
            return [list(v) for v in itertools.product(*(D.enumerate_values(t) for _, t in b.params))], True
    rng = random.Random(f"{SEED}:{name}")
    return [[D.sample(t, rng) for _, t in b.params] for _ in range(N_SAMPLES)], False


@lru_cache(maxsize=None)
def reference_runs(name: str):
    b = BY_NAME[name]
    fn = load(b.reference)[name]
    return [call(fn, args) for args in inputs_for(name)[0]]


def evaluate(task):
    """Worker: rarity by execution plus a Z3 equivalence check for one candidate."""
    name, origin, op, desc, src = task
    b = BY_NAME[name]
    inputs, exhaustive = inputs_for(name)
    refs = reference_runs(name)
    fn = load(src)[name]
    n_diff, timeouts, first = 0, 0, None
    for args, ref in zip(inputs, refs):
        r = call(fn, args, step_limit=20_000)
        if r.kind == "timeout":
            timeouts += 1
            if timeouts > 3:
                break
            continue
        if not r.same_as(ref):
            n_diff += 1
            if first is None:
                first = args
    z = diff_check(b.reference, src, name, b.params, b.loop_bound, timeout_ms=60_000)
    witness_ok = None
    if z.status == "witness":
        args = [z.witness[p] for p, _ in b.params]
        m = call(fn, args, step_limit=200_000)
        witness_ok = m.kind != "timeout" and not m.same_as(call(load(b.reference)[name], args))
    unwind = None
    if z.status == "no_witness" and not exhaustive:
        unwind = unwind_possible(src, name, b.params, b.loop_bound)
    return {
        "function": name, "origin": origin, "op": op, "description": desc, "source": src, "unwind_possible": unwind,
        "n": len(inputs), "exhaustive": exhaustive, "n_diff": n_diff, "timeouts": timeouts,
        "rarity": n_diff / len(inputs), "sample_witness": first,
        "z3_status": z.status, "z3_witness": z.witness, "z3_seconds": round(z.seconds, 3),
        "z3_detail": z.detail, "z3_witness_confirmed": witness_ok,
    }


def candidate_tasks():
    tasks = []
    for b in BENCHMARKS:
        for desc, src in b.hand_mutants():
            tasks.append((b.name, "hand", "HAND", desc, src))
        for desc, src in b.hand_rewrites():
            tasks.append((b.name, "rewrite", "REWRITE", desc, src))
        for m in mutants(b.reference):
            tasks.append((b.name, "auto", m.op, m.description, m.source))
    return tasks


def label(c) -> str | None:
    if c["timeouts"]:
        return None  # non-terminating mutants are out of scope (bounded analysis)
    if c["z3_status"] == "witness" and c["z3_witness_confirmed"]:
        return "bug"
    if c["z3_status"] == "no_witness":
        if c["n_diff"]:
            raise AssertionError(f"executor unsound: Z3 says equivalent but sampling differs: {c['function']} {c['description']}")
        # Equivalence is certain only if the domain was enumerated or no path exceeds the unrolling bound.
        if c["exhaustive"] or c["unwind_possible"] is False:
            return "control"
    return None


TARGET = {"very_rare": 4, "rare": 3, "uncommon": 1, "common": 1}
MIN_BUGS, MAX_BUGS = 3, 6
TARGET_HARD = {"very_rare": 1, "rare": 1, "uncommon": 0, "common": 0}


def select(pool, rng: random.Random):
    chosen = []
    by_fn: dict[str, list] = {}
    for c in pool:
        by_fn.setdefault(c["function"], []).append(c)
    for b in BENCHMARKS:
        cands = by_fn.get(b.name, [])
        bugs = [c for c in cands if c["label"] == "bug"]
        picked = [c for c in bugs if c["origin"] == "hand"]
        auto = [c for c in bugs if c["origin"] == "auto"]
        rng.shuffle(auto)
        auto.sort(key=lambda c: c["op"] in {x["op"] for x in picked})  # prefer operator diversity
        target = TARGET_HARD if b.tier == "hard" else TARGET
        for bname in ("very_rare", "rare", "uncommon", "common"):
            have = sum(bucket(c["rarity"]) == bname for c in picked)
            for c in [c for c in auto if bucket(c["rarity"]) == bname]:
                if have >= target[bname]:
                    break
                picked.append(c)
                have += 1
        for c in auto:
            if len(picked) >= MIN_BUGS or b.tier == "hard":
                break
            if c not in picked:
                picked.append(c)
        picked = picked[:MAX_BUGS]
        for c in picked:
            chosen.append({**c, "kind": "bug"})
        clean = {"function": b.name, "origin": "reference", "op": "NONE", "description": "unmodified reference",
                 "source": b.reference, "rarity": 0.0, "kind": "control", "z3_status": "no_witness"}
        chosen.append(clean)
        eq = [c for c in cands if c["label"] == "control" and c["origin"] in ("rewrite", "hand")]
        if not eq:
            eq = [c for c in cands if c["label"] == "control" and c["op"] in ("ROR", "CRP", "RNG", "AOR", "LCR")]
            rng.shuffle(eq)
            eq.sort(key=lambda c: c["op"] != "ROR")
        if eq:
            chosen.append({**eq[0], "kind": "control"})
    for k, c in enumerate(chosen):
        c["tier"] = BY_NAME[c["function"]].tier
        c["id"] = f"sp1-{k:03d}-{c['function']}"
        c["bucket"] = bucket(c["rarity"]) if c["kind"] == "bug" else ("clean" if c["origin"] == "reference" else "equivalent")
    return chosen


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    tasks = candidate_tasks()
    print(f"evaluating {len(tasks)} candidates ...", file=sys.stderr)
    with ProcessPoolExecutor(max_workers=10) as ex:
        pool = list(ex.map(evaluate, tasks, chunksize=4))
    for c in pool:
        c["label"] = label(c)
    (DATA / "candidate_pool.json").write_text(json.dumps(pool, indent=1))
    instances = select(pool, random.Random(SEED))
    meta = {b.name: {"params": [[n, repr(t)] for n, t in b.params], "loop_bound": b.loop_bound, "tier": b.tier,
                     "origin": b.origin, "reference": b.reference} for b in BENCHMARKS}
    (DATA / "instances.json").write_text(json.dumps({"benchmarks": meta, "instances": instances}, indent=1))
    n_bug = sum(c["kind"] == "bug" for c in instances)
    print(f"pool: {len(pool)}  bugs: {sum(c['label'] == 'bug' for c in pool)}  "
          f"equivalent: {sum(c['label'] == 'control' for c in pool)}  dropped: {sum(c['label'] is None for c in pool)}")
    print(f"selected: {len(instances)} instances ({n_bug} bugs, {len(instances) - n_bug} controls)")
    from collections import Counter
    print(Counter(c["bucket"] for c in instances))


if __name__ == "__main__":
    main()
