# How the implementation maps to the approved proposal

This file checks each commitment in `docs/CS3263_Project_Proposal.pdf` (submitted 28 Sep 2026) against what
the repository does. ✅ = done as proposed; ➕ = done, and extended beyond the proposal;
⚠️ = deviation (justified in the report); ⏳ = not done yet.

## Research questions

| Proposal | Implementation | Status |
|---|---|---|
| **RQ1:** which arm finds more valid failure witnesses, and does the gap widen with trigger rarity (SP1) and shortest-trace length (SP2)? | Valid-witness rates per arm and model; SP1 broken down by measured trigger rarity (`build.py`), SP2 by gold shortest trace (SATPlan). Report §5, Fig. 1–2. | ✅ |
| **RQ2:** which arm fabricates more failures on correct controls? | False alarms on 59 SP1 controls (clean and equivalent) and on all fixed SP2 designs; invalid witnesses also counted. | ✅ |

## Formulation (proposal §2)

| Proposal | Implementation | Status |
|---|---|---|
| *system ⊨ spec* iff *system ∧ ¬spec* is unsatisfiable (PropLogic) | Report §2, used for both scales | ✅ |
| **SP1:** CSP/SAT with variables = inputs and intermediates; constraints = code semantics ∧ ¬spec; loops unrolled to k | `sp1/symexec.py` + `sp1/solve.py`; Lemma 1 / Theorem 1 in §2.1 | ✅ |
| SP1 code semantics via **off-the-shelf** symbolic execution | **Own bounded symbolic executor.** Off-the-shelf tools (e.g. CrossHair) explore paths under a time budget and report "no counterexample found" rather than proving bounded UNSAT, which Theorem 1 needs. Checked against real Python by differential tests. | ⚠️ |
| SP1 solver: Z3, as in the CSP lecture's LLM+SMT example | Z3 5.3 via `z3-solver` | ✅ |
| **SP2:** STRIPS/PDDL; fluents = state; actions = events (send, drop, retry, crash); goal = violation fluent such as ChargedTwice(o) | `sp2/families.py` (5 typed PDDL domains), `planning/` toolkit; goal `(charged-twice o1)` etc. | ✅ |
| SP2 solvers: SATPlan T = 1…T_max for the shortest trace; forward search with FF's heuristic to certify fixed variants | `planning/satplan.py`; `planning/search.py` GBFS + h_FF. Complete GBFS, because FF's own hill-climbing is incomplete and cannot certify. Theorems 2–3. | ✅ |
| Complexity: finite CSP NP-complete; PlanSAT PSPACE | §2 | ✅ |

## Instances

| Proposal | Implementation | Status |
|---|---|---|
| SP1: benchmark functions [EvalPlus] with injected bugs, plus clean controls | 27 HumanEval/EvalPlus-style functions, **rewritten** (renamed identifiers, new docstrings) as the contamination mitigation; 808 automatic mutants + 42 hand-written bugs; clean controls | ✅ |
| (not in proposal) | Hard tier (10 functions needing constructed witnesses); **provably equivalent mutants** as hard controls; trigger-rarity measurement | ➕ |
| SP2: payments, inventory, cache, lock, queue, one domain each; flawed, fixed, subtly wrong; several sizes | Exactly these five families × 3 variants × sizes 1–4 = 60 designs, each with a design document | ✅ |
| (not in proposal) | Stress sizes 6 and 8 (17–27-event traces); long set, sizes 12 and 16 for payments and inventory (30–51 events, 5.5 models only); opaque-vocabulary ablation | ➕ |

## SP3: translation scored separately

| Proposal | Implementation | Status |
|---|---|---|
| SP1: model writes pre/postconditions; *sound* = reference satisfies them; *discriminating* = mutant violates them | Soundness via `spec_check(reference, spec)` (`run_sp1.py`); discriminating = valid witness on the mutant | ✅ |
| SP2: variants differ only in design facts that the model extracts; scored against gold facts | Variants differ only in design facts (test `test_variants_differ_only_in_design_facts`); `translation_scores` compares design facts and the full initial state with gold | ✅ |

## Approach and evaluation (proposal §3)

| Proposal | Implementation | Status |
|---|---|---|
| (A) Direct: verdict + witness (SP2 traces in the family's event vocabulary) | `sp1/arms.py run_direct`, `sp2/arms.py run_direct`; tools disabled so the model cannot execute code | ✅ |
| (B) Translate: model writes the specification; solver searches; solver errors fed back for repair | Up to 2 repairs with verifier/VAL-style messages | ✅ |
| Identical inputs to both arms (code or design text; in SP2 also the family domain) | Same code+docstring+domain (SP1); same design doc + PDDL domain + object names (SP2) | ✅ |
| Exact scoring on gold models: inputs run against the unmutated reference; traces replayed on the gold PDDL problem; outcomes valid / fabricated / miss / correct no-failure | `sp1/score.py`, `sp2/score.py` | ✅ |

## Responsible AI (proposal §4)

Automation bias ("no failure" only within the bound or model), accountability, dual use: all in report §7,
plus fabricated failures, attacks on the reviewer and privacy. ✅➕

## Milestones and risks (proposal §6)

| Proposal | Status |
|---|---|
| M0 SP1 Direct with execution scoring; M1 SP1 Translate (Z3); M2 SP2 for two families, both solvers; M3 more families, model tiers, cross-scale analysis, draft report | ✅ (all five families; three Claude tiers) |
| Risk (iii) contamination: rename identifiers, rewrite docstrings | ✅ + opaque ablation |
| Risk (iv) tool limits: keep supported functions, report coverage | ✅ 59 unencodable/non-terminating candidates dropped and reported; checker timeouts, Z3 *unknown* and incomplete spec coverage reported as *undecided*, never as "no bug"; planner search limits reported as *tool limit*, never as "safe" |
| Risk (v) solver blow-up: cap bounds, report time-outs | ✅ SATPlan/GBFS limits reported (inventory sizes 6–8) |
| Risk (vi) cost: SoC open-weight endpoint; ≤ $100 for frontier tiers | Frontier tiers done (≈ $80 list-price equivalent, incl. pilots, reruns and the long set). **SoC open-weight models** ⏳ |
| Division of work as proposed | ⏳ report §8 must be rewritten to reflect actual contributions and AI use |
