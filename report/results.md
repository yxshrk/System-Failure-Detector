# 5. Results

All numbers come from `experiments/analyze.py` (full tables in `results/tables.md`). Brackets are 95%
Wilson intervals (a binomial interval that stays valid at 0% and 100%); paired comparisons use the exact
McNemar test on the instances where exactly one arm is right.

## 5.1 SP1: functions (115 bugs, 59 controls)

| model | arm | base found /95 | hard found /20 | fabri­cated | false alarms /59 | unde­cided | $ per inst. | output tokens |
|---|---|---|---|---|---|---|---|---|
| Haiku 4.5 | Direct | 100% [96–100] | 95% [76–99] | 0 | 0 | – | 0.025 | 4,838 |
| Haiku 4.5 | Translate | 98% [93–99] | 95% [76–99] | 1 | 0 | 1 | 0.026 | 4,968 |
| Sonnet 5.5 | Direct | 100% | 100% | 0 | 0 | – | 0.009 | 431 |
| Sonnet 5.5 | Translate | 100% | 95% | 0 | 0 | 1 | 0.008 | 208 |
| Opus 5.5 | Direct | 100% | 100% | 0 | 0 | – | 0.018 | 470 |
| Opus 5.5 | Translate | 100% | 95% | 0 | 0 | 6 | 0.021 | 383 |

*Table 1.* SP1 outcomes. In *Translate* the named model writes the specification and Z3 searches it.
*Undecided:* the checker timed out or Z3 answered *unknown* (on bugs or controls).

* *The repair loop matters.* Using only the first specification, valid witnesses drop to 106 (Haiku), 113 (Sonnet) and 104 (Opus) of 115.
* *SP3.* Of the specifications whose soundness check completed, these were *sound*, i.e. the reference satisfies them: 169/172 (Haiku), 173/173 (Sonnet) and 165/165 (Opus). *Discriminating*, meaning the mutant violates them, is the valid-witness rate above. All three unsound specs are Haiku errors (§A.2–A.3), not ambiguous docstrings: the docstring fixes the answer on each violating reference input.

**RQ1.** Every model finds essentially every bug in both arms, at every trigger rarity (Fig. 1). At this
ceiling the test cannot detect a rarity effect; difficulty shows only as cost (hard-tier answers use 2–3×
the tokens) and as Z3 *unknown* on arithmetic-heavy specs. Random testing differs: $N$
uniform inputs catch a bug of rarity $r$ with probability $1-(1-r)^N$ (ProbGrapModel p.22), so 100 inputs catch 34% of rare and
5% of very rare bugs, and 1,000 catch 93% and 36%. Rarity defeats *testing*, not code reading or symbolic search.

**RQ2.** No model raised a false alarm in either arm on the 59 controls, 22 of them equivalent mutants
built to look buggy. Translate left 1 (Haiku) and 5 (Opus) controls *undecided* rather than wrongly certifying them.

**Translate failures.** Every one comes from the specification or the tool, never from the search: two
postconditions copied the code's bug (§A.2); one spec raised an exception and produced a fabricated
witness (§A.3); and eight checks were undecided (three checker timeouts on subset-sum DP specs, five Z3
*unknown*s at the 60 s limit on calendar and divisor arithmetic and a 17-step simulation).

![](../results/figures/sp1_rarity.png){width=48%} ![](../results/figures/sp2_length.png){width=48%}

*Fig. 1 (left):* SP1 base tier, valid witnesses vs. trigger rarity (LLM arms pooled over models) against
random testing. *Fig. 2 (right):* SP2 valid traces vs. shortest trace length (main + stress).

## 5.2 SP2: designs (60 main + 30 stress + 60 opaque + 12 long)

| model | arm | main valid /40 | main FA /20 | stress valid /20 | stress FA /10 | opaque valid /40 | opaque FA /20 | $ per inst. (main) |
|---|---|---|---|---|---|---|---|---|
| Haiku 4.5 | Direct | 78% [62–88] | 60% [39–78] | 85% | 80% | 68% | 95% | 0.062 |
| Haiku 4.5 | Translate | 85% [71–93] | **35%** [18–57] | 90% | **40%** | 63% | **45%** | 0.051 |
| Sonnet 5.5 | Direct | 100% | 0% | 100% | 0% | 100% | 0% | 0.025 |
| Sonnet 5.5 | Translate | 100% | 0% | 100% | 0% | 100% | 0% | 0.018 |
| Opus 5.5 | Direct | 100% | 0% | 100% | 0% | 100% | 0% | 0.048 |
| Opus 5.5 | Translate | 100% | 0% | 100% | 0% | 100% | 0% | 0.036 |

*Table 2.* SP2 outcomes. In *Translate* the named model writes the PDDL problem and the planners
search it. "Valid" = a trace that replays on the gold problem and reaches the violation
(flawed + subtle designs). FA = false alarm, a violation claimed on a fixed design.

**RQ1.** Sonnet 5.5 and Opus 5.5 produced a valid trace every time, from 6 up to 51 events (on the long set
8/8 per model and arm, 95% interval [68–100], with no false alarm).
Haiku stays near 80% with no length trend; its errors are design misreadings (RQ2 below). Paired over its
150 designs, only Translate is right on 41 and only Direct on 21 (per-set exact McNemar p = 0.15,
0.39 and 0.17; pooled p = 0.015, but the opaque designs rename the main ones).

**RQ2.** Fabrication separates the arms.

* *Haiku Direct* claims violations on 60% of fixed designs (80% stress, 95% opaque). Translate roughly halves this in every set, to 35% (40%, 45%), though no single set reaches p < 0.05.
* *Sonnet and Opus* raised no false alarm in either arm, with or without mechanism names.

* *Why Haiku's Direct traces fail:* every one that reached a precondition check failed on a design fact. 16 (main) and 30 (opaque) used an event of *another* design variant, typically a familiar failure pattern (§A.4); 3 and 2 had vocabulary or arity errors.

**SP3 (translation quality).**

* *Sonnet and Opus* reproduced the gold initial state exactly in all 90 main and stress problems. On the opaque set they omitted one fact in 8/60, but that fact (`pay-checks-hold`) is in no action's precondition, so the problems stay equivalent to gold.
* *Haiku's design facts* were exact in 49/60 main and 35/60 opaque problems. Its other errors were permissive initial facts that the planner exploited (§A.5). All 450 translations parsed without repair.


**Cost.** Over the 150 instances all models ran, Translate is cheaper for every model (US$ per instance: Haiku 0.053 vs
0.063, Sonnet 0.019 vs 0.025, Opus 0.040 vs 0.048). Total usage was US$80 for 2,553 calls.

## 5.3 The classical tools

| family | facts / actions (size 1 → 8) | shortest trace (size 1 → 8) | SATPlan vars / clauses (size 4) | reachable states, fixed (size 1 / 4 / 8) |
|---|---|---|---|---|
| payments | 27 / 24 → 55 / 66 | 8 → 22 | 721 / 2,173 | 148 / 532 / 1,044 |
| inventory | 22 / 14 → 218 / 945 | 6 → 27 | 4,568 / 18,236 | 16 / 24,992 / >2.6M |
| lock | 52 / 23 → 80 / 37 | 8 → 22 | 1,018 / 3,581 | 79 / 235 / 443 |
| queue | 16 / 8 → 44 / 36 | 7 → 21 | 535 / 1,783 | 14 / 38 / 70 |
| cache | 20 / 13 → 97 / 153 | 7 → 21 | 978 / 3,564 | 26 / 80 / 180 |

*Table 3.* Difficulty in course terms (SATPlan formula at the shortest $T$). Grounding keeps only relaxed-reachable instances of the $K^V$
possible ones (Planning p.10). A state is a subset of $F$ (flawed variant shown), so $2^{|F|}$ bounds the state space
($2^{44}$ to $2^{218}$ at size 8), but certification only visits reachable states.

* *Worst case vs. observed.* PlanSAT is PSPACE-complete (Planning p.38), but only inventory shows it: its $S{+}1$ interchangeable customers interleave, so reachable states grow 1,500× from size 1 to 4, while the other families grow roughly linearly with a timer or counter. Trace length is not the driver: queue and inventory at size 8 need 21 and 27 events.
* *SATPlan* finds shortest traces in milliseconds for four families. On inventory it takes 1.1 s at size 3, about 2 minutes at size 4, and times out (300 s) at sizes 6 and 8.
* *Certification* takes 9,026 GBFS expansions at inventory size 4 and 2.7 M (176 s) at size 6. From size 8 our 3 M-expansion / 5-minute budget runs out, so every Translate run on inventory's fixed design is scored *undecided*, not safe (the gold label comes from a conservation invariant).
