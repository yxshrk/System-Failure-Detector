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

**RQ2: who raises false alarms on safe designs?** Haiku and Llama; the 5.5 models and Qwen raise none.

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
