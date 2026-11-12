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

**Summary.** Can an LLM show concretely how unshipped software would fail? We test function review (SP1: find an input that breaks a Python function's docstring) and distributed-system design review (SP2: find an order of timeouts, retries, lost messages and crashes that breaks a safety property like "no order is charged twice"). On 174 functions and 162 designs, scored exactly against ground truth, we compare Claude Haiku 4.5, Sonnet 5.5 and Opus 5.5, and the open-weight Qwen 3.8 27B and Llama 3.1 8B, each answering directly (Direct) or translating for a solver (Translate). Translation's value depends on the model: it adds no accuracy for strong models, cuts mid-tier false alarms, and cannot rescue a weak one.

**SP1** (Translate: a specification checked by Z3). Claude and Qwen raise no false alarm and find nearly every
bug in both arms, even bugs random testing rarely triggers (100 inputs expose 5% of the very rare ones); Translate
trails only there (29/32 vs 32/32 model–bug pairs), as its specification can copy the bug. Llama 3.1 8B fabricates
in Direct (false alarms on 76% of correct functions); Translate cuts this to 20%, mostly as 70 of 174 runs
yield no usable spec.

**SP2** (Translate: PDDL for the planners; both arms get the STRIPS actions). The 5.5 models are
never wrong in either arm, up to 51 events and on the *opaque* set (mechanism-revealing names replaced); Qwen matches
them in Translate on the main set. Translation pays for Haiku, which in Direct applies familiar patterns to designs that rule them
out: its false alarms on correct designs fall from 60% to 35% (opaque: 95% to 45%), lower in 4 of 5 families. Llama
fabricates in Direct; its broken Translate files miss 29 of 40 failures, so "safe" means little.

**In practice,** Direct suffices when the spec is explicit and the model strong; Translate adds a no-failure
certificate, valid only if the translation is correct and the solver finishes.

# 1. Motivation and research questions

A *pre-mortem* asks how a design will fail before it ships. Failures that matter are often reachable
only through rare inputs or long event interleavings: model checking at AWS found a DynamoDB
data-loss bug whose shortest trace had 35 steps, after it had passed design review, code review and
testing [1]. An AI assistant for code and design review is therefore valuable only if it can produce
*witnesses*, i.e. concrete failing inputs or event traces, and only if it does not fabricate failures
that do not exist.

The course asks: "When should you use LLM reasoning
directly? When should you translate problem specification then call tool?", and whether that is "likely to change in the near future". We compare
two arms on the same inputs:

* **(A) Direct.** The LLM reads the input and answers with a verdict and a witness.
* **(B) Translate.** The LLM writes a formal description of the problem, and a classical solver searches for the witness. Solver errors are fed back for repair, as in Logic-LM [9] and the LLM+SMT method [5].

Arm B is the course's bet: with the structure explicit, a solver prunes what reasoning must enumerate.

We study two review sub-problems; **SP3** is not a third but scores Translate's translations against gold (SP1: sound, discriminating spec? SP2: exact initial state?), to tell translation errors from solver errors.

* **SP1: function review.** The LLM gets a Python function and a docstring saying what it must do, and must find an input that breaks the docstring. For example, `days_in_month` with 400 mistyped as 399 returns 28 instead of 29 for February of year 400, so `month=2, year=400` is a witness. In Translate it writes pre- and postconditions, and Z3 searches.
* **SP2: distributed-system design review.** The LLM gets a design document of about 200 words for a service (payments, inventory, lock, queue or cache) and the list of events that can occur, and must find an order of events (timeouts, retries, lost or delayed messages, crashes) that breaks a safety property. For example, a timed-out checkout retries, both attempts pass the duplicate check before either is recorded, and the card is charged twice. In Translate it writes only the initial state of a planning problem; the events and the goal are given, and planners search.
* **RQ1.** Which arm finds more *valid* witnesses, and does the gap widen as failures get harder to reach (*trigger rarity* in SP1, the chance that a random input exposes the bug; *shortest-trace length* in SP2, the fewest events that reach the failure)?
* **RQ2.** Which arm fabricates more failures on correct *controls*, i.e. functions or designs with no failure?

# 2. Formulation

Both problems search for a counterexample, and the Translate arm does so literally: the solver is asked whether $\alpha \land \lnot\beta$ is satisfiable, with $\alpha$ = "the system as implemented" and $\beta$ = "the requirement" ($\alpha \models \beta$ iff it is not, [3] Ch. 7). A model is a *failure witness*: in SP1 an input satisfying $pre \land \lnot post$ (Z3), in SP2 a plan reaching the violation $G$ (SATPlan; GBFS answers the same question by search). The LLM writes a different half in each problem. In SP1 it writes $\beta$ (`pre`, `post`) and the code $\alpha$ is encoded automatically. In SP2 we fix $\beta$ (the goal, e.g. `charged-twice`, and actions such as `charge-again` that set it) and the LLM writes part of $\alpha$, the initial state; the action schemas, where the failure mechanism lives, are given to both arms.

## 2.1 SP1: a function as a CSP, solved by SMT

**Setting.** A *reference* is a correct function and a *mutant* a copy with one small injected change; the LLM is not told which it sees. Below, $\Phi_{spec}$ is what the Translate arm solves (does some input break the LLM's specification?), while $\Phi_{gold}$ is ours, used only for ground truth (does some input make mutant and reference differ?).

**CSP.** Each instance is a CSP $(X, D, C)$ ([3] Ch. 6).

* **Variables $X$:** the function's inputs. An integer input is one variable. A list input is a length variable $n$ plus element variables $e_0, \dots, e_{m-1}$, where $m$ is the maximum length.
* **Domains $D$:** the stated ranges, e.g. $1 \le month \le 12$, $0 \le n \le m$, and each $e_i \in [lo, hi]$.
* **Constraints $C$:** $\llbracket f \rrbracket(x, r) \land \lnot spec(x, r)$, where $\llbracket f \rrbracket(x, r)$ holds iff $r$ is what $f$ returns on $x$.

The result and intermediate values are not separate variables but shared sub-terms fixed by the inputs.
The domains are finite, so this is
a finite CSP, a class that is NP-complete. Z3, however, receives SMT (SAT extended with theories such as integer arithmetic) over unbounded integers
(`Int`) with the bounds as ordinary constraints; products of variables and `//` or `%` by a variable
make it non-linear integer arithmetic, undecidable in general. Our bounded queries are decidable, but
Z3's non-linear procedures are incomplete, so it can answer *unknown* (§5.1).

**Building $\llbracket f \rrbracket$: bounded symbolic execution** [12]. Rather than running the code on one input, the executor runs it once on symbolic inputs and produces one formula covering every path: a branch setting `y = 1` if `x > 0` and `y = 2` otherwise, then returning `y`, becomes $ret = \mathit{If}(x > 0, 1, 2)$. We wrote our own because tools such as CrossHair [16] cannot prove unsatisfiability within a bound, which Theorem 1 needs. It walks the syntax tree once with a symbolic environment
$\rho$ (variable → Z3 term) and a *path condition* $\pi$ (when control reaches the statement).
`x = e` sets $\rho[x] \leftarrow \llbracket e \rrbracket_\rho$. `if c` runs both branches, from $(\rho, \pi \land c)$ and
$(\rho, \pi \land \lnot c)$, and joins them with $\rho[x] = \mathit{If}(\pi_1, \rho_1[x], \rho_2[x])$ and $\pi = \pi_1 \lor \pi_2$
(`break`/`continue` likewise). `return e` sets $ret \leftarrow \mathit{If}(\pi, \llbracket e \rrbracket, ret)$ and $\pi \leftarrow \bot$. An
operation that raises when $b$ (bad index, `x // 0`, …) sets $exc \leftarrow exc \lor (\pi \land b)$ and $\pi \leftarrow \pi \land \lnot b$. A `while` or symbolic-`range`
loop is unrolled $k$ times, iteration $j$ under $\pi \land cond_j$, then $unwind \leftarrow unwind \lor (\pi \land cond_k)$. The
result is three terms over $X$: $ret$, $exc$ ("raises") and $unwind$ ("exceeds a bound"). Integers are unbounded and `//`, `%`
follow Python's floor semantics. Lists are values: aliasing (`ys = xs; ys.sort()`) is not modelled.

**Lemma 1 (encoding correctness).** Call $x_0 \in D$ *covered* if $unwind[x_0] = \bot$: its run needs at most $k$ iterations of each `while` or symbolic-`range` loop and at most $k$ elements in each list built from a symbolic count (concrete `range` loops are expanded in full). For $f$ in the supported, alias-free subset and covered $x_0$: $exc[x_0] = \top$ iff $f(x_0)$ raises, and otherwise $ret[x_0] = f(x_0)$.

*Proof sketch.* Induction over statements, with the invariant: $\pi[x_0] = \top$ iff the concrete run
on $x_0$ reaches this point, and then $\rho[x][x_0]$ is the concrete value of $x$. The join selects the branch taken, `return` and raises record the outcome under the path condition, and $cond_k$ marks a
$(k{+}1)$-th iteration. ∎

**The two queries.** The LLM's specification is two Python functions, `pre(x)` (is $x$ a valid input?) and `post(x, r)` (is $r$ correct for $x$?), compiled like $f$ and unrolled to
$k' = \max(k, L{+}1)$ where $L$ is the longest list input (doubled up to $4k'$ while the coverage
query $\Psi$ below is satisfiable); $pre(x)$ means "returns normally with a true value" (likewise $post$), and a subscript names a term's function ($ret_f$: what $f$ returns).

$$\Phi_{spec} = D(x) \land \lnot unwind_f \land \lnot unwind_{pre} \land pre(x) \land \big(exc_f \lor (\lnot unwind_{post} \land \lnot post(x, ret_f))\big)$$

$$\begin{aligned}\Phi_{gold} = {} & D(x) \land \lnot unwind_{ref} \land \lnot unwind_{mut} \\ & \land \big((exc_{ref} \oplus exc_{mut}) \lor (\lnot exc_{ref} \land \lnot exc_{mut} \land ret_{ref} \ne ret_{mut})\big)\end{aligned}$$

In words: $\Phi_{spec}$ seeks a valid, in-bounds input on which $f$ raises or breaks $post$; $\Phi_{gold}$, one on which exactly one of reference and mutant raises, or both return and differ.

**Theorem 1 (soundness and bounded completeness).** Suppose the *coverage* query
$\Psi = D(x) \land \lnot unwind_f \land \big(unwind_{pre} \lor (pre(x) \land \lnot exc_f \land unwind_{post})\big)$
is unsatisfiable, i.e. on every input covered by $f$ the spec's own loops fit $k'$. Then $\Phi_{spec}$
is satisfiable iff some covered $x_0 \in D$ satisfies $pre$ while $f$ raises or violates $post$ (a
$pre$ that raises counts as false, a $post$ that raises as violated), and every satisfying assignment is such an $x_0$.

*Proof sketch.* By Lemma 1 on $f$, $pre$ and $post$, each conjunct has its concrete meaning wherever
the relevant function fits its bound; $\lnot\Psi$ says that it does at every input where it is
evaluated. If $\Psi$ is still satisfiable at $4k'$, `spec_check` reports *undecided*, never "no failure". ∎

The same argument covers $\Phi_{gold}$ with "behaves
differently from the reference" for "violates the spec". The build checks that no reference loop can exceed its bound, and accepts a mutant as equivalent only
if its domain was enumerated or $unwind_{mut}$ is unsatisfiable (cf. CBMC's [17] unwinding assertions).

**The solver.** Z3 [4] decides satisfiability. Every satisfying assignment is re-executed in Python before it counts, and Lemma 1 is tested against real execution on 25 random
inputs per benchmark and hand-written mutant. Appendix B.1 shows a full instance.

## 2.2 SP2: a distributed-system design as a STRIPS planning problem

**Setting.** A distributed system is a set of components communicating over an unreliable network, so failures often depend on event order: SP2 asks whether a design permits an unlucky order, such as a timer expiring while a request is in flight. We use five classic designs, the *families*, each with one safety property and three *variants*: *flawed*, *subtle* (looks fixed but is not) and *fixed* (safe).

* *payments:* a retried charge must not bill twice (no dedup; key saved after charge; atomic insert)
* *inventory:* must not oversell (lost update; payment after hold expiry; atomic decrement + hold check)
* *lock:* a stale writer must not win (no fencing or lease check; lease check only; fencing tokens [14])
* *queue:* redelivery must not pay out twice (no dedup; ids in memory; id in the DB transaction)
* *cache:* must not end stale (update DB then delete cache; the reverse; leases revoked by delete)

Variants differ only in their *design facts*; in payments one initial fact says whether deduplication is absent, racy or atomic. *Size* scales a timer or capacity, lengthening the shortest failure.

**STRIPS task** ([3] Ch. 11). Each family is a typed PDDL domain and each variant and size a problem; grounding (propositionalization, [3] Ch. 9; up to $K^V$ instances per schema with $K$ objects, $V$ parameters) gives $\Pi = (F, A, I, G)$:

* $F$, what can be true: ground facts such as `(no-record o1)`. A state $s \subseteq F$ is the set of facts that hold (closed world assumption).
* $A$, what can happen: each action has $pre(a)$, $add(a)$, $del(a)$. It is applicable in $s$ iff $pre(a) \subseteq s$, and then $\mathrm{RESULT}(s, a) = (s \setminus del(a)) \cup add(a)$.
* $I$, how this design starts and behaves: design facts such as `(dedup-racy)`, counters `(next-tick t0 t1)` and the starting situation.
* $G$, what must never happen: e.g. `{(charged-twice o1)}`.

A plan reaching $s_n \supseteq G$ is a failure trace. The planner chooses *every* event, including loss and crashes, so a plan is a counterexample, not a course of action: planning serves as explicit-state model checking of a **safety** property. In payments, attempt a0 passes the duplicate check, the timer expires, retry a1 also passes because `accept-new-racy` does *not* delete `no-record o1`, and both charge (B.2 shows it).

**Modelling assumptions:** events interleave one at a time; effects are deterministic and
unconditional, preconditions and goals positive; the environment can do exactly the domain's failure events; object counts, hence states, are finite. PlanSAT is
PSPACE-complete [10] (its delete-free relaxation is polynomial given positive preconditions, as here, so $h_{FF}$ is tractable); each SATPlan call decides
*bounded* PlanSAT for one horizon $T$, which is NP-complete for $T$ polynomial in the task size [10].

**Scope.** Liveness failures are not STRIPS goals and are out of scope. "Safe" covers the instance at its size, not every size; we rely on the small-scope hypothesis [15], that most flaws already appear in small instances, and on an inductive invariant where search runs out (inventory from size 8, §6).

**SATPlan encoding** [6]. For horizon $T$: a variable $f^t$ per
fact and step $t \le T$, and $a^t$ per action and step $t < T$, with CNF clauses (facts not yet reachable at step $t$ become constants):

**1. initial state:** $f^0$ for $f \in I$, $\lnot f^0$ for $f \notin I$; **2. goal:** $g^T$ for each $g \in G$; **3. preconditions:** $a^t \Rightarrow p^t$ for each $p \in pre(a)$; **4. effects:** $a^t \Rightarrow f^{t+1}$ for $f \in add(a)$, $a^t \Rightarrow \lnot f^{t+1}$ for $f \in del(a) \setminus add(a)$; and

5. **explanatory frame axioms:** $f^t \land \lnot f^{t+1} \Rightarrow \bigvee\{a^t : f \in del(a) \setminus add(a)\}$ and $\lnot f^t \land f^{t+1} \Rightarrow \bigvee\{a^t : f \in add(a)\}$;
6. **exactly one action per step:** the exclusion axioms, strengthened, in linear size.

**Lemma 2.** Under (6), clauses (4)–(5) are equivalent to the standard successor-state axioms
$F^{t+1} \Leftrightarrow ActionCausesF^t \lor (F^t \land \lnot ActionCausesNotF^t)$ ([3] Ch. 7).
*Proof.* Let $a$ act at step $t$. (4) forces $f^{t+1}$ if $f \in add(a)$ and $\lnot f^{t+1}$ if
$f \in del(a) \setminus add(a)$; otherwise (5) forces $f^{t+1} = f^t$. Hence $s_{t+1} = \mathrm{RESULT}(s_t, a)$, with $a$ applicable by (3). ∎

**Theorem 2.** The horizon-$T$ formula is satisfiable iff a plan of exactly $T$ actions ends in a state
containing $G$, and the true action variables of a model form one. Iterating $T$ from 0 returns a *shortest* trace at the first satisfiable $T$; decoded plans are re-validated. UNSAT for all $T \le T_{max}$ proves only bounded safety.

**Certifying safety: greedy best-first search with $h_{FF}$**. $h_{FF}(s)$ is the length of a relaxed plan for the task with delete lists ignored, extracted
from layered reachability (FF's relaxed planning graph [7]), or $\infty$ if $G$ is unreachable even in the relaxation. GBFS expands states
in order of $h_{FF}$, never revisits one, tests for the goal on generation, and discards states with
$h_{FF} = \infty$.

**Theorem 3.** If GBFS returns *unsolvable*, $G$ is unreachable from $I$.
*Proof.* The state space is finite and each state is queued at most once, so the search terminates.
When the queue empties, every generated state has been expanded or discarded and none was a goal. So
any path from $I$ to a goal would have to pass through a discarded state. Discarding is safe: ignoring
delete lists only adds behaviour, so if $G$ is unreachable from $s$ in the relaxation, it is unreachable
from $s$ in the real task. ∎

By the same argument GBFS finds a plan whenever one exists, though not always a shortest one ($h_{FF}$
is inadmissible); FF's hill-climbing phase is incomplete and cannot
certify. Every safe (*fixed*) variant has finite $h_{FF}(I)$, so certification needs the exhaustive search and
$h_{FF}$ contributes only its dead-end test: on sizes 1–4 it expands 1.2× (cache) to 3.8× (queue) fewer
states than plain BFS, without changing the exponential growth. **Pipeline:** in the Translate arm GBFS decides
reachability on the model's problem; if a plan exists, SATPlan returns a shortest trace within its 120 s budget, else the GBFS trace is kept (B.2–3).


# 3. Problem instances

## 3.1 SP1: 174 function instances

**Benchmarks.** 27 *base* functions, HumanEval/EvalPlus-style tasks [8] (`below_zero`, `is_prime`, …)
plus business rules (calendar, grade bands, discounts, withdrawals), and 10 *hard* ones where a witness
must be *constructed* (sorting networks, rate limiters, Luhn, subset-sum DP, …). To limit memorisation from training data, identifiers are renamed and
docstrings rewritten without examples; each docstring fixes the return value on the stated domain, so
the docstring *is* the specification.

**Mutants and labels.** The candidates are 808 automatic first-order (single-change) mutants, 42 hand-written bugs (e.g. a forgotten 400-year rule) and 9
equivalent rewrites.

Each candidate is labelled in four steps. Its *trigger rarity* is the probability that a random
in-domain input exposes it (integers uniform; a list draws its length, then its elements, uniformly),
computed exhaustively for integer domains up to 70k points and from 5,000 samples otherwise. $\Phi_{gold}$ is then solved, every Z3 witness is confirmed by real
execution, and equivalence is accepted only under the conditions of §2.1.

**Selection.** For each function we keep every hand bug, fill the rarity buckets with automatic mutants
(preferring rare ones), and add two controls: the clean reference, plus an equivalent mutant when one
exists; equivalent mutants look buggy but are not.

**Result.** 174 instances: 115 bugs (trigger rarity: 67 common ≥10%, 19 uncommon 1–10%, 21 rare 0.1–1%, 8 very rare <0.1%) and 59 controls (37
clean, 22 provably equivalent). Of the 859 candidates, 59 were dropped as non-terminating, not encodable or not provably equivalent.

## 3.2 SP2: 60 designs, plus 30 stress, 60 opaque and 12 long variants

The main set crosses the five families of §2.2, three variants and sizes 1–4. Each design document (about 200 words; A.7 shows one) states the components, the failure model and the mechanism without judging it; subtle variants read like a fix the engineer believes works. Gold shortest traces are 6–15 events. Three further sets were added:

* *Stress* (sizes 6 and 8): 17–27 events.
* *Opaque:* the main set with design facts and design-specific events renamed (`mode-2`, `accept-3`) and comments removed; the semantics are unchanged.
* *Long:* payments and inventory at sizes 12 and 16 (30–51 events), 5.5 models and Llama only.

# 4. Method

**Models.** Claude Haiku 4.5, Sonnet 5.5 and Opus 5.5 with default extended thinking, called through
the Claude Code CLI with *all tools disabled* (so Direct cannot run code). Two open-weight models on SoC's endpoint (SoCLaaS)
bracket them: Qwen 3.8 27B [18], which reasons before answering, and Llama 3.1 8B [19], which does not, both at temperature 0; Llama's answers never exceed 8,192
output tokens. Qwen ran SP1 and the SP2 main set only, as one SP2 answer took 5–10 minutes on the shared endpoint.
Both arms see the same inputs: the code with its docstring and the
input domain (SP1); the design document, the family's PDDL domain (events, with comments) and object names (SP2).

**Arms.** Direct returns JSON with a verdict and a witness (a failing input, or a list of ground actions). Translate returns `pre(...)` and `post(..., result)` in the supported Python subset, stating the docstring's intent, not the code's behaviour (SP1), or the complete initial state, including design facts and counters, with object names and the goal given (SP2); `spec_check` or the pipeline of §2.2 then runs.

**Repair loop (Translate only).** Errors are fed back up to twice: syntax, unsupported constructs, a vacuous precondition, a wrong goal, type or arity.

**Tool budgets.** An SP1 spec check has a 120 s deadline; Z3
queries time out at 60 s; planner search is capped at 3 M expansions or 300 s, SATPlan at 120 s. A
budget hit, a Z3 *unknown* or a failed coverage check ($\Psi$ satisfiable) is reported as *undecided*,
never as "no failure".

**Scoring** is exact, against ground truth (our *gold* reference functions and problem files): an SP1 witness is valid only if it is in-domain and the code
under review and the unmutated reference behave differently on it; an SP2 trace is valid if replaying
it on the gold problem reaches the violation.

Outcomes are *valid witness*, *fabricated* (an invalid witness or a false alarm on a control: a
hallucination made checkable), *miss*, *correct no-failure*, or *undecided* (counted as no answer).

<!-- RESULTS -->
