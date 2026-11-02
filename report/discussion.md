# 6. Analysis and insights

**SP1: localisation, not search.** A first-order mutant leaves a visible diff against a docstring that
states the intent, and reading code is white-box. Trigger rarity, which decides whether *testing* finds
a bug, therefore has no effect on either LLM arm (Fig. 1).

On the hard tier, where the witness must be *constructed*, the models paid 2–3× more tokens rather than
failing. This matches Kang et al. as presented in the lecture (GenAI p.18): when candidates are easy to
generate and check, a chain of thought stays short enough, and our functions are small.

**SP1: translation moves the risk into the specification.** The spec must state the docstring's intent
while the model is looking at code that contradicts it. Twice the postcondition inherited the bug
(§A.2), and once a broken spec produced a fabricated witness (§A.3). Both are invisible to the solver,
which is faithful to the spec.

The repair loop fixes form (Haiku 106 → 112 and Opus 104 → 114 of 115) but not meaning, because the
verifier has no ground truth. Nearly every specification is *constructive*: `post` recomputes the
answer and compares it with `result` (169–172 of 174 per model; `results/tables.md`). Translate in
SP1 is therefore a differential check between the code and a second, model-written implementation
(N-version programming) rather than a check of declarative properties, which is why a spec can
inherit the bug it is meant to expose. Specs should be written blind to the code, or checked against known
input/output pairs.

**SP2: the jagged frontier runs between model generations.** The 5.5 models are perfect in both arms on
all three sets. Haiku's Direct errors are not slips in long traces. Every failing trace that
reached a precondition check failed on a *design fact* (Table 3): a well-known failure pattern applied
to a design whose text rules it out (§A.4).

Translation does not remove misreading; Haiku moves the same mistake into the design facts it writes.
It also adds permissive initial states that the planner exploits (§A.5). But translation helps the
weaker model in three ways:

* *Fewer false alarms:* 60% → 35% (main), 80% → 40% (stress) and 95% → 45% (opaque).
* *Inspectable errors:* a wrong design fact is one line in a problem file, while a wrong Direct trace is a narrative of 6–35 steps.
* *Lower cost:* the planner, not the model, does the search.

**Length vs. familiarity.** Up to 27 events, trace length did not affect the 5.5 models, and Haiku shows
no length trend. Our violations are textbook patterns; once the pattern is recognised, a longer trace is
bookkeeping. With design facts renamed `mode-N`, the 5.5 models stayed perfect, so they map the
mechanism described in the text, not just its name. Haiku leans on names: its Direct false alarms rose
from 60% to 95%. Translate held it to 45%, because writing the initial state forces a commitment to one
design fact per mechanism, which free-form reasoning skips.

**The tools have cliffs too (§5.3).** Iterating the horizon makes SATPlan slow on symmetric
interleavings. Exhaustive certification explodes with the state space, and bounded symbolic execution
excludes paths beyond the bound. The remedies are outside this course: symmetry and partial-order
reduction (TLC, SPIN), unwinding assertions (CBMC) and k-induction. On the size-8 inventory a Direct
"safe" is unverifiable too; the difference is that the tool says "unknown".

**Is translating worth it?**

* *Direct suffices* when the specification is local and explicit, the artefact small and the model strong: SP1 at every tier, and SP2 for the 5.5 models even with opaque names. It never fabricated an SP1 witness, and its "no bug" answers were right on all 59 controls.
* *Translate pays off* when a weaker model must be used (Haiku's false alarms roughly halved, most of all with opaque names) and when a *guarantee* is required. A solver certificate with an audit trail is something Direct cannot provide.
* *Its weaknesses* are specification correctness (anchoring, permissive models) and the tools' state-space and term-size limits.

Direct accuracy on problems of this size will keep rising, as the step from Haiku 4.5 to the 5.5 models
shows. But "computationally difficult problems [are] likely to remain difficult" (GenAI p.31). Our
largest designs did not reach that regime for the 5.5 models; the size-8 inventory did for the tools.

**Threats to validity.**

* *Mutants.* They are small, first-order faults [13]; real bugs often span several lines. Some automatic mutants are unidiomatic (`if not x not in out`) and hint at the mutated line, yet Direct also found 41–42 of the 42 cue-free hand-written bugs.
* *Specifications.* Docstrings are complete specifications; vaguer real ones would hurt Translate more.
* *Familiarity.* The SP2 families are textbook patterns, and the opaque ablation removes lexical cues but not conceptual familiarity; novel designs would be a stronger test.
* *Scaffolding: the event model gives the mechanism away.* Both arms get the action schemas, and these contain each failure mechanism as a named, guarded event: `accept-new-racy` does not delete `no-record`, and `crash-restart-losing-memory` deletes `seen`. SP2 Translate therefore reduces to choosing one or two design facts per family, and that choice decides the outcome. With exact design facts, the Translate verdict was correct in 47/49 (Haiku) and 60/60 (Sonnet, Opus) main-set problems; with wrong ones, in 0/11. The opaque set hides the names, not the structure. Writing the event model, the error-prone step in practice (Planning p.15), is not tested; a tier where the model writes the action schemas is the natural next step.
* *Sampling.* Each instance is sampled once. We report Wilson intervals and exact McNemar tests, but many cells are at ceiling.
