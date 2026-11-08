---
title: "AI Pre-Mortems: Can Frontier Models Predict How Code and Systems Fail?"
subtitle: "CS3263 Foundations of Artificial Intelligence, Semester 1 AY2026/27, Project Report (Group 19)"
author:
  - "Yash Raj Khandelwal (A0273647U, e1123050@u.nus.edu)"
  - "Joshua Tan Yu Jie (A0281260M, e1155388@u.nus.edu)"
  - "Hein Htet Zaw (A0301513Y, e1355879@u.nus.edu)"
---

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

```{=html}
<div class="pagebreak"></div>
```

**Summary.** On 174 functions (SP1) and 162 designs (SP2), scored exactly on gold models, we compare
Claude Haiku 4.5, Sonnet 5.5 and Opus 5.5, and the open-weight Qwen 3.8 27B and Llama 3.1 8B,
answering directly or translating for Z3, SATPlan and GBFS.
For every model except Llama, SP1 is at ceiling for both arms at every trigger rarity, with no false alarms. In SP2 the 5.5 models
find a valid trace every time in both arms, up to 51 events and even with mechanism names hidden, with no false alarms,
and Qwen does so in Translate;
translation cuts Haiku's false alarms on correct designs from 60% to 35% (95% to 45% with hidden names; nominal paired
p = 0.002, as designs share five templates).
Llama 3.1 8B fabricates in Direct (no valid SP2 trace; false alarms on 76% of SP1 controls). Translation silences it
rather than fixing it: its specifications and problem files are mostly unusable or incomplete, so it answers "safe" or nothing.
Translation's risks are specs that copy the bug, permissive models that planners exploit, and solver blow-up.

# 1. Motivation and research questions

A *pre-mortem* asks how a design will fail before it ships. Failures that matter are often reachable
only through rare inputs or long event interleavings: model checking at AWS found a DynamoDB
data-loss bug whose shortest trace had 35 steps, after it had passed design review, code review and
testing [1]. An AI assistant for code and design review is therefore valuable only if it can produce
*witnesses*, i.e. concrete failing inputs or event traces, and only if it does not fabricate failures
that do not exist.

The GenAI lecture asks: "When should you use LLM reasoning
directly? When should you translate problem specification then call tool?" (GenAI p.31). We compare
two arms on the same inputs:

* **(A) Direct.** The model reads the code (or design document) and answers with a verdict and a witness.
* **(B) Translate.** The model writes a formal specification, and a classical solver searches for the witness (GenAI p.14). Solver errors are fed back for repair, as in Logic-LM [9] (PropLogic p.3) and the LLM+SMT method of the CSP lecture [5] (CSP p.17–18).

Arm B is the course's case for a factored formulation (CSP p.6, p.12): once the structure is explicit,
a general solver prunes what unstructured reasoning must enumerate.

In **SP1** the object is one function and the witness a failing input; in **SP2** it is a
distributed-system design and the witness a failure trace; **SP3** scores the translations themselves.

* **RQ1.** Which arm finds more *valid* failure witnesses, and does the gap widen with trigger rarity (SP1) and with shortest-trace length (SP2)?
* **RQ2.** Which arm fabricates more failures on correct controls?

# 2. Formulation

Both scales rest on $\alpha \models \beta$ iff $\alpha \land \lnot\beta$ is unsatisfiable (PropLogic
p.28, p.35; [3] Ch. 7), with $\alpha$ = "the system as implemented" and $\beta$ = "the requirement". A model (PropLogic p.11) of
$\alpha \land \lnot\beta$ is a run that breaks the requirement: a *failure witness*. For a contract
$\forall x\,(pre \Rightarrow post)$, the negation is $\exists x\,(pre \land \lnot post)$ (FOL p.12), and
the solver's satisfying assignment to $x$ is the witness.

## 2.1 SP1: a function as a CSP, solved by SMT

**CSP.** Each instance is a CSP $(X, D, C)$ (CSP p.7).

* **Variables $X$:** the function's inputs. An integer input is one variable. A list input is a length variable $n$ plus element variables $e_0, \dots, e_{m-1}$, where $m$ is the maximum length.
* **Domains $D$:** the stated ranges, e.g. $1 \le month \le 12$, $0 \le n \le m$, and each $e_i \in [lo, hi]$. Sorted or distinct lists add ordering or inequality constraints.
* **Constraints $C$:** $\llbracket f \rrbracket(x, r) \land \lnot spec(x, r)$, where $\llbracket f \rrbracket(x, r)$ holds iff $r$ is what $f$ returns on $x$.

The result $r$ and intermediate values are not separate variables: each is a shared sub-term of one formula DAG, fixed by
the inputs, i.e. an auxiliary variable already eliminated (CSP p.13). The domains are finite, so this is
a finite CSP, a class that is NP-complete (CSP p.8). Z3, however, receives SMT over unbounded integers
(`Int`) with the bounds as ordinary constraints; products of variables and `//` or `%` by a variable
make it non-linear integer arithmetic, undecidable in general. Our bounded queries are decidable, but
Z3's non-linear procedures are incomplete, so it can answer *unknown* (§5.1); a bit-vector encoding would
reduce each query to SAT, at the cost of proving that no value overflows.

**Building $\llbracket f \rrbracket$: bounded symbolic execution** [12] (`sp1/symexec.py`). The proposal
planned an off-the-shelf executor. We wrote our own because tools such as CrossHair explore paths
under a time budget and report "no counterexample found" rather than proving unsatisfiability within a
bound, which Theorem 1 needs. The executor walks the syntax tree once with a symbolic environment
$\rho$ (variable → Z3 term) and a *path condition* $\pi$ (when control reaches the statement).
`x = e` sets $\rho[x] \leftarrow \llbracket e \rrbracket_\rho$. `if c` runs both branches, from $(\rho, \pi \land c)$ and
$(\rho, \pi \land \lnot c)$, and joins them with $\rho[x] = \mathit{If}(\pi_1, \rho_1[x], \rho_2[x])$ and $\pi = \pi_1 \lor \pi_2$
(`break`/`continue` likewise). `return e` sets $ret \leftarrow \mathit{If}(\pi, \llbracket e \rrbracket, ret)$ and $\pi \leftarrow \bot$. An
operation that raises when $b$ (bad index, `x // 0`, …) sets $exc \leftarrow exc \lor (\pi \land b)$ and $\pi \leftarrow \pi \land \lnot b$. A
loop is unrolled $k$ times, iteration $j$ under $\pi \land cond_j$, then $unwind \leftarrow unwind \lor (\pi \land cond_k)$. The
result is three terms over $X$: $ret$, $exc$ ("raises") and $unwind$ ("needs more than $k$ iterations"). Integers are unbounded and `//`, `%`
follow Python's floor semantics. Lists are values: aliasing (`ys = xs; ys.sort()`) is not modelled.

**Lemma 1 (encoding correctness).** For $f$ in the supported, alias-free subset, let $x_0 \in D$ be an input whose execution needs at most $k$
iterations of every loop. Then $unwind[x_0] = \bot$; $exc[x_0] = \top$ iff $f(x_0)$ raises; and otherwise
$ret[x_0] = f(x_0)$. If the execution needs more than $k$ iterations, $unwind[x_0] = \top$.

*Proof sketch.* Induction over statements, with the invariant: $\pi[x_0] = \top$ iff the concrete run
on $x_0$ reaches this point, and then $\rho[x][x_0]$ is the concrete value of $x$. Assignment preserves it;
at an `if` exactly one branch condition holds at $x_0$, so the join selects the branch taken; `return`
and raising operations record the outcome under the run's path condition; and $cond_k$ marks a $(k{+}1)$-th
iteration. ∎

**The two queries.** The model-written `pre` and `post` are compiled the same way, unrolled to
$k' = \max(k, L{+}1)$ where $L$ is the longest list input (doubled up to $4k'$ while the coverage
query $\Psi$ below is satisfiable), and $pre(x)$ stands for "returns normally with a true value" (likewise $post$).

$$\Phi_{spec} = D(x) \land \lnot unwind_f \land \lnot unwind_{pre} \land pre(x) \land \big(exc_f \lor (\lnot unwind_{post} \land \lnot post(x, ret_f))\big)$$

$$\begin{aligned}\Phi_{gold} = {} & D(x) \land \lnot unwind_{ref} \land \lnot unwind_{mut} \\ & \land \big((exc_{ref} \oplus exc_{mut}) \lor (\lnot exc_{ref} \land \lnot exc_{mut} \land ret_{ref} \ne ret_{mut})\big)\end{aligned}$$

**Theorem 1 (soundness and bounded completeness).** Suppose the *coverage* query
$\Psi = D(x) \land \lnot unwind_f \land \big(unwind_{pre} \lor (pre(x) \land \lnot exc_f \land unwind_{post})\big)$
is unsatisfiable, i.e. on every input within $f$'s bound the spec's own loops fit $k'$. Then $\Phi_{spec}$
is satisfiable iff some $x_0 \in D$ within the bound satisfies $pre$ while $f$ raises or violates $post$ (a
$pre$ that raises counts as false, a $post$ that raises as violated), and every model is such an $x_0$.

*Proof sketch.* By Lemma 1 on $f$, $pre$ and $post$, each conjunct has its concrete meaning wherever
the relevant function fits its bound; $\lnot\Psi$ says that it does at every input where it is
evaluated. If $\Psi$ is still satisfiable at $4k'$, `spec_check` reports *undecided*, never "no failure". ∎

Equivalently, $\Phi_{spec}$ is unsatisfiable iff $f \models spec$ on all inputs within the bound: the
entailment theorem applied to the bounded program. The same argument covers $\Phi_{gold}$ with "behaves
differently from the reference" for "violates the spec". The build checks that no reference loop can exceed its bound, and accepts a mutant as equivalent only
if its domain was enumerated or $unwind_{mut}$ is unsatisfiable.

**The solver.** Z3 [4], an SMT ("SAT modulo theories") solver, decides satisfiability with DPLL(T): a
DPLL core (PropLogic p.35) with conflict-directed backjumping (CSP p.40–41) searches the Boolean
skeleton, and integer theory solvers return conflicts (clause learning is beyond the slides [4]). Every
model is re-executed in Python before it counts, and Lemma 1 is tested: on every benchmark and
hand-written mutant, the symbolic outcome must equal real execution on 25 random inputs
(`tests/test_symexec.py`). Appendix B.1 shows a full instance.

## 2.2 SP2: a design as a STRIPS planning problem

**STRIPS task** (Planning p.7–11). Each family is a typed PDDL domain and each variant/size a
problem; grounding (propositionalization, FOL p.17–19; up to $K^V$ instances per schema, Planning p.10)
gives $\Pi = (F, A, I, G)$:

* $F$ is the set of ground facts; a state $s \subseteq F$ is the set of facts that hold (closed world assumption).
* $I$ is the initial state: design facts such as `(dedup-racy)`, counters `(next-tick t0 t1)` and the starting situation. $G$ is the violation, e.g. `{(charged-twice o1)}`.
* Each action $a \in A$ has $pre(a)$, $add(a)$ and $del(a)$. It is applicable in $s$ iff $pre(a) \subseteq s$, and then $\mathrm{RESULT}(s, a) = (s \setminus del(a)) \cup add(a)$ (Planning p.9).

A plan reaching $s_n \supseteq G$ is a failure trace. For example, `accept-new-racy o1 a1` does *not*
delete `no-record o1`, so a second request can pass the lookup before the first charge records the key
(B.2 lists its $pre$, $add$ and $del$).

**Modelling assumptions:** events interleave one at a time; effects are deterministic and
unconditional, preconditions and goals positive; the environment can do exactly the failure events in
the domain (loss, delay, pauses, crashes, ticks); object counts, hence states, are finite. PlanSAT is
PSPACE-complete [10] (NP-hard even without negative effects, Planning p.38); each SATPlan call decides
*bounded* PlanSAT for one horizon $T$, which is NP-complete for $T$ polynomial in the task size [10].

**What a plan means here.** The planner chooses *every* event, including loss, crashes and ticks, so a
plan is a counterexample, not a course of action: planning serves as explicit-state model checking of a
**safety** property. Liveness failures (an order never confirmed, starvation) are not STRIPS goals and are
out of scope. "Safe" covers the instance at its size, not every size; we rely on the small-scope
hypothesis [15], that most flaws already appear in small instances, and on an inductive invariant
where search runs out (inventory from size 8, §6).

**SATPlan encoding** [6] (Planning p.31–37; `planning/satplan.py`). For horizon $T$: a variable $f^t$ per
fact and step $t \le T$, and $a^t$ per action and step $t < T$, with CNF clauses (PropLogic p.46):

1. **initial state:** $f^0$ for $f \in I$ and $\lnot f^0$ for $f \notin I$;
2. **goal:** $g^T$ for each $g \in G$;
3. **preconditions:** $a^t \Rightarrow p^t$ for each $p \in pre(a)$;
4. **effects:** $a^t \Rightarrow f^{t+1}$ for $f \in add(a)$, and $a^t \Rightarrow \lnot f^{t+1}$ for $f \in del(a) \setminus add(a)$;
5. **explanatory frame axioms:** $f^t \land \lnot f^{t+1} \Rightarrow \bigvee\{a^t : f \in del(a) \setminus add(a)\}$ and $\lnot f^t \land f^{t+1} \Rightarrow \bigvee\{a^t : f \in add(a)\}$;
6. **exactly one action per step:** the lecture's exclusion axioms (Planning p.36) strengthened from at most to exactly one, encoded in linear size (sequential counter) instead of pairwise.

As a sound optimisation, facts that cannot yet be true (or false) at step $t$ become constants and
actions that cannot yet apply get no variable (relaxed layers over-approximate
reachability).

**Lemma 2.** Under (6), clauses (4)–(5) are equivalent to the lecture's successor-state axioms
$F^{t+1} \Leftrightarrow ActionCausesF^t \lor (F^t \land \lnot ActionCausesNotF^t)$ (Planning p.34).
*Proof.* Let $a$ act at step $t$. If $f \in add(a)$, (4) forces $f^{t+1}$; if
$f \in del(a) \setminus add(a)$, (4) forces $\lnot f^{t+1}$; otherwise no active action adds or deletes $f$,
so (5) forces $f^{t+1} = f^t$. Hence $s_{t+1} = \mathrm{RESULT}(s_t, a)$, with $a$ applicable by (3). ∎

**Theorem 2.** The horizon-$T$ formula is satisfiable iff a plan of exactly $T$ actions ends in a state
containing $G$, and the true action variables of a model form one. Iterating $T = 0, 1, 2, \dots$ up to the
first satisfiable $T$ returns a *shortest* failure trace, so a violation is caught at the first step it holds,
even if a later action would undo it; decoded plans are re-validated. UNSAT for all $T \le T_{max}$ proves only bounded safety.

**Certifying safety: greedy best-first search with $h_{FF}$** (`planning/search.py`). $h_{FF}(s)$ is the length of a relaxed plan for the task with delete lists ignored (Planning p.28), extracted
from layered reachability (FF's relaxed planning graph [7], beyond the slides), or $\infty$ if $G$ is unreachable even in the relaxation. GBFS expands states
in order of $h_{FF}$, never revisits one, tests for the goal on generation, and discards states with
$h_{FF} = \infty$.

**Theorem 3.** If GBFS returns *unsolvable*, $G$ is unreachable from $I$.
*Proof.* The state space is finite and each state is queued at most once, so the search terminates.
When the queue empties, every generated state has been expanded or discarded and none was a goal. So
any path from $I$ to a goal would have to pass through a discarded state. Discarding is safe: ignoring
delete lists only adds behaviour, so if $G$ is unreachable from $s$ in the relaxation, it is unreachable
from $s$ in the real task. ∎

By the same argument GBFS finds a plan whenever one exists, though not always a shortest one ($h_{FF}$
is inadmissible, Planning p.25); FF's hill-climbing phase (Planning p.28) is incomplete and cannot
certify. Every fixed variant has finite $h_{FF}(I)$, so certification needs the exhaustive search and
$h_{FF}$ contributes only its dead-end test: on sizes 1–4 it expands 1.2× (cache) to 3.8× (queue) fewer
states than plain BFS (inventory size 4: 9,026 vs 24,992), without changing the exponential growth. **Pipeline:** in the Translate arm GBFS decides
reachability on the model's problem; if a plan exists, SATPlan with $T_{max}$ = the GBFS length returns a shortest trace (if its 120 s budget runs out, as in 17 inventory runs, the GBFS trace is kept). Appendix B.2–B.3 show real clauses, horizon iteration and a GBFS certificate.

**What each arm translates.** Both scales check $\alpha \land \lnot\beta$, but the model writes a
different half: in SP1 it writes $\beta$ (`pre`/`post`) and the code $\alpha$ is encoded mechanically; in SP2
we fix $\beta$ (the goal, plus *monitor* actions such as `charge-again`) and the model writes part of $\alpha$,
the initial state with its design facts. The action schemas, where the failure mechanism lives, are
given to both arms (§6).

# 3. Problem instances

## 3.1 SP1: 174 function instances

**Benchmarks.** 27 *base* functions, HumanEval/EvalPlus-style tasks [8] (`below_zero`, `is_prime`, …)
plus business rules (calendar, grade bands, discounts, withdrawals), and 10 *hard* ones where a witness
must be *constructed* (sorting networks, comparator medians, token-bucket rate limiters, a debouncer,
Luhn, Zeller's congruence, banker's rounding, subset-sum DP). As planned, identifiers are renamed and
docstrings rewritten without examples; each docstring fixes the return value on the stated domain, so
the docstring *is* the specification.

**Mutants and labels.** The candidates are 808 automatic first-order mutants (ROR, AOR, CRP,
LCR, condition negation, range off-by-one, statement deletion), 42 hand-written realistic bugs (a
forgotten 400-year rule, a comparator dropped as an "optimisation") and 9
equivalent rewrites.

Each candidate is labelled in four steps. Its *trigger rarity* is the probability that a random
in-domain input exposes it (integers uniform; a list draws its length, then its elements, uniformly),
computed exhaustively for integer domains up to 70k points and from 5,000 samples otherwise. $\Phi_{gold}$ is then solved, every Z3 witness is confirmed by real
execution, and equivalence is accepted only under the conditions of §2.1. Rarity buckets are common
(≥10%), uncommon (1–10%), rare (0.1–1%) and very rare (<0.1%).

**Selection.** For each function we keep every hand bug, fill the rarity buckets with automatic mutants
(preferring rare ones), and add two controls: the clean reference, plus an equivalent mutant when one
exists. These are deliberately hard: dropping comparator (a, c) leaves a median-of-5
network correct.

**Result.** 174 instances: 115 bugs (67 common, 19 uncommon, 21 rare, 8 very rare) and 59 controls (37
clean, 22 provably equivalent). Of the 859 candidates, 59 were dropped as non-terminating, not encodable or not provably equivalent.
The median Z3 query took 0.03 s (mean 0.2 s).

## 3.2 SP2: 60 designs, plus 30 stress, 60 opaque and 12 long variants

Each design document (about 200 words) states the components, the failure model and the mechanism
without judging it; subtle variants read like a fix the engineer believes works. Gold shortest traces
are 6–15 events. Three further sets were added:

* *Stress* (sizes 6 and 8): 17–27 events.
* *Opaque:* the main set with design facts and design-specific events renamed (`mode-2`, `accept-3`) and their comments removed; the semantics are unchanged, but "racy" in the text no longer matches `(dedup-racy)` by name.
* *Long:* payments and inventory at sizes 12 and 16 (30–51 events), 5.5 models only.

| family | violation | flawed | subtle | fixed |
|---|---|---|---|---|
| payments | charged twice | no deduplication | key saved only after charge | insert-if-absent |
| inventory | sold > stock | lost stock update | pay after hold expiry | atomic decrement + hold check |
| lock | stale write wins | no fencing, no lease check | lease checked before write | fencing tokens [14] |
| queue | payout twice | no consumer dedup | dedup ids in memory | dedup id in the DB transaction |
| cache | stale cache at end | update DB, delete cache | delete cache, update DB | leases revoked by delete |

# 4. Method

**Models.** Claude Haiku 4.5, Sonnet 5.5 and Opus 5.5 with default extended thinking, called through
the Claude Code CLI with *all tools disabled* (so Direct cannot run code). Two open-weight models served
by SoC's OpenAI-compatible endpoint (SoCLaaS) bracket them: Qwen 3.8 27B, which reasons before answering,
and Llama 3.1 8B, which does not. Both run at temperature 0 with a 32k-token output budget that includes
reasoning; Qwen ran SP1 and the SP2 main set only, as one SP2 answer took 5–10 minutes on the shared endpoint.
Requests the endpoint dropped under load were resubmitted, not scored. Both arms see the same inputs:

* SP1: the code with its docstring, plus the input domain.
* SP2: the design document, the family's PDDL domain (events, with comments) and object names.

**Direct arm.** JSON with a verdict and a witness: a failing input (SP1) or a list of ground actions (SP2).

**Translate arm, SP1.** The model writes `pre(...)` and `post(..., result)` in the supported Python subset, stating the docstring's intent, not the code's behaviour; `spec_check` then runs.

**Translate arm, SP2.** The model writes the PDDL problem. Object names and the goal are given, so the translation is the complete initial state, including design facts and counters; mapping prose to one design fact per mechanism is the semantic step SP3 scores; the pipeline of §2.2 then solves it.

**Repair loop.** Errors are fed back up to twice: syntax errors, unsupported constructs, a vacuous precondition, a wrong goal, type or arity errors: a harness with verification and retries (GenAI p.28).

**Tool budgets.** An SP1 spec check has a 120 s deadline in a child process killed after 150 s; Z3
queries time out at 60 s; planner search is capped at 3 M expansions or 300 s, SATPlan at 120 s. A
budget hit, a Z3 *unknown* or a failed coverage check ($\Psi$ satisfiable) is reported as *undecided*,
never as "no failure".

**Scoring** is exact, on gold models: an SP1 witness is valid only if it is in-domain and the code
under review and the unmutated reference behave differently on it; an SP2 trace is valid if replaying
it on the gold problem reaches the violation.

Outcomes are *valid witness*, *fabricated* (an invalid witness or a false alarm on a control: a
hallucination made checkable, GenAI p.9), *miss*,
*correct no-failure*, or *undecided* (the tool gave up; counted as no answer). Every LLM response is cached, so all numbers can be regenerated offline.

<!-- RESULTS -->
