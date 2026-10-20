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

<!-- RESULTS -->
