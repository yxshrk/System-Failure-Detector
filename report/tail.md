# 7. Responsible AI

**Automation bias and what "no failure" means.** A verdict from either arm is a belief about a model,
not a fact about the world (ProbGrapModel p.4).

* SP1 Translate certifies only within the list capacities and the unrolling bound. Code that needs more iterations is excluded, not checked; our `is_prime` control with `d + d <= n` runs past the 16-unroll bound on large inputs.
* SP2 certifies only within the family's event model. A failure mode the domain does not contain is invisible to both arms.

We therefore report bounded verdicts in the form "no counterexample within k steps under assumptions X",
never "verified safe". Wording matters: the Decision lecture's certainty and framing effects
(Decision p.24–25) predict that reviewers over-trust the first. Whether to skip manual review is a
maximum-expected-utility decision (Decision p.15–16, 31). Accepting is rational only if
P(hidden failure | "no failure") < review cost / incident loss, and for payments or locks the loss term
dominates. Our data gives that posterior directly. On the SP2 main set, 2 of Haiku Direct's 11 "safe"
verdicts were wrong (18%), while all 16 of Haiku Translate's were right. Both figures depend on our
base rate of flawed designs, which Bayes' rule (ProbGrapModel p.24–25) makes explicit.

**Fabricated failures.** A false alarm costs reviewer time and, repeated, teaches reviewers to ignore
the tool. This is a precision/recall operating point to be chosen by stakes, like the fairness–accuracy
Pareto frontier (ResponsibleAI p.18–19). A Translate witness is correct *with respect to the model's
own specification* by construction. It is still a fabrication if that specification is wrong: seven of
Haiku's SP2 Translate traces were legal only in its mistranslated problem. A Translate pipeline can
also miss a failure because the spec copied the bug. Witnesses should therefore always be executed or
replayed on the real artefact before anyone acts on them, as our scoring does.

**Accountability and auditability.** The Translate arm leaves an audit trail: the spec or problem
file, the solver log and the witness. This is close to a white-box explanation (ResponsibleAI p.24),
and it lets a named engineer sign off on *what was checked*. Direct answers are black-box narratives
whose stated reasoning is at best a post-hoc explanation (ResponsibleAI p.25–26). The DeLLMa result
in the Decision lecture (p.36) makes the same argument for structured pipelines. Responsibility for
shipping stays with the humans who sign off (ResponsibleAI p.6).

**Dual use.** A failing input is an adversarial example by another name (ResponsibleAI p.27, 30). The
same pipeline that finds a double-charge trace for a defender produces an exploit for an attacker, and
AI lowers the cost and raises the scale of such attacks (ResponsibleAI p.2–4). Mitigations we would
adopt: run only on code and designs the user owns, follow coordinated disclosure, and do not publish raw
witnesses for deployed, unpatched systems. The reviewer itself is an attack surface too (ResponsibleAI
p.31). A comment planted in code under review could steer the Direct arm towards "no bug". The
Translate arm is less exposed, because the solver, not the model, decides, but the specification is
still model-written.

**Privacy.** Sending proprietary code or designs to a hosted model discloses them, and renaming
identifiers does not anonymise (ResponsibleAI p.10). On-premise open-weight models avoid this.

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
