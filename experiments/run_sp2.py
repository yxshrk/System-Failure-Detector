"""Run the SP2 arms over the design instances and score every answer.

    python -m experiments.run_sp2 --models haiku --arms direct,translate [--ids ...] [--workers 6]

Writes results/sp2/<model>__<arm>.jsonl.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from premortem.llm import LLMAuthError, get_llm  # noqa: E402
from premortem.sp2.arms import run_direct, run_translate  # noqa: E402
from premortem.sp2.score import outcome, translation_scores  # noqa: E402

OUT = ROOT / "results" / "sp2"


def load_instances():
    return json.loads((ROOT / "data" / "sp2" / "instances.json").read_text())["instances"]


def run_one(llm, arm, inst):
    r = run_direct(llm, inst) if arm == "direct" else run_translate(llm, inst)
    rec = r.to_dict()
    rec["outcome"], rec["outcome_detail"] = outcome(rec, inst)
    rec.update({k: inst[k] for k in ("family", "variant", "size", "violation", "shortest")})
    if arm == "translate":
        rec["sp3"] = translation_scores(inst, r.problem)
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="haiku")
    ap.add_argument("--arms", default="direct,translate")
    ap.add_argument("--ids", default=None)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args(argv)
    insts = load_instances()
    if args.ids:
        wanted = set(args.ids.split(","))
        insts = [i for i in insts if i["id"] in wanted]
    OUT.mkdir(parents=True, exist_ok=True)
    for model in args.models.split(","):
        llm = get_llm(model)
        for arm in args.arms.split(","):
            t0 = time.time()
            recs = []
            with ProcessPoolExecutor(max_workers=args.workers) as ex:  # searches are CPU-bound Python
                futs = {ex.submit(run_one, llm, arm, i): i["id"] for i in insts}
                for k, f in enumerate(as_completed(futs), 1):
                    try:
                        rec = f.result()
                    except LLMAuthError as e:  # logged out: stop before overwriting results with no-answers
                        ex.shutdown(wait=False, cancel_futures=True)
                        sys.exit(f"{e}\nLog in again (run `claude`, then /login) and rerun; results were not written.")
                    except Exception as e:
                        rec = {"instance": futs[f], "arm": arm, "model": model, "outcome": "harness_error",
                               "outcome_detail": repr(e)}
                    recs.append(rec)
                    print(f"[{model}/{arm}] {k}/{len(insts)} {rec['instance']}: {rec['outcome']}", file=sys.stderr, flush=True)
            recs.sort(key=lambda r: r["instance"])
            path = OUT / (f"{model}__{arm}.partial.jsonl" if args.ids else f"{model}__{arm}.jsonl")
            path.write_text("".join(json.dumps(r) + "\n" for r in recs))
            cost = sum(r.get("llm_cost", 0) for r in recs)
            print(f"== {model}/{arm}: {dict(Counter(r['outcome'] for r in recs))}  cost ${cost:.2f}  {time.time() - t0:.0f}s",
                  file=sys.stderr)


if __name__ == "__main__":
    main()
