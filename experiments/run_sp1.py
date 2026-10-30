"""Run the SP1 arms over the instance set and score every answer.

    python -m experiments.run_sp1 --models haiku,sonnet --arms direct,translate [--limit 10] [--workers 6]

Writes results/sp1/<model>__<arm>.jsonl, one scored record per instance.
LLM responses are cached, so re-running only pays for new calls.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from premortem.llm import LLMAuthError, get_llm  # noqa: E402
from premortem.sp1.arms import run_direct, run_translate  # noqa: E402
from premortem.sp1.benchmarks import BY_NAME  # noqa: E402
from premortem.sp1.score import outcome  # noqa: E402
from premortem.sp1.solve import spec_check  # noqa: E402

OUT = ROOT / "results" / "sp1"


def load_instances():
    return json.loads((ROOT / "data" / "sp1" / "instances.json").read_text())["instances"]


def base_subset(insts, per_bucket: int = 8, seed: int = 3263) -> set:
    """Stratified sample of the base tier: every rare/very-rare bug, and up to
    ``per_bucket`` instances of each other bucket (used for the most expensive model)."""
    import random
    rng = random.Random(seed)
    out = set()
    for b in ("common", "uncommon", "rare", "very_rare", "clean", "equivalent"):
        pool = sorted(i["id"] for i in insts if i["tier"] == "base" and i["bucket"] == b)
        rng.shuffle(pool)
        out |= set(pool if b in ("rare", "very_rare") else pool[:per_bucket])
    return out


def run_one(llm, arm: str, inst: dict) -> dict:
    b = BY_NAME[inst["function"]]
    if arm == "direct":
        r = run_direct(llm, inst, b.params)
    else:
        r = run_translate(llm, inst, b.params, b.name, b.loop_bound)
    rec = r.to_dict()
    rec["outcome"], rec["outcome_detail"] = outcome(rec, inst, b.params, b.reference, b.name)
    rec.update({"function": inst["function"], "kind": inst["kind"], "bucket": inst["bucket"],
                "rarity": inst["rarity"], "op": inst["op"]})
    if arm == "translate" and r.spec and r.tool_status in ("witness", "no_witness", "unknown", "timeout", "incomplete"):
        s = spec_check(b.reference, b.name, r.spec, b.params, b.loop_bound)
        rec["spec_sound"] = {"no_witness": True, "witness": False}.get(s.status)
        rec["spec_unsound_example"] = s.witness
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="haiku")
    ap.add_argument("--arms", default="direct,translate")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--ids", default=None, help="comma-separated instance ids")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--tier", default=None, help="base | hard | subset (stratified base sample) ")
    args = ap.parse_args(argv)

    insts = load_instances()
    if args.tier == "subset":
        insts = [i for i in insts if i["tier"] == "hard" or i["id"] in base_subset(insts)]
    elif args.tier:
        insts = [i for i in insts if i["tier"] == args.tier]
    if args.ids:
        wanted = set(args.ids.split(","))
        insts = [i for i in insts if i["id"] in wanted]
    if args.limit:
        insts = insts[: args.limit]
    OUT.mkdir(parents=True, exist_ok=True)
    for model in args.models.split(","):
        llm = get_llm(model)
        for arm in args.arms.split(","):
            t0 = time.time()
            recs = []
            # processes, not threads: each worker gets its own Z3 context, so spec checks run in parallel
            with ProcessPoolExecutor(max_workers=args.workers) as ex:
                futs = {ex.submit(run_one, llm, arm, inst): inst["id"] for inst in insts}
                for k, f in enumerate(as_completed(futs), 1):
                    try:
                        rec = f.result()
                    except LLMAuthError as e:  # logged out: stop before overwriting results with no-answers
                        ex.shutdown(wait=False, cancel_futures=True)
                        sys.exit(f"{e}\nLog in again (run `claude`, then /login) and rerun; results were not written.")
                    except Exception as e:  # keep the batch going; record the failure
                        rec = {"instance": futs[f], "arm": arm, "model": model, "outcome": "harness_error",
                               "outcome_detail": repr(e)}
                    recs.append(rec)
                    print(f"[{model}/{arm}] {k}/{len(insts)} {rec['instance']}: {rec['outcome']}", file=sys.stderr, flush=True)
            recs.sort(key=lambda r: r["instance"])
            path = OUT / f"{model}__{arm}.jsonl"
            if args.tier and args.tier != "subset":
                path = OUT / f"{model}__{arm}.{args.tier}.partial.jsonl"
            if args.limit or args.ids:
                path = OUT / f"{model}__{arm}.partial.jsonl"
            path.write_text("".join(json.dumps(r) + "\n" for r in recs))
            from collections import Counter
            cost = sum(r.get("llm_cost", 0) for r in recs)
            print(f"== {model}/{arm}: {dict(Counter(r['outcome'] for r in recs))}  cost ${cost:.2f}  {time.time() - t0:.0f}s",
                  file=sys.stderr)


if __name__ == "__main__":
    main()
