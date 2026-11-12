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
query $\Psi$ below is satisfiable). In the formulas, $pre(x)$ means "running `pre` on $x$ returns True without raising an exception", and $post(x, r)$ means the same for `post`. A subscript names a term's function ($ret_f$: what $f$ returns).

$$\Phi_{spec} = D(x) \land \lnot unwind_f \land \lnot unwind_{pre} \land pre(x) \land \big(exc_f \lor (\lnot unwind_{post} \land \lnot post(x, ret_f))\big)$$

$$\begin{aligned}\Phi_{gold} = {} & D(x) \land \lnot unwind_{ref} \land \lnot unwind_{mut} \\ & \land \big((exc_{ref} \oplus exc_{mut}) \lor (\lnot exc_{ref} \land \lnot exc_{mut} \land ret_{ref} \ne ret_{mut})\big)\end{aligned}$$

In words: $\Phi_{spec}$ seeks a valid, in-bounds input on which $f$ raises or breaks $post$; $\Phi_{gold}$ seeks an input on which exactly one of reference and mutant raises, or both return and differ.

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



# 5. Results

Tables, intervals and paired tests come from `experiments/analyze.py` (full output in `results/tables.md`). Brackets are 95%
Wilson intervals; as instances share templates, intervals and tests are nominal (§6).

## 5.1 SP1: functions (115 bugs, 59 controls)

**RQ1: who finds more bugs as they get rarer?** Claude and Qwen find nearly every bug in both arms (Table 1, Fig. 1), but the arms part with rarity. Over model–bug pairs (four models), both find 267/268 common and 75/76 uncommon; Direct finds 84/84 rare and 32/32 very rare (eight distinct bugs), Translate 82/84 and 29/32. That favours Direct, but thinly: Translate fails 3/32 very rare pairs vs 4/428 others, the three being two bugs with unsound specs (§6). Otherwise difficulty shows only as cost (hard-tier Direct answers use 2–5×
the tokens) and as Z3 *unknown* on arithmetic-heavy specs. Random testing with $N$
inputs catches a bug of rarity $r$ with probability $1-(1-r)^N$: 100 inputs catch 34% of rare and
5% of very rare bugs, 1,000 catch 93% and 36%. Rarity defeats *random testing* far more than either LLM arm.

**RQ2: who raises false alarms on correct code?** No Claude or Qwen run raised a false alarm on the 59 controls, 22 of them equivalent mutants built to look buggy; Translate left 1 (Haiku) and 5 (Opus) *undecided*. Llama Direct raised 45 false alarms and invented a witness for 60 of the 115 bugs. Translate cut its false alarms to 12, but all 12, and 20 of its 22 misses, came from unsound specs.

::: keep
| model | arm | base found /95 | hard found /20 | fabri&shy;cated | false alarms /59 | no answer | $ per inst. | output tokens |
|---|---|---|---|---|---|---|---|---|
| Haiku&nbsp;4.5 | Direct | 100% | 95% | 0 | 0 | – | 0.025 | 4,838 |
| Haiku&nbsp;4.5 | Translate | 98% | 95% | 1 | 0 | 1 | 0.026 | 4,968 |
| Sonnet,&nbsp;Opus&nbsp;5.5 | Direct | 100% | 100% | 0 | 0 | – | 0.009, 0.018 | 431, 470 |
| Sonnet,&nbsp;Opus&nbsp;5.5 | Translate | 100% | 95% | 0 | 0 | 1, 6 | 0.008, 0.021 | 208, 383 |
| Qwen&nbsp;3.8&nbsp;27B | Direct | 99% | 100% | 0 | 0 | 1 | – | 1,200 |
| Qwen&nbsp;3.8&nbsp;27B | Translate | 99% | 95% | 0 | 0 | 4 | – | 6,447 |
| Llama&nbsp;3.1&nbsp;8B | Direct | 41% | 5% | 60 | 45 | 7 | – | 451 |
| Llama&nbsp;3.1&nbsp;8B | Translate | 28% | 20% | 14 | 12 | 70 | – | 429 |

*Table 1.* SP1 outcomes. *Fabricated* counts invalid witnesses on bugs; false alarms are separate. *No answer*
(bugs and controls): a checker timeout or Z3 *unknown* (*undecided*) for Claude; no verdict, no accepted spec or an endpoint limit for open-weight models.
:::

**SP3: how good are the translations?** Of the specifications whose soundness check completed, these were *sound* (the reference satisfies them): 169/172 (Haiku), 173/173 (Sonnet), 165/165 (Opus) and 169/170 (Qwen). *Discriminating* (the mutant violates them) is the valid-witness rate above. Llama differs in kind: only 104 of its 174 specs passed the checker (70 runs failed after two repairs, 46 of them calling the unsupported `isinstance`), and only 45 of the 103 with a soundness verdict are sound.

**Translate failures.** For the Claude models every one comes from the specification or the tool, never the search: two postconditions copied the code's bug (§A.2), one spec raised an exception and produced a fabricated witness (§A.3), and eight checks were undecided (three timeouts, five Z3 *unknown*s).

![](../results/figures/sp1_rarity.png){width=48%} ![](../results/figures/sp2_length.png){width=48%}

*Fig. 1 (left):* SP1 base tier, valid witnesses vs. trigger rarity (Llama dashed) against random testing. *Fig. 2 (right):* SP2 valid traces vs. shortest trace length (main + stress; inventory sizes 6 and 8: best known).

## 5.2 SP2: designs (60 main + 30 stress + 60 opaque + 12 long)

::: keep
| model | arm | main valid /40 | main FA /20 | stress valid /20 | stress FA /10 | opaque valid /40 | opaque FA /20 | $/inst. main |
|---|---|---|---|---|---|---|---|---|
| Haiku&nbsp;4.5 | Direct | 78% [62–88] | 60% [39–78] | 85% | 80% | 68% | 95% | 0.062 |
| Haiku&nbsp;4.5 | Translate | 85% [71–93] | 35% [18–57] | 90% | 40% | 63% | 45% | 0.051 |
| Sonnet,&nbsp;Opus&nbsp;5.5 | Direct | 100% | 0% | 100% | 0% | 100% | 0% | 0.025, 0.048 |
| Sonnet,&nbsp;Opus&nbsp;5.5 | Translate | 100% | 0% | 100% | 0% | 100% | 0% | 0.018, 0.036 |
| Qwen&nbsp;3.8&nbsp;27B | Direct | 93% | 0% | – | – | – | – | – |
| Qwen&nbsp;3.8&nbsp;27B | Translate | 100% | 0% | – | – | – | – | – |
| Llama&nbsp;3.1&nbsp;8B | Direct | 0% | 70% | 0% | 60% | 0% | 90% | – |
| Llama&nbsp;3.1&nbsp;8B | Translate | 3% | 10% | 0% | 10% | 0% | 40% | – |

*Table 2.* SP2 outcomes. In *Translate* the named model writes the PDDL problem and the planners search it. "Valid" = a trace that
replays on the gold problem and reaches the violation (flawed + subtle designs). FA = false alarm on a fixed
design. Translate was *undecided* on inventory's fixed design at size 8.
:::

**RQ1: who finds more traces as they get longer?** Sonnet 5.5 and Opus 5.5 produced a valid trace every time, from 6 to 51 events (on the long set 8/8 per model and arm, 95% interval [68–100], with no false alarm; Translate was undecided on its inventory fixed designs, sizes 12 and 16). Haiku stays near 80% with no length trend. Paired over the 150 designs Haiku ran, only Translate is right on 41 and only Direct on 21, an edge significant in no single set. Qwen's Translate was right on all 60 main designs and its Direct on 57, its 3 invalid traces being format slips, not misreadings. Llama Direct had no valid trace.

**RQ2: who raises false alarms on correct designs?** Haiku and Llama; the other models raise none.

* *Haiku Direct* claims violations on 60% of fixed designs (80% stress, 95% opaque). Translate cuts this to 35% (40%, 45%), lower in 4 of 5 families on main and opaque. Its Direct traces fail on design facts: 16 (main) and 30 (opaque) used an event of *another* design variant, typically a familiar pattern (§A.4).
* *Llama Direct* claims violations on 70% of fixed designs (60% stress, 90% opaque); Translate cuts this to 10% (10%, 40%) but misses 29 of 40 violating main-set designs: "safe" for the wrong reason.

**SP3: how good are the translations?**

* *Sonnet and Opus* reproduced the gold initial state exactly in all 90 main and stress problems, and *Qwen* in all 60 main ones.
* *Haiku's design facts* were exact in 49/60 main and 35/60 opaque. Its other errors were permissive facts the planner exploited (§A.5). Only 2 of 474 Claude translations needed repair.
* *Llama* left out about a third of the gold initial facts (mean recall 0.64 on the main set; design facts exact in 22/60; 8 never parsed). With facts missing the violation can become unreachable: the planner proved "no violation" on all 29 missed flawed designs and on 16 of the 20 fixed ones.

## 5.3 The classical tools

* *Worst case vs. observed.* PlanSAT is PSPACE-complete, but only inventory shows pronounced state explosion (Table 3): its $S{+}1$ interchangeable customers interleave, so reachable states grow 1,500× from size 1 to 4; the other families grow roughly linearly. Trace length is not the driver: queue and inventory at size 8 have traces of 21 and 27 events.
* *SATPlan* finds shortest traces in milliseconds for four families. On inventory it takes 1.1 s at size 3, about 2 minutes at size 4, and times out (300 s, the gold-label budget) at sizes 6 and 8.
* *Certification* takes 9,026 GBFS expansions at inventory size 4 and 2.7 M (176 s) at size 6. From size 8 our 3 M-expansion / 5-minute budget runs out, so Translate on inventory's fixed design is scored *undecided*, not safe (the gold label comes from a conservation invariant).

::: keep
| family | facts / actions (size 1 → 8) | shortest trace (size 1 → 8) | SATPlan vars / clauses (size 4) | reachable states, fixed (size 1 / 4 / 8) |
|---|---|---|---|---|
| payments | 27 / 24 → 55 / 66 | 8 → 22 | 721 / 2,173 | 148 / 532 / 1,044 |
| inventory | 22 / 14 → 218 / 945 | 6 → 27 | 4,568 / 18,236 | 16 / 24,992 / >2.6M |
| lock | 52 / 23 → 80 / 37 | 8 → 22 | 1,018 / 3,581 | 79 / 235 / 443 |
| queue | 16 / 8 → 44 / 36 | 7 → 21 | 535 / 1,783 | 14 / 38 / 70 |
| cache | 20 / 13 → 97 / 153 | 7 → 21 | 978 / 3,564 | 26 / 80 / 180 |

*Table 3.* Difficulty in course terms (SATPlan at the shortest $T$; $F$ of the flawed variant). A state is a subset of $F$, so
$2^{|F|}$ bounds the state space ($2^{44}$ to $2^{218}$ at size 8), but certification only visits reachable states. Inventory from size 6: best known length, not proven shortest.
:::


# 6. Analysis and insights

**The answer in brief.** (1) With a capable model the two arms nearly tie on these benchmarks, consistent with recognition rather than search. (2) Translation moves part of the error into the specification rather than eliminating it, so it helps only a model that writes the formal language reliably. (3) Only the tools can prove that no failure exists, and that is where they run out of budget.

**1. Capable models nearly tie, consistent with recognition rather than search.** In SP1 a first-order mutant leaves a visible diff against a docstring that states the intent, so trigger rarity, which decides whether *random testing* finds a bug, did not hurt Direct on capable models (Fig. 1). In Kang et al.'s terms [2], the next step (find the line contradicting the docstring) is cheap, so the chain of thought stays short. SP2's violations are textbook patterns; once one is recognised, a longer trace is bookkeeping: from 6–15 to 30–51 events the 5.5 models found a valid trace on every violating design, and Direct answers grew only from about 1.2k to 1.5k tokens. With facts renamed `mode-N` they were still never wrong: they did not rely on names. Most cells are at ceiling, so these benchmarks cannot rank the strongest models.

**2. Translation moves the error.** In SP1 the spec must state the docstring's intent while the LLM reads code that contradicts it. Most specs are *constructive*: `post` recomputes the answer and compares it with `result` (Claude 169–172/174, Qwen 168/170, Llama 125/174). SP1 Translate is thus a differential check against a second, LLM-written implementation (N-version programming), so a spec can inherit the bug it should expose (§A.2), which may explain Translate's small gap on rare bugs. Repair fixes form (Haiku 106 → 112, Opus 104 → 114 of 115) but not meaning. In SP2, Haiku's Direct errors are design misreadings: it applies a well-known pattern, such as the check-then-act race, to a design whose text rules it out (§A.4). Translation moves this into the design facts and adds permissive initial facts that the planner turns into shortcuts (§A.5), yet it still helps Haiku: on the opaque set its Direct false alarms rose from 60% to 95%, while Translate held them to 45%, as the initial state forces one design fact per mechanism. Llama 3.1 8B, which does not reason, fabricates in Direct, and translation silences this rather than repairing it: it cannot write the formal language reliably (§5), and problem files missing a third of the initial state make flawed and fixed designs alike look safe. Llama alone cannot locate a threshold: it differs from Qwen in size, reasoning and generation at once, and Qwen did not run the other SP2 sets.

**3. Only the tools can prove that no failure exists, and that is their limit.** Direct can answer "no failure" but cannot prove it; Translate can, with a solver result and audit trail. That proof holds only for the problem as translated (Llama's 29 wrong "no violation" proofs show how hollow it can be), and its value is argued, not measured. On inventory, the one family with state explosion, the safety search exceeds its budget from size 8: Translate is undecided while Sonnet and Opus Direct answer correctly, without proof (how they answered was not measured). The standard remedies lie outside the course: *symmetry reduction* (merging states that differ by a permutation of interchangeable objects, such as inventory's customers), *partial-order reduction* (one order for independent events), and *inductive invariants* (k-induction with $k = 1$), which prove safety by entailment with three checks:
$$Inv(s_0), \qquad Inv(s_t) \land T(s_t, s_{t+1}) \models Inv(s_{t+1}), \qquad Inv \models \lnot G.$$
Inventory's label from size 8 rests on one, proved by hand (§A.8): stock + holding + sold = S.

**When to use which.** Choosing an arm is a maximum-expected-utility decision ([3] Ch. 16). With a share $q$ of flawed designs and costs $c_{FA}$ per false alarm (reviewer time), $c_{miss}$ per flawed design left without a valid witness, $c_{rev}$ per undecided case, and $c_{run}$ per run (model calls),
$$EU(arm) = -\big((1-q)\,P_{FA}\,c_{FA} + q\,P_{miss}\,c_{miss} + P_{und}\,c_{rev} + c_{run}\big).$$
For Haiku on the SP2 main set, Translate has fewer false alarms (35% vs 60%), fewer flawed designs without a valid trace (6 vs 9 of 40), nothing undecided and the lower cost (US$0.051 vs 0.062), so at these point estimates it wins for any $q$ and positive costs; the false-alarm gap is clearest on the opaque set, where Translate trades two detections (27 to 25 of 40) for half the false alarms (19 to 9 of 20): at $q = 1/2$, counting errors alone, it wins while a miss costs under ten false alarms. For the 5.5 models on SP2 the error rates are zero: Translate is cheaper per run and wins on the main set, but abstains on inventory's fixed designs from size 8. $c_{run}$ omits fixed costs, which were not measured: SP1's encoder serves only Translate, while SP2 gave both arms the authored domain, so Direct without it is untested. *Use Direct* when the model is strong (judged on validation cases with known answers), the review small, the specification complete, and an answer without proof is acceptable. *Use Translate* when a "no failure" answer must be proved or audited, or when a mid-tier model, by the same test, misreads designs but writes the formal language reliably, and replay every witness on the real artefact. Neither the amount reviewed nor specification completeness was varied, so these conditions are argued.

**Will this change?** Direct will likely keep improving on small, recognisable problems (Haiku 4.5 to the 5.5 models, which also differ in tier), but worst-case hardness and the missing proof remain.

**Threats to validity.**

* *Scaffolding.* The given action schemas contain each failure mechanism as a named, guarded event, so SP2 Translate reduces to choosing one or two design facts per family, and that choice decides the outcome: correct in 47/49 (Haiku) and 60/60 (5.5 models, Qwen) main-set problems with exact facts, 0/11 (Haiku) with wrong ones. Writing the event model, as in [11], is untested.
* *Mutants* are small, first-order faults [13]; real bugs often span several lines (Claude and Qwen Direct also found 41–42 of 42 hand-written bugs; Llama 9).
* *Specifications.* Docstrings are complete; vaguer real ones would hurt Translate more. Functions were selected to be encodable (integers, Booleans, lists; no strings, floats or recursion), favouring the tools.
* *Familiarity and contamination.* SP1 functions derive from public benchmarks; renaming does not remove contamination. SP2 families are textbook patterns; the opaque set removes only lexical cues.
* *Authorship.* The design documents and gold models were produced together; two documents contradicted their models and were corrected, with all affected instances rerun.
* *Sampling and configuration.* Instances are sampled once and share five templates (so intervals and p-values are nominal). Claude models used default thinking, open-weight ones temperature 0, so effort and sampling differ. Only Translate gets a repair loop.


# 7. Responsible AI

**Automation bias: what "no failure" means.** A verdict is a belief about a *model*, not a fact about
the world: SP1 certifies only within the domain and unroll bounds (Theorem 1), and
SP2 only within the event model, so a failure mode the domain lacks is invisible to both arms. We therefore say "no counterexample within the input and loop bounds" (SP1) or "no reachable
violation in this finite event model" (SP2), never "verified safe", which certainty and framing effects ([3] Ch. 16) predict reviewers over-trust. Skipping manual review is
rational only if P(hidden failure | "no failure") is below review cost divided by incident loss
(if review would catch the failure). On our SP2 main set, 2 of Haiku Direct's 10
"safe" verdicts were wrong and none of Haiku Translate's 13 (95% upper bound 23%); both depend on the
base rate of flawed designs (Bayes' rule, [3] Ch. 12) and miss failure modes outside the benchmark.

**Fabricated failures.** False alarms waste reviewer time and train reviewers to ignore the tool. A Translate witness is correct only
*with respect to the model's own specification*: 13 of Haiku's main-set SP2 Translate traces (40 across
all sets) were legal only in its mistranslated problem, as the planner optimises the model as written, not as meant (the King Midas problem). Witnesses must therefore be replayed on the real artefact, as our scoring
does.

**Accountability.** Translate leaves an audit trail (spec, solver log, witness), close to a white-box
explanation ([3] Ch. 27), so a named engineer can sign off on *what was checked*; Direct's
witnesses replay, but its explanations are post-hoc. Humans who sign off stay responsible; the tool aids a human–AI review team.

**Dual use and attacks on the reviewer.** A witness can help construct an exploit, and AI lowers the cost of
attacks; we would run the tool only on code the user owns, follow coordinated
disclosure, and withhold witnesses for unpatched deployed systems. A comment planted in the code could
steer the Direct arm to "no bug"; Translate may be less exposed, since the solver
decides, but its spec is still model-written (untested). Sending proprietary code to a hosted model also discloses it; on-premise models avoid that.

# 8. Division of work and use of AI tools

**Contributions.**

* *Yash:* coordination; directed the build of the SP1 and SP2 pipelines; ran all Claude experiments; and drafted the report.
* *Joshua:* the backend for the SoC open-weight models (`premortem/llm.py`) and the Qwen and Llama runs (§5–6).
* *Hein:* the SP3 analyses (spec-style classifier, design facts vs. outcomes); the precise statements of both formulations and their limits (§2, §6); and the final clarity review (summary, definitions, statistical claims).

**Use of AI tools.** We used Claude Code (Anthropic) to execute our proposal design and perform the experiments in accordance with our specifications. We then vetted the outputs and refined our preliminary analysis with AI assistance, ultimately reviewing and making the final edits and modifications ourselves to produce our final submission.


# References

[1] C. Newcombe, T. Rath, F. Zhang, B. Munteanu, M. Brooker, M. Deardeuff. How Amazon Web Services uses formal methods. *Communications of the ACM*, 58(4), 2015.

[2] L. Kang, Z. Zhao, D. Hsu, W. S. Lee. On the empirical complexity of reasoning and planning in LLMs. *Findings of EMNLP*, 2024.

[3] S. Russell, P. Norvig. *Artificial Intelligence: A Modern Approach*, 4th ed. Pearson, 2021. Ch. 6 (CSP), Ch. 7 and 9 (logic), Ch. 11 (planning), Ch. 12 (probability), Ch. 16 (decisions), Ch. 27 (ethics and safety).

[4] L. de Moura, N. Bjørner. Z3: An efficient SMT solver. *TACAS*, 2008.

[5] Y. Hao, Y. Chen, Y. Zhang, C. Fan. Large language models can solve real-world planning rigorously with formal verification tools. *NAACL*, 2025.

[6] H. Kautz, B. Selman. Planning as satisfiability. *ECAI*, 1992.

[7] J. Hoffmann, B. Nebel. The FF planning system: Fast plan generation through heuristic search. *Journal of Artificial Intelligence Research*, 14, 2001.

[8] J. Liu, C. S. Xia, Y. Wang, L. Zhang. Is your code generated by ChatGPT really correct? Rigorous evaluation of large language models for code generation (EvalPlus). *NeurIPS*, 2023.

[9] L. Pan, A. Albalak, X. Wang, W. Y. Wang. Logic-LM: Empowering large language models with symbolic solvers for faithful logical reasoning. *Findings of EMNLP*, 2023.

[10] T. Bylander. The computational complexity of propositional STRIPS planning. *Artificial Intelligence*, 69, 1994.

[11] L. Guan, K. Valmeekam, S. Sreedharan, S. Kambhampati. Leveraging pre-trained large language models to construct and utilize world models for model-based task planning. *NeurIPS*, 2023.

[12] J. C. King. Symbolic execution and program testing. *Communications of the ACM*, 19(7), 1976.

[13] R. Just, D. Jalali, L. Inozemtseva, M. D. Ernst, R. Holmes, G. Fraser. Are mutants a valid substitute for real faults in software testing? *FSE*, 2014.

[14] M. Kleppmann. How to do distributed locking. Blog post, 2016 (the fencing-token argument used in the lock family).

[15] D. Jackson. *Software Abstractions: Logic, Language, and Analysis*, revised ed. MIT Press, 2012 (the small-scope hypothesis).

[16] P. Schanely. CrossHair: an analysis tool for Python. https://github.com/pschanely/CrossHair.

[17] E. Clarke, D. Kroening, F. Lerda. A tool for checking ANSI-C programs. *TACAS*, 2004.

[18] Qwen Team. Qwen 3.8 27B, open-weight model, served by SoC's SoCLaaS endpoint, accessed November 2026.

[19] A. Dubey et al. The Llama 3 herd of models. arXiv:2407.21783, 2024.

Course material: CS3263 course notes.


# Appendix A. Artefacts from the cached runs

**A.1 A rare SP1 bug** (`days_in_month`, mutant 400 → 399, trigger rarity 0.019%; every model except Llama found it in
both arms):

```python
return y % 4 == 0 and (y % 100 != 0 or y % 399 == 0)
```

**A.2 Specification anchoring** (Translate, Haiku 4.5, mutant `y % 400 == 0 -> y % 400 != 0`). The
spec's helper copies the mutated line from the code under review, so Z3 reports no violation and the
soundness check against the reference fails. The `withdraw` miss is the same pattern (`new_balance <= 0`
copies the mutated boundary).

```python
def leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 != 0)
```

**A.3 A wrong specification yields a fabricated witness** (Translate, Haiku 4.5, `weekday`). After
`m += 12` for January and February, `t[m - 1]` is out of range, so `post` raises; the verifier counts
that as a violation and returns `{day: 1, month: 1, year: 1801}`, on which the code is correct.

```python
t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
if m < 3:
    m += 12
    y -= 1
sakamoto_result = (y + y // 4 - y // 100 + y // 400 + t[m - 1] + day) % 7
```

**A.4 A false alarm on a fixed design** (Direct, Haiku 4.5, `payments-fixed-1`; replay fails at step 2
because `(dedup-racy)` is false in this design):
`send o1 a0 t0` → `accept-new-racy o1 a0` → `tick o1 a0 t0 t1` → `time-out-and-retry o1 a0 a1 t1` →
`send o1 a1 t0` → `accept-new-racy o1 a1` → `charge o1 a0` → `lose-response o1` → `charge-again o1 a1`.

**A.5 The planner exploits translation slack** (Translate, Haiku 4.5). In `lock-flawed-3` the model's
`:init` adds `(lease-age t0)`, a lease clock running before anyone holds the lock; the planner's trace
starts `tick t0 t1` → `tick t1 t2` → …, legal only in the model's problem, and replay on gold fails at
step 1. In `queue-fixed-8`, 15 extra `(zero-tick …)` facts let the trace start `receive w1 m1 t15`,
skipping the visibility timeout.

**A.6 Gold shortest trace for `payments-subtle-1`** (SATPlan, 8 events; the retry passes the
idempotency lookup because the record is written only after a charge):
`send o1 a0 t0` → `accept-new-racy o1 a0` → `tick o1 a0 t0 t1` → `time-out-and-retry o1 a0 a1 t1` →
`send o1 a1 t0` → `accept-new-racy o1 a1` → `charge o1 a1` → `charge-again o1 a0`.

**A.7 A design document as the LLM sees it** (`payments-subtle-1`):

> Checkout payment flow (design doc)
>
> When a customer places order o1, the checkout service (the client) sends a charge request to an
> external payment provider and waits for the reply. The network between them is unreliable: a request
> or a response can be lost, and messages can be delayed arbitrarily, so a request may still be in
> transit after the client has stopped waiting for it. The provider serves requests concurrently on
> several worker threads, in whatever order they arrive, so the steps of different requests (looking up
> records, charging, writing records) can interleave.
>
> Each request is one attempt (a0 for the first try). After sending an attempt the client starts a
> timer at t0; every clock tick advances it by one, and when it reaches t1 (1 tick after sending)
> without a response the client gives up on that attempt and retries with the next attempt number
> (a1, then a2). At most two retries are made. If a success response arrives while the client is still
> waiting, the order is confirmed and no further attempts are made.
>
> Charging and duplicate protection. Every attempt for an order carries the same idempotency key
> (derived from the order number). When a request arrives, the provider looks the key up in its
> idempotency table. If a record is found, the provider does not charge again; it just returns the
> stored success response. If no record is found, the provider approves the request, charges the card,
> and, once the charge has succeeded, writes the record for the key together with the response.
>
> Initially the client is about to send attempt a0 for order o1; nothing has been charged and the provider has no record for o1.

**A.8 The inventory invariant behind the fixed label from size 8** (proved by hand, because search runs out of budget there). In every reachable state, stock + holding + sold = $S$. Initially stock = $S$; `reserve-atomic` moves a unit from stock to holding, `expire-hold` moves it back, `pay` moves it to sold, and the other actions change no count or are disabled by the fixed design facts; each customer leaves browsing once, so no count rises twice. Hence sold ≤ $S$ < $S + 1$.


# Appendix B. The encodings, as generated by the code

*Produced by `python -m experiments.encodings`; every formula below is printed from the objects the experiments use.*

## B.1 SP1: the CSP/SMT instance for `days_in_month` (mutant 400 → 399)

Code under review (the helper; the docstring states the 400-year rule):

```python
def leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 399 == 0)
```

**Variables and domains** X = {month, year}, from `domain.make_symbolic`:

```
month >= 1
month <= 12
year >= 1
year <= 3000
```

**Code semantics** ⟦f⟧, the Z3 term the symbolic executor builds for the return value. `exc` and `unwind` simplify to False, because this function cannot raise or loop:

```
result = If(And(Not(2 == month),
       Not(Or(4 == month,
              6 == month,
              9 == month,
              11 == month))),
   31,
   If(And(Not(2 == month),
          Or(4 == month,
             6 == month,
             9 == month,
             11 == month)),
      30,
      If(And(0 == year%4,
             If(0 == year%100,
                0 == year%399,
                Not(0 == year%100))),
         29,
         28)))
exc    = False
unwind = False
```

The unmutated reference builds the same term with `year%400` in place of `year%399`.

**Specification** written by Sonnet 5.5 in the Translate arm (verbatim, from the response cache):

```python
def pre(month, year):
    return 1 <= month <= 12 and 1 <= year <= 3000

def is_leap_spec(year):
    if year % 400 == 0:
        return True
    if year % 100 == 0:
        return False
    return year % 4 == 0

def post(month, year, result):
    if month == 2:
        if is_leap_spec(year):
            return result == 29
        return result == 28
    if month == 4 or month == 6 or month == 9 or month == 11:
        return result == 30
    return result == 31
```

The executor compiles `pre` and `post(month, year, result)` the same way, with `result` bound to the code's term above. The full query Φ = domain ∧ ¬unwind ∧ pre ∧ (exc ∨ ¬post) is a DAG of 117 shared nodes. Z3 proves it **equivalent** to the readable formula:

```
Φ  ≡  1 ≤ month ≤ 12 ∧ 1 ≤ year ≤ 3000 ∧ month = 2
      ∧ L399(year) ≠ L400(year)
L399(y) = y%4 = 0 ∧ (y%100 ≠ 0 ∨ y%399 = 0)   (the code)
L400(y) = y%400 = 0 ∨ (y%100 ≠ 0 ∧ y%4 = 0)   (the spec)
```

In words: a failing input is a February in a year where the two leap rules disagree. Z3 answers `sat` with the model `[year = 400, month = 2]`; 400 is divisible by 400 but not by 399, so the code returns 28 instead of 29.


## B.2 SP2: STRIPS action and SATPlan clauses (`payments-subtle-1`, step t = 4)

Ground task: 27 facts, 27 ground actions after relaxed-reachability grounding.

**Ground STRIPS action** `accept-new-racy o1 a1`:

```
PRE = {dedup-racy, in-flight o1 a1, no-record o1}
ADD = {approved o1 a1}
DEL = {in-flight o1 a1}
```

**Precondition and effect clauses** for this action at t = 4 (each clause is a disjunction). The static design fact `(dedup-racy)` is true at every step, so the encoder fixes it to a constant and its precondition clause is satisfied and dropped:

```
¬accept-new-racy(o1,a1)@4 ∨ in-flight(o1,a1)@4
¬accept-new-racy(o1,a1)@4 ∨ no-record(o1)@4
¬accept-new-racy(o1,a1)@4 ∨ approved(o1,a1)@5
¬accept-new-racy(o1,a1)@4 ∨ ¬in-flight(o1,a1)@5
```

**Explanatory frame clauses** for the fact `(no-record o1)`. It can stop holding only if an action that deletes it occurs (here `charge`), and start holding only if one adds it (none does):

```
¬no-record(o1)@4 ∨ no-record(o1)@5 ∨ charge(o1,a0)@4
no-record(o1)@4 ∨ ¬no-record(o1)@5
```

**Exactly one action per step** is added as a cardinality constraint over all action variables of the step (sequential-counter encoding, `pysat.card.CardEnc.equals`).

**Horizon iteration** (T = 0, 1, …; the first satisfiable T is the shortest trace):

| T | variables | clauses | result |
|---|---|---|---|
| 0 | 0 | 0 | UNSAT |
| 1 | 5 | 9 | UNSAT |
| 2 | 18 | 42 | UNSAT |
| 3 | 41 | 101 | UNSAT |
| 4 | 78 | 209 | UNSAT |
| 5 | 129 | 364 | UNSAT |
| 6 | 188 | 550 | UNSAT |
| 7 | 258 | 773 | UNSAT |
| 8 | 332 | 1016 | SAT |

Decoded plan (8 events): `send o1 a0 t0` → `accept-new-racy o1 a0` → `tick o1 a0 t0 t1` → `time-out-and-retry o1 a0 a1 t1` → `send o1 a1 t0` → `accept-new-racy o1 a1` → `charge o1 a1` → `charge-again o1 a0`


## B.3 SP2: certifying the fixed variant with GBFS + h_FF (`payments-fixed-1`)

h_FF(initial state) = 4 (finite, so the delete relaxation alone cannot rule the violation out). GBFS expanded 72 states, generated 200, pruned 28 dead ends (h_FF = ∞) and returned **unsolvable**: the open list emptied, so `(charged-twice o1)` is unreachable from the initial state.

