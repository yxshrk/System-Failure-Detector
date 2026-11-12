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
  T(s, runs, { x: X, y: 0.16, w: W, h: 0.2, fontSize: 8, charSpacing: 1 });
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
  T(s, "Two review tasks: Python functions (SP1) and distributed-system designs (SP2)", { x: 0.6, y: 2.6, w: 8.8, h: 0.35, fontSize: 15, color: INK2 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 3.15, w: 1.15, h: 0.38, rectRadius: 0.08, fill: { color: "EAF2FC" }, line: { color: BLUE, width: 1.25 } });
  T(s, "Direct", { x: 0.6, y: 3.15, w: 1.15, h: 0.38, fontSize: 14, bold: true, color: BLUE, align: "center", valign: "middle" });
  T(s, "vs", { x: 1.8, y: 3.15, w: 0.4, h: 0.38, fontSize: 14, color: INK2, align: "center", valign: "middle" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 2.25, y: 3.15, w: 1.35, h: 0.38, rectRadius: 0.08, fill: { color: "FDEEE7" }, line: { color: ORANGE, width: 1.25 } });
  T(s, "Translate", { x: 2.25, y: 3.15, w: 1.35, h: 0.38, fontSize: 14, bold: true, color: ORANGE, align: "center", valign: "middle" });
  T(s, [{ text: "Yash Raj Khandelwal", options: { breakLine: true } }, { text: "Joshua Tan Yu Jie", options: { breakLine: true } }, { text: "Hein Htet Zaw" }],
    { x: 0.6, y: 3.95, w: 6, h: 1.1, fontSize: 18, paraSpaceAfter: 4 });
  T(s, "Semester 1, AY2026/27", { x: 6.4, y: 4.7, w: 3.0, h: 0.35, fontSize: 14, color: INK2, align: "right" });
  s.addNotes("Introduce the team. Our question: can an LLM act as a pre-mortem reviewer, finding how a function or a system design will fail before it ships? We compare two ways of using it, Direct and Translate, on functions and on designs. Our headline: translation's value depends on the model. It adds no accuracy for strong models, cuts false alarms for a mid-tier one, and cannot rescue a weak one.");
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
  s.addNotes("In July 2026 Coinkite disclosed that since 2021 its Coldcard wallets had generated seed phrases from a predictable software fallback. By Coinkite's own account, an AI-assisted review of that firmware missed it. Real failures are rare and deep, like the 35-step DynamoDB trace that passed every review. So an AI reviewer helps only if it gives a concrete, checkable witness and never invents failures. That raises the course question: find the failure directly, or translate for a solver? Sources: Decrypt (decrypt.co/374766), Coinkite's entropy technical backgrounder (blog.coinkite.com/entropy-technical-backgrounder), Unchained (unchainedcrypto.com).");
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
  s.addNotes("To answer it, we need tasks where the answer can be checked. SP1: given a Python function and its docstring, find an input that breaks the docstring, like a leap-year rule with 400 typed as 399. SP2: given a design document and the events that can occur, find an order of events that breaks a safety property, like a retried payment charged twice. Either way, the answer is a witness anyone can replay.");
}

// 4. The two arms (§1, §4 scoring)
{
  const s = base(1, "Direct: the LLM searches. Translate: a solver searches", "Two arms, same input, same exact scoring. The only difference is who searches for the failure.");
  s.addImage({ path: `${D}/method.png`, x: 0.908, y: 1.3, w: 8.185, h: 3.5, altText: "Direct: the LLM searches for the failure itself. Translate: the LLM writes the problem formally as a specification and a solver searches, with errors fed back for repair. Both witnesses are replayed on the reference." });
  takeaway(s, "Both arms are scored the same way: a witness counts only if it replays on the gold reference.");
  s.addNotes("We find witnesses in two ways, which we call arms. Direct: the LLM searches for the failure itself. Translate: the LLM writes the problem formally as a specification, a solver searches, and errors go back for repair. Both arms are scored the same way: a witness counts only if it replays on the gold reference.");
}

// 5. Research questions (§1)
{
  const s = base(1, "Two research questions", "What we measure for each arm");
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
  s.addNotes("With the arms defined, here is what we measure. RQ1: which arm finds more valid witnesses, and does the gap widen as failures get harder to reach, meaning rarer failing inputs or longer failure traces? RQ2: which arm invents failures on correct functions and designs? And SP3 scores the translations themselves, so we can tell a translation error from a solver error.");
}

// 6. Worked example (§1)
{
  const s = base(1, "Worked example: a bug random testing misses", "One mutated constant. Only 7 of the 36,000 valid inputs (0.02%) expose it.");
  s.addImage({ path: `${D}/worked_example.png`, x: 0.85, y: 1.3, w: 8.3, h: 3.451, altText: "days_in_month with 399 instead of 400: random testing finds it 18% of the time with 1,000 inputs; Opus 5.5 Direct answers February 2000; Opus 5.5 Translate writes a spec and Z3 returns February 2400." });
  takeaway(s, "Gold check: the reference returns 29 and the mutant 28 on both inputs, so both arms found a valid witness.");
  s.addNotes("Here is one bug through both arms. One mutated constant, 400 to 399. Only 7 of 36,000 inputs fail, so 1,000 random tests catch it 18% of the time. Opus Direct reasons its way to February 2000. Opus Translate writes the spec from the docstring and Z3 finds February 2400 in 0.01 s. Both are confirmed against the reference.");
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
  s.addNotes("SP2 is classical planning. Facts describe the state, actions are the events including failures, the initial state encodes the design, and the goal is the violation. The planner chooses every event, so a plan is a counterexample: planning used as model checking of a safety property. In this trace the retry passes the duplicate check because the record is written only after charging, so the card is charged twice.");
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
  s.addNotes("Why should we trust a solver's answer? For SP1 we show the encoding matches Python on every input within the loop bounds, so every Z3 answer is an input that breaks the spec, and unsatisfiable means no failure within those bounds. For SP2, our SATPlan clauses are equivalent to the successor-state axioms, so the first satisfiable horizon gives a shortest trace. To certify safety, greedy best-first search runs until its queue is empty. Planning is PSPACE-complete, so this is where the tools can run out.");
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
    "60 main designs at sizes 1 to 4. Also 30 stress designs (traces of 17 to 27 events), 60 opaque (the main set with revealing names replaced) and 12 long (30 to 51 events)",
  ]);
  takeaway(s, "Ground truth comes from our own solvers, plus one hand proof for the largest inventory designs.");
  s.addNotes("Now the experiment, starting with what we tested. SP1 has 174 instances from 37 functions: bugs from common to very rare triggers, plus controls, including equivalent mutants that look buggy but are not. SP2 has five services, each flawed, subtle or fixed, at several sizes, plus stress, opaque and long sets. Every instance has a known answer.");
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
  ], { x: X, y: 2.65, w: W, h: 2.1, fontSize: 13, paraSpaceAfter: 8 });
  takeaway(s, "Undecided is never counted as \"no failure\".");
  s.addNotes("Then how we ran it. Five models in three tiers: strong, mid-tier Haiku, and weak Llama. Direct runs with all tools disabled, so it must reason rather than execute. Translate gets up to two repairs. Every answer gets exactly one label, and a tool that runs out of budget is undecided, never no failure.");
}

// 12. Scoreboard (§5 overview)
{
  const s = base(4, "Strong models are near-perfect; Haiku and Llama are not", "Every model and arm at a glance. Darker cells are worse: bugs missed, or false alarms raised.");
  s.addImage({ path: `${D}/scoreboard.png`, x: X, y: 1.25, w: W, h: 3.55, altText: "Scoreboard of every model and arm on bugs found, false alarms, failure traces found and false alarms with names hidden" });
  takeaway(s, "Now each research question in turn.");
  s.addNotes("Now the results, first at a glance. The 5.5 models and Qwen are near-perfect on the sets they ran, with zero false alarms. Haiku is fine on functions but struggles on designs, especially false alarms with names hidden. Llama fails everywhere: in Direct it fabricates, with 45 false alarms on 59 correct functions.");
}

// 13. RQ1 (§5.1-5.2)
{
  const s = base(4, "Strong models find nearly every failure, even the hardest", "RQ1. Which arm finds more valid witnesses, and does the gap widen as failures get harder to reach?");
  s.addImage({ path: `${D}/hardness_panel.png`, x: X, y: 1.28, w: W, h: 3.45, altText: "Left: failures found vs how rare the failing input is, for random testing and both arms. Right: valid traces vs shortest failure trace length for Sonnet, Opus and Haiku" });
  takeaway(s, "Rarity defeats random testing (5% of very rare bugs at 100 inputs), not the LLMs. Translate trails only on the rarest bugs: 29 of 32 model–bug pairs against 32 of 32.");
  s.addNotes("RQ1 first. Random testing falls off as bugs get rarer; Direct finds all of them, Translate 29 of 32 very rare pairs, two bugs, so only a hint. On designs, trace length from 6 to 51 events does not hurt Sonnet or Opus, and Haiku stays near 80% with no length trend. This looks like recognition rather than search.");
}

// 14. RQ2 (§5.1-5.2)
{
  const s = base(4, "Translation cuts the mid-tier model's false alarms", "RQ2. Which arm invents more failures where there are none? Here: false alarms on the 20 correct designs.");
  s.addImage({ path: `${D}/false_alarms.png`, x: X, y: 1.28, w: W, h: 3.45, altText: "False alarms on correct designs, Direct vs Translate: Haiku 12 to 7 of 20 (19 to 9 with names hidden), Llama 14 to 2 (18 to 8), Sonnet, Opus and Qwen 0 in both arms" });
  takeaway(s, "The strong models raise none in either arm. Llama's drop is silence, not skill: its files left out facts, so the planner found nothing.");
  s.addNotes("RQ2. On functions only Llama raised false alarms. On correct designs, translation helps the mid-tier model: Haiku's false alarms fall from 12 to 7 of 20, and from 19 to 9 with names hidden. The strong models stay at zero. Llama's drop is not better reasoning: its problem files left out facts, so the planner found no violation.");
}

// 15. SP3 (§5, §5.3)
{
  const s = base(4, "Translate fails through its specification or its tools", "SP3. How good were the translations?");
  T(s, "Sonnet and Opus wrote the exact initial state in all 90 main and stress designs. Where translation failed, it failed in four ways:",
    { x: X, y: 1.28, w: W, h: 0.42, fontSize: 12 });
  table(s, [
    [hcell("What goes wrong"), hcell("What we saw")],
    [lab("The specification copies the bug"), "Two Claude postconditions copied the code's bug, e.g. Haiku's leap-year spec, so Z3 found nothing"],
    [lab("The translation is too permissive"), "13 of Haiku's main-set traces worked only in its own mistranslated problem, e.g. a lease clock started before anyone held the lock"],
    [lab("The model cannot write the formal language"), "Llama: 70 of 174 function runs gave no usable spec, and its design files left out about a third of the initial facts"],
    [lab("The solver runs out"), "Functions: 3 timeouts and 5 Z3 \"unknown\". Designs: inventory needs 2.7M states at size 6 and exceeds the budget from size 8"],
  ], { x: X, y: 1.8, w: 6.15, colW: [1.95, 4.2], rowH: [0.28, 0.6, 0.6, 0.6, 0.6], fontSize: 10.5 });
  s.addImage({ path: `${D}/inventory_panel.png`, x: 6.75, y: 1.8, w: 2.875, h: 2.9, altText: "States expanded to prove safety vs design size: inventory explodes and exceeds the budget at size 8, the other designs stay small" });
  takeaway(s, "A Translate answer is only as good as the translation, so every witness is replayed on the real artefact.");
  s.addNotes("SP3 asks how good the translations were. Sonnet and Opus wrote the exact initial state in all 90 main and stress designs, but translation is not free. The table shows the four ways it failed. Inventory explodes: 2.7 million states at size 6, and from size 8 the budget runs out. On its safe design Translate is then undecided, while Sonnet and Opus Direct still answer correctly, without proof. The standard remedies, symmetry reduction and inductive invariants, lie outside the course; we proved the inventory invariant by hand.");
}

// 16. The answer in brief (§6 opening)
{
  const s = base(5, "The answer in brief", "Course question, part 1: when to use the LLM directly, and when to translate?");
  const a = (y, n, head, body) => {
    card(s, X, y, W, 1.02);
    s.addShape(pres.shapes.OVAL, { x: 0.6, y: y + 0.26, w: 0.5, h: 0.5, fill: { color: INK }, line: { color: INK } });
    T(s, n, { x: 0.6, y: y + 0.26, w: 0.5, h: 0.5, fontSize: 16, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
    T(s, head, { x: 1.35, y: y + 0.13, w: 8.05, h: 0.32, fontSize: 15, bold: true });
    T(s, body, { x: 1.35, y: y + 0.47, w: 8.05, h: 0.5, fontSize: 12, color: INK2 });
  };
  a(1.3, "1", "Strong models: the arms nearly tie, consistent with recognition, not search",
    "Sonnet 5.5 and Opus 5.5 were never wrong on designs in either arm, up to 51 events and with names hidden.");
  a(2.44, "2", "Translation moves the error into the specification; it does not remove it",
    "It cuts Haiku's false alarms (12 to 7 of 20 correct designs; 19 to 9 with names hidden) but cannot rescue Llama, which cannot write the formal language.");
  a(3.58, "3", "Only the tools can certify \"no failure\", and that is where they run out",
    "Inventory's safe design from size 8: Translate is undecided, while Sonnet and Opus Direct answer correctly, without proof.");
  takeaway(s, "So which arm to use depends on the model, and on whether the answer must be proved.");
  s.addNotes("Putting the results together, the answer in brief. One: with a strong model the two arms nearly tie, consistent with recognising patterns rather than searching. Two: translation moves part of the error into the specification rather than removing it, so it helps only a model that writes the formal language reliably: Haiku yes, Llama no. Three: only the tools can certify that there is no failure, and that is exactly where they run out of budget.");
}

// 17. Trade-offs and when to use which (§6)
{
  const s = base(5, "Trade-offs, and when to use which arm", "Choosing an arm is a maximum-expected-utility decision");
  table(s, [
    [hcell(""), { text: "Direct", options: { bold: true, color: BLUE, fill: { color: HEAD } } }, { text: "Translate", options: { bold: true, color: ORANGE, fill: { color: HEAD } } }],
    [lab("Proof of absence"), "None", "Yes, with an audit trail, for the problem as translated and within the bounds"],
    [lab("Needs"), "The model (plus, in SP2, the same event rules)", "A solver, an encoder, and a model fluent in the specification language"],
    [lab("Fails by"), "Pattern-matching the wrong design", "A wrong specification, a loose problem file, or a timeout"],
    [lab("Use when"), "The model is strong, the review small, the specification complete, and an answer without proof is fine",
      "Absence must be certified or audited, or a mid-tier model misreads designs but writes the formal language well. Always replay the witness"],
  ], { x: X, y: 1.28, w: W, colW: [1.6, 3.55, 4.1], rowH: [0.28, 0.42, 0.42, 0.42, 0.62], fontSize: 11.5 });
  T(s, [
    B("EU(arm) = −[ (1 − q) · P(false alarm) · c"), { text: "FA", options: { subscript: true, bold: true } },
    B(" + q · P(miss) · c"), { text: "miss", options: { subscript: true, bold: true } },
    B(" + P(undecided) · c"), { text: "rev", options: { subscript: true, bold: true } },
    B(" + c"), { text: "run", options: { subscript: true, bold: true } }, B(" ]"),
  ], { x: X, y: 3.7, w: W, h: 0.32, fontSize: 13.5, align: "center" });
  T(s, "q is the share of flawed designs; the c terms are the costs of a false alarm, a miss, a manual review and a run.",
    { x: X, y: 4.0, w: W, h: 0.26, fontSize: 10.5, color: INK2, align: "center" });
  bullets(s, [
    "Haiku on designs: Translate has fewer false alarms (35% vs 60%), fewer misses (6 vs 9 of 40), nothing undecided and a lower cost (US$0.051 vs 0.062 per design)",
  ], { x: X, y: 4.3, w: W, h: 0.5, fontSize: 12 });
  takeaway(s, "So for Haiku, at these estimates, Translate wins whatever the mix of flawed and correct designs.");
  s.addNotes("So which arm should you use? Choosing is a maximum-expected-utility decision: weigh the cost of a false alarm against the cost of a miss, a manual review and a run. For Haiku on designs, Translate has fewer false alarms, fewer misses and costs less, so it wins whatever the mix. Qwen nearly matched the 5.5 models where it ran, so an open-weight model can do this locally.");
}

// 18. Limitations and will this change (§6)
{
  const s = base(5, "Limitations, and will this change?", "Course question, part 2");
  bullets(s, [
    "Scaffolding: SP2 gives both arms the failure mechanisms as named events; writing the event model is untested",
    "Bugs are mostly single-change mutants, docstrings are complete, and functions were chosen to be encodable (integers, Booleans, lists)",
    "Ceiling effect: most cells are at or near 100%, so these benchmarks cannot rank the strongest models",
    "Public benchmarks and textbook designs may be in training data; hiding names removes only lexical cues",
  ], { x: X, y: 1.3, w: W, h: 2.2, fontSize: 13, paraSpaceAfter: 6 });
  card(s, X, 3.3, W, 1.0);
  T(s, "Will this change?", { x: 0.6, y: 3.4, w: 8.8, h: 0.3, fontSize: 14, bold: true });
  T(s, "Direct will likely keep improving on small, recognisable problems (Haiku 4.5 to the 5.5 models), but worst-case hardness and the missing certificate remain.",
    { x: 0.6, y: 3.73, w: 8.8, h: 0.5, fontSize: 12 });
  takeaway(s, "Bottom line: translation's value depends on the model. It adds no accuracy for strong models, cuts false alarms for a mid-tier one, and cannot rescue a weak one.");
  s.addNotes("Finally, what this does not show, and whether it will change. SP2 hands both arms the failure mechanisms as named events; writing the event model is untested. Most cells are at or near 100%, so we cannot rank the strongest models. Will this change? Direct will likely keep improving on small, recognisable problems, but worst-case hardness and the missing certificate remain. Bottom line: translation's value depends on the model. Thank you.");
}

pres.writeFile({ fileName: `${D}/premortem_slides.pptx` }).then(f => console.log("wrote", f));
