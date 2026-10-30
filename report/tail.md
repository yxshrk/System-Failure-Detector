# 7. Responsible AI

**Automation bias: what "no failure" means.** A verdict is a belief about a *model*, not a fact about
the world (ProbGrapModel p.4). SP1 certifies only within the domain bounds and the unroll bound
(Theorem 1). SP2 certifies only within the event model, so a failure mode the domain lacks is
invisible to both arms. We therefore phrase verdicts as "no counterexample within k steps under
assumptions X", never "verified safe", since the certainty and framing effects (Decision p.24–25)
predict that reviewers over-trust the latter. Skipping manual review is a maximum-expected-utility
decision (Decision p.15–16, 31): it is rational only if P(hidden failure | "no failure") is below
review cost divided by incident loss. Our data estimates that posterior directly. On the SP2 main set,
2 of Haiku Direct's 11 "safe" verdicts were wrong (18%), and none of Haiku Translate's 16. Both figures
depend on the base rate of flawed designs, which Bayes' rule makes explicit (ProbGrapModel p.24–25).

**Fabricated failures.** False alarms waste reviewer time and train reviewers to ignore the tool. This
is a precision/recall operating point to be set by the stakes (ResponsibleAI p.18–19). A Translate
witness is correct only *with respect to the model's own specification*. Eleven of Haiku's main-set SP2 Translate traces (31 across all sets) were legal only in its mistranslated problem, and a spec can also hide a bug by
copying it. Witnesses must therefore be executed or replayed on the real artefact, as our scoring
does.

**Accountability.** Translate leaves an audit trail (spec, solver log, witness), close to a white-box
explanation (ResponsibleAI p.24). A named engineer can then sign off on *what was checked*. Direct
answers are post-hoc narratives (ResponsibleAI p.25–26), and DeLLMa (Decision p.36) makes the same
case for structured pipelines. Responsibility stays with the humans who sign off (ResponsibleAI p.6).

**Dual use and attacks on the reviewer.** A failing input is an adversarial example by another name
(ResponsibleAI p.27, 30), so the same pipeline yields exploits, and AI lowers the cost of attacks
(ResponsibleAI p.2–4). We would run it only on code the user owns, follow coordinated disclosure, and
withhold witnesses for unpatched deployed systems. A comment planted in the code could steer the
Direct arm to "no bug" (ResponsibleAI p.31). Translate is less exposed because the solver decides,
though its spec is still model-written. Sending proprietary code to a hosted model also discloses it
(ResponsibleAI p.10); on-premise open-weight models avoid that.

# 8. Division of work and use of AI tools

* **Yash Raj Khandelwal (leader):** coordination; SP2 design families, design documents and gold models; planning toolkit integration (SATPlan, GBFS/h_FF certification, gold replay); experiment runs; report.
* **Joshua Tan Yu Jie:** SP1 benchmark functions and mutants; symbolic executor and Z3 pipeline; rarity estimation and instance construction.
* **Hein Htet Zaw:** LLM harness and prompts; Direct/Translate arms and repair loop; SP3 scoring; analysis and figures.
* **All:** analysis, responsible AI, review of every component.

**AI assistance.** Claude Code (Anthropic) was used as a programming assistant to implement parts of
the code base: the planning toolkit, the symbolic executor and the experiment harness. It was also used
to draft parts of this report from our design decisions and measured results. Every number in this report is produced by the scripts in
the repository from cached model outputs. The research questions, formulations, design families and
evaluation protocol follow our proposal.
