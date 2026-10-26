# 5. Results

All numbers come from `experiments/analyze.py` (full tables in `results/tables.md`). Brackets are 95%
Wilson intervals. "Fabricated" means a claimed witness that does not reproduce on the gold model.

## 5.1 SP1: functions (115 bugs, 59 controls)

| model | arm | base bugs found (95) | hard bugs found (20) | fabricated | false alarms (59) | checker timeouts | $/inst. | out tokens |
|---|---|---|---|---|---|---|---|---|
| Haiku 4.5 | Direct | 100% [96–100] | 95% [76–99] | 0 | 0 | – | 0.025 | 4,838 |
| Haiku 4.5 | Translate | 98% [93–99] | 95% [76–99] | 1 | 0 | 0 | 0.026 | 4,968 |
| Sonnet 5.5 | Direct | 100% | 100% | 0 | 0 | – | 0.009 | 431 |
| Sonnet 5.5 | Translate | 100% | 95% | 0 | 0 | 1 | 0.008 | 208 |
| Opus 5.5 | Direct | 100% | 100% | 0 | 0 | – | 0.018 | 470 |
| Opus 5.5 | Translate | 100% | 95% | 0 | 0 | 2 | 0.021 | 383 |

*Table 1.* SP1 outcomes.

* *The repair loop matters.* Using only the first specification, valid witnesses drop to 106 (Haiku), 113 (Sonnet) and 104 (Opus) of 115.
* *Direct's cost tracks difficulty.* Hard-tier answers cost 2–3× the tokens of base-tier ones for every model.

**RQ1.** Every model finds essentially every bug in both arms, independently of trigger rarity (Fig. 1).
Random testing on the same bugs is a different story: 100 inputs catch 34% of rare and 5% of very rare
bugs, and 1,000 inputs catch 93% and 36%. Rarity defeats *testing*, not code reading or symbolic search.

**RQ2.** No model raised a false alarm in either arm on the 59 controls. These include 22 equivalent
mutants built to look buggy, such as a sorting network with a different but still valid comparator.

**Translate failures.** Every one comes from the specification or the tool, never from the search:

* two postconditions copied the code's bug (§A.2);
* one spec raised an exception and produced a fabricated witness (§A.3);
* three checker timeouts, all on the subset-sum DP specs.

![Fig. 1: SP1 base tier. Bugs with a valid witness vs. trigger rarity: both LLM arms (pooled over the three models) against random testing with 100 and 1,000 uniform inputs.](../results/figures/sp1_rarity.png){width=62%}

## 5.2 SP2: designs (60 main + 30 stress + 60 opaque)

| model | arm | main: valid (40) | main: false alarms (20) | stress: valid (20) | stress: false alarms (10) | opaque: valid (40) | opaque: false alarms (20) | $/inst. |
|---|---|---|---|---|---|---|---|---|
| Haiku 4.5 | Direct | 80% [65–90] | 55% [34–74] | 80% | 60% | 62% | 85% | 0.063 |
| Haiku 4.5 | Translate | 82% [68–91] | **20%** [8–42] | 90% | **10%** | 68% | **40%** | 0.050 |
| Sonnet 5.5 | Direct | 100% | 0% | 100% | 0% | 100% | 0% | 0.024 |
| Sonnet 5.5 | Translate | 100% | 0% | 100% | 0% | 100% | 0% | 0.017 |
| Opus 5.5 | Direct | 100% | 0% | 100% | 0% | 100% | **15%** | 0.047 |
| Opus 5.5 | Translate | 100% | 0% | 100% | 0% | 100% | 0% | 0.036 |

*Table 2.* SP2 outcomes. "Valid" = a trace that replays on the gold problem and reaches the violation
(flawed + subtle designs). "False alarm" = a violation claimed on a fixed design.

**RQ1.** Sonnet 5.5 and Opus 5.5 produced a valid trace every time, from 6 up to 27 events (Fig. 2).
Haiku stays near 80% with no length trend; its errors are design misreadings (Table 3). Paired over all
150 designs, Haiku is right in 46 cases where only Translate is right and in 20 where only Direct is
(per-set exact McNemar p = 0.15, 0.09, 0.06).

**RQ2.** Fabrication separates the arms.

* *Haiku Direct* claims violations on 55% of fixed designs (60% stress, 85% opaque). Translate cuts this to 20% (10%, 40%).
* *Opus Direct* made its only errors of the study with opaque names: three false alarms on the durable-dedup queue design, where it applied the in-memory mechanism. Opus Translate was perfect on the same inputs.

| failure cause (Direct traces that do not replay) | Haiku main | Haiku opaque | Opus opaque |
|---|---|---|---|
| uses an event of *another* design variant | 16 | 30 | 3 |
| vocabulary / arity error | 1 | 1 | 0 |

*Table 3.* Every failing Direct trace that reached a precondition check failed on a design fact: the
model reasoned about the wrong mechanism, typically a familiar failure pattern (§A.4).

**SP3 (translation quality).**

* *Sonnet and Opus* reproduced the gold initial state exactly in all 90 main and stress problems. On the opaque set they omitted one fact in 8/60, but that fact (`pay-checks-hold`) is in no action's precondition, so the problems stay equivalent to gold.
* *Haiku's design facts* were exact in 52/60 main and 32/60 opaque problems. Its other errors were permissive initial facts that the planner exploited (§A.5).
* *Repairs:* only 1 of 450 SP2 translations needed a repair to parse.

![Fig. 2: SP2 valid traces vs. shortest violating-trace length (main + stress sets). Sonnet 5.5 and Opus 5.5 are at 100% throughout.](../results/figures/sp2_length.png){width=62%}

**Cost.** Translate is cheaper on SP2 for every model: about 500 output tokens against about 1,200 for a
Direct trace, because the planner does the search. Haiku spent 10–15k tokens per Direct answer and was
still the least accurate. Total usage was US$57 (list-price equivalent) for 1,999 calls, including
pilots.

## 5.3 The classical tools

* *SATPlan* finds shortest traces in milliseconds for four families. On inventory, where symmetric customers interleave, it takes 1.1 s at size 3, about 2 minutes at size 4, and times out (300 s) at sizes 6 and 8.
* *GBFS with h_FF* finds a trace within a few dozen expansions, though not always a shortest one (29 events where 21 suffice at inventory size 6).
* *Certification scales with the reachable state space* (Fig. 3): 9,026 expansions at inventory size 4 and 2.7 M (177 s) at size 6. At size 8 our 3 M-expansion / 5-minute budget runs out, so every Translate run there returned "no violation within the search limit", not a proof.

![Fig. 3: Certifying the fixed designs. Left: SATPlan exhausting T ≤ 40 (main sizes). Right: states expanded by complete GBFS with h_FF, including stress sizes (log scale).](../results/figures/solver_scaling.png){width=78%}
