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
and Qwen does so in Translate on the main set;
translation cuts Haiku's false alarms on correct designs from 60% to 35% (95% to 45% with hidden names; nominal paired
p = 0.18 and 0.002, as designs share five templates).
Llama 3.1 8B fabricates in Direct, and translation silences rather than fixes this: its specifications and problem files
are mostly unusable or incomplete, so it answers "safe" or nothing.
Translation risks specs that copy the bug, permissive models that planners exploit, and solver blow-up.

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
* **Domains $D$:** the stated ranges, e.g. $1 \le month \le 12$, $0 \le n \le m$, and each $e_i \in [lo, hi]$.
* **Constraints $C$:** $\llbracket f \rrbracket(x, r) \land \lnot spec(x, r)$, where $\llbracket f \rrbracket(x, r)$ holds iff $r$ is what $f$ returns on $x$.

The result $r$ and intermediate values are not separate variables: each is a shared sub-term of one formula DAG, fixed by
the inputs, i.e. an auxiliary variable already eliminated (CSP p.13). The domains are finite, so this is
a finite CSP, a class that is NP-complete (CSP p.8). Z3, however, receives SMT over unbounded integers
(`Int`) with the bounds as ordinary constraints; products of variables and `//` or `%` by a variable
make it non-linear integer arithmetic, undecidable in general. Our bounded queries are decidable, but
Z3's non-linear procedures are incomplete, so it can answer *unknown* (§5.1).

**Building $\llbracket f \rrbracket$: bounded symbolic execution** [12] (`sp1/symexec.py`). The proposal
planned an off-the-shelf executor; we wrote our own because tools such as CrossHair cannot prove
unsatisfiability within a bound, which Theorem 1 needs. The executor walks the syntax tree once with a symbolic environment
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
on $x_0$ reaches this point, and then $\rho[x][x_0]$ is the concrete value of $x$. The join selects the branch taken, `return` and raises record the outcome under the path condition, and $cond_k$ marks a
$(k{+}1)$-th iteration. ∎

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

**The solver.** Z3 [4] decides satisfiability with DPLL(T): a DPLL core (PropLogic p.35) with
conflict-directed backjumping (CSP p.40–41) searches the Boolean skeleton, and integer theory solvers return
conflicts. Every model is re-executed in Python before it counts, and Lemma 1 is tested against real execution on 25 random
inputs per benchmark and hand-written mutant (`tests/test_symexec.py`). Appendix B.1 shows a full instance.

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
**safety** property. Liveness failures are not STRIPS goals and are out of scope. "Safe" covers the instance at its size, not every size; we rely on the small-scope
hypothesis [15], that most flaws already appear in small instances, and on an inductive invariant
where search runs out (inventory from size 8, §6).

**SATPlan encoding** [6] (Planning p.31–37; `planning/satplan.py`). For horizon $T$: a variable $f^t$ per
fact and step $t \le T$, and $a^t$ per action and step $t < T$, with CNF clauses (PropLogic p.46; facts not yet reachable at step $t$ become constants):

1. **initial state:** $f^0$ for $f \in I$ and $\lnot f^0$ for $f \notin I$;
2. **goal:** $g^T$ for each $g \in G$;
3. **preconditions:** $a^t \Rightarrow p^t$ for each $p \in pre(a)$;
4. **effects:** $a^t \Rightarrow f^{t+1}$ for $f \in add(a)$, and $a^t \Rightarrow \lnot f^{t+1}$ for $f \in del(a) \setminus add(a)$;
5. **explanatory frame axioms:** $f^t \land \lnot f^{t+1} \Rightarrow \bigvee\{a^t : f \in del(a) \setminus add(a)\}$ and $\lnot f^t \land f^{t+1} \Rightarrow \bigvee\{a^t : f \in add(a)\}$;
6. **exactly one action per step:** the exclusion axioms (Planning p.36), strengthened, in linear size.

**Lemma 2.** Under (6), clauses (4)–(5) are equivalent to the lecture's successor-state axioms
$F^{t+1} \Leftrightarrow ActionCausesF^t \lor (F^t \land \lnot ActionCausesNotF^t)$ (Planning p.34).
*Proof.* Let $a$ act at step $t$. (4) forces $f^{t+1}$ if $f \in add(a)$ and $\lnot f^{t+1}$ if
$f \in del(a) \setminus add(a)$; otherwise (5) forces $f^{t+1} = f^t$. Hence $s_{t+1} = \mathrm{RESULT}(s_t, a)$, with $a$ applicable by (3). ∎

**Theorem 2.** The horizon-$T$ formula is satisfiable iff a plan of exactly $T$ actions ends in a state
containing $G$, and the true action variables of a model form one. Iterating $T$ from 0 returns a *shortest* failure trace at the first satisfiable $T$; decoded plans are re-validated. UNSAT for all $T \le T_{max}$ proves only bounded safety.

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
reachability on the model's problem; if a plan exists, SATPlan returns a shortest trace within its 120 s budget, else the GBFS trace is kept (B.2–B.3 show real clauses and a certificate).

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

**Mutants and labels.** The candidates are 808 automatic first-order mutants, 42 hand-written realistic bugs (a
forgotten 400-year rule, a comparator dropped as an "optimisation") and 9
equivalent rewrites.

Each candidate is labelled in four steps. Its *trigger rarity* is the probability that a random
in-domain input exposes it (integers uniform; a list draws its length, then its elements, uniformly),
computed exhaustively for integer domains up to 70k points and from 5,000 samples otherwise. $\Phi_{gold}$ is then solved, every Z3 witness is confirmed by real
execution, and equivalence is accepted only under the conditions of §2.1.

**Selection.** For each function we keep every hand bug, fill the rarity buckets with automatic mutants
(preferring rare ones), and add two controls: the clean reference, plus an equivalent mutant when one
exists. These are deliberately hard.

**Result.** 174 instances: 115 bugs (67 common, 19 uncommon, 21 rare, 8 very rare) and 59 controls (37
clean, 22 provably equivalent). Of the 859 candidates, 59 were dropped as non-terminating, not encodable or not provably equivalent.

## 3.2 SP2: 60 designs, plus 30 stress, 60 opaque and 12 long variants

Each design document (about 200 words) states the components, the failure model and the mechanism
without judging it; subtle variants read like a fix the engineer believes works. Gold shortest traces
are 6–15 events. Three further sets were added:

* *Stress* (sizes 6 and 8): 17–27 events.
* *Opaque:* the main set with design facts and design-specific events renamed (`mode-2`, `accept-3`) and comments removed; the semantics are unchanged.
* *Long:* payments and inventory at sizes 12 and 16 (30–51 events), 5.5 models only.

Each family has one violation and three variants (flawed; subtle, which looks fixed; fixed):

* *payments*, charged twice: no deduplication; key saved only after charge; atomic insert-if-absent
* *inventory*, sold > stock: lost stock update; payment after hold expiry; atomic decrement + hold check
* *lock*, stale write wins: no fencing or lease check; lease checked before write; fencing tokens [14]
* *queue*, payout twice: no consumer dedup; dedup ids in memory; dedup id in the DB transaction
* *cache*, stale cache at end: update DB, delete cache; delete cache, update DB; leases revoked by delete

# 4. Method

**Models.** Claude Haiku 4.5, Sonnet 5.5 and Opus 5.5 with default extended thinking, called through
the Claude Code CLI with *all tools disabled* (so Direct cannot run code). Two open-weight models on SoC's endpoint (SoCLaaS)
bracket them: Qwen 3.8 27B, which reasons before answering, and Llama 3.1 8B, which does not, both at temperature 0 with a
32k-token output budget. Qwen ran SP1 and the SP2 main set only, as one SP2 answer took 5–10 minutes on the shared endpoint.
Requests dropped under load were resubmitted, not scored. Both arms see the same inputs: the code with its docstring and the
input domain (SP1); the design document, the family's PDDL domain (events, with comments) and object names (SP2).

**Direct arm.** JSON with a verdict and a witness: a failing input (SP1) or a list of ground actions (SP2).

**Translate arm, SP1.** The model writes `pre(...)` and `post(..., result)` in the supported Python subset, stating the docstring's intent, not the code's behaviour; `spec_check` then runs.

**Translate arm, SP2.** The model writes the complete initial state, including design facts and counters (object names and the goal are given); the pipeline of §2.2 then solves it.

**Repair loop.** Errors are fed back up to twice: syntax errors, unsupported constructs, a vacuous precondition, a wrong goal, type or arity errors: a harness with verification and retries (GenAI p.28).

**Tool budgets.** An SP1 spec check has a 120 s deadline; Z3
queries time out at 60 s; planner search is capped at 3 M expansions or 300 s, SATPlan at 120 s. A
budget hit, a Z3 *unknown* or a failed coverage check ($\Psi$ satisfiable) is reported as *undecided*,
never as "no failure".

**Scoring** is exact, on gold models: an SP1 witness is valid only if it is in-domain and the code
under review and the unmutated reference behave differently on it; an SP2 trace is valid if replaying
it on the gold problem reaches the violation.

Outcomes are *valid witness*, *fabricated* (an invalid witness or a false alarm on a control: a
hallucination made checkable, GenAI p.9), *miss*, *correct no-failure*, or *undecided* (counted as no answer).



# 5. Results

All numbers come from `experiments/analyze.py` (full tables, with every interval, in `results/tables.md`). Brackets are 95%
Wilson intervals (valid at 0% and 100%); paired comparisons use the exact McNemar test.

## 5.1 SP1: functions (115 bugs, 59 controls)

**RQ1.** Every model except Llama finds essentially every bug in both arms, at every trigger rarity (Table 1, Fig. 1). At this
ceiling the test cannot detect a rarity effect; difficulty shows only as cost (hard-tier answers use 2–3×
the tokens) and as Z3 *unknown* on arithmetic-heavy specs. Random testing differs: $N$
inputs from the same sampler catch a bug of rarity $r$ with probability $1-(1-r)^N$ (ProbGrapModel p.22), so 100 inputs catch 34% of rare and
5% of very rare bugs, and 1,000 catch 93% and 36%. On these benchmarks rarity defeats *testing*, not code reading or symbolic search, for a capable model.
Llama Direct finds 33 of 55 common base-tier bugs but only 6 of 40 rarer ones, though rarity and difficulty are confounded here.

**RQ2.** No Claude or Qwen run raised a false alarm on the 59 controls, 22 of them equivalent mutants built to look buggy; Translate left 1 (Haiku) and 5 (Opus) *undecided*. Llama Direct raised 45 false alarms and invented a witness for 60 of the 115 bugs. Translate cut its false alarms to 12 (exact McNemar p < 0.001), but all 12, and 20 of its 22 misses, came from unsound specs.

::: keep
| model | arm | base found /95 | hard found /20 | fabri&shy;cated | false alarms /59 | no answer | $ per inst. | output tokens |
|---|---|---|---|---|---|---|---|---|
| Haiku&nbsp;4.5 | Direct | 100% | 95% | 0 | 0 | – | 0.025 | 4,838 |
| Haiku&nbsp;4.5 | Translate | 98% | 95% | 1 | 0 | 1 | 0.026 | 4,968 |
| Sonnet&nbsp;5.5 | Direct | 100% | 100% | 0 | 0 | – | 0.009 | 431 |
| Sonnet&nbsp;5.5 | Translate | 100% | 95% | 0 | 0 | 1 | 0.008 | 208 |
| Opus&nbsp;5.5 | Direct | 100% | 100% | 0 | 0 | – | 0.018 | 470 |
| Opus&nbsp;5.5 | Translate | 100% | 95% | 0 | 0 | 6 | 0.021 | 383 |
| Qwen&nbsp;3.8&nbsp;27B | Direct | 99% | 100% | 0 | 0 | 1 | – | 1,200 |
| Qwen&nbsp;3.8&nbsp;27B | Translate | 99% | 95% | 0 | 0 | 4 | – | 6,447 |
| Llama&nbsp;3.1&nbsp;8B | Direct | 41% | 5% | 60 | 45 | 7 | – | 451 |
| Llama&nbsp;3.1&nbsp;8B | Translate | 28% | 20% | 14 | 12 | 70 | – | 429 |

*Table 1.* SP1 outcomes. In *Translate* the named model writes the specification and Z3 searches it. *No answer*
(bugs and controls): a checker timeout or Z3 *unknown* (*undecided*) for Claude; no verdict, no accepted spec, or (Qwen's 4) the endpoint's 15-minute limit for open-weight models.
:::

*SP3.* Of the specifications whose soundness check completed, these were *sound* (the reference satisfies them): 169/172 (Haiku), 173/173 (Sonnet), 165/165 (Opus) and 169/170 (Qwen). *Discriminating* (the mutant violates them) is the valid-witness rate above. Haiku's three unsound specs are model errors (§A.2–A.3): the docstring fixes the answer on each violating reference input. Llama differs in kind: only 103 of its 174 specs passed the checker (70 runs failed after two repairs, 46 of them calling the unsupported `isinstance`), and only 45 of the 103 are sound.

**Translate failures.** For the Claude models every one comes from the specification or the tool, never the search: two postconditions copied the code's bug (§A.2), one spec raised an exception and produced a fabricated witness (§A.3), and eight checks were undecided (three timeouts, five Z3 *unknown*s).

![](../results/figures/sp1_rarity.png){width=48%} ![](../results/figures/sp2_length.png){width=48%}

*Fig. 1 (left):* SP1 base tier, valid witnesses vs. trigger rarity (Llama dashed) against random testing. *Fig. 2 (right):* SP2 valid traces vs. shortest trace length (main + stress).

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
replays on the gold problem and reaches the violation (flawed + subtle designs). FA = false alarm, a violation claimed on a fixed
design. Translate was *undecided* (not FA) on inventory's fixed design at size 8. Qwen ran the main set only.
:::

**RQ1.** Sonnet 5.5 and Opus 5.5 produced a valid trace every time, from 6 up to 51 events (on the long set 8/8 per model and arm, 95% interval [68–100], with no false alarm; Translate was undecided on its inventory fixed designs, sizes 12 and 16). Haiku stays near 80% with no length trend. On overall correctness, paired over its 150 designs, only Translate is right on 41 and only Direct on 21 (exact McNemar p = 0.15, 0.39 and 0.17 per set; 0.015 pooled, but the sets share templates and are not independent). Qwen's Translate was right on all 60 main designs and its Direct on 57, its 3 invalid traces being format slips, not misreadings. Llama Direct produced no valid trace on any set.

**RQ2.** Fabrication separates the arms.

* *Haiku Direct* claims violations on 60% of fixed designs (80% stress, 95% opaque). Translate roughly halves this, to 35% (40%, 45%); exact McNemar on false alarms gives p = 0.18, 0.22, 0.002. Its Direct traces fail on design facts: 16 (main) and 30 (opaque) used an event of *another* design variant, typically a familiar failure pattern (§A.4).
* *Llama Direct* claims violations on 70% of fixed designs (60% stress, 90% opaque); Translate cuts this to 10% (10%, 40%; exact McNemar p = 0.002, 0.13, 0.002) but misses 29 of 40 violating main-set designs: its "safe" verdicts are right for the wrong reason.

**SP3 (translation quality).**

* *Sonnet and Opus* reproduced the gold initial state exactly in all 90 main and stress problems, and *Qwen* in all 60 main ones. On the opaque set the 5.5 models omitted one fact in 8/60, which no action's precondition uses.
* *Haiku's design facts* were exact in 49/60 main and 35/60 opaque. Its other errors were permissive initial facts the planner exploited (§A.5). All 450 Claude translations parsed without repair.
* *Llama* left out about a third of the gold initial facts (mean recall 0.64 on the main set; design facts exact in 22/60; 8 never parsed), mostly the static successor and ordering facts of clocks and tokens. Without them the violation is unreachable: the planner proved "no violation" on all 29 missed flawed designs and on 16 of the 20 fixed ones.

**Cost.** Over the 150 instances all Claude models ran, Translate is always cheaper (US$ per instance: Haiku 0.053 vs
0.063, Sonnet 0.019 vs 0.025, Opus 0.040 vs 0.048). Total Claude usage was US$80 for 2,553 calls; SoC serves the open-weight models free.

## 5.3 The classical tools

* *Worst case vs. observed.* PlanSAT is PSPACE-complete (Planning p.38), but only inventory shows pronounced state explosion (Table 3): its $S{+}1$ interchangeable customers interleave, so reachable states grow 1,500× from size 1 to 4; the other families grow roughly linearly. Trace length is not the driver: queue and inventory at size 8 need 21 and 27 events.
* *SATPlan* finds shortest traces in milliseconds for four families. On inventory it takes 1.1 s at size 3, about 2 minutes at size 4, and times out (300 s) at sizes 6 and 8.
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
$2^{|F|}$ bounds the state space ($2^{44}$ to $2^{218}$ at size 8), but certification only visits reachable states.
:::


# 6. Analysis and insights

**SP1: localisation, not search.** A first-order mutant leaves a visible diff against a docstring that
states the intent, so trigger rarity, which decides whether *testing* finds a bug, showed no detectable
effect on capable models (Fig. 1). In Kang et al.'s terms [2] (GenAI p.18), base-tier SP1 is the easy case: the next step
(find the line contradicting the docstring) is cheap, so the chain of thought stays short. Where a witness
must be *constructed*, the models paid 2–3× more tokens rather than failing.

**SP1: translation moves the risk into the specification.** The spec must state the docstring's intent
while the model reads code that contradicts it. Nearly every spec is *constructive*: `post` recomputes the
answer and compares it with `result` (169–172 of 174 per model). SP1 Translate is thus a differential check
against a second, model-written implementation (N-version programming), which is why a spec can inherit the
bug it should expose (§A.2). The repair loop fixes form (Haiku 106 → 112, Opus 104 → 114 of 115) but not
meaning; specs should be written blind to the code, or checked against known examples.

**SP2: the jagged frontier runs between model generations.** The 5.5 models are never wrong in either arm on
all four sets (Translate is undecided only where certification runs out of budget, §5.3). Haiku's Direct errors are
design misreadings: it applies a well-known pattern, such as the check-then-act race, to a design whose text rules it out
(§A.4). Translation does not remove misreading; Haiku moves it into the design facts and adds permissive initial facts that
the planner turns into shortcuts (§A.5). Still, its false alarms roughly halved, at lower cost.

**Open weights: a floor below which translation silences instead of fixing.** Qwen 3.8 27B, free on SoC's endpoint, matches
the 5.5 models on SP1 and the SP2 main set in Translate, at the cost of reasoning (about 8–10k output tokens per SP2 Direct answer). Llama 3.1 8B, which does not reason, fabricates in Direct: witnesses that do not
reproduce, and traces with wrong event names or arity (37 of 48 classified main-set failures). Translation
silences this rather than repairing it: Llama cannot write the formal language reliably (70 of 174 SP1 runs end with no accepted
spec, 8 of 60 SP2 problems never parse), and problem files missing a third of the initial state make flawed and fixed designs
alike look safe. So false alarms fall for the wrong reason: against the policy "always answer safe", Llama Translate on the SP2
main set adds one valid trace and two false alarms, so it beats that policy only if a miss costs over four false alarms (at $\pi = 1/2$). "Translate when the model is weak" holds only above a floor: the model must
write the formal language correctly and completely. Open-weight results on other SP2 sets are Llama's.

**Length vs. familiarity.** Our violations are textbook patterns; once one is recognised, a longer trace
is bookkeeping: from 6–15 to 30–51 events the 5.5 models found a valid trace on every violating design, and Direct answers grew only from about 1.2k to 1.5k tokens. With facts renamed `mode-N`, they were still never wrong, so they map the
mechanism, not just its name. Haiku leans on names: its Direct false alarms rose from 60% to 95%; Translate held it to 45%: writing
the initial state forces one design fact per mechanism.

**The tools have cliffs too (§5.3).** The standard remedies lie outside the course: *symmetry reduction* (merging states
that differ by a permutation of interchangeable objects, such as inventory's customers), *partial-order reduction* (one order for
independent events, Planning p.9), CBMC's *unwinding assertions* (checking that $unwind$ is unsatisfiable), and *inductive
invariants* (k-induction with $k = 1$), which prove safety by entailment (PropLogic p.28) with three checks:
$$Inv(s_0), \qquad Inv(s_t) \land T(s_t, s_{t+1}) \models Inv(s_{t+1}), \qquad Inv \models \lnot G.$$
Inventory's label from size 8 rests on one, proved by hand: stock + holding + sold = S. Initially stock = S; `reserve-atomic`
moves a unit from stock to holding, `expire-hold` moves it back, `pay` moves it to sold, and the other
actions change no count or are disabled by the fixed design facts; each customer leaves browsing once,
so no count rises twice. Hence sold ≤ S < S + 1.

**Is translating worth it? A decision rule.** Choosing an arm is a maximum-expected-utility decision
(Decision p.16). With a share $\pi$ of flawed designs and costs $c_{FA}$ per false alarm (reviewer time),
$c_{miss}$ per flawed design left without a valid witness, $c_{rev}$ per undecided case left to a reviewer,
and $c_{run}$ per run (model-call charges only),
$$EU(arm) = -\big((1-\pi)\,P_{FA}\,c_{FA} + \pi\,P_{miss}\,c_{miss} + P_{und}\,c_{rev} + c_{run}\big).$$
For Haiku on the SP2 main set, Translate has fewer false alarms (35% vs 60%), fewer flawed designs
without a valid trace (6 vs 9 of 40), nothing undecided and the lower cost (US$0.051 vs 0.062), so
under this loss and these rates it wins for any $\pi$ and positive costs; on the opaque set it trades
two detections for half the false alarms. For the 5.5 models on SP2 the error rates are zero, so cost
meets abstention: Translate is cheaper and wins outright on the main set, but is undecided on
inventory's fixed design from size 8, where Direct answers correctly. On SP1, Opus's Translate is
dearer and leaves one bug and five controls undecided, so Direct wins; Sonnet's small model-call
saving must be weighed against one unresolved faulty instance and its review cost. Only Translate can *certify* absence, with a solver result and
audit trail that hold relative to the translated model. *Direct suffices* when the specification is local and explicit, the artefact small and the model strong.

Direct accuracy may keep rising, as the step from Haiku 4.5 to the 5.5 models suggests. But "computationally difficult
problems [are] likely to remain difficult" (GenAI p.31): inventory from size 8 reached that regime for the tools.

**Threats to validity.**

* *Mutants* are small, first-order faults [13]; real bugs often span several lines (Direct also found 41–42 of 42 hand-written bugs).
* *Specifications.* Docstrings are complete; vaguer real ones would hurt Translate more. Functions were selected to be encodable (integers, Booleans, lists; no strings, floats or recursion), favouring the tools.
* *Familiarity and contamination.* SP1 functions derive from public benchmarks; renaming does not remove contamination. SP2 families are textbook patterns; the opaque set removes only lexical cues.
* *Authorship.* The design documents and gold models were produced together; two documents contradicted their models and were corrected, with all affected instances rerun.
* *Scaffolding.* The given action schemas contain each failure mechanism as a named, guarded event, so SP2 Translate reduces to choosing one or two design facts per family, and that choice decides the outcome: correct in 47/49 (Haiku) and 60/60 (5.5 models, Qwen) main-set problems with exact facts, 0/11 (Haiku) with wrong ones. Writing the event model (Planning p.15), as in [11], is untested.
* *Sampling and configuration.* Instances are sampled once and share five templates (so intervals and p-values are nominal); many cells are at ceiling. Claude models used default thinking, open-weight ones temperature 0, so effort and sampling differ (Haiku 10–15k tokens, the 5.5 models about 1k).


# 7. Responsible AI

**Automation bias: what "no failure" means.** A verdict is a belief about a *model*, not a fact about
the world (ProbGrapModel p.4): SP1 certifies only within the domain and unroll bounds (Theorem 1), and
SP2 only within the event model, so a failure mode the domain lacks is invisible to both arms. We therefore say "no counterexample within the input and loop bounds" (SP1) or "no reachable
violation in this finite event model" (SP2), never "verified safe", which certainty and framing effects (Decision p.24–25) predict reviewers over-trust. Skipping manual review is
rational only if P(hidden failure | "no failure") is below review cost divided by incident loss
(Decision p.15–16, if review would catch the failure). On our SP2 main set, 2 of Haiku Direct's 10
"safe" verdicts were wrong and none of Haiku Translate's 13 (95% upper bound 23%); both depend on the
base rate of flawed designs (Bayes' rule, ProbGrapModel p.24–25) and miss failure modes outside the benchmark.

**Fabricated failures.** False alarms waste reviewer time and train reviewers to ignore the tool. A Translate witness is correct only
*with respect to the model's own specification*: 13 of Haiku's main-set SP2 Translate traces (40 across
all sets) were legal only in its mistranslated problem, as the planner optimises the model as written, not as meant (the King Midas problem,
ResponsibleAI p.35). Witnesses must therefore be replayed on the real artefact, as our scoring
does.

**Accountability.** Translate leaves an audit trail (spec, solver log, witness), close to a white-box
explanation (ResponsibleAI p.24), so a named engineer can sign off on *what was checked*; Direct
answers are post-hoc narratives (p.25–26). Responsibility stays with the humans who sign off (p.6); the tool supports a human–AI review team (p.45).

**Dual use and attacks on the reviewer.** A witness can help construct an exploit, and AI lowers the cost of
attacks (ResponsibleAI p.2–4); we would run the tool only on code the user owns, follow coordinated
disclosure, and withhold witnesses for unpatched deployed systems. A comment planted in the code could
steer the Direct arm to "no bug" (ResponsibleAI p.31); Translate may be less exposed, since the solver
decides, but its spec is still model-written (untested). Sending proprietary code to a hosted model also discloses it
(ResponsibleAI p.8–10); on-premise open-weight models avoid that.

# 8. Division of work and use of AI tools

**Contributions.** The work departed from the proposal's planned split.

* *Yash:* coordination; directed the Claude Code sessions that built the SP1 and SP2 pipelines; ran all Claude experiments; and drafted the report.
* *Joshua:* the backend for the SoC open-weight models (`premortem/llm.py`) and the Qwen and Llama runs (§5–6).
* *Hein:* the SP3 analyses (spec-style classifier, design facts vs. outcomes) and the precise statements of both formulations and their limits (§2, §6).

**Use of AI tools.** We used Claude Code (Anthropic) extensively. *Ours, from the proposal:* the research questions, the two formulations and their solvers, the five design families and their variants, the evaluation protocol and the risk plan. *Generated by Claude Code from our specifications and instructions:* the code, the PDDL domains and design documents, the statements and proofs in §2, and drafts of this report. *Checked mechanically:* every number comes from the repository's scripts and cached model outputs; 207 tests check the executor against Python and the planners against each other.


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

[15] D. Jackson. *Software Abstractions: Logic, Language, and Analysis*, revised ed. MIT Press, 2012 (the small-scope hypothesis).

Course material: CS3263 lecture slides (PropLogic, CSP, FirstOrderLogic as FOL, Planning, GenerativeReasoningAgenticAI as GenAI, Decision, ProbGrapModel, ResponsibleAI), cited as *Deck p.N*.


# Appendix A. Artefacts from the cached runs

**A.1 A rare SP1 bug** (`days_in_month`, mutant 400 → 399, trigger rarity 0.019%; every model found it in
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

