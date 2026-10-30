---
title: "AI Pre-Mortems: Can Frontier Models Predict How Code and Systems Fail?"
subtitle: "CS3263 Foundations of Artificial Intelligence, Semester 1 AY2026/27, Project Report (Group 19)"
author:
  - "Yash Raj Khandelwal (A0273647U, e1123050@u.nus.edu)"
  - "Joshua Tan Yu Jie (A0281260M, e1155388@u.nus.edu)"
  - "Hein Htet Zaw (A0301513Y, e1355879@u.nus.edu)"
---

**Summary.** We built a benchmark of 174 buggy and correct functions (SP1) and 150 distributed-system design instances (SP2), with gold models that score every claimed failure exactly. On it we compared Claude
Haiku 4.5, Sonnet 5.5 and Opus 5.5, each answering directly or translating for Z3 / SATPlan / FF.

* *SP1.* Both arms find essentially every bug, independent of trigger rarity, which instead decides whether random testing finds it. No model fabricated a failure on any control.
* *SP2.* The 5.5 models are perfect in both arms up to 27-event traces, even with mechanism names hidden. Haiku's Direct answers misread designs: 60% false alarms on correct designs (95% with hidden names), cut to 35% (45%) by translation.
* *Translation's risks.* Specifications that copy the bug, permissive models that planners exploit, and solver blow-up (state explosion in certification).

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

```{=html}
<div class="pagebreak"></div>
```

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

Both scales rest on $\alpha \models \beta$ iff $\alpha \land \lnot\beta$ is unsatisfiable (PropLogic
p.28, p.35), with $\alpha$ = "the system as implemented" and $\beta$ = "the requirement". A model of
$\alpha \land \lnot\beta$ is a run that breaks the requirement: a *failure witness*. For a contract
$\forall x\,(pre \Rightarrow post)$, the negation is $\exists x\,(pre \land \lnot post)$ (FOL p.12), and
the solver's value for $x$ is the witness (existential instantiation, FOL p.18).

## 2.1 SP1: a function as a CSP, solved by SMT

**CSP.** Each instance is a CSP $(X, D, C)$ (CSP p.7).

* **Variables $X$:** the function's inputs. An integer input is one variable. A list input is a length variable $n$ plus element variables $e_0, \dots, e_{m-1}$, where $m$ is the maximum length.
* **Domains $D$:** the stated ranges, e.g. $1 \le month \le 12$, $0 \le n \le m$, and each $e_i \in [lo, hi]$. Sorted or distinct lists add ordering or inequality constraints.
* **Constraints $C$:** $\llbracket f \rrbracket(x, r) \land \lnot spec(x, r)$, where $\llbracket f \rrbracket(x, r)$ holds iff $r$ is what $f$ returns on $x$.

Intermediate values are shared sub-terms of one formula DAG, which play the role of auxiliary
variables (CSP p.13). The domains are finite, so this is a finite CSP: NP-complete (CSP p.8).

**Building $\llbracket f \rrbracket$: bounded symbolic execution** (`sp1/symexec.py`). The proposal
planned an off-the-shelf executor. We wrote our own because tools such as CrossHair explore paths
under a time budget and report "no counterexample found" rather than proving unsatisfiability within a
bound, which Theorem 1 needs. The executor walks the syntax tree once with a symbolic environment
$\rho$ (variable → Z3 term) and a *path condition* $\pi$ (when control reaches the statement):

| construct | rule |
|---|---|
| `x = e` | $\rho[x] \leftarrow \llbracket e \rrbracket_\rho$ |
| `if c: S1 else: S2` | run S1 from $(\rho, \pi \land c)$ and S2 from $(\rho, \pi \land \lnot c)$, reaching $(\rho_1, \pi_1)$ and $(\rho_2, \pi_2)$; join to $\rho[x] = \mathit{If}(\pi_1, \rho_1[x], \rho_2[x])$ and $\pi = \pi_1 \lor \pi_2$ |
| `return e` | $ret \leftarrow \mathit{If}(\pi, \llbracket e \rrbracket, ret)$, then $\pi \leftarrow \bot$ |
| operation that raises when $b$ (index out of range, `x // 0`, unbound local, …) | $exc \leftarrow exc \lor (\pi \land b)$, then $\pi \leftarrow \pi \land \lnot b$ |
| loop | unrolled $k$ times; iteration $j$ runs under $\pi \land cond_j$; afterwards $unwind \leftarrow unwind \lor (\pi \land cond_k)$ |

`break`/`continue` states re-join like `if`. The result is three terms over $X$: $ret$, $exc$
("raises") and $unwind$ ("needs more than $k$ iterations"). Integers are unbounded and `//`, `%`
follow Python's floor semantics.

**Lemma 1 (encoding correctness).** Let $x_0 \in D$ be an input whose execution needs at most $k$
iterations of every loop. Then:

* $unwind[x_0] = \bot$;
* $exc[x_0] = \top$ iff $f(x_0)$ raises;
* otherwise $ret[x_0] = f(x_0)$.

If the execution needs more than $k$ iterations, $unwind[x_0] = \top$.

*Proof sketch.* Induction over statements, with the invariant: $\pi[x_0] = \top$ iff the concrete run
on $x_0$ reaches this point, and in that case $\rho[x][x_0]$ is the concrete value of $x$.

* Assignment preserves the invariant.
* At an `if` exactly one of $\pi \land c$ and $\pi \land \lnot c$ is true at $x_0$, so the join selects the environment of the branch actually taken.
* `return` and raising operations record the outcome under exactly the path condition of the run that performs them, then disable that path.
* Unrolling reproduces each concrete iteration, and $cond_k$ is true exactly when a $(k{+}1)$-th iteration would start. ∎

**The two queries.** The model-written `pre` and `post` are compiled the same way, unrolled to
$k' = \max(k, L{+}1)$ where $L$ is the longest list input (doubled up to $4k'$ while the coverage
query $\Psi$ below is satisfiable), and $pre(x)$ stands for "returns normally with a true value" (likewise $post$).

$$\Phi_{spec} = D(x) \land \lnot unwind_f \land \lnot unwind_{pre} \land pre(x) \land \big(exc_f \lor (\lnot unwind_{post} \land \lnot post(x, ret_f))\big)$$

$$\Phi_{gold} = D(x) \land \lnot unwind_{ref} \land \lnot unwind_{mut} \land \big((exc_{ref} \oplus exc_{mut}) \lor (\lnot exc_{ref} \land \lnot exc_{mut} \land ret_{ref} \ne ret_{mut})\big)$$

**Theorem 1 (soundness and bounded completeness).** Suppose the *coverage* query
$\Psi = D(x) \land \lnot unwind_f \land \big(unwind_{pre} \lor (pre(x) \land \lnot exc_f \land unwind_{post})\big)$
is unsatisfiable, i.e. on every input within $f$'s bound the spec's own loops fit $k'$. Then:

* $\Phi_{spec}$ is satisfiable iff some $x_0 \in D$ within the bound satisfies $pre$ while $f$ raises or violates $post$. A $pre$ that raises counts as false, and a $post$ that raises counts as violated, exactly as `spec_check` encodes them.
* Every model of $\Phi_{spec}$ is such an $x_0$.

*Proof sketch.* By Lemma 1 on $f$, $pre$ and $post$, each conjunct has its concrete meaning wherever
the relevant function fits its bound; $\lnot\Psi$ says that it does at every input where it is
evaluated. If $\Psi$ is still satisfiable at $4k'$, `spec_check` reports *undecided*, never "no failure". ∎

Equivalently, $\Phi_{spec}$ is unsatisfiable iff $f \models spec$ on all inputs within the bound,
which is the entailment theorem applied to the bounded program. The same argument covers
$\Phi_{gold}$ with "behaves differently from the reference" in place of "violates the spec". UNSAT
therefore means "no failure within the bound", the same caveat as bounded PlanSAT (Planning p.38).
The build checks that no reference loop can exceed its bound, and accepts a mutant as equivalent only
if its domain was enumerated or $unwind_{mut}$ is unsatisfiable.

**The solver.** Z3 [4] is an SMT ("SAT modulo theories") solver, used as a Python library
(`Solver().add(Φ)`, `check()`, `model()`). It decides satisfiability with the DPLL(T) architecture: a
CDCL SAT core (DPLL with clause learning, PropLogic p.35) searches the Boolean skeleton, and
integer-arithmetic theory solvers check each candidate and return conflict clauses. Non-linear terms
(products or moduli of variables) and the 60 s solver limit can make Z3 answer *unknown*, which we
score as *undecided*, never as a correct "no failure".
Every model is re-executed in real Python before it counts. Lemma 1 is also checked empirically: on
every benchmark and hand-written mutant, the symbolic outcome must equal real execution on 25 random
inputs (`tests/test_symexec.py`). Appendix B.1 shows a complete instance and query.

## 2.2 SP2: a design as a STRIPS planning problem

**STRIPS task** (Planning p.7–11). Each family is a typed PDDL domain and each variant/size a
problem; grounding gives $\Pi = (F, A, I, G)$:

* $F$ is the set of ground facts.
* A state $s \subseteq F$ is the set of facts that hold. The closed world assumption makes everything else false.
* $I$ is the initial state: the design facts, e.g. `(dedup-racy)`, the counters `(next-tick t0 t1)`, and the starting situation.
* $G$ is the violation, e.g. `{(charged-twice o1)}`.
* Each action $a \in A$ has $pre(a)$, $add(a)$ and $del(a)$. It is applicable in $s$ iff $pre(a) \subseteq s$, and then $\mathrm{RESULT}(s, a) = (s \setminus del(a)) \cup add(a)$ (Planning p.9).

A plan reaching $s_n \supseteq G$ is a failure trace. For example, `accept-new-racy o1 a1` has
$pre = \{$`dedup-racy`, `in-flight o1 a1`, `no-record o1`$\}$, $add = \{$`approved o1 a1`$\}$ and
$del = \{$`in-flight o1 a1`$\}$. It does *not* delete `no-record o1`, so a second request can pass the
lookup before the first charge records the key.

**Modelling assumptions:** events interleave one at a time; effects are deterministic; the
environment can do exactly the failure events in the domain (loss, delay, pauses, crashes, ticks); and
object counts are finite. The state space is therefore finite. PlanSAT is in PSPACE and NP-hard even
without negative effects (Planning p.38); it is PSPACE-complete [10].

**SATPlan encoding** (Planning p.31–37; `planning/satplan.py`). For horizon $T$: a variable $f^t$ per
fact and step $t \le T$, and $a^t$ per action and step $t < T$, with clauses:

1. **initial state:** $f^0$ for $f \in I$ and $\lnot f^0$ for $f \notin I$;
2. **goal:** $g^T$ for each $g \in G$;
3. **preconditions:** $a^t \Rightarrow p^t$ for each $p \in pre(a)$;
4. **effects:** $a^t \Rightarrow f^{t+1}$ for $f \in add(a)$, and $a^t \Rightarrow \lnot f^{t+1}$ for $f \in del(a) \setminus add(a)$;
5. **explanatory frame axioms:** $f^t \land \lnot f^{t+1} \Rightarrow \bigvee\{a^t : f \in del(a) \setminus add(a)\}$ and $\lnot f^t \land f^{t+1} \Rightarrow \bigvee\{a^t : f \in add(a)\}$;
6. **exactly one action per step:** a cardinality constraint (sequential-counter encoding).

As a sound optimisation, facts that cannot yet be true (or false) at step $t$ become constants, and
actions that cannot yet be applicable get no variable. This uses relaxed layers, which over-approximate
the states reachable in $t$ steps.

**Lemma 2.** Under (6), clauses (4)–(5) are equivalent to the lecture's successor-state axioms
$F^{t+1} \Leftrightarrow ActionCausesF^t \lor (F^t \land \lnot ActionCausesNotF^t)$ (Planning p.34).
*Proof.* Let $a$ be the single action at step $t$.

* If $f \in add(a)$, (4) forces $f^{t+1}$.
* If $f \in del(a) \setminus add(a)$, (4) forces $\lnot f^{t+1}$.
* Otherwise no active action adds or deletes $f$, so both clauses in (5) force $f^{t+1} = f^t$.

Hence $s_{t+1} = \mathrm{RESULT}(s_t, a)$, and (3) makes $a$ applicable in $s_t$. ∎

**Theorem 2.** The horizon-$T$ formula is satisfiable iff a plan of exactly $T$ actions reaches $G$,
and the true action variables of a model form one. Iterating $T = 0, 1, 2, \dots$ returns a *shortest*
failure trace; decoded plans are re-validated. UNSAT for all $T \le T_{max}$ proves only bounded safety.

**Certifying safety: greedy best-first search with $h_{FF}$** (`premortem/planning/search.py`).

$h_{FF}(s)$ is the length of a relaxed plan extracted from the relaxed planning graph with delete lists
ignored (Planning p.28; [7]), or $\infty$ if $G$ is unreachable even in the relaxation. GBFS expands states
in order of $h_{FF}$, never revisits a state, tests for the goal on generation, and discards states with
$h_{FF} = \infty$.

**Theorem 3.** If GBFS returns *unsolvable*, $G$ is unreachable from $I$.
*Proof.* The state space is finite and each state is queued at most once, so the search terminates.
When the queue empties, every generated state has been expanded or discarded and none was a goal. So
any path from $I$ to a goal would have to pass through a discarded state. Discarding is safe: ignoring
delete lists only adds behaviour, so if $G$ is unreachable from $s$ in the relaxation, it is unreachable
from $s$ in the real task. ∎

By the same argument GBFS finds a plan whenever one exists, though not always a shortest one. FF's
enforced hill-climbing is incomplete and could not certify. Every fixed variant has finite $h_{FF}(I)$,
so certification needs the exhaustive search. **Pipeline:** in the Translate arm GBFS decides
reachability on the model's problem; if a plan exists, SATPlan with $T_{max}$ = the GBFS length returns a shortest trace (if its 120 s budget runs out, which happened in 17 inventory runs, the GBFS trace is kept). Appendix B.2–B.3 print real clauses, the horizon iteration and a GBFS certificate.

# 3. Problem instances

## 3.1 SP1: 174 function instances

**Benchmarks.** There are 27 base functions and 10 hard ones.

* *Base:* HumanEval/EvalPlus-style tasks [8] (`below_zero`, `is_prime`, `fizz_buzz`, …) plus business rules (calendar, grade bands, discounts, withdrawals).
* *Hard:* functions where a witness must be *constructed*: sorting networks, comparator medians, sliding-window and token-bucket rate limiters, a debouncer, Luhn, Zeller's congruence, banker's rounding, subset-sum DP.

As planned in the proposal, identifiers are renamed and docstrings rewritten without examples. Each
docstring fully determines the return value on the stated domain, so the docstring *is* the
specification.

**Mutants and labels.** The candidates are:

* 808 automatic first-order mutants (operators ROR, AOR, CRP, LCR, condition negation, range off-by-one, statement deletion);
* 42 hand-written realistic bugs, such as a forgotten 400-year rule, a lost token-bucket remainder, or a comparator dropped as an "optimisation";
* 9 equivalent rewrites.

Each candidate is labelled in four steps. Its *trigger rarity* is the probability that a uniformly
random in-domain input exposes it, computed exhaustively for integer domains up to 70k points and
from 5,000 samples otherwise. $\Phi_{gold}$ is then solved, every Z3 witness is confirmed by real
execution, and equivalence is accepted only under the conditions of §2.1. Rarity buckets are common
(≥10%), uncommon (1–10%), rare (0.1–1%) and very rare (<0.1%).

**Selection.** For each function we keep every hand bug, fill the rarity buckets with automatic mutants
(preferring rare ones), and add two controls: the clean reference, plus an equivalent mutant when one
exists. These are deliberately hard controls; for example, dropping comparator (a, c) leaves a
median-of-5 network correct.

**Result.** 174 instances:

* 115 bugs: 67 common, 19 uncommon, 21 rare, 8 very rare;
* 59 controls: 37 clean, 22 provably equivalent.

Of the 859 candidates, 59 were dropped as non-terminating or not encodable. The median Z3 query took
0.04 s.

## 3.2 SP2: 60 designs, plus 30 stress and 60 opaque variants

| family | violation | flawed | subtle (looks fixed) | fixed | size knob |
|---|---|---|---|---|---|
| payments | charged twice | no deduplication | key looked up, recorded only after the charge | atomic insert-if-absent | timeout 1–7 ticks |
| inventory | sold > stock | read-modify-write stock (lost update) | payment accepted after hold expiry | atomic decrement + hold check | stock 1–4 |
| lock | stale write after newer one | no fencing, no lease check | lease checked just before writing | fencing tokens | lease 1–7 ticks |
| queue | payout twice | no consumer dedup | dedup ids in process memory | dedup id in the same DB transaction | visibility 1–7 |
| cache | cache older than DB at end | update DB, then delete cache | delete cache, then update DB | leases revoked by delete | 1–4 updates |

Each design document (about 200 words) states the components, the failure model and the mechanism
without judging it; subtle variants read like a fix the engineer believes works. Gold shortest traces
are 6–15 events. Two further sets were added:

* *Stress* (sizes 6 and 8): 17–27 events.
* *Opaque:* the main set with design facts and design-specific events renamed (`mode-2`, `accept-3`) and every domain comment that names or describes a mechanism removed. The semantics are unchanged, but "racy" in the text can no longer be matched to `(dedup-racy)` by name.

# 4. Method

**Models.** Claude Haiku 4.5, Sonnet 5.5 and Opus 5.5 with default extended thinking, called through
the Claude Code CLI with *all tools disabled* (so Direct cannot run code). Both arms see the same
inputs:

* SP1: the code with its docstring, plus the input domain.
* SP2: the design document, the family's PDDL domain (the event vocabulary, with comments) and the object names.

**Direct arm.** It returns JSON containing a verdict and a witness: a failing input for SP1, or a list of ground actions for SP2.

**Translate arm, SP1.** The model writes `pre(...)` and `post(..., result)` in the supported Python subset, stating the docstring's intent rather than the code's behaviour. The verifier then runs `spec_check`.

**Translate arm, SP2.** The model writes the PDDL problem: objects, the complete initial state including design facts and counters, and the goal. We parse and validate it, ground it, and run GBFS + h_FF to decide reachability. If a trace exists, SATPlan shortens it to an optimal one, within a 120 s budget.

**Repair loop.** Errors are fed back up to twice: syntax errors, unsupported constructs, a vacuous precondition, a wrong goal, and type or arity errors with VAL-style messages.

**Tool budgets.** Each SP1 spec check has a 120 s in-process deadline and runs in a child process that is killed after 150 s.
Z3 queries time out at 60 s. Planner search is capped at 3 M expansions or 300 s, and SATPlan at 120 s.
A run that hits a budget, a Z3 *unknown* and a failed coverage check ($\Psi$ satisfiable) are all
reported as *undecided*, never as "no failure".

**Scoring** is exact and on gold models.

* SP1 witnesses are executed on the code under review and on the unmutated reference. A witness is valid only if it is in-domain and the two behave differently.
* SP2 traces are replayed on the gold problem; a trace is valid if it reaches the violation.

Outcomes are *valid witness*, *fabricated* (invalid witness, or a false alarm on a control), *miss*,
*correct no-failure*, or *undecided* (the tool gave up; counted as no answer). Every LLM response is cached, so all numbers can be regenerated offline.

<!-- RESULTS -->
