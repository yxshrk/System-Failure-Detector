"""Build SP2 gold instances: problem, design document, shortest trace, solver stats.

Run:  python -m premortem.sp2.build
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..planning import bfs, gbfs, ground, parse_domain, parse_problem, satplan
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
                    "gold": gold,
                })
                print(f"{instances[-1]['id']:28s} shortest={instances[-1]['shortest']}  {time.perf_counter() - t0:.1f}s", flush=True)
    write(add_opaque(instances))


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
    else:
        main()
