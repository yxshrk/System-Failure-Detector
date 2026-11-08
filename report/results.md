# 5. Results

All numbers come from `experiments/analyze.py` (full tables in `results/tables.md`). Brackets are 95%
Wilson intervals (a binomial interval that stays valid at 0% and 100%); paired comparisons use the exact
McNemar test on the instances where exactly one arm is right.

## 5.1 SP1: functions (115 bugs, 59 controls)

::: keep
| model | arm | base found /95 | hard found /20 | fabri­cated | false alarms /59 | no answer, unde­cided | $ per inst. | output tokens |
|---|---|---|---|---|---|---|---|---|
| Haiku 4.5 | Direct | 100% [96–100] | 95% [76–99] | 0 | 0 | – | 0.025 | 4,838 |
| Haiku 4.5 | Translate | 98% [93–99] | 95% [76–99] | 1 | 0 | 1 | 0.026 | 4,968 |
| Sonnet 5.5 | Direct | 100% | 100% | 0 | 0 | – | 0.009 | 431 |
| Sonnet 5.5 | Translate | 100% | 95% | 0 | 0 | 1 | 0.008 | 208 |
| Opus 5.5 | Direct | 100% | 100% | 0 | 0 | – | 0.018 | 470 |
| Opus 5.5 | Translate | 100% | 95% | 0 | 0 | 6 | 0.021 | 383 |
| Qwen 3.8 27B | Direct | 99% | 100% | 0 | 0 | 1 | – | 1,200 |
| Qwen 3.8 27B | Translate | 99% | 95% | 0 | 0 | 4 | – | 6,447 |
| Llama 3.1 8B | Direct | 41% [32–51] | 5% [1–24] | 60 | 45 | 7 | – | 451 |
| Llama 3.1 8B | Translate | 28% [20–38] | 20% [8–42] | 14 | 12 | 70 | – | 429 |

*Table 1.* SP1 outcomes. In *Translate* the named model writes the specification and Z3 searches it.
*No answer, undecided* (bugs and controls): for the Claude models the checker timed out or Z3 answered
*unknown*; for the open-weight models the reply had no verdict, the spec never passed the checker, or
(all 4 of Qwen's Translate cases) reasoning ran past the endpoint's 15-minute stream limit. SoC serves both models free.
:::

*SP3.* Of the specifications whose soundness check completed, these were *sound*, i.e. the reference satisfies them: 169/172 (Haiku), 173/173 (Sonnet), 165/165 (Opus) and 169/170 (Qwen). *Discriminating*, meaning the mutant violates them, is the valid-witness rate above. Haiku's three unsound specs are model errors (§A.2–A.3), not ambiguous docstrings: the docstring fixes the answer on each violating reference input; Qwen's one copied a leap-year bug. Llama is different in kind: only 103 of its 174 specs passed the checker; 70 runs still failed after two repairs (46 calling the unsupported `isinstance`, 17 with syntax errors, 7 defining helper functions), and only 45 of the 103 are sound.

**RQ1.** Every model except Llama finds essentially every bug in both arms, at every trigger rarity (Fig. 1). At this
ceiling the test cannot detect a rarity effect; difficulty shows only as cost (hard-tier answers use 2–3×
the tokens) and as Z3 *unknown* on arithmetic-heavy specs. Random testing differs: $N$
inputs from the same sampler catch a bug of rarity $r$ with probability $1-(1-r)^N$ (ProbGrapModel p.22), so 100 inputs catch 34% of rare and
5% of very rare bugs, and 1,000 catch 93% and 36%. On these benchmarks rarity defeats *testing*, not code reading or symbolic search, for a capable model.
Llama is the exception: Direct finds 33 of 55 common base-tier bugs but only 6 of 40 rarer ones,
though rare mutants also sit in subtler conditions, so rarity and difficulty are confounded here.

**RQ2.** No Claude or Qwen run raised a false alarm in either arm on the 59 controls, 22 of them equivalent mutants
built to look buggy. Translate left 1 (Haiku) and 5 (Opus) controls *undecided*. Llama Direct raised 45 false
alarms and invented a non-reproducing witness for 60 of the 115 bugs. Translate cut its false alarms to 12 (34 controls
false-alarmed only in Direct, 1 only in Translate; exact McNemar p < 0.001), but all 12, and 20 of its 22 misses,
came from unsound specs.

**Translate failures.** For the Claude models, every one comes from the specification or the tool, never from the search: two
postconditions copied the code's bug (§A.2); one spec raised an exception and produced a fabricated
witness (§A.3); and eight checks were undecided (three checker timeouts on subset-sum DP specs, five Z3
*unknown*s at the 60 s limit on calendar and divisor arithmetic and a 17-step simulation).

![](../results/figures/sp1_rarity.png){width=48%} ![](../results/figures/sp2_length.png){width=48%}

*Fig. 1 (left):* SP1 base tier, valid witnesses vs. trigger rarity (LLM arms pooled over the Claude models and
Qwen; Llama dashed) against random testing. *Fig. 2 (right):* SP2 valid traces vs. shortest trace length (main + stress).

## 5.2 SP2: designs (60 main + 30 stress + 60 opaque + 12 long)

::: keep
| model | arm | main valid /40 | main FA /20 | stress valid /20 | stress FA /10 | opaque valid /40 | opaque FA /20 | $/inst. (main) |
|---|---|---|---|---|---|---|---|---|
| Haiku 4.5 | Direct | 78% [62–88] | 60% [39–78] | 85% | 80% | 68% | 95% | 0.062 |
| Haiku 4.5 | Translate | 85% [71–93] | **35%** [18–57] | 90% | **40%** | 63% | **45%** | 0.051 |
| Sonnet 5.5 | Direct | 100% | 0% | 100% | 0% | 100% | 0% | 0.025 |
| Sonnet 5.5 | Translate | 100% | 0% | 100% | 0% | 100% | 0% | 0.018 |
| Opus 5.5 | Direct | 100% | 0% | 100% | 0% | 100% | 0% | 0.048 |
| Opus 5.5 | Translate | 100% | 0% | 100% | 0% | 100% | 0% | 0.036 |
| Qwen 3.8 27B | Direct | 93% [80–97] | 0% | – | – | – | – | – |
| Qwen 3.8 27B | Translate | 100% | 0% | – | – | – | – | – |
| Llama 3.1 8B | Direct | 0% [0–9] | 70% [48–85] | 0% | 60% | 0% | 90% | – |
| Llama 3.1 8B | Translate | 3% [0–13] | 10% [3–30] | 0% | 10% | 0% | 40% | – |

*Table 2.* SP2 outcomes. In *Translate* the named model writes the PDDL problem and the planners
search it. "Valid" = a trace that replays on the gold problem and reaches the violation
(flawed + subtle designs). FA = false alarm, a violation claimed on a fixed design. Translate was
*undecided* (not a false alarm) on inventory's fixed design at size 8, for every model that ran it.
Qwen ran the main set only.
:::

**RQ1.** Sonnet 5.5 and Opus 5.5 produced a valid trace every time, from 6 up to 51 events (on the long set
8/8 per model and arm, 95% interval [68–100], with no false alarm; Translate was undecided on its inventory
fixed designs, sizes 12 and 16).
Haiku stays near 80% with no length trend; its errors are design misreadings (RQ2 below). On overall correctness, paired
over its 150 designs, only Translate is right on 41 and only Direct on 21 (exact McNemar p = 0.15, 0.39
and 0.17 per set; 0.015 pooled, but the sets share templates and are not independent).
Qwen's Translate was right on all 60 main designs; its Direct was right on 57, and its 3 invalid traces
are format slips (each step prefixed with the word `action`), not misreadings. Llama Direct produced no
valid trace on any set, at any length.

**RQ2.** Fabrication separates the arms.

* *Haiku Direct* claims violations on 60% of fixed designs (80% stress, 95% opaque). Translate roughly halves this, to 35% (40%, 45%); exact McNemar on false alarms gives p = 0.18, 0.22, 0.002.
* *Sonnet, Opus and Qwen* raised no false alarm in either arm (Qwen: main set only); Sonnet and Opus also had none without mechanism names.
* *Llama Direct* claims violations on 70% of fixed designs (60% stress, 90% opaque); Translate cuts this to 10% (10%, 40%; exact McNemar p = 0.002, 0.13, 0.002). But it also misses 29 of 40 violating main-set designs (13/20 stress, 23/40 opaque): its "safe" verdicts are right on fixed designs for the wrong reason (SP3 below).

* *Why Haiku's Direct traces fail:* every one that reached a precondition check failed on a design fact. 16 (main) and 30 (opaque) used an event of *another* design variant, typically a familiar failure pattern (§A.4); 3 and 2 had vocabulary or arity errors.

**SP3 (translation quality).**

* *Sonnet and Opus* reproduced the gold initial state exactly in all 90 main and stress problems. On the opaque set they omitted one fact in 8/60, but that fact (`pay-checks-hold`) is in no action's precondition, so the problems stay equivalent to gold.
* *Haiku's design facts* were exact in 49/60 main and 35/60 opaque problems. Its other errors were permissive initial facts that the planner exploited (§A.5). All 450 translations parsed without repair.
* *Qwen* reproduced the gold initial state exactly in all 60 main problems.
* *Llama* left out about a third of the gold initial facts (mean recall 0.64 on the main set; exact in 0/60, design facts exact in 22/60; 8 never parsed). Most omissions are the static successor and ordering facts of clocks and tokens (`next-tick`, `older`, `token-leq`); without them clocks cannot tick and versions cannot be compared, so the violation is unreachable: the planner proved "no violation" on all 29 missed flawed designs and on 16 of the 20 fixed ones.


**Cost.** Over the 150 instances all models ran, Translate is always cheaper (US$ per instance: Haiku 0.053 vs
0.063, Sonnet 0.019 vs 0.025, Opus 0.040 vs 0.048). Total usage was US$80 for 2,553 calls.

## 5.3 The classical tools

* *Worst case vs. observed.* PlanSAT is PSPACE-complete (Planning p.38), but only inventory shows pronounced state explosion (Table 3): its $S{+}1$ interchangeable customers interleave, so reachable states grow 1,500× from size 1 to 4, while the other families grow roughly linearly with a timer or counter. Trace length is not the driver: queue and inventory at size 8 need 21 and 27 events.
* *SATPlan* finds shortest traces in milliseconds for four families. On inventory it takes 1.1 s at size 3, about 2 minutes at size 4, and times out (300 s) at sizes 6 and 8.
* *Certification* takes 9,026 GBFS expansions at inventory size 4 and 2.7 M (176 s) at size 6. From size 8 our 3 M-expansion / 5-minute budget runs out, so every Translate run on inventory's fixed design is scored *undecided*, not safe (the gold label comes from a conservation invariant).

::: keep
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
:::
