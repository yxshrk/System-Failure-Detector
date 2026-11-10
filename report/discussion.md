# 6. Analysis and insights

**SP1: localisation, not search.** A first-order mutant leaves a visible diff against a docstring that
states the intent, so trigger rarity, which decides whether *testing* finds a bug, did not
hurt Direct on capable models (Fig. 1). Translate's small gap (§5.1) may come from anchoring: rare bugs sit in corner-case clauses a spec can copy. In Kang et al.'s terms [2], base-tier SP1 is the easy case: the next step
(find the line contradicting the docstring) is cheap, so the chain of thought stays short. Where a witness
must be *constructed*, the models paid 2–5× more tokens rather than failing.

**SP1: translation moves the risk into the specification.** The spec must state the docstring's intent
while the model reads code that contradicts it. Most specs are *constructive*: `post` recomputes the
answer and compares it with `result` (Claude 169–172/174, Qwen 168/170, Llama 125/174). SP1 Translate is a differential check
against a second, model-written implementation (N-version programming), so a spec can inherit the
bug it should expose (§A.2). Repair fixes form (Haiku 106 → 112, Opus 104 → 114 of 115) but not
meaning; specs should be written blind to the code, or checked against known examples.

**SP2: the jagged frontier runs between model generations.** The 5.5 models are never wrong in either arm on
all four sets (Translate is undecided only where certification runs out of budget, §5.3). Haiku's Direct errors are
design misreadings: it applies a well-known pattern, such as the check-then-act race, to a design whose text rules it out
(§A.4). Translation does not remove misreading; Haiku moves it into the design facts and adds permissive initial facts that
the planner turns into shortcuts (§A.5).

**Open weights: in Llama, translation silences instead of fixing.** Qwen 3.8 27B matches
the 5.5 models on SP1 and the SP2 main set in Translate, at the cost of reasoning (about 8–10k output tokens per SP2 Direct answer). Llama 3.1 8B, which does not reason, fabricates in Direct: witnesses that do not
reproduce, and traces with wrong event names or arity (37 of 48 classified main-set failures). Translation
silences this rather than repairing it: Llama cannot write the formal language reliably (70 of 174 SP1 runs end with no accepted
spec, 8 of 60 SP2 problems never parse), and problem files missing a third of the initial state make flawed and fixed designs
alike look safe. So false alarms fall for the wrong reason: against the policy "always answer safe", Llama Translate on the SP2
main set adds one valid trace and two false alarms, so it beats that policy only if a miss costs over four false alarms (at $\pi = 1/2$). "Translate when the model is weak" needs a caveat: the model must
write the formal language correctly and completely. Llama alone cannot locate a threshold: it differs from Qwen in size, reasoning and generation at once, and Qwen did not run the other SP2 sets.

**Length vs. familiarity.** Our violations are textbook patterns; once one is recognised, a longer trace
is bookkeeping: from 6–15 to 30–51 events the 5.5 models found a valid trace on every violating design, and Direct answers grew only from about 1.2k to 1.5k tokens. With facts renamed `mode-N` they were still never wrong: they map the
mechanism, not its name. Haiku leans on names: its Direct false alarms rose from 60% to 95%; Translate held it to 45%: the
initial state forces one design fact per mechanism.

**The tools have cliffs too (§5.3).** The standard remedies lie outside the course: *symmetry reduction* (merging states
that differ by a permutation of interchangeable objects, such as inventory's customers), *partial-order reduction* (one order for
independent events), CBMC's [17] *unwinding assertions* (checking that $unwind$ is unsatisfiable), and *inductive
invariants* (k-induction with $k = 1$), which prove safety by entailment with three checks:
$$Inv(s_0), \qquad Inv(s_t) \land T(s_t, s_{t+1}) \models Inv(s_{t+1}), \qquad Inv \models \lnot G.$$
Inventory's label from size 8 rests on one, proved by hand: stock + holding + sold = S. Initially stock = S; `reserve-atomic`
moves a unit from stock to holding, `expire-hold` moves it back, `pay` moves it to sold, and the other
actions change no count or are disabled by the fixed design facts; each customer leaves browsing once,
so no count rises twice. Hence sold ≤ S < S + 1.

**Is translating worth it? A decision rule.** Choosing an arm is a maximum-expected-utility decision ([3] Ch. 16). With a share $\pi$ of flawed designs and costs $c_{FA}$ per false alarm (reviewer time),
$c_{miss}$ per flawed design left without a valid witness, $c_{rev}$ per undecided case,
and $c_{run}$ per run (model calls),
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

Hard search problems should stay hard for reasoning models, yet Sonnet and Opus Direct were right on inventory's fixed designs where the tools gave up (sizes 8–16): recognising a pattern is not solving the search. Direct will likely keep improving on small, recognisable problems (Haiku 4.5 to 5.5), but worst-case hardness and the missing certificate remain.

**Threats to validity.**

* *Mutants* are small, first-order faults [13]; real bugs often span several lines (Claude and Qwen Direct also found 41–42 of 42 hand-written bugs; Llama 9).
* *Specifications.* Docstrings are complete; vaguer real ones would hurt Translate more. Functions were selected to be encodable (integers, Booleans, lists; no strings, floats or recursion), favouring the tools.
* *Familiarity and contamination.* SP1 functions derive from public benchmarks; renaming does not remove contamination. SP2 families are textbook patterns; the opaque set removes only lexical cues.
* *Authorship.* The design documents and gold models were produced together; two documents contradicted their models and were corrected, with all affected instances rerun.
* *Scaffolding.* The given action schemas contain each failure mechanism as a named, guarded event, so SP2 Translate reduces to choosing one or two design facts per family, and that choice decides the outcome: correct in 47/49 (Haiku) and 60/60 (5.5 models, Qwen) main-set problems with exact facts, 0/11 (Haiku) with wrong ones. Writing the event model, as in [11], is untested.
* *Sampling and configuration.* Instances are sampled once and share five templates (so intervals and p-values are nominal); many cells are at ceiling. Claude models used default thinking, open-weight ones temperature 0, so effort and sampling differ (Haiku 10–15k tokens, the 5.5 models about 1k).
