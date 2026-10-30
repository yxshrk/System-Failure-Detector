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

| | Haiku 4.5 Direct | Haiku 4.5 Translate | Sonnet 5.5 Direct / Translate | Opus 5.5 Direct / Translate |
|---|---|---|---|---|
| SP1 bugs found (115) | 114 | 112 | 115 / 114 | 115 / 114 |
| SP1 false alarms (59 controls) | 0 | 0 | 0 / 0 | 0 / 0 |
| SP2 valid traces, main (40) | 31 | 34 | 40 / 40 | 40 / 40 |
| SP2 false alarms, main (20 fixed designs) | 12 | 7 | 0 / 0 | 0 / 0 |
| SP2 false alarms, opaque names (20) | 19 | 9 | 0 / 0 | 0 / 0 |

* **Rarity.** Trigger rarity decides whether random testing finds a bug: 100 random inputs catch 5% of the very rare bugs. It has no effect on either LLM arm.
* **Model generations.** The 5.5 models are perfect on SP2 up to 27-event traces, even with mechanism names hidden. Haiku 4.5's Direct errors come from misreading the design, and translation roughly halves its false alarms.
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
results/              scored records (*.jsonl), tables.md, figures/, llm_cache/ (every LLM response)
report/               report sections (report.md, results.md, discussion.md, tail.md, ...), build.sh -> full.md + report.docx
tests/                symbolic executor vs real Python, planner tests, gold-model properties
```

## Reproducing

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                      # 200 tests
.venv/bin/python -m premortem.sp1.build            # ~40 s, 10 processes
.venv/bin/python -m premortem.sp2.build            # ~35 min (SATPlan/GBFS on the large inventory sizes)
.venv/bin/python -m experiments.run_sp1 --models haiku,sonnet,opus
.venv/bin/python -m experiments.run_sp2 --models haiku,sonnet,opus
.venv/bin/python -m experiments.analyze            # results/tables.md, results/figures/*.png
.venv/bin/python -m experiments.encodings > report/encodings.md   # Appendix B: the real Z3 / SATPlan encodings
```

LLM calls go through the Claude Code CLI in headless mode (`claude -p --tools ""`), so the models cannot execute code in either arm. Every response is cached under `results/llm_cache/`, keyed by a hash of the model, system prompt and prompt, so the analysis can be re-run offline at no cost.

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

- [ ] **Open-weight models via SoCLaaS.** Add an OpenAI-compatible backend to `premortem/llm.py`, then run both arms on a subset (SP2 main, SP1 hard tier, base sample). Translation is expected to matter most for weaker models; so far only Haiku 4.5 shows a gap.
- [ ] **Review the code, the instances and the report** (`report/*.md`).
- [ ] **Rewrite §8 "Division of work"** to state each member's actual contributions and how AI tools were used (required by the guidelines).
- [ ] **Presentation:** 15 minutes, in the week of 9 Nov.
