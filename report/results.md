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
