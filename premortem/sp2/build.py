"""Build SP2 gold instances: problem, design document, shortest trace, solver stats.

Run:  python -m premortem.sp2.build            (main, stress and opaque sets)
      python -m premortem.sp2.build --long     (append the long-trace set)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..planning import bfs, gbfs, ground, parse_domain, parse_problem, satplan
from ..planning.validate import validate_plan
from .families import FAMILIES, SIZES, STRESS_SIZES, VARIANTS, design_predicates
from .opaque import opaque_domain, opaque_text, renaming

DATA = Path(__file__).resolve().parents[2] / "data" / "sp2"
T_MAX = 40


def solve_gold(fam, variant: str, size: int, stress: bool = False) -> dict:
    dom = parse_domain(fam.domain)
    task = ground(dom, parse_problem(fam.problem(variant, size), dom))
    t0 = time.perf_counter()
    g = gbfs(task, max_expansions=3_000_000, time_limit=300)
    t_g = time.perf_counter() - t0
    t0 = time.perf_counter()
    b = bfs(task, max_expansions=300_000 if stress else 2_000_000)
    t_b = time.perf_counter() - t0
    # On the stress sizes SATPlan is only asked for the shortest plan (horizon capped at the GBFS length);
    # proving the fixed variants with it is out of reach and is what GBFS is for.
    if stress and g.status != "solved":
        from ..planning.satplan import SatPlanResult
        sp = SatPlanResult(plan=None, length=None, status="skipped", stats=[], seconds=0.0)
    else:
        sp = satplan(task, g.length if (stress and g.length) else T_MAX, time_limit=300 if stress else 600)
    return {
        "n_facts": len(task.facts), "n_actions": len(task.actions),
        "gbfs": {"status": g.status, "length": g.length, "expanded": g.expanded, "h_init": g.h_init, "seconds": round(t_g, 4)},
        "bfs": {"status": b.status, "length": b.length, "expanded": b.expanded, "seconds": round(t_b, 4)},
        "satplan": {"status": sp.status, "length": sp.length, "seconds": round(sp.seconds, 4), "plan": sp.plan,
                    "horizons": [{"T": h.T, "vars": h.n_vars, "clauses": h.n_clauses, "seconds": round(h.solve_seconds, 4),
                                  "sat": h.sat} for h in sp.stats]},
        "gbfs_plan": g.plan,
    }


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    instances = []
    for name, fam in FAMILIES.items():
        for variant in VARIANTS:
            for size in SIZES + STRESS_SIZES:
                stress = size in STRESS_SIZES
                t0 = time.perf_counter()
                gold = solve_gold(fam, variant, size, stress)
                reachable = gold["gbfs"]["status"] == "solved"
                assert reachable == (variant != "fixed"), (name, variant, size)
                certificate = certify(name, variant, size, gold)
                exact = gold["satplan"]["status"] == "solved"
                shortest = (gold["satplan"]["length"] if exact else gold["gbfs"]["length"]) if reachable else None
                if reachable and not exact and name == "inventory":
                    # SATPlan times out here; the optimum is 3S+3 for both violating variants
                    # (SATPlan-verified for S <= 4, and reached by GBFS on the flawed variant).
                    shortest = 3 * size + 3
                instances.append({
                    "id": f"sp2-{name}-{variant}-{size}", "family": name, "variant": variant, "size": size,
                    "set": "stress" if stress else "main", "knob": fam.knob(size), "violation": reachable,
                    "shortest": shortest,
                    "shortest_exact": exact if reachable else None,
                    "design": fam.design(variant, size), "naming": fam.naming(variant, size),
                    "problem": fam.problem(variant, size), "design_facts": list(fam.design_facts[variant]),
                    "certificate": certificate, "gold": gold,
                })
                print(f"{instances[-1]['id']:28s} shortest={instances[-1]['shortest']}  {time.perf_counter() - t0:.1f}s", flush=True)
    write(add_opaque(instances))


LONG_FAMILIES = ("payments", "inventory")
LONG_SIZES = (12, 16)


def solve_long(name: str, fam, variant: str, size: int) -> dict:
    """Gold for the long-trace set: GBFS decides reachability and gives the trace; SATPlan confirms the
    shortest length where it is fast (payments); BFS is skipped. Inventory's fixed variant is beyond
    any search budget, so its search is capped and the label rests on the invariant."""
    dom = parse_domain(fam.domain)
    task = ground(dom, parse_problem(fam.problem(variant, size), dom))
    limit = 60 if (name == "inventory" and variant == "fixed") else 300
    t0 = time.perf_counter()
    g = gbfs(task, max_expansions=3_000_000, time_limit=limit)
    t_g = time.perf_counter() - t0
    if g.plan:
        assert validate_plan(task, g.plan).valid, (name, variant, size)
    from ..planning.satplan import SatPlanResult
    sp = (satplan(task, g.length, time_limit=120) if (name == "payments" and g.status == "solved")
          else SatPlanResult(plan=None, length=None, status="skipped", stats=[], seconds=0.0))
    return {
        "n_facts": len(task.facts), "n_actions": len(task.actions),
        "gbfs": {"status": g.status, "length": g.length, "expanded": g.expanded, "h_init": g.h_init, "seconds": round(t_g, 4)},
        "bfs": {"status": "skipped", "length": None, "expanded": None, "seconds": 0.0},
        "satplan": {"status": sp.status, "length": sp.length, "seconds": round(sp.seconds, 4), "plan": sp.plan,
                    "horizons": [{"T": h.T, "vars": h.n_vars, "clauses": h.n_clauses, "seconds": round(h.solve_seconds, 4),
                                  "sat": h.sat} for h in sp.stats]},
        "gbfs_plan": g.plan,
    }


def add_long(instances: list[dict]) -> list[dict]:
    """Append (or replace) the long-trace set: payments and inventory at sizes 12 and 16 (30-51 events)."""
    out = [i for i in instances if i.get("set") != "long"]
    for name in LONG_FAMILIES:
        fam = FAMILIES[name]
        for variant in VARIANTS:
            for size in LONG_SIZES:
                t0 = time.perf_counter()
                gold = solve_long(name, fam, variant, size)
                reachable = gold["gbfs"]["status"] == "solved"
                assert reachable == (variant != "fixed"), (name, variant, size)
                exact = gold["satplan"]["status"] == "solved"
                shortest = (gold["satplan"]["length"] if exact else gold["gbfs"]["length"]) if reachable else None
                if reachable and name == "inventory":
                    shortest = 3 * size + 3  # as for the stress sizes; GBFS reaches exactly this length
                    assert gold["gbfs"]["length"] == shortest, (name, variant, size, gold["gbfs"]["length"])
                i = {
                    "id": f"sp2-{name}-{variant}-{size}", "family": name, "variant": variant, "size": size,
                    "set": "long", "knob": fam.knob(size), "violation": reachable,
                    "shortest": shortest, "shortest_exact": exact if reachable else None,
                    "design": fam.design(variant, size), "naming": fam.naming(variant, size),
                    "problem": fam.problem(variant, size), "design_facts": list(fam.design_facts[variant]),
                    "certificate": certify(name, variant, size, gold), "gold": gold,
                    "domain": fam.domain, "design_predicates": sorted(design_predicates(name)),
                }
                out.append(i)
                print(f"{i['id']:28s} shortest={shortest}  {time.perf_counter() - t0:.1f}s", flush=True)
    return out


INVARIANT = {
    "inventory": "units are conserved: stock + holding + sold = S in every reachable state, so at most S of "
                 "the S+1 customers can buy",
}


def certify(name: str, variant: str, size: int, gold: dict) -> str | None:
    """How the gold label of a fixed (safe) variant is established."""
    if variant != "fixed":
        return None
    if gold["gbfs"]["status"] == "unsolvable":
        return "GBFS search exhausted the reachable states (Theorem 3)"
    if name in INVARIANT:  # search budget ran out; the label rests on an invariant argument
        return "analytic invariant: " + INVARIANT[name]
    raise AssertionError(f"{name}-{variant}-{size}: fixed variant neither certified by search nor by an invariant")


def refresh_text(instances: list[dict]) -> list[dict]:
    """Regenerate design documents, naming, certificates and opaque copies without re-solving."""
    base = [i for i in instances if i.get("set", "main") != "opaque"]
    for i in base:
        fam = FAMILIES[i["family"]]
        assert i["problem"] == fam.problem(i["variant"], i["size"]), i["id"]
        i["design"] = fam.design(i["variant"], i["size"])
        i["naming"] = fam.naming(i["variant"], i["size"])
        i["certificate"] = certify(i["family"], i["variant"], i["size"], i["gold"])
    return add_opaque(base)


def add_opaque(instances: list[dict]) -> list[dict]:
    """Attach the domain text to every instance and append the opaque-vocabulary copies of the main set."""
    base = [i for i in instances if i.get("set", "main") != "opaque"]
    for i in base:
        i["domain"] = FAMILIES[i["family"]].domain
        i["design_predicates"] = sorted(design_predicates(i["family"]))
    extra = []
    for i in base:
        if i.get("set", "main") != "main":
            continue
        ren = renaming(i["family"])
        o = {k: v for k, v in i.items() if k != "gold"}
        o.update({
            "id": i["id"] + "-opaque", "set": "opaque",
            "domain": opaque_domain(i["family"]), "problem": opaque_text(i["family"], i["problem"]),
            "design_facts": [ren.get(f, f) for f in i["design_facts"]],
            "design_predicates": sorted(ren[p] for p in i["design_predicates"]),
        })
        extra.append(o)
    return base + extra


def write(instances: list[dict]):
    (DATA / "instances.json").write_text(json.dumps({"instances": instances}, indent=1))


if __name__ == "__main__":
    import sys
    if "--augment-only" in sys.argv:
        write(add_opaque(json.loads((DATA / "instances.json").read_text())["instances"]))
    elif "--long" in sys.argv:
        write(add_long(json.loads((DATA / "instances.json").read_text())["instances"]))
    elif "--refresh-text" in sys.argv:
        write(refresh_text(json.loads((DATA / "instances.json").read_text())["instances"]))
    else:
        main()
