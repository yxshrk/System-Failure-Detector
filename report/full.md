---
title: "AI Pre-Mortems: Can Frontier Models Predict How Code and Systems Fail?"
subtitle: "CS3263 Foundations of Artificial Intelligence, Semester 1 AY2026/27, Project Report (Group 19)"
author:
  - "Yash Raj Khandelwal (A0273647U, e1123050@u.nus.edu)"
  - "Joshua Tan Yu Jie (A0281260M, e1155388@u.nus.edu)"
  - "Hein Htet Zaw (A0301513Y, e1355879@u.nus.edu)"
---

**Summary.** We built a benchmark of 174 buggy and correct functions (SP1) and 150 distributed-system
designs (SP2), with gold models that score every claimed failure exactly. On it we compared Claude
Haiku 4.5, Sonnet 5.5 and Opus 5.5, each answering directly or translating for Z3 / SATPlan / FF.

* *SP1.* Both arms find essentially every bug, independent of trigger rarity, which instead decides whether random testing finds it. No model fabricated a failure on any control.
* *SP2.* The 5.5 models are perfect in both arms up to 27-event traces. Haiku's Direct answers misread designs: 55% false alarms on correct designs, cut to 20% by translation. When names give no hints, Opus Direct also fails where Opus Translate does not.
* *Translation's risks.* Specifications that copy the bug, permissive models that planners exploit, and solver blow-up (state explosion in certification).

# 1. Motivation and research questions

A *pre-mortem* asks how a design will fail before it ships. Failures that matter are often reachable
only through rare inputs or long event interleavings: model checking at AWS found a DynamoDB
data-loss bug whose shortest trace had 35 steps, after it had passed design review, code review and
testing [1]. An AI assistant for code and design review is therefore valuable only if it can produce
*witnesses*, i.e. concrete failing inputs or event traces, and only if it does not fabricate failures
that do not exist.

The GenAI lecture poses the question this project explores: "When should you use LLM reasoning
directly? When should you translate problem specification then call tool?" (GenAI p.31). We compare
two arms on the same inputs:

* **(A) Direct.** The model reads the code (or design document) and answers with a verdict and a witness.
* **(B) Translate.** The model writes a formal specification, and a classical solver searches for the witness. Solver errors are fed back for repair, as in Logic-LM [9] and in the LLM+SMT method of the CSP lecture [5].

We study two scales. In **SP1** the object is one function and the witness is a failing input. In
**SP2** the object is a distributed-system design and the witness is a failure trace. A third
sub-problem, **SP3**, scores the translations themselves.

* **RQ1.** Which arm finds more *valid* failure witnesses, and does the gap widen with trigger rarity (SP1) and with shortest-trace length (SP2)?
* **RQ2.** Which arm fabricates more failures on correct controls?

# 2. Formulation

Both scales reduce to one course idea: *system ⊨ spec iff system ∧ ¬spec is unsatisfiable*
(PropLogic p.28, p.35; R&N Ch. 7 [3]). Any model of system ∧ ¬spec lies in M(system) \ M(spec) and
is a failure. For a contract ∀x (pre(x) ⇒ post(x, f(x))), the negation is ∃x (pre(x) ∧ ¬post(x, f(x))),
and existential instantiation (FOL p.18) yields the concrete failing input.

## 2.1 SP1: CSP/SMT over a bounded program

**Variables and domains.** The CSP variables (X, D, C) (CSP p.7) are the function's inputs, with finite
domains stated in the task, plus intermediate values. Integers range over intervals. A list is a
symbolic length n ∈ [min, max] together with `max` element variables. Sorted or distinct lists add
ordering constraints.

**Constraints.** The code's semantics comes from our bounded symbolic executor (`premortem/sp1/symexec.py`),
which compiles a Python subset into Z3 terms. It merges paths instead of forking them: both sides of a
symbolic branch are executed and the variable environments are joined with If(c, a, b). Each
program point carries an *alive* condition (its path condition), so `return`, `break`, `continue` and
exceptions simply shrink it. The formula therefore grows linearly in program size × unrolling depth,
avoiding the exponential path explosion of classic forking symbolic execution. Python semantics are
modelled exactly where it matters: floor division and modulo on negatives, `IndexError` on symbolic
indices, `UnboundLocalError`, `None` on some paths only, and short-circuit `and`/`or`.

**Bounds.** Loops over symbolic ranges and `while` loops are unrolled k times. Paths that would need
more iterations are collected in an *unwind* condition that is assumed false, so an UNSAT answer means
"no failure within the bounds", the same caveat as bounded PlanSAT (Planning p.38).

**Queries.**

* Gold labels: `diff_check` asks whether ∃x ∈ D with outcome(mutant, x) ≠ outcome(reference, x).
* Arm B: `spec_check` asks whether ∃x ∈ D with pre(x) ∧ (raises(f, x) ∨ ¬post(x, f(x))).

Z3 decides both. Finite-domain CSP is NP-complete (CSP p.8), and SAT is NP-complete (Planning p.31).

**Executor correctness.** It is tested differentially against real Python on every benchmark and
hand mutant: 25 random inputs each, with return values and exceptions compared (`tests/test_symexec.py`).
While building the instance set it caught one soundness bug of its own, a missing
`UnboundLocalError` model, which an assertion detected when Z3 called a mutant "equivalent" but random
testing disagreed.

## 2.2 SP2: STRIPS planning over a design

Each design family is a STRIPS domain (Planning p.7–12).

* **Fluents** are system state, e.g. `(waiting o1 a0)` or `(record o1)`.
* **Actions** are events from every actor: client sends and retries, network loss, server steps, timer ticks, crashes, lease expiry.
* **Goal** is a violation fluent such as `(charged-twice o1)`.
* **Timers** are STRIPS counters, e.g. `(next-tick t0 t1)`.

Variants of one family differ *only* in nullary design facts in the initial state, such as
`(dedup-racy)` versus `(dedup-atomic)`. The design text therefore determines a small set of facts
that the translation must get right.

Two solvers are used:

* **SATPlan** (Planning p.31–37) for the shortest failure trace. Our encoding uses fluent and action variables per step, a fully specified initial state, precondition and effect axioms, explanatory frame axioms, and exactly one action per step, with planning-graph-style layer pruning. The horizon is iterated T = 0, 1, … up to T_max.
* **Greedy best-first search with h_FF** (relaxed planning graph, Hoffmann & Nebel [7]; R&N §11.3) with a closed list, for *certification*. FF's own enforced hill-climbing is incomplete, so we use a complete search: when the open list empties, the violation is provably unreachable in the model.

We built every fixed variant so that the violating action stays reachable in the delete relaxation (h_FF(init) is finite). Proving a fix therefore needs exhaustive search, not a static check. Both PlanSAT and bounded PlanSAT are in PSPACE, and both stay NP-hard even without negative effects (Planning p.38). Bylander (1994) shows PlanSAT is PSPACE-complete.

# 3. Problem instances

## 3.1 SP1: 174 function instances

**Benchmarks.** We use 27 base functions and 10 hard functions.

* *Base*: HumanEval/EvalPlus-style tasks [8] such as `below_zero`, `has_close_elements`, `is_prime`, `fizz_buzz` and rolling max, plus business rules (calendar, grade bands, volume discount, account withdrawal).
* *Hard*: functions where a witness must be *constructed* rather than read off the changed line. These are sorting networks, median selection by comparators, sliding-window and token-bucket rate limiters, a button debouncer, the Luhn checksum, Zeller's congruence, banker's rounding, and subset-sum DP.

Following the contamination mitigation in the proposal, identifiers are renamed and every docstring is
rewritten. Docstrings contain no examples, and each one fully determines the return value on the stated
domain, so the docstring *is* the specification.

**Mutants.**

* *Automatic*: the classic first-order operators (ROR, AOR, CRP, LCR, condition negation, range off-by-one, statement deletion) give 808 candidates.
* *Hand-written*: 42 realistic bugs, such as a hard-coded capacity, a window-limited dedupe, a forgotten 400-year rule, a lost refill remainder, and a comparator dropped as an "optimisation".
* *Rewrites*: 9 pieces of equivalent code that looks suspicious.

**Labelling each candidate.**

1. *Rarity*: we measure trigger rarity, the probability that a uniformly random in-domain input exposes the bug. It is computed exhaustively for integer domains up to 70k points and from 5,000 samples otherwise.
2. *Z3 check*: we run `diff_check`.
3. *Confirmation*: every Z3 witness is confirmed by real execution.
4. *Equivalence*: a mutant is an equivalent control only if Z3 proves equivalence and either the domain was enumerated or no path exceeds the unrolling bound.

Non-terminating mutants are excluded. Rarity buckets are common (≥10%), uncommon (1–10%), rare (0.1–1%)
and very rare (<0.1%).

**Selection.** Per function we keep all hand bugs and fill the rarity buckets with automatic mutants, preferring rare ones and operator diversity. We add two controls per function: the clean reference, and an equivalent mutant or rewrite when one exists. Equivalent mutants are deliberately hard controls; for example, removing comparator (a, c) from the 5-input network leaves the median unchanged.

**Result.** 174 instances: 115 bugs (42 hand-written and 73 automatic; 67 common, 19 uncommon, 21 rare,
8 very rare) and 59 controls (37 clean, 22 provably equivalent). Of the 859 candidates, 728 were bugs,
72 were equivalent and 59 were dropped (non-terminating or not encodable). The median Z3 equivalence
query took 0.04 s.

## 3.2 SP2: 60 design instances, plus 30 stress and 60 opaque-vocabulary variants

| family | violation | flawed | subtle (looks fixed) | fixed | size knob |
|---|---|---|---|---|---|
| payments | card charged twice | provider never deduplicates | idempotency key looked up, recorded only after the charge (check-then-act race) | atomic insert-if-absent reservation | client timeout 1–7 ticks |
| inventory | more sales than stock | read-modify-write stock update (lost update) | atomic decrement, but payment accepted after the hold expired | atomic decrement + payment checks hold | stock and hold length 1–4 |
| lock | stale write applied after newer holder's | no fencing, no lease check | lease checked right before writing (pause after check) | fencing tokens | lease 1–7 ticks |
| queue | payout performed twice | no consumer dedup | dedup ids in process memory (lost on crash) | dedup id written in the same DB transaction | visibility timeout 1–7 |
| cache | cache older than DB after all writes | update DB then delete cache | delete cache then update DB | leases revoked by delete | 1–4 sequential updates |

Each instance comes with a design document of roughly 250 words. It describes the components, the
failure model (loss, delay, pauses, crashes) and the mechanism, without judging it. The subtle variants
are written the way an engineer would describe a fix they believe works. Gold shortest traces have 6–15
events.

Two further sets probe RQ1 and validity. The *stress* set (sizes 6 and 8) lengthens the shortest
violation to 17–27 events. In the *opaque* set the main instances are rewritten so that design facts and
design-specific events have neutral names (`mode-2`, `accept-3`) and no comments. Semantics are
unchanged, but a model can no longer map "racy" in the text to `(dedup-racy)` by word matching.

# 4. Method

**Model access.** Both arms call the same models: Claude Haiku 4.5, Sonnet 5.5 and Opus 5.5, with their
default extended thinking. Calls go through the Claude Code CLI in headless mode with *all tools
disabled* and the system prompt replaced, so the Direct arm cannot run code. Arms see identical
information:

* SP1: the code with its docstring, plus the input domain.
* SP2: the design document, the family's PDDL domain (the event vocabulary, with comments) and the object names.

**Direct arm.** It returns JSON containing a verdict and a witness: a failing input for SP1, or a list of ground actions for SP2.

**Translate arm, SP1.** The model writes `pre(...)` and `post(..., result)` in the supported Python subset, stating the docstring's intent rather than the code's behaviour. The verifier then runs `spec_check`.

**Translate arm, SP2.** The model writes the PDDL problem: objects, the complete initial state including design facts and counters, and the goal. We parse and validate it, ground it, and run GBFS + h_FF to decide reachability. If a trace exists, SATPlan shortens it to an optimal one.

**Repair loop.** Errors are fed back up to twice: syntax errors, unsupported constructs, a vacuous precondition, a wrong goal, and type or arity errors with VAL-style messages.

**Tool budgets.** Each SP1 spec check runs in a child process that is killed after 150 s, reported as
a *checker timeout*. Z3 queries time out at 60 s. Planner search is capped at 3 M expansions or 300 s,
and SATPlan at 120 s.

**Scoring** is exact and on gold models.

* SP1 witnesses are executed on the code under review and on the unmutated reference. A witness is valid only if it is in-domain and the two behave differently.
* SP2 traces are replayed on the gold problem; a trace is valid if it reaches the violation.

Outcomes are *valid witness*, *fabricated* (invalid witness, or a false alarm on a control), *miss*, or
*correct no-failure*. Every LLM response is cached, so all numbers can be regenerated offline.



# 5. Results

All numbers come from `experiments/analyze.py`; the full tables are in `results/tables.md`. Brackets
give 95% Wilson intervals. "Fabricated" means a claimed witness that does not reproduce on the gold
model.

## 5.1 SP1: functions (174 instances; 115 bugs, 59 controls)

| model | arm | base bugs found (95) | hard bugs found (20) | fabricated | false alarms (59 controls) | checker timeouts | $/instance | output tokens |
|---|---|---|---|---|---|---|---|---|
| Haiku 4.5 | Direct | 100% [96–100] | 95% [76–99] | 0 | 0 | – | 0.025 | 4,838 |
| Haiku 4.5 | Translate | 98% [93–99] | 95% [76–99] | 1 | 0 | 0 | 0.026 | 4,968 |
| Sonnet 5.5 | Direct | 100% | 100% | 0 | 0 | – | 0.009 | 431 |
| Sonnet 5.5 | Translate | 100% | 95% | 0 | 0 | 1 | 0.008 | 208 |
| Opus 5.5 | Direct | 100% | 100% | 0 | 0 | – | 0.018 | 470 |
| Opus 5.5 | Translate | 100% | 95% | 0 | 0 | 2 | 0.021 | 383 |

*Table 1.* SP1 outcomes. The Translate arm's repair loop matters here: using only the first
specification, valid witnesses drop to 106/115 (Haiku), 113/115 (Sonnet) and 104/115 (Opus). Opus in
particular often reached for unsupported constructs first.

The Direct arm's token cost tracks difficulty: hard-tier answers cost 2–3× the base-tier ones for every
model.

**RQ1 (SP1).** Every model finds a valid witness for essentially every bug, in both arms and on both
tiers, and the rate does not depend on trigger rarity (Fig. 1). Random testing on the same bugs depends
on rarity sharply. With 100 random inputs it catches 34% of the rare bugs and 5% of the very rare ones;
with 1,000 inputs, 93% and 36%. Rarity is therefore a property that defeats *testing*, not code
*reading* or symbolic search.

**RQ2 (SP1).** No model raised a single false alarm in either arm on the 59 controls. That includes
the 22 equivalent mutants built to look buggy, such as a 5-input sorting network with a different but
still valid comparator, or a median network with a provably redundant comparator removed. A Direct
"no bug" is an unverifiable claim, yet it was right every time here.

**Where the SP1 failures are.** Every Translate failure traces back to the specification or to the
tool, never to the search.

* Two Haiku misses come from postconditions that copied the code's bug (§A.2).
* One fabricated witness comes from a spec that raised an exception (§A.3).
* The remaining no-answers are checker timeouts on the subset-sum DP, where the model's own DP specification made symbolic execution blow up. These are reported separately as *tool timeouts*.

![Fig. 1: SP1 base tier. Bugs with a valid witness vs. trigger rarity: both LLM arms (pooled over the three models) against random testing with 100 and 1,000 uniform inputs.](../results/figures/sp1_rarity.png){width=78%}

## 5.2 SP2: designs (60 main + 30 stress + 60 opaque instances)

| model | arm | main: valid traces (40) | main: false alarms (20) | stress: valid (20) | stress: false alarms (10) | opaque: valid (40) | opaque: false alarms (20) | $/instance (main) |
|---|---|---|---|---|---|---|---|---|
| Haiku 4.5 | Direct | 80% [65–90] | 55% [34–74] | 80% | 60% | 62% | 85% | 0.063 |
| Haiku 4.5 | Translate | 82% [68–91] | **20%** [8–42] | 90% | **10%** | 68% | **40%** | 0.050 |
| Sonnet 5.5 | Direct | 100% | 0% | 100% | 0% | 100% | 0% | 0.024 |
| Sonnet 5.5 | Translate | 100% | 0% | 100% | 0% | 100% | 0% | 0.017 |
| Opus 5.5 | Direct | 100% | 0% | 100% | 0% | 100% | **15%** | 0.047 |
| Opus 5.5 | Translate | 100% | 0% | 100% | 0% | 100% | 0% | 0.036 |

*Table 2.* SP2 outcomes. "Valid" = a trace that replays on the gold problem and reaches the violation
(flawed + subtle designs). "False alarm" = a violation claimed on a fixed design.

**RQ1 (SP2).** For Sonnet 5.5 and Opus 5.5, trace length does not matter in either arm: every trace
was valid, from 6 events up to the 27-event stress instances (Fig. 2). Haiku's valid rate stays near
80% with no clear trend from 6 to 27 events. Its errors point to *design misreading* rather than an
inability to carry a long trace (Table 3). Translate's gain for Haiku is concentrated on the fixed
designs. Paired over all 150 SP2 instances, Haiku is correct in 46 cases where only Translate is right
and in 20 where only Direct is right (per-set exact McNemar p = 0.15, 0.09 and 0.06; small samples).

**RQ2 (SP2).** Fabrication separates the arms.

* **Haiku.** Direct claims a violation on 55% of the fixed designs (60% on the stress set). Translate cuts this to 20% (10%).
* **Opaque vocabulary.** With descriptive names removed, Haiku Direct's false-alarm rate rises to 85%. Opus Direct produces its only errors of the study: three false alarms on the durable-dedup queue design, where it applied the in-memory mechanism. Opus Translate, with the same inputs, is perfect.

| failure cause (Direct traces that do not replay) | Haiku main | Haiku opaque | Opus opaque |
|---|---|---|---|
| uses an event of *another* design variant | 16 | 30 | 3 |
| vocabulary / arity error | 1 | 1 | 0 |

*Table 3.* Every failing Direct trace that reached a precondition check failed on a design fact: the
model reasoned about the wrong mechanism, typically the familiar failure pattern (§A.4).

**SP3 (translation quality).**

* *Sonnet and Opus.* On the main and stress sets, both reproduced the gold initial state exactly in all 90 problems. On the opaque set they omitted one fact in 8/60 problems. That fact (`pay-checks-hold`) appears in no action's precondition, so the problems remain semantically equivalent to gold.
* *Haiku.* The design facts were exact in 52/60 main problems and 32/60 opaque ones. The non-design errors were permissive initial facts, such as a lease clock already running, which the planner exploited (§A.5).
* *Repair loop.* Only 1 of the 450 SP2 translations needed a repair to parse, so in SP2 every error that mattered was semantic.

![Fig. 2: SP2 valid traces vs. shortest violating-trace length (main + stress sets). Sonnet 5.5 and Opus 5.5 are at 100% throughout.](../results/figures/sp2_length.png){width=95%}

**Cost.**

* *Translate is cheaper on SP2 for every model.* Writing a problem file takes about 500 output tokens for Sonnet and Opus, against about 1,200 for a Direct trace. The search is done by the planner.
* *Haiku spends 10–15k tokens per Direct answer and is still the least accurate.* Thinking volume did not buy correctness.
* *Total usage.* Across both sub-problems it was US$57 list-price equivalent for 1,999 calls (Haiku $28, Opus $20, Sonnet $9), including pilots.

## 5.3 The classical tools

* *SATPlan* finds every shortest trace in milliseconds for four families. On inventory, where symmetric customers interleave, it needs 1.1 s at size 3 and about 2 minutes at size 4, and it times out (300 s) at sizes 6 and 8.
* *GBFS with h_FF* finds a violating trace within a few dozen expansions, though not always the shortest one (29 events where 21 suffice on inventory size 6). It also proves the fixed designs safe.
* *Certification scales with the reachable state space* (Fig. 3): 9,026 expansions for inventory size 4, 2.7 M (177 s) for size 6. At size 8 our 3 M-expansion / 5-minute budget runs out, so that design cannot be certified. Every Translate run on it therefore returned "no violation found within the search limit", not a proof.

![Fig. 3: Certifying the fixed designs. Left: SATPlan exhausting T ≤ 40 (main sizes). Right: states expanded by complete GBFS with h_FF, including the stress sizes (log scale).](../results/figures/solver_scaling.png){width=95%}


# 6. Analysis and insights

**SP1: localisation, not search.** A first-order mutant leaves a visible diff against a docstring that
states the intent, and reading code is white-box. Trigger rarity, which decides whether *testing* finds
a bug, therefore has no effect on either LLM arm (Fig. 1).

The hard tier forces the witness to be *constructed*, for example a permutation that a broken sorting
network mis-sorts. Instead of failing, every model paid 2–3× more output tokens. This matches the
lecture's reading of Kang et al. (GenAI p.18): when candidates are easy to generate and to check, a
chain of thought stays short enough. Our functions are small enough that the linearised search fits.

**SP1: translation moves the risk into the specification.** The spec must state the docstring's intent
while the model is looking at code that contradicts it. Twice the postcondition inherited the bug
(§A.2), and once a broken spec produced a fabricated witness (§A.3). Both are invisible to the solver,
which is faithful to the spec.

The repair loop fixes form, not meaning. Valid witnesses using only first specifications vs. after
repairs are Haiku 106 → 112 and Opus 104 → 114 of 115, but the verifier has no ground truth to repair
against. Specs should be written blind to the code, or checked against known input/output pairs. Three
subset-sum specs also made bounded symbolic execution blow up past 150 s: the tool has its own limits.

**SP2: the jagged frontier runs between model generations.** The 5.5 models are perfect in both arms on
the main and stress sets. Haiku's Direct errors are not slips in long traces. Every failing trace that
reached a precondition check failed on a *design fact* (Table 3): a well-known failure pattern applied
to a design whose text rules it out (§A.4).

Translation does not remove misreading; Haiku moves the same mistake into the design facts it writes.
It also adds permissive initial states that the planner exploits (§A.5). But translation helps the
weaker model in three ways:

* *Fewer false alarms:* 55% → 20% (main), 60% → 10% (stress) and 85% → 40% (opaque).
* *Inspectable errors:* a wrong design fact is one line in a problem file, while a wrong Direct trace is a narrative of 10–27 steps.
* *Lower cost:* the planner, not the model, does the search.

**Length vs. familiarity.** Up to 27 events, trace length did not affect the 5.5 models, and Haiku shows
no length trend. Our violations are textbook patterns; once the pattern is recognised, a longer trace is
bookkeeping. The opaque ablation is where a frontier model cracked. With design facts renamed `mode-N`,
Opus Direct mapped "ids recorded in the same database transaction" to the in-memory mode and raised
three false alarms. Opus Translate, with identical inputs, was perfect: writing the initial state forces
a commitment to one design fact per mechanism, which free-form reasoning skips.

**Where the tools hit their limits (Fig. 3).**

* SATPlan iterates the horizon, so certifying the size-4 inventory fix takes 42 s (T ≤ 40), against 9,026 GBFS expansions. Its 15-event trace takes about 2 minutes, against 15 expansions.
* Exhaustive certification explodes with symmetric customers: 2.7 M expansions at size 6, and beyond our budget at size 8.
* Bounded symbolic execution silently excludes paths beyond the unroll bound.

The known remedies are outside this course: symmetry and partial-order reduction (TLC, SPIN), unwinding
assertions (CBMC), and k-induction. On the size-8 inventory a Direct "safe" is unverifiable too; the
difference is that the tool says "unknown".

**Is translating worth it?**

* *Direct suffices* when the specification is local and explicit, the artefact small and the model strong: SP1 at every tier, and SP2 for the 5.5 models with descriptive names. It never fabricated an SP1 witness, and its "no bug" answers were right on all 59 controls.
* *Translate pays off* when a weaker model must be used (Haiku's false alarms fell by about two-thirds), when the vocabulary gives no hints (the only arm in which Opus made no errors), and when a *guarantee* is required. A solver certificate with an audit trail is something Direct cannot provide.
* *Its weaknesses* are specification correctness (anchoring, permissive models) and the tools' state-space and term-size limits.

Direct accuracy on problems of this size will keep rising, as the step from Haiku 4.5 to the 5.5 models
shows. But "computationally difficult problems [are] likely to remain difficult" (GenAI p.31). Our
largest designs did not reach that regime for the 5.5 models; the size-8 inventory did for the tools.

**Threats to validity.**

* *Mutants.* They are small, first-order faults [13]; real bugs often span several lines.
* *Specifications.* Docstrings are complete specifications; vaguer real ones would hurt Translate more.
* *Familiarity.* The SP2 families are textbook patterns, and the opaque ablation removes lexical cues but not conceptual familiarity; novel designs would be a stronger test.
* *Scaffolding.* Both arms get the event model, which in practice must itself be written, an error-prone step (Planning p.15).
* *Sampling.* Each instance is sampled once. We report Wilson intervals and exact McNemar tests, but many cells are at ceiling.


# 7. Responsible AI

**Automation bias and what "no failure" means.** A verdict from either arm is a belief about a model,
not a fact about the world (ProbGrapModel p.4).

* SP1 Translate certifies only within the list capacities and the unrolling bound. Code that needs more iterations is excluded, not checked; our `is_prime` control with `d + d <= n` runs past the 16-unroll bound on large inputs.
* SP2 certifies only within the family's event model. A failure mode the domain does not contain is invisible to both arms.

We therefore report bounded verdicts in the form "no counterexample within k steps under assumptions X",
never "verified safe". Wording matters: the Decision lecture's certainty and framing effects
(Decision p.24–25) predict that reviewers over-trust the first. Whether to skip manual review is a
maximum-expected-utility decision (Decision p.15–16, 31). Accepting is rational only if
P(hidden failure | "no failure") < review cost / incident loss, and for payments or locks the loss term
dominates. Our data gives that posterior directly. On the SP2 main set, 2 of Haiku Direct's 11 "safe"
verdicts were wrong (18%), while all 16 of Haiku Translate's were right. Both figures depend on our
base rate of flawed designs, which Bayes' rule (ProbGrapModel p.24–25) makes explicit.

**Fabricated failures.** A false alarm costs reviewer time and, repeated, teaches reviewers to ignore
the tool. This is a precision/recall operating point to be chosen by stakes, like the fairness–accuracy
Pareto frontier (ResponsibleAI p.18–19). A Translate witness is correct *with respect to the model's
own specification* by construction. It is still a fabrication if that specification is wrong: seven of
Haiku's SP2 Translate traces were legal only in its mistranslated problem. A Translate pipeline can
also miss a failure because the spec copied the bug. Witnesses should therefore always be executed or
replayed on the real artefact before anyone acts on them, as our scoring does.

**Accountability and auditability.** The Translate arm leaves an audit trail: the spec or problem
file, the solver log and the witness. This is close to a white-box explanation (ResponsibleAI p.24),
and it lets a named engineer sign off on *what was checked*. Direct answers are black-box narratives
whose stated reasoning is at best a post-hoc explanation (ResponsibleAI p.25–26). The DeLLMa result
in the Decision lecture (p.36) makes the same argument for structured pipelines. Responsibility for
shipping stays with the humans who sign off (ResponsibleAI p.6).

**Dual use.** A failing input is an adversarial example by another name (ResponsibleAI p.27, 30). The
same pipeline that finds a double-charge trace for a defender produces an exploit for an attacker, and
AI lowers the cost and raises the scale of such attacks (ResponsibleAI p.2–4). Mitigations we would
adopt: run only on code and designs the user owns, follow coordinated disclosure, and do not publish raw
witnesses for deployed, unpatched systems. The reviewer itself is an attack surface too (ResponsibleAI
p.31). A comment planted in code under review could steer the Direct arm towards "no bug". The
Translate arm is less exposed, because the solver, not the model, decides, but the specification is
still model-written.

**Privacy.** Sending proprietary code or designs to a hosted model discloses them, and renaming
identifiers does not anonymise (ResponsibleAI p.10). On-premise open-weight models avoid this.

# 8. Division of work and use of AI tools

* **Yash Raj Khandelwal (leader):** coordination; SP2 design families, design documents and gold models; planning toolkit integration (SATPlan, GBFS/h_FF certification, gold replay); experiment runs; report.
* **Joshua Tan Yu Jie:** SP1 benchmark functions and mutants; symbolic executor and Z3 pipeline; rarity estimation and instance construction.
* **Hein Htet Zaw:** LLM harness and prompts; Direct/Translate arms and repair loop; SP3 scoring; analysis and figures.
* **All:** analysis, responsible AI, review of every component.

**AI assistance.** Claude Code (Anthropic) was used as a programming assistant to implement parts of
the code base: the planning toolkit, the symbolic executor and the experiment harness. It was also used
to draft parts of this report from our design decisions and measured results. Every number in this report is produced by the scripts in
the repository from cached model outputs. The research questions, formulations, design families and
evaluation protocol follow our proposal.


# References

[1] C. Newcombe, T. Rath, F. Zhang, B. Munteanu, M. Brooker, M. Deardeuff. How Amazon Web Services uses formal methods. *Communications of the ACM*, 58(4), 2015.

[2] L. Kang, Z. Zhao, D. Hsu, W. S. Lee. On the empirical complexity of reasoning and planning in LLMs. *Findings of EMNLP*, 2024.

[3] S. Russell, P. Norvig. *Artificial Intelligence: A Modern Approach*, 4th ed. Pearson, 2021. Ch. 6 (CSP), Ch. 7 (logical agents), Ch. 11 (planning), Ch. 16 (decisions).

[4] L. de Moura, N. Bjørner. Z3: An efficient SMT solver. *TACAS*, 2008.

[5] Y. Hao, Y. Chen, Y. Zhang, C. Fan. Large language models can solve real-world planning rigorously with formal verification tools. *NAACL*, 2025.

[6] H. Kautz, B. Selman. Planning as satisfiability. *ECAI*, 1992.

[7] J. Hoffmann, B. Nebel. The FF planning system: Fast plan generation through heuristic search. *Journal of Artificial Intelligence Research*, 14, 2001.

[8] J. Liu, C. S. Xia, Y. Wang, L. Zhang. Is your code generated by ChatGPT really correct? Rigorous evaluation of large language models for code generation (EvalPlus). *NeurIPS*, 2023.

[9] L. Pan, A. Albalak, X. Wang, W. Y. Wang. Logic-LM: Empowering large language models with symbolic solvers for faithful logical reasoning. *Findings of EMNLP*, 2023.

[10] T. Bylander. The computational complexity of propositional STRIPS planning. *Artificial Intelligence*, 69, 1994.

[11] L. Guan, K. Valmeekam, S. Sreedharan, S. Kambhampati. Leveraging pre-trained large language models to construct and utilize world models for model-based task planning. *NeurIPS*, 2023 (Planning lecture p.15).

[12] J. C. King. Symbolic execution and program testing. *Communications of the ACM*, 19(7), 1976.

[13] R. Just, D. Jalali, L. Inozemtseva, M. D. Ernst, R. Holmes, G. Fraser. Are mutants a valid substitute for real faults in software testing? *FSE*, 2014.

[14] M. Kleppmann. How to do distributed locking. Blog post, 2016 (the fencing-token argument used in the lock family).

Course material: CS3263 lecture slides (PropLogic, CSP, FirstOrderLogic, Planning, GenerativeReasoningAgenticAI, Decision, ProbGrapModel, ResponsibleAI), cited as *Deck p.N*.


# Appendix A. Worked examples (from the cached runs)

**A.1 A rare SP1 bug found by both arms.** In `days_in_month`, mutant `400 → 399` inside the leap-year
helper changes the result only for February of years divisible by 399 but not by 4 or 400. Its trigger
rarity is 0.019%. Every model, in both arms, produced a valid witness. Random testing with 1,000 inputs
finds it with probability 17%.

**A.2 Specification anchoring (Translate, Haiku 4.5).** For the mutant `y % 400 == 0 → y % 400 != 0`,
the model was asked to specify the *docstring*. Instead its postcondition re-implemented the code's
leap test, bug included:

```python
def leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 != 0)   # copied from the code under review
```

Because the specification agrees with the bug, Z3 correctly reports "no violation", and the bug is
missed. The `withdraw` miss is the same pattern: the spec's `new_balance <= 0` copies the mutated
boundary. In both cases the soundness check (does the *reference* satisfy the spec?) fails, so the
error is detectable whenever a trusted reference exists. It is not detectable in deployment.

**A.3 A fabricated SP1 witness from a wrong specification (Translate, Haiku 4.5).** For `weekday`,
the model specified the answer via Sakamoto's algorithm but indexed its month table with `m - 1` after
shifting January to month 13. That raises `IndexError` for January and February. Our verifier treats an
exception in `post` as a violation, so it returned 1 January 1801, on which the code is correct.

**A.4 A false alarm on a fixed design (Direct, Haiku 4.5).** For `payments-fixed-1` (atomic
insert-if-absent), the model's 8-step trace uses `accept-new-racy`. That event belongs to the racy
variant, and its precondition `(dedup-racy)` is false in this design. The model recognised the
well-known check-then-act race and applied it to a design that explicitly rules it out. Replay on the
gold problem fails at step 2.

**A.5 The planner exploits translation slack (Translate, Haiku 4.5).** In `lock-flawed-3` the model's
problem file declared `(lease-age t0)` in the initial state, i.e. a lease clock running before anyone
holds the lock. SATPlan's shortest trace starts with `(tick t0 t1)`, which is legal only in the model's
problem, so replay on the gold problem fails at step 1. In `queue-flawed-1` an extra `(zero-tick t1)`
let the planner skip the visibility timeout. Classical planners are adversarial towards their model:
every over-permissive fact becomes a shortcut.

**A.6 Gold shortest trace for `payments-subtle-1` (SATPlan, 8 events).**
`send o1 a0 t0` → `tick o1 a0 t0 t1` → `time-out-and-retry o1 a0 a1 t1` → `accept-new-racy o1 a0` →
`send o1 a1 t0` → `accept-new-racy o1 a1` → `charge o1 a1` → `charge-again o1 a0`.

In words: the first request is delayed past the client's timeout. Both the original and the retry pass
the idempotency lookup before either charge has written the record.
