# AI Pre-Mortems: can frontier models predict how code and systems fail?

CS3263 Foundations of AI, Semester 1 AY2026/27, Project Group 19
(Yash Raj Khandelwal, Joshua Tan Yu Jie, Hein Htet Zaw)

We compare two ways of using a frontier LLM as a pre-mortem reviewer:

* **Direct**: the model reads the code or design document and outputs a failure witness (a failing input, or a failure event trace).
* **Translate**: the model writes a formal specification and a classical solver searches for the witness, with solver errors fed back for repair.

Both scales use the same course idea: *system ⊨ spec* iff *system ∧ ¬spec* is unsatisfiable, so any satisfying assignment is a failure witness.

| | SP1: one function | SP2: one design |
|---|---|---|
| question | does some input violate the docstring? | does some event sequence reach a violation? |
| formulation | CSP/SMT: inputs and intermediates are variables, the code is constraints (bounded symbolic execution), conjoined with ¬spec | STRIPS planning: fluents are system state, actions are events, the goal is a violation fluent |
| solver | Z3 | SATPlan (shortest trace) plus complete GBFS with h_FF (certifies fixes) |
| instances | 27 base and 10 hard functions; 115 confirmed bugs and 59 controls (clean or provably equivalent) | 5 design families × {flawed, subtle, fixed} × 4 sizes = 60 designs |
| SP3 (translation quality) | is the model's spec sound (the reference satisfies it)? | do the model's initial state and design facts match gold? |

Scoring is exact. A witness counts only if it reproduces on the gold model: a failing input must make the code differ from the unmutated reference, and a trace must replay on the gold PDDL problem.

## Results at a glance

| | Haiku 4.5 Direct | Haiku 4.5 Translate | Sonnet 5.5 Direct / Translate | Opus 5.5 Direct / Translate | Qwen 3.8 27B Direct / Translate | Llama 3.1 8B Direct / Translate |
|---|---|---|---|---|---|---|
| SP1 bugs found (115) | 114 | 112 | 115 / 114 | 115 / 114 | 114 / 113 | 40 / 31 |
| SP1 false alarms (59 controls) | 0 | 0 | 0 / 0 | 0 / 0 | 0 / 0 | 45 / 12 |
| SP2 valid traces, main (40) | 31 | 34 | 40 / 40 | 40 / 40 | 37 / 40 | 0 / 1 |
| SP2 false alarms, main (20 fixed designs) | 12 | 7 | 0 / 0 | 0 / 0 | 0 / 0 | 14 / 2 |
| SP2 false alarms, opaque names (20) | 19 | 9 | 0 / 0 | 0 / 0 | not run | 18 / 8 |

Qwen 3.8 27B and Llama 3.1 8B are open-weight models served by SoCLaaS; Qwen ran SP1 and the SP2 main set only.

* **Rarity.** Trigger rarity decides whether random testing finds a bug: 100 random inputs catch 5% of the very rare bugs. Direct, for Claude and Qwen, found every rare and very rare bug. Translate fell slightly behind as bugs got rarer (29/32 vs 32/32 model–bug pairs on very rare bugs), but those three misses come from two bugs, so treat it as a hint.
* **Model generations.** The 5.5 models are perfect on SP2 up to 51-event traces (long set: payments and inventory at sizes 12 and 16), even with mechanism names hidden. Haiku 4.5's Direct errors come from misreading the design, and translation roughly halves its false alarms.
* **Open-weight models.** Qwen 3.8 27B matches the 5.5 models (its 3 Direct misses on SP2 are format slips). Llama 3.1 8B fabricates in Direct; Translate cuts its false alarms, but only because its specs and problem files are unusable or incomplete, so it answers "safe" or nothing.
* **Translation's own failure modes.** Specifications can copy the bug, permissive problem files get exploited by the planner, and checkers time out. Certification also explodes on the symmetric inventory design: 2.7 M states at size 6, beyond budget at size 8.

Full tables are in `results/tables.md` and figures in `results/figures/`. The report draft is `report/full.md`, with a Word export at `report/report.docx`.

## Layout

```
premortem/
  llm.py              Claude CLI backend (tools disabled), response cache
  parsing.py          JSON / code-block extraction
  sp1/
    symexec.py        bounded symbolic executor: Python subset -> Z3 (path merging, loop unrolling)
    domain.py         finite input domains (the CSP variable domains)
    solve.py          Z3 queries: diff_check (gold), spec_check (Translate arm)
    concrete.py       step-limited real execution for exact scoring
    benchmarks.py     37 functions (HumanEval/EvalPlus-style, renamed, rewritten docstrings)
    mutate.py         first-order mutation operators (ROR, AOR, CRP, LCR, NEG, RNG, SDL)
    build.py          mutant pool -> trigger rarity + Z3 labels -> instance set
    arms.py, score.py Direct / Translate arms and exact scoring
  planning/           STRIPS toolkit: PDDL parser, grounding, VAL-style validator, SATPlan, GBFS/h_FF, BFS, A*
  sp2/
    families.py       5 design families: PDDL domain, problem generator, design document
    build.py          gold problems, shortest traces, solver statistics
    arms.py, score.py Direct / Translate arms, gold replay, SP3 scores
experiments/          run_sp1.py, run_sp2.py, analyze.py, encodings.py (prints the exact solver inputs)
data/                 generated instance sets (sp1/instances.json, sp2/instances.json)
results/              scored records (*.jsonl), tables.md, figures/, llm_cache/ (every LLM response, one JSONL per model)
report/               report sections (report.md, results.md, discussion.md, tail.md, ...), build.sh -> full.md + report.docx
tests/                symbolic executor vs real Python, planner tests, gold-model properties
```

## Reproducing

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                      # 207 tests
.venv/bin/python -m premortem.sp1.build            # ~40 s, 10 processes
.venv/bin/python -m premortem.sp2.build            # ~35 min (SATPlan/GBFS on the large inventory sizes)
.venv/bin/python -m premortem.sp2.build --long     # append the long-trace set (sizes 12, 16), ~2 min
.venv/bin/python -m experiments.run_sp1 --models haiku,sonnet,opus
.venv/bin/python -m experiments.run_sp2 --models haiku,sonnet,opus
.venv/bin/python -m experiments.analyze            # results/tables.md, results/figures/*.png
.venv/bin/python -m experiments.encodings > report/encodings.md   # Appendix B: the real Z3 / SATPlan encodings
```

LLM calls go through the Claude Code CLI in headless mode (`claude -p --tools ""`), so the models cannot execute code in either arm. Every response is cached in `results/llm_cache/<model>.jsonl`, keyed by a hash of the model, system prompt and prompt, so the experiments can be re-run offline at no cost: set `PREMORTEM_CACHE_ONLY=1` to guarantee no model is called (for `soc:` models also set `SOCLAAS_BASE_URL` to any value).

## Contributing (group notes)

**Setup.** You need Python 3.12+ and, for new LLM runs, the Claude Code CLI (`claude`) logged in.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m experiments.analyze     # rebuilds tables and figures from the cached runs
bash report/build.sh                        # report sections -> report/full.md + report/report.docx
```

All model answers are cached in `results/llm_cache/`, so re-running the experiments only calls a model
for prompts that are new.

**Open items**

- [x] **Open-weight models via SoCLaaS.** Qwen 3.8 27B and Llama 3.1 8B ran through `OpenAICompatible` in `premortem/llm.py` (§4–6 of the report). To rerun or add a model (NUS network or VPN; key from the [SoCLaaS guide](https://dochub.comp.nus.edu.sg/cf/guides/soclaas/start)):

  ```bash
  export SOCLAAS_BASE_URL=https://soclaas-api.comp.nus.edu.sg/v1 SOCLAAS_API_KEY=<key>
  .venv/bin/python -m premortem.llm --list                       # model ids the endpoint serves
  .venv/bin/python -m experiments.run_sp1 --models soc:<model-id> --workers 4
  .venv/bin/python -m experiments.run_sp2 --models soc:<model-id> --workers 4
  ```

  Results land in `results/sp*/soc-<model-id>__<arm>.jsonl`; add the model to `MODEL_ORDER` in `experiments/analyze.py`. Keep total workers around 10: the endpoint drops requests it cannot start within a minute and rejects more with HTTP 429, and the backend waits and resubmits both. Reasoning models need the 32k-token budget; Qwen 3.8 takes 5–10 minutes per SP2 answer.
- [ ] **Review the code, the instances and the report** (`report/*.md`).
- [x] **§8 "Division of work"** states each member's actual contributions (matching the git history) and AI use per component.
- [ ] **Presentation:** 15 minutes, in the week of 9 Nov.
