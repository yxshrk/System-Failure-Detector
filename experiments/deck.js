// Builds results/figures/slides/premortem_slides.pptx from the slide PNGs.
// Usage: node experiments/deck.js results/figures/slides   (needs pptxgenjs: npm install pptxgenjs)
// The deck follows the report's five steps: Question (§1), Formulation (§2), Experiment (§3-4),
// Results (§5), Answer (§6). Every slide: a step marker, a claim as the title, one idea, a takeaway line.
const pptxgen = require("pptxgenjs");
const D = process.argv[2];
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "AI Pre-Mortems";
const INK = "0B0B0B", INK2 = "52514E", MUTED = "B5B3AD", BG = "FCFCFB", BLUE = "2A78D6", ORANGE = "EB6834", CARD = "F4F3F0", HEAD = "EBEAE6", LINE = "E4E3DF";
const F = "Arial";
const X = 0.375, W = 9.25;
const T = (s, text, o) => s.addText(text, Object.assign({ fontFace: F, color: INK, margin: 0, isTextBox: true, valign: "top" }, o));
const STEPS = ["Question", "Formulation", "Experiment", "Results", "Answer"];

// Step marker, claim title, subtitle.
function base(step, title, sub) {
  const s = pres.addSlide();
  s.background = { color: BG };
  const runs = [];
  STEPS.forEach((n, i) => {
    const on = i + 1 === step;
    runs.push({ text: `${i + 1}  ${n.toUpperCase()}`, options: { color: on ? INK : MUTED, bold: on } });
    if (i < STEPS.length - 1) runs.push({ text: "    ›    ", options: { color: MUTED } });
  });
  T(s, runs, { x: X, y: 0.14, w: W, h: 0.22, fontSize: 9, charSpacing: 1 });
  T(s, title, { x: X, y: 0.4, w: W, h: 0.42, fontSize: 20, bold: true });
  if (sub) T(s, sub, { x: X, y: 0.84, w: W, h: 0.3, fontSize: 12, color: INK2 });
  return s;
}
// The slide's point, same place and style on every slide.
function takeaway(s, text) {
  s.addShape(pres.shapes.RECTANGLE, { x: X, y: 4.93, w: 0.05, h: 0.4, fill: { color: INK }, line: { color: INK } });
  T(s, text, { x: X + 0.18, y: 4.88, w: W - 0.18, h: 0.5, fontSize: 13, valign: "middle" });
}
// Each item is a string or an array of runs ({ text, options }) forming one bullet.
function bullets(s, items, o) {
  const runs = [];
  items.forEach((t, i) => {
    const parts = Array.isArray(t) ? t : [{ text: t }];
    parts.forEach((p, j) => {
      const opt = Object.assign({}, p.options);
      if (j === 0) opt.bullet = { indent: 14 };
      if (j === parts.length - 1 && i < items.length - 1) opt.breakLine = true;
      runs.push({ text: p.text, options: opt });
    });
  });
  T(s, runs, Object.assign({ fontSize: 14, paraSpaceAfter: 8 }, o));
}
const hcell = t => ({ text: t, options: { bold: true, fill: { color: HEAD } } });
const lab = t => ({ text: t, options: { bold: true } });
const card = (s, x, y, w, h) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: CARD }, line: { color: CARD } });
const table = (s, rows, o) => s.addTable(rows, Object.assign({ fontFace: F, fontSize: 11, color: INK, border: { type: "solid", pt: 0.75, color: LINE }, margin: 0.06, valign: "middle" }, o));
const sub = t => ({ text: t, options: { subscript: true } });
const B = t => ({ text: t, options: { bold: true } });

// 1. Title (Summary)
{
  const s = pres.addSlide();
  s.background = { color: BG };
  T(s, "CS3263 Foundations of AI  ·  Project Group 19", { x: 0.6, y: 0.8, w: 8.8, h: 0.35, fontSize: 14, color: INK2 });
  T(s, "AI Pre-Mortems", { x: 0.6, y: 1.25, w: 8.8, h: 0.8, fontSize: 44, bold: true });
  T(s, "Can frontier models predict how code and systems fail?", { x: 0.6, y: 2.05, w: 8.8, h: 0.5, fontSize: 22 });
  T(s, "Two review sub-problems: Python functions (SP1) and distributed-system designs (SP2)", { x: 0.6, y: 2.6, w: 8.8, h: 0.35, fontSize: 15, color: INK2 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 3.15, w: 1.15, h: 0.38, rectRadius: 0.08, fill: { color: "EAF2FC" }, line: { color: BLUE, width: 1.25 } });
  T(s, "Direct", { x: 0.6, y: 3.15, w: 1.15, h: 0.38, fontSize: 14, bold: true, color: BLUE, align: "center", valign: "middle" });
  T(s, "vs", { x: 1.8, y: 3.15, w: 0.4, h: 0.38, fontSize: 14, color: INK2, align: "center", valign: "middle" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 2.25, y: 3.15, w: 1.35, h: 0.38, rectRadius: 0.08, fill: { color: "FDEEE7" }, line: { color: ORANGE, width: 1.25 } });
  T(s, "Translate", { x: 2.25, y: 3.15, w: 1.35, h: 0.38, fontSize: 14, bold: true, color: ORANGE, align: "center", valign: "middle" });
  T(s, [{ text: "Yash Raj Khandelwal", options: { breakLine: true } }, { text: "Joshua Tan Yu Jie", options: { breakLine: true } }, { text: "Hein Htet Zaw" }],
    { x: 0.6, y: 3.95, w: 6, h: 1.1, fontSize: 18, paraSpaceAfter: 4 });
  T(s, "Semester 1, AY2026/27", { x: 6.4, y: 4.7, w: 3.0, h: 0.35, fontSize: 14, color: INK2, align: "right" });
  s.addNotes("Introduce the team. Our question: can an LLM act as a pre-mortem reviewer, finding how a function or a system design will fail before it ships? We compare two ways of using it, Direct and Translate, on functions and on designs. Our short answer: it depends on how strong the model is.");
}

// 2. Motivation (§1)
{
  const s = base(1, "The failures that matter are the ones review misses", "A pre-mortem asks how something will fail, before it ships.");
  bullets(s, [
    "Real failures hide behind rare inputs or long orders of events",
    "Coldcard wallets, disclosed July 2026: a five-year-old randomness bug. By the maker's account, an AI-assisted review missed it",
    "AWS DynamoDB: a 35-step data-loss trace passed design review, code review and testing",
    "So an AI reviewer helps only if it shows a witness (a concrete failing input or event trace) and never invents a failure on correct code",
  ], { x: X, y: 1.3, w: 4.6, h: 3.45, fontSize: 13.5, paraSpaceAfter: 7 });
  s.addImage({ path: `${D}/img/coldcard_q_mk5.png`, x: 5.3, y: 1.3, w: 1.95, h: 1.78, altText: "Coldcard Q and Mk5 hardware bitcoin wallets made by Coinkite" });
  T(s, [{ text: "Coldcard Q and Mk5 hardware wallets, made by Coinkite", options: { breakLine: true } }, { text: "Image: coldcard.com", options: { fontSize: 9 } }],
    { x: 7.4, y: 1.35, w: 2.225, h: 0.8, fontSize: 11, color: INK2, paraSpaceAfter: 4 });
  T(s, "Sources: Decrypt (Aug 2026); Coinkite, \"Entropy technical backgrounder\"; Unchained (Aug 2026)", { x: 7.4, y: 2.35, w: 2.225, h: 0.7, fontSize: 8, color: INK2 });
  s.addImage({ path: `${D}/coldcard_timeline.png`, x: 5.25, y: 3.2, w: 4.375, h: 1.55, altText: "Timeline: Mar 2021 bug ships, Jul 2026 AI-assisted review misses it (Coinkite's account), Jul to Aug 2026 wallets drained, reported US$38M to over US$114M" });
  takeaway(s, "The course question: should the LLM find the failure directly, or translate the problem for a solver? And will that change?");
  s.addNotes("In July 2026 Coinkite disclosed that since 2021 its Coldcard wallets had generated seed phrases from a predictable fallback; by its own account, an AI-assisted review missed it. Real failures are rare and deep, like DynamoDB's 35-step trace that passed every review. So an AI reviewer helps only if it gives a checkable witness and never invents failures. Should it find the failure directly, or translate for a solver?");
}

// 3. The two tasks (§1)
{
  const s = base(1, "Two tasks: how a function fails, and how a design fails", "We test the question on two kinds of review");
  const task = (x, head, lines) => {
    card(s, x, 1.3, 4.5, 3.4);
    T(s, head, { x: x + 0.28, y: 1.48, w: 3.95, h: 0.32, fontSize: 15, bold: true });
    T(s, lines.flatMap(([k, v], i) => [B(k + "  "), { text: v, options: { breakLine: i < lines.length - 1 } }]),
      { x: x + 0.28, y: 1.98, w: 3.95, h: 2.65, fontSize: 14, paraSpaceAfter: 14 });
  };
  task(X, "SP1: function review", [
    ["Given:", "a Python function and a docstring saying what it must do."],
    ["Find:", "an input that breaks the docstring."],
    ["Example:", "a leap-year rule with 400 typed as 399. February 2000 gets 28 days."],
  ]);
  task(5.125, "SP2: design review", [
    ["Given:", "a design document for a service, and the events that can occur."],
    ["Find:", "an order of timeouts, retries, lost messages and crashes that breaks a safety property."],
    ["Example:", "a timed-out payment is retried before the first attempt is recorded, and the card is charged twice."],
  ]);
  takeaway(s, "In both tasks the answer is a witness: something anyone can replay and check.");
  s.addNotes("To answer it, we need tasks whose answers can be checked. SP1 asks for an input that breaks a function's docstring; SP2 asks for an order of events that breaks a design's safety property. Either way, the answer is a witness anyone can replay.");
}

// 4. The two arms (§1, §4 scoring)
{
  const s = base(1, "Direct: the LLM answers itself. Translate: a solver searches", "Two arms, same input, same exact scoring. The difference is who looks for the failure.");
  s.addImage({ path: `${D}/method.png`, x: 0.908, y: 1.3, w: 8.185, h: 3.5, altText: "Direct: the LLM finds the failure itself. Translate: the LLM writes the problem formally as a specification and a solver searches, with errors fed back for repair. Both witnesses are replayed on the reference." });
  takeaway(s, "Both arms are scored the same way: a witness counts only if it replays on the gold reference.");
  s.addNotes("We find witnesses in two ways, which we call arms. Direct: the LLM finds the failure itself. Translate: the LLM writes the problem formally as a specification, a solver searches, and errors go back for repair. Both arms are scored the same way: a witness counts only if it replays on the gold reference.");
}

// 5. Research questions (§1)
{
  const s = base(1, "Two research questions, and one check", "What we measure for each arm");
  const q = (y, label, head, body) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: X, y, w: 0.85, h: 0.42, rectRadius: 0.08, fill: { color: HEAD }, line: { color: HEAD } });
    T(s, label, { x: X, y, w: 0.85, h: 0.42, fontSize: 13, bold: true, align: "center", valign: "middle" });
    T(s, [B(head), { text: " " + body }], { x: 1.45, y: y - 0.01, w: 8.175, h: 0.95, fontSize: 13 });
  };
  q(1.35, "RQ1", "Which arm finds more valid witnesses, and does the gap widen as failures get harder to reach?",
    "Measured on buggy functions (by how rare the failing input is) and flawed designs (by the length of the shortest failure trace).");
  q(2.5, "RQ2", "Which arm invents more failures where there are none?",
    "Measured on controls: functions and designs with no failure.");
  q(3.45, "SP3", "Also: how good are the translations?",
    "We score each one against our gold version, to tell a translation error from a solver error.");
  takeaway(s, "First, one bug through both arms.");
  s.addNotes("With the arms defined, here is what we measure. RQ1 asks whether one arm finds more real failures, especially the hard-to-reach ones. RQ2 asks which arm invents failures that are not there. SP3 checks the translations themselves.");
}

// 6. Worked example (§1)
{
  const s = base(1, "Worked example: a bug random testing misses", "One mutated constant. Only 7 of the 36,000 valid inputs (0.02%) expose it.");
  s.addImage({ path: `${D}/worked_example.png`, x: 0.85, y: 1.3, w: 8.3, h: 3.451, altText: "days_in_month with 399 instead of 400: random testing finds it 18% of the time with 1,000 inputs; Opus 5.5 Direct answers February 2000; Opus 5.5 Translate writes a spec and Z3 returns February 2400." });
  takeaway(s, "Gold check: the reference returns 29 and the mutant 28 on both inputs, so both arms found a valid witness.");
  s.addNotes("Here is one bug through both arms. One mutated constant, 400 to 399. Only 7 of 36,000 inputs fail, so 1,000 random tests catch it 18% of the time. Opus Direct answers February 2000. Opus Translate writes the spec from the docstring and Z3 finds February 2400 in 0.01 s. Both are confirmed against the reference.");
}

// 7. SP1 formulation (§2.1)
{
  const s = base(2, "SP1 as a CSP: a solution is a failing input", "A constraint satisfaction problem (CSP), solved by an SMT solver (Z3)");
  table(s, [
    [hcell(""), hcell("In general"), hcell("In the leap-year example")],
    [lab("Variables"), "the function's inputs", "month, year"],
    [lab("Domains"), "the stated input ranges", "1 ≤ month ≤ 12, 1 ≤ year ≤ 3000 (36,000 inputs)"],
    [lab("Constraint"), "the code's result breaks the requirement", "result = code(month, year) and not post(month, year, result)"],
  ], { x: X, y: 1.3, w: 4.8, colW: [0.95, 1.6, 2.25], rowH: [0.3, 0.3, 0.46, 0.62], fontSize: 10.5 });
  bullets(s, [
    "Bounded symbolic execution turns the code into one formula covering every path, with loops unrolled k times",
    "A solution is an input on which the code breaks its requirement. Here: month = 2, year = 2400, one of 7",
    "No solution means no such input exists within the bounds",
  ], { x: X, y: 3.15, w: 4.8, h: 1.6, fontSize: 12, paraSpaceAfter: 6 });
  T(s, "How Translate builds and solves the problem", { x: 5.425, y: 1.28, w: 4.2, h: 0.2, fontSize: 10, bold: true, color: INK2 });
  s.addImage({ path: `${D}/sp1_formulation.png`, x: 5.425, y: 1.5, w: 4.2, h: 3.22, altText: "SP1 on the leap-year bug: symbolic execution turns the code into one formula, the LLM writes the requirement from the docstring, and Z3 searches for an input where the code's result breaks it. Satisfiable: month 2, year 2400, re-run in Python. Unsatisfiable: no failing input within the bounds." });
  takeaway(s, [{ text: "The code meets its requirement (" }, B("code ⊨ requirement"), { text: ") exactly when " }, B("code ∧ ¬requirement"), { text: " is unsatisfiable, so any solution is a failure witness." }]);
  s.addNotes("How does Translate turn this into a solver problem? SP1 is constraint satisfaction: month and year are variables with finite domains, and the constraint is that the code's result breaks the requirement. Symbolic execution turns the code into one formula; the LLM writes the requirement from the docstring, and Z3 searches for an input where both hold. Here it finds February 2400. Underneath is entailment: the code meets its requirement exactly when code and not requirement is unsatisfiable.");
}

// 8. SP2 formulation (§2.2)
{
  const s = base(2, "SP2 as a planning problem: a plan is a failure trace", "A STRIPS planning problem, written in PDDL and solved by planners");
  table(s, [
    [hcell(""), hcell("Meaning"), hcell("Payments example")],
    [lab("Facts"), "what is true in the system now", "(no-record o1): no record for order o1 yet"],
    [lab("Actions"), "events that can happen, including failures", "accept-new-racy, time-out-and-retry"],
    [lab("Initial state"), "the design, written as facts", "(dedup-racy): the record is written only after the charge"],
    [lab("Goal"), "the violation we look for", "(charged-twice o1)"],
  ], { x: X, y: 1.3, w: 5.4, colW: [1.1, 1.95, 2.35], rowH: [0.3, 0.46, 0.46, 0.46, 0.3], fontSize: 10.5 });
  bullets(s, [
    "The planner chooses every event, including the failures, so a plan is an order of events that breaks the design",
    [{ text: "SATPlan finds a shortest such trace; greedy best-first search (GBFS) with h" }, sub("FF"), { text: " proves that none exists" }],
  ], { x: X, y: 3.5, w: 5.4, h: 1.25, fontSize: 12, paraSpaceAfter: 6 });
  T(s, "Shortest failure trace found by SATPlan (8 events)", { x: 6.05, y: 1.3, w: 3.575, h: 0.22, fontSize: 10, bold: true, color: INK2 });
  T(s, "a0 is the first attempt and a1 the retry, for order o1. Highlighted: both attempts pass the duplicate check.", { x: 6.05, y: 1.53, w: 3.575, h: 0.34, fontSize: 9.5, color: INK2 });
  s.addImage({ path: `${D}/sp2_trace.png`, x: 6.239, y: 1.9, w: 3.197, h: 2.85, altText: "Shortest failure trace for payments-subtle-1: eight events ending in charged-twice" });
  takeaway(s, "Both arms are given the actions. In Translate, the LLM writes only the initial state.");
  s.addNotes("SP2 is classical planning: facts are the state, actions are events including failures, the initial state encodes the design, and the goal is the violation. The planner chooses every event, so a plan is a counterexample: planning as model checking. Here the retry passes the duplicate check because the record is written only after charging. Both arms are given these actions; in Translate the model writes only the initial state. Names like dedup-racy give the mechanism away, so one set replaces them.");
}

// 9. Guarantees and complexity (§2)
{
  const s = base(2, "What a solver's answer proves, and what it costs", "Why a solver's answer can be trusted, and where it stops");
  const sup = (a, b, c) => ({ text: [{ text: a }, { text: b, options: { superscript: true } }, { text: c }] });
  table(s, [
    [hcell(""), hcell("SP1: Z3"), hcell("SP2: SATPlan and GBFS")],
    [lab("How is it encoded?"), "Symbolic execution turns the code into one formula covering every path, with loops unrolled k times",
      "One Boolean per fact and per action at each step, with effect and frame axioms and exactly one action per step"],
    [lab("Why is the encoding right?"), "Lemma 1: within the bounds, the formula gives exactly what Python gives",
      "Lemma 2: these clauses are equivalent to the textbook successor-state axioms"],
    [lab("It reports a failure. What does that prove?"), "Theorem 1: the input breaks the LLM's specification",
      "Theorem 2: the trace reaches the violation, and the first horizon that works gives a shortest trace"],
    [lab("It reports none. What does that prove?"), "Theorem 1: no input within the bounds breaks the specification. If the bounds are exceeded, the answer is \"undecided\"",
      "Theorem 3: the violation is unreachable at this size"],
    [lab("How hard is the worst case?"), "NP-complete. On non-linear arithmetic Z3 may answer \"unknown\"",
      sup("PSPACE-complete; each SATPlan call is NP-complete. Up to 2", "218", " states at size 8")],
  ], { x: X, y: 1.28, w: W, colW: [2.05, 3.5, 3.7], rowH: [0.28, 0.6, 0.48, 0.6, 0.6, 0.48] });
  takeaway(s, [{ text: "h" }, sub("FF"), { text: " only prunes dead ends, which is safe because ignoring deletes only adds behaviour. Every witness is replayed on the real code or gold problem before it counts." }]);
  s.addNotes("Why should we trust a solver's answer? For SP1 we show the encoding matches Python on every input within the loop bounds, and test it on 25 random inputs per function, so every Z3 answer is an input that breaks the spec, and unsatisfiable means no input within those bounds breaks it. For SP2, our SATPlan clauses are equivalent to the successor-state axioms, so the first satisfiable horizon gives a shortest trace. To certify safety, greedy best-first search runs until its queue is empty.");
}

// 10. Problem instances (§3)
{
  const s = base(3, "Problem instances, each with a known answer", "174 function instances and 162 design instances");
  const col = (x, head, big, lines) => {
    card(s, x, 1.3, 4.5, 3.45);
    T(s, head, { x: x + 0.28, y: 1.43, w: 3.95, h: 0.3, fontSize: 14, bold: true });
    T(s, big, { x: x + 0.28, y: 1.72, w: 3.95, h: 0.55, fontSize: 32, bold: true });
    bullets(s, lines, { x: x + 0.28, y: 2.38, w: 3.95, h: 2.3, fontSize: 11.5, paraSpaceAfter: 5 });
  };
  col(X, "Functions (SP1)", "174", [
    "37 Python functions, renamed and with rewritten docstrings, to limit memorisation",
    "115 buggy versions: single-change mutants (chosen from 808) and 42 hand-written bugs, from common to very rare triggers",
    "59 controls with no bug: 37 clean originals and 22 changed versions proved equivalent, which look buggy but are not",
  ]);
  col(5.125, "Designs (SP2)", "162", [
    "Five services: payments, inventory, lock, queue, cache",
    "Three versions of each: flawed, subtle (a fix that does not work) and fixed (safe; the control)",
    "Size scales a timer or a capacity, so the shortest failure gets longer",
    "Main: 60 designs at sizes 1 to 4. Stress: 30 at sizes 6 and 8 (17 to 27 events). Opaque: the main 60 with revealing names replaced. Long: 12 at sizes 12 and 16 (30 to 51 events)",
  ]);
  takeaway(s, "Ground truth comes from our own solvers, plus one hand proof for the largest inventory designs.");
  s.addNotes("Now the experiment, starting with what we tested. SP1 has 174 instances from 37 functions: bugs from common to very rare triggers, plus controls, including equivalent mutants that look buggy but are not. SP2 has five services, each flawed, subtle or fixed; size scales a timer or capacity, so failures get longer. Our solvers supply the ground truth, so what Translate tests is the translation.");
}

// 11. Method (§4)
{
  const s = base(3, "Method: five models, the same inputs, exact scoring", "Models in three tiers; both arms see the same input");
  table(s, [
    [hcell("Tier"), hcell("Models")],
    [lab("Strong"), "Claude Sonnet 5.5 and Opus 5.5; Qwen 3.8 27B (open-weight; ran SP1 and the SP2 main set only)"],
    [lab("Mid-tier"), "Claude Haiku 4.5"],
    [lab("Weak"), "Llama 3.1 8B (open-weight)"],
  ], { x: X, y: 1.3, w: W, colW: [1.3, 7.95], rowH: 0.3, fontSize: 12 });
  bullets(s, [
    [B("Direct: "), { text: "the model answers with a verdict and a witness. All tools are disabled, so it cannot run the code." }],
    [B("Translate: "), { text: "the model writes the specification or initial state, and the solver searches. Errors are fed back for up to two repairs." }],
    [B("Scoring: "), { text: "each answer gets one label: valid witness (it replays on the gold reference), fabricated (an invalid witness, or a false alarm on a control), miss, correct no-failure, or undecided (the tool ran out of budget or could not decide)." }],
    [B("Runs and budgets: "), { text: "one run per instance. Planner search stops at 3 million states or 5 minutes; each Z3 query at 60 seconds." }],
  ], { x: X, y: 2.72, w: W, h: 2.1, fontSize: 12.5, paraSpaceAfter: 7 });
  takeaway(s, "Undecided is never counted as \"no failure\".");
  s.addNotes("Then how we ran it. Five models in three tiers: strong, mid-tier Haiku, and weak Llama. Direct runs with all tools disabled, so it must reason rather than execute. Translate gets up to two repairs. Every answer gets exactly one label, and a tool that runs out of budget is undecided, never no failure.");
}

// 12. Scoreboard (§5 overview)
{
  const s = base(4, "Strong models are near-perfect; Haiku and Llama are not", "Every model and arm at a glance. Darker cells are worse: bugs missed, or false alarms raised.");
  s.addImage({ path: `${D}/scoreboard.png`, x: X, y: 1.1, w: W, h: 3.55, altText: "Scoreboard of every model and arm on bugs found, false alarms, failure traces found and false alarms with names hidden" });
  takeaway(s, "Now each research question in turn.");
  s.addNotes("Now the results, first at a glance. The 5.5 models and Qwen are near-perfect on the sets they ran, with zero false alarms; Qwen's three invalid traces in Direct were format slips, not misreadings. Haiku is fine on functions but struggles on designs, especially false alarms with names hidden. Llama fails everywhere: in Direct it fabricates, with 45 false alarms on 59 correct functions.");
}

// 13. RQ1 (§5.1-5.2)
{
  const s = base(4, "Strong models find nearly every failure, even the hardest", "RQ1. Does one arm find more real failures, and does the gap grow as failures get harder to reach?");
  s.addImage({ path: `${D}/hardness_panel.png`, x: X, y: 1.28, w: W, h: 3.45, altText: "Left: failures found as the failing input gets rarer; random testing collapses while Direct and Translate stay near 100%. Right: failure traces found as traces get longer; Sonnet and Opus stay at 100%, Haiku near 80%" });
  takeaway(s, "Random testing collapses as bugs get rarer; the LLMs do not. Translate trails only slightly.");
  s.addNotes("RQ1 asked whether harder-to-reach failures hurt either arm. On the left, random testing finds fewer bugs as they get rarer, because a rare bug needs a lucky input, yet both arms keep finding them. On the right, longer traces don't hurt Sonnet or Opus, and Haiku stays near 80%. That matters, because a search has to explore more states as traces get longer. But while the traces got several times longer, the answers from Sonnet and Opus grew by only about a quarter. That fits recognising a familiar bug pattern rather than searching, though we did not measure how they reasoned.");
}

// 14. RQ2 (§5.1-5.2)
{
  const s = base(4, "Translation cuts the mid-tier model's false alarms", "RQ2. Which arm invents failures that aren't there? Here: the 20 correct designs.");
  s.addImage({ path: `${D}/false_alarms.png`, x: 1.181, y: 1.22, w: 7.638, h: 2.85, altText: "False alarms on correct designs, Direct vs Translate: Haiku 12 to 7 of 20 (19 to 9 with names hidden), Llama 14 to 2 (18 to 8), Sonnet, Opus and Qwen 0 in both arms" });
  T(s, [{ text: "Names hidden: the same 20 designs, with revealing names such as dedup-racy replaced by neutral labels.", options: { breakLine: true } }, { text: "20 designs per cell, one run each. With readable names the 95% intervals overlap (60% [39–78] against 35% [18–57]); the drop appears in 4 of 5 families." }], { x: X, y: 4.1, w: W, h: 0.6, fontSize: 11, color: INK2, align: "center" });
  takeaway(s, "The strong models raise no false alarms in either arm. Llama's drop is not a real gain: its problem files leave out facts, so it calls most designs safe and misses 29 of 40 real failures.");
  s.addNotes("So the strong models find the failures. RQ2 asks the opposite: which arm invents failures that aren't there? On correct designs, translating cuts Haiku's false alarms from 12 to 7 of 20. Why? In Direct, Haiku recognises a famous failure, like the double charge on a retry, and reports it even when this design prevents it. In Translate, it must first write down this design's facts. Every event is a planning action with preconditions. So if the facts say this design prevents an event, the planner can never use it, and the false failure cannot be built. And the drop is a real gain, because Haiku still finds 34 of 40 real failures. Llama's drop is not, because its problem files leave out facts, so the planner finds no violation in 29 of the 40 flawed designs.");
}

// 15. SP3 (§5, §5.3): four kinds of failure, one count each
{
  const s = base(4, "Translate fails through its specification or its tools", "SP3. How good were the translations?");
  T(s, "Sonnet and Opus wrote the exact initial state in all 90 main and stress designs. The failures came in four kinds:",
    { x: X, y: 1.25, w: W, h: 0.3, fontSize: 12 });
  const kind = (x, y, head, big, body) => {
    card(s, x, y, 3.05, 1.5);
    T(s, head, { x: x + 0.16, y: y + 0.1, w: 2.75, h: 0.26, fontSize: 11.5, bold: true });
    T(s, big, { x: x + 0.16, y: y + 0.38, w: 2.75, h: 0.42, fontSize: 22, bold: true });
    T(s, body, { x: x + 0.16, y: y + 0.82, w: 2.75, h: 0.62, fontSize: 10.5, color: INK2 });
  };
  kind(X, 1.65, "The specification copies the bug", "2", "Claude specs copied the buggy line into the requirement, so code and requirement agree and Z3 finds no failing input");
  kind(3.525, 1.65, "The translation is too permissive", "13", "Haiku main-set traces that work only in its too-loose problem, not in the real design");
  kind(X, 3.27, "The model cannot write the spec", "70 of 174", "Llama runs with no usable spec; its design files left out about a third of the facts");
  kind(3.525, 3.27, "The solver runs out", "From size 8", "proving inventory safe means ruling out every route to a violation: 2.7M states at size 6, over budget from size 8");
  s.addImage({ path: `${D}/inventory_panel.png`, x: 6.78, y: 1.7, w: 2.845, h: 2.87, altText: "States expanded to prove safety vs design size: inventory explodes and exceeds the budget at size 8, the other designs stay small" });
  takeaway(s, "A Translate answer is only as good as the translation, so every witness is replayed on the real code or design.");
  s.addNotes("Translating helps Haiku, but it can also fail, and SP3 asks how. We saw four ways. First, if the LLM copies the buggy line into the requirement, code and requirement agree, so Z3 finds no failing input. Second, if the problem file allows things the real design doesn't, the planner finds a failure that exists only in that wrong problem. Third, a weak model can't write the formal language reliably, so the solver often gets no usable spec. Fourth, to prove a design safe, the planner must rule out every route to a violation. For inventory that means millions of states, so from size 8 it runs out of budget.");
}

// 16. The answer in brief (§6 opening)
{
  const s = base(5, "The answer in brief", "When should we use the LLM directly, and when should we translate?");
  const a = (y, n, head, body) => {
    card(s, X, y, W, 1.02);
    s.addShape(pres.shapes.OVAL, { x: 0.6, y: y + 0.26, w: 0.5, h: 0.5, fill: { color: INK }, line: { color: INK } });
    T(s, n, { x: 0.6, y: y + 0.26, w: 0.5, h: 0.5, fontSize: 16, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
    T(s, head, { x: 1.35, y: y + 0.14, w: 8.1, h: 0.32, fontSize: 14.5, bold: true });
    T(s, body, { x: 1.35, y: y + 0.52, w: 8.1, h: 0.4, fontSize: 12, color: INK2 });
  };
  a(1.3, "1", "Strong models: both arms nearly tie (consistent with recognition, not search)",
    "Sonnet and Opus were never wrong on designs, up to 51 events and with names hidden.");
  a(2.44, "2", "Translating moves the error into the specification; it doesn't remove it",
    "Haiku's false alarms fall from 12 to 7 of 20; Llama can't write the formal language reliably.");
  a(3.58, "3", "Only the tools can prove there is no failure, and that's where they run out",
    "Inventory's safe design from size 8: Translate is undecided, while Sonnet and Opus Direct answer correctly but without proof.");
  takeaway(s, "Which arm to use depends on how strong the model is, and on whether you need proof.");
  s.addNotes("So what is our answer? One: with a strong model, both arms nearly tie. Two: translating doesn't remove errors; it moves them into the spec the LLM writes, so it helps only a model that writes the formal language well. Three: only a solver can prove there is no failure, but that proof needs exhaustive search, which is exactly where the tools run out.");
}

// 17. When to use which arm (§6)
{
  const s = base(5, "Trade-offs, and when to use which arm", "Choosing an arm is a maximum-expected-utility decision");
  const use = (x, head, color, items, foot) => {
    card(s, x, 1.22, 4.5, 1.43);
    T(s, head, { x: x + 0.2, y: 1.29, w: 4.1, h: 0.28, fontSize: 13, bold: true, color });
    bullets(s, items, { x: x + 0.2, y: 1.6, w: 4.1, h: 0.7, fontSize: 11.5, paraSpaceAfter: 1 });
    T(s, foot, { x: x + 0.2, y: 2.25, w: 4.1, h: 0.34, fontSize: 10, color: INK2 });
  };
  use(X, "Use Direct when", BLUE, ["the model is strong and the review small", "the spec is complete", "an answer without proof is fine"],
    "Needs the model and, for designs, the event rules; fails by misreading the design.");
  use(5.125, "Use Translate when", ORANGE, ["you must prove or audit \"no failure\"", "a mid-tier model misreads designs but writes the formal language well"],
    "Needs a solver and an encoder; fails through the spec or the tools.");
  T(s, [
    B("EU(arm) = −[ (1 − q) · P(false alarm) · c"), { text: "FA", options: { subscript: true, bold: true } },
    B(" + q · P(miss) · c"), { text: "miss", options: { subscript: true, bold: true } },
    B(" + P(undecided) · c"), { text: "rev", options: { subscript: true, bold: true } },
    B(" + c"), { text: "run", options: { subscript: true, bold: true } }, B(" ]"),
  ], { x: X, y: 2.7, w: W, h: 0.3, fontSize: 13, align: "center" });
  T(s, "q is the share of flawed designs; the c terms are the costs of a false alarm, a miss (a flawed design left without a valid trace), a manual review and a run.",
    { x: X, y: 2.98, w: W, h: 0.26, fontSize: 9.5, color: INK2, align: "center" });
  table(s, [
    [hcell("Haiku, Direct → Translate"), hcell("Failures found"), hcell("False alarms"), hcell("Verdict, at these estimates")],
    [lab("Readable names"), "31 → 34 of 40", "12 → 7 of 20", "Translate wins at any costs"],
    [lab("Names hidden"), "27 → 25 of 40", "19 → 9 of 20", "Translate wins while a miss costs under 10 false alarms (half the designs flawed, errors only)"],
  ], { x: X, y: 3.3, w: W, colW: [1.95, 1.35, 1.3, 4.65], rowH: [0.28, 0.3, 0.45], fontSize: 11 });
  takeaway(s, "At these estimates, Translate wins for Haiku at any costs with readable names, and with names hidden unless a miss costs 10 false alarms or more.");
  s.addNotes("So which arm should you use? As in the course, this is a maximum-expected-utility choice: pick the arm whose mistakes cost less on average. Take Haiku. With readable names, Translate makes fewer mistakes of both kinds and is cheaper to run, so it wins outright. With names hidden, it's a trade-off. Out of 20 correct designs, Translate raises 9 false alarms instead of 19, so it saves 10. Out of 40 flawed designs, it finds 25 failures instead of 27, so it misses 1 more for every 20. So picture a review of 20 correct and 20 flawed designs: Translate would save ten false alarms but miss one more failure. Ignoring running costs, that makes Translate the better choice unless one missed failure is worse than ten false alarms.");
}

// 18. Limitations and will this change (§6)
{
  const s = base(5, "Limitations, and will this change?", "The second half of the course question");
  const col = (x, head, items) => {
    card(s, x, 1.25, 4.5, 1.95);
    T(s, head, { x: x + 0.2, y: 1.34, w: 4.1, h: 0.3, fontSize: 13, bold: true });
    bullets(s, items, { x: x + 0.2, y: 1.7, w: 4.1, h: 1.45, fontSize: 11.5, paraSpaceAfter: 5 });
  };
  col(X, "What we did not test", [
    "Having the LLM write the event model: both arms were given the failure events",
    "Multi-line bugs and vague docstrings (ours are mostly single-change bugs with complete docstrings)",
  ]);
  col(5.125, "What limits the conclusions", [
    "The functions were chosen to be encodable, which favours Translate",
    "The benchmarks may be in training data",
    "Most scores are at or near 100%, so the strongest models can't be ranked",
  ]);
  card(s, X, 3.38, W, 1.0);
  T(s, "Will this change?", { x: 0.6, y: 3.47, w: 8.8, h: 0.3, fontSize: 14, bold: true });
  T(s, "Direct will likely keep improving on small, recognisable problems (Haiku 4.5 to the 5.5 models, which also differ in tier), but it still cannot prove there is no failure, and search can still take exponential time in the worst case.",
    { x: 0.6, y: 3.8, w: 8.8, h: 0.5, fontSize: 12 });
  takeaway(s, "Bottom line: translation's value depends on the model. It adds no accuracy for strong models, cuts false alarms for a mid-tier one, and cannot rescue a weak one.");
  s.addNotes("Finally, how far can you trust this answer? Both arms were given the failure mechanisms as named events, so we have not tested a model writing the event model itself. We also chose functions that can be encoded, which favours Translate. Will the answer change? Direct will likely keep improving on small, recognisable problems. But it still cannot prove there is no failure, and for the solvers, search can still take exponential time in the worst case. So the value of translating depends on the model. Thank you.");
}

pres.writeFile({ fileName: `${D}/premortem_slides.pptx` }).then(f => console.log("wrote", f));
