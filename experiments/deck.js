// Builds results/figures/slides/premortem_slides.pptx from the slide PNGs.
// Usage: node experiments/deck.js results/figures/slides   (needs pptxgenjs: npm install pptxgenjs)
// Slides follow the report: motivation and questions (§1), formulation (§2), instances and method (§3-4),
// results by RQ and SP3 (§5), answer, trade-offs and limitations (§6).
const pptxgen = require("pptxgenjs");
const D = process.argv[2];
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "AI Pre-Mortems";
const INK = "0B0B0B", INK2 = "52514E", BG = "FCFCFB", BLUE = "2A78D6", ORANGE = "EB6834", CARD = "F4F3F0", HEAD = "EBEAE6";
const F = "Arial";
const T = (s, text, o) => s.addText(text, Object.assign({ fontFace: F, color: INK, margin: 0, isTextBox: true, valign: "top" }, o));

function base(title, sub) {
  const s = pres.addSlide();
  s.background = { color: BG };
  T(s, title, { x: 0.375, y: 0.28, w: 9.25, h: 0.45, fontSize: 22, bold: true });
  if (sub) T(s, sub, { x: 0.375, y: 0.74, w: 9.25, h: 0.3, fontSize: 12, color: INK2 });
  return s;
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
function image(file, alt, notes) {
  const s = pres.addSlide();
  s.background = { color: BG };
  s.addImage({ path: `${D}/${file}`, x: 0, y: 0, w: 10, h: 5.625, altText: alt });
  s.addNotes(notes);
  return s;
}
// Small label in the top-right corner naming the research question a results slide answers.
function tag(s, text) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.75, y: 0.3, w: 0.875, h: 0.34, rectRadius: 0.08, fill: { color: HEAD }, line: { color: HEAD } });
  T(s, text, { x: 8.75, y: 0.3, w: 0.875, h: 0.34, fontSize: 12, bold: true, align: "center", valign: "middle" });
}
const hcell = (t, c) => ({ text: t, options: { bold: true, color: c || INK, fill: { color: HEAD } } });
const lab = t => ({ text: t, options: { bold: true } });
const card = (s, x, y, w, h) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: CARD }, line: { color: CARD } });

// 1. Title (Summary)
{
  const s = pres.addSlide();
  s.background = { color: BG };
  T(s, "CS3263 Foundations of AI  ·  Project Group 19", { x: 0.6, y: 0.9, w: 8.8, h: 0.35, fontSize: 14, color: INK2 });
  T(s, "AI Pre-Mortems", { x: 0.6, y: 1.35, w: 8.8, h: 0.8, fontSize: 44, bold: true });
  T(s, "Can frontier models predict how code and systems fail?", { x: 0.6, y: 2.15, w: 8.8, h: 0.5, fontSize: 22 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 2.95, w: 1.15, h: 0.38, rectRadius: 0.08, fill: { color: "EAF2FC" }, line: { color: BLUE, width: 1.25 } });
  T(s, "Direct", { x: 0.6, y: 2.95, w: 1.15, h: 0.38, fontSize: 14, bold: true, color: BLUE, align: "center", valign: "middle" });
  T(s, "vs", { x: 1.8, y: 2.95, w: 0.4, h: 0.38, fontSize: 14, color: INK2, align: "center", valign: "middle" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 2.25, y: 2.95, w: 1.35, h: 0.38, rectRadius: 0.08, fill: { color: "FDEEE7" }, line: { color: ORANGE, width: 1.25 } });
  T(s, "Translate", { x: 2.25, y: 2.95, w: 1.35, h: 0.38, fontSize: 14, bold: true, color: ORANGE, align: "center", valign: "middle" });
  T(s, [{ text: "Yash Raj Khandelwal", options: { breakLine: true } }, { text: "Joshua Tan Yu Jie", options: { breakLine: true } }, { text: "Hein Htet Zaw" }],
    { x: 0.6, y: 3.85, w: 6, h: 1.1, fontSize: 18, paraSpaceAfter: 4 });
  T(s, "Semester 1, AY2026/27", { x: 6.4, y: 4.6, w: 3.0, h: 0.35, fontSize: 14, color: INK2, align: "right" });
  s.addNotes("Introduce the team. The question: can an LLM act as a pre-mortem reviewer, finding how a function or a system design will fail before it ships? We compare two ways of using it, Direct and Translate, on functions and on system designs. Our headline: translation's value depends on the model. It adds no accuracy for strong models, cuts false alarms for a mid-tier one, and cannot rescue a weak one.");
}

// 2. Motivation (§1)
{
  const s = base("Motivation: an AI assistant for code and design review", "A pre-mortem asks how something will fail before it ships");
  bullets(s, [
    "Aug 2026, Coldcard bitcoin wallets: a 5-year-old randomness bug let attackers drain wallets (reported losses US$38M to over US$114M). Coinkite says its own AI-assisted review missed it",
    "Failures that matter hide behind rare inputs or long event orderings (AWS DynamoDB: a 35-step data-loss trace passed every review)",
    "A useful reviewer must give a witness (a failing input or event trace), never call broken code safe, and never invent failures",
    "Course question: use the LLM directly, or have it translate the problem for a solver?",
  ], { x: 0.375, y: 1.25, w: 4.6, h: 3.9 });
  s.addImage({ path: `${D}/img/coldcard_q_mk5.png`, x: 5.35, y: 1.15, w: 2.47, h: 2.25, altText: "Coldcard Q and Mk5 hardware bitcoin wallets made by Coinkite" });
  T(s, [{ text: "Coldcard Q and Mk5 hardware wallets, made by Coinkite", options: { breakLine: true } }, { text: "Image: coldcard.com", options: { fontSize: 10 } }],
    { x: 8.0, y: 1.6, w: 1.625, h: 1.2, fontSize: 12, color: INK2, paraSpaceAfter: 6 });
  s.addImage({ path: `${D}/coldcard_timeline.png`, x: 5.25, y: 3.6, w: 4.375, h: 1.55, altText: "Timeline: Mar 2021 bug ships, Jul 2026 AI-assisted review misses it (Coinkite's account), Jul to Aug 2026 wallets drained, reported US$38M to over US$114M" });
  T(s, "Sources: Decrypt (Aug 2026); Coinkite, \"Entropy technical backgrounder\"; Unchained (Aug 2026)", { x: 5.25, y: 5.18, w: 4.375, h: 0.25, fontSize: 9, color: INK2 });
  s.addNotes("In July 2026 Coinkite disclosed that since 2021 its Coldcard wallets had generated seed phrases from a predictable software fallback. By Coinkite's own account, an AI-assisted review of that firmware missed it; reported losses range from US$38M to over US$114M. Real failures are rare and deep, like the 35-step DynamoDB trace that passed every review. So an AI reviewer helps only if it gives a concrete, checkable witness, never calls broken code safe, and never invents failures. Sources: Decrypt (decrypt.co/374766), Coinkite's entropy technical backgrounder (blog.coinkite.com/entropy-technical-backgrounder), Unchained (unchainedcrypto.com).");
}

// 3. Two arms (§1, §4 scoring)
image("method.png", "Direct vs Translate pipeline diagram",
  "Two approaches on the same input. Direct: the LLM reads the code or design and outputs the failure itself. Translate: the LLM writes a formal spec, a solver searches, and errors go back for repair. Both are scored the same way: the witness only counts if it reproduces on the gold model.");

// 4. Tasks and research questions (§1)
{
  const s = base("Two review tasks, two questions", "What we ask each model to do, and what we measure");
  const task = (x, head, color, body) => {
    card(s, x, 1.2, 4.5, 1.5);
    T(s, head, { x: x + 0.25, y: 1.33, w: 4.0, h: 0.3, fontSize: 14, bold: true, color });
    T(s, body, { x: x + 0.25, y: 1.7, w: 4.0, h: 0.95, fontSize: 12 });
  };
  task(0.375, "SP1: function review", BLUE, "Given a Python function and its docstring, find an input that breaks the docstring, e.g. a leap-year rule with 400 mistyped as 399.");
  task(5.125, "SP2: design review", ORANGE, "Given a design document and the events that can occur, find an order of timeouts, retries, lost messages and crashes that breaks a safety property, e.g. \"no order is charged twice\".");
  const q = (y, label, body) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.375, y, w: 0.8, h: 0.4, rectRadius: 0.08, fill: { color: HEAD }, line: { color: HEAD } });
    T(s, label, { x: 0.375, y, w: 0.8, h: 0.4, fontSize: 13, bold: true, align: "center", valign: "middle" });
    T(s, body, { x: 1.4, y: y - 0.02, w: 8.225, h: 0.62, fontSize: 13 });
  };
  q(2.95, "RQ1", "Which arm finds more valid witnesses, and does the gap widen as failures get harder to reach? (rarer inputs in SP1, longer traces in SP2)");
  q(3.7, "RQ2", "Which arm fabricates more failures on correct controls, i.e. functions or designs with no failure?");
  q(4.45, "SP3", "Not a third task: we score Translate's translations against gold (sound spec? exact initial state?), to tell translation errors from solver errors.");
  s.addNotes("We study two review tasks. SP1: given a function and its docstring, find an input that breaks the docstring. SP2: given a design document, find an order of events that breaks a safety property, such as charging a card twice. Two research questions. RQ1: which arm finds more valid witnesses, and does the gap widen as failures get harder to reach? RQ2: which arm invents failures on correct inputs? SP3 is not a third task: it scores the translations, so we can tell a translation error from a solver error. Here is one SP1 bug end to end.");
}

// 5. Worked example (§1)
image("worked_example.png", "Worked example: leap-year bug with 399 instead of 400",
  "One mutated constant, 400 to 399. Only 7 of 36,000 inputs fail, so 1,000 random tests catch it 18% of the time. Opus Direct reasons its way to February 2000. Opus Translate writes the spec from the docstring and Z3 finds February 2400 in 0.01 s. Both are confirmed against the reference. Next: how the Translate arm turns this into a solver problem.");

// 6. SP1 formulation (§2.1)
{
  const s = base("SP1 formulation: a function as a CSP, solved by SMT", "Does some input break the docstring?");
  bullets(s, [
    "Variables: the function's inputs (a list is a length plus element variables)",
    "Domains: the stated ranges, e.g. 1 ≤ month ≤ 12",
    "Constraints: code(x) = r  ∧  ¬spec(x, r)",
    "Bounded symbolic execution turns the code into one formula: if x > 0: y = 1 else: y = 2  →  If(x > 0, 1, 2)",
    "Translate: the LLM writes pre / post, Z3 finds x. Every witness is re-run in Python",
  ], { x: 0.375, y: 1.25, w: 4.6, h: 3.9 });
  s.addImage({ path: `${D}/sp1_formulation.png`, x: 5.25, y: 1.25, w: 4.375, h: 3.9, altText: "SP1 pipeline on a toy function: code becomes ret = If(x > 0, 1, 2), conjoined with not post, Z3 returns x = 0" });
  s.addNotes("SP1 is constraint satisfaction. The inputs are variables with finite domains, and the constraint is that the code's output violates the spec. We wrote our own bounded symbolic executor to turn Python into a Z3 formula. Key idea: system entails spec iff system AND NOT spec is unsatisfiable, so Z3's satisfying assignment is the failing input.");
}

// 7. SP2 formulation (§2.2)
{
  const s = base("SP2 formulation: a design as a STRIPS planning problem", "Does some order of events reach a violation?");
  bullets(s, [
    "Facts F: system state, e.g. (no-record o1)",
    "Actions A: events, including timeouts, retries, lost messages and crashes",
    "Initial state I: the design facts, e.g. (dedup-racy)",
    "Goal G: the violation, e.g. (charged-twice o1)",
    [{ text: "SATPlan finds a shortest trace. GBFS + h" }, { text: "FF", options: { subscript: true } }, { text: " searches exhaustively and certifies \"safe\"" }],
    "Both arms get the event rules (actions). Translate: the LLM writes only the initial state",
  ], { x: 0.375, y: 1.25, w: 4.6, h: 3.9 });
  s.addImage({ path: `${D}/sp2_trace.png`, x: 5.25, y: 1.25, w: 4.375, h: 3.9, altText: "Shortest failure trace for payments-subtle-1: eight events ending in charged-twice" });
  s.addNotes("SP2 is classical planning. The planner controls every event, including failures, so a plan is a counterexample, not a course of action: planning used as model checking of a safety property. Walk through the payments trace: the retry passes the duplicate check because the record is written only after charging, so the card is charged twice.");
}

// 8. Guarantees and complexity (§2)
{
  const s = base("What the solvers guarantee, and what it costs", "Why a solver's answer can be trusted, and where it stops");
  const sup = (a, b, c) => ({ text: [{ text: a }, { text: b, options: { superscript: true } }, { text: c }] });
  const rows = [
    [hcell(""), hcell("SP1: Z3 on a CSP", BLUE), hcell("SP2: SATPlan + GBFS on STRIPS", ORANGE)],
    [lab("Encoding"), "Bounded symbolic execution: one formula for all paths, loops unrolled k times",
      "A variable per fact and action per step; effects, explanatory frame axioms, exactly one action per step"],
    [lab("Encoding is correct"), "Lemma 1: within the bounds, the formula returns what Python returns (tested on 25 random inputs per function)",
      "Lemma 2: these clauses equal the textbook successor-state axioms"],
    [lab("\"Failure found\" means"), "Theorem 1: every Z3 answer is an input that breaks the spec",
      "Theorem 2: satisfiable at horizon T iff a T-step trace reaches G; the first such T gives a shortest trace"],
    [lab("\"No failure\" means"), "Theorem 1: none within the input and loop bounds; otherwise \"undecided\"",
      "Theorem 3: if GBFS empties its queue without reaching G, G is unreachable at this size"],
    [lab("Worst case"), "Finite CSP: NP-complete. Non-linear integers: Z3 can answer \"unknown\"",
      sup("PlanSAT: PSPACE-complete; each SATPlan call is NP-complete. Up to 2", "218", " states at size 8")],
  ];
  s.addTable(rows, { x: 0.375, y: 1.15, w: 9.25, colW: [1.6, 3.8, 3.85], fontFace: F, fontSize: 11, color: INK,
    border: { type: "solid", pt: 0.75, color: "E4E3DF" }, rowH: [0.3, 0.62, 0.62, 0.62, 0.46, 0.46], margin: 0.06, valign: "middle" });
  T(s, [{ text: "h" }, { text: "FF", options: { subscript: true } },
    { text: " only prunes dead ends, which is safe because ignoring deletes only adds behaviour (1.2× to 3.8× fewer states than BFS). Every witness is replayed on the real code or gold problem before it counts." }],
    { x: 0.375, y: 4.55, w: 9.25, h: 0.6, fontSize: 12 });
  s.addNotes("Why trust the solver? For SP1 we proved the encoding matches Python on every input within the loop bounds, so every Z3 answer is an input that breaks the spec, and unsatisfiable means no failure within those bounds. A finite CSP is NP-complete, and with non-linear arithmetic Z3 can answer unknown, which we score as undecided. For SP2, our SATPlan clauses are equivalent to the successor-state axioms, so the first satisfiable horizon gives a shortest failure trace. To certify safety, greedy best-first search runs until its queue is empty; the FF heuristic only prunes dead ends, which is safe. Planning is PSPACE-complete, so this is where the tools can run out, as inventory shows later.");
}

// 9. Problem instances and method (§3-4)
{
  const s = base("Problem instances and method", "Built and labelled automatically, scored by exact replay on the gold model");
  const col = (x, head, big, lines, color) => {
    card(s, x, 1.15, 4.5, 2.85);
    T(s, head, { x: x + 0.3, y: 1.3, w: 3.9, h: 0.3, fontSize: 14, bold: true, color });
    T(s, big, { x: x + 0.3, y: 1.62, w: 3.9, h: 0.6, fontSize: 36, bold: true });
    bullets(s, lines, { x: x + 0.3, y: 2.32, w: 3.9, h: 1.6, fontSize: 12, paraSpaceAfter: 5 });
  };
  col(0.375, "SP1: functions", "174", [
    "37 functions (27 base, 10 hard), renamed, docstrings rewritten",
    "115 bugs from 808 auto mutants + 42 hand-written, picked by rarity",
    "59 controls: 37 clean, 22 provably equivalent",
  ], BLUE);
  col(5.125, "SP2: designs", "162", [
    "60 main: payments, inventory, lock, queue, cache × flawed / subtle / fixed × sizes 1–4",
    "+ 30 stress (17–27 events), 60 opaque (names hidden), 12 long (30–51 events)",
    "Gold labels from SATPlan and GBFS (inventory fixed from size 8: hand proof)",
  ], ORANGE);
  T(s, [
    { text: "Models: ", options: { bold: true } },
    { text: "strong = Sonnet 5.5, Opus 5.5 (Claude) and Qwen 3.8 27B; mid-tier = Haiku 4.5 (Claude); weak = Llama 3.1 8B. Qwen and Llama are open-weight, on SoCLaaS; Qwen ran SP1 and the SP2 main set only.", options: { breakLine: true } },
    { text: "Arms: ", options: { bold: true } },
    { text: "both see the same inputs. Direct has all tools disabled, so it cannot run the code. Translate gets up to two repairs. A budget hit is \"undecided\", never \"no failure\"." },
  ], { x: 0.375, y: 4.15, w: 9.25, h: 1.2, fontSize: 12, paraSpaceAfter: 6 });
  s.addNotes("SP1: 174 instances. Bugs are single-change mutants plus hand-written bugs, chosen to cover common through very rare triggers; controls include equivalent mutants that look buggy but are not. SP2: 60 main designs across five families, plus stress, opaque and long sets. Five models in three tiers: strong, mid-tier Haiku, and weak Llama. Direct runs with all tools disabled, so it must reason rather than execute.");
}

// 10. Scoreboard (§5 overview)
image("scoreboard.png", "Scoreboard heatmap of all models and arms",
  "The results at a glance. The 5.5 models and Qwen 27B are near-perfect on the sets they ran with zero false alarms. Haiku 4.5 is fine on functions but struggles on designs, especially false alarms with names hidden. Llama 8B fails everywhere: in Direct it fabricates, 45 of 59 false alarms on correct code. Now each research question in turn.");

// 11. RQ1: harder failures (§5.1-5.2 RQ1)
{
  const s = base("Harder failures do not hurt the strong models", "SP1: rarer triggering inputs. SP2: longer failure traces");
  tag(s, "RQ1");
  s.addImage({ path: `${D}/hardness_panel.png`, x: 0.375, y: 1.2, w: 9.25, h: 3.4, altText: "Left: failures found vs rarity for random testing and LLM arms. Right: valid traces vs trace length for Sonnet, Opus and Haiku" });
  T(s, "Rarity defeats random testing (5% of very rare bugs at 100 inputs) far more than the LLMs. The 5.5 models stay perfect up to 51-event traces.", { x: 0.375, y: 4.8, w: 9.25, h: 0.5, fontSize: 14 });
  s.addNotes("RQ1. Random testing falls off as bugs get rarer; Direct finds all of them, Translate 29 of 32 very rare pairs (two bugs, so a hint). On designs, trace length from 6 to 51 events does not hurt Sonnet or Opus; Haiku stays near 80% with no length trend. This looks like recognition rather than search.");
}

// 12. RQ2: false alarms (§5.1-5.2 RQ2)
tag(image("false_alarms.png", "Slope chart: false alarms Direct vs Translate",
  "RQ2. Translation helps the mid-tier model: Haiku false alarms 12 to 7, and 19 to 9 with names hidden. The strong models stay at zero. Caveat on Llama: on the 20 correct main designs, Llama Translate said safe 16 times, raised 2 false alarms and gave no answer twice. Its problem files left out facts, so the planner found no violation; that is not better reasoning."), "RQ2");

// 13. Where Translate breaks (§5 SP3, §5.3)
{
  const s = base("Where Translate breaks", "SP3 scores the translations: the error moves into the specification, and the tools have limits");
  tag(s, "SP3");
  const c = (y, head, body) => {
    card(s, 0.375, y, 4.6, 0.98);
    T(s, head, { x: 0.55, y: y + 0.12, w: 4.25, h: 0.3, fontSize: 14, bold: true });
    T(s, body, { x: 0.55, y: y + 0.42, w: 4.25, h: 0.5, fontSize: 12, color: INK2 });
  };
  c(1.25, "The spec copies the bug", "Haiku's spec reused the mutated leap() line, so Z3 found nothing");
  c(2.35, "The planner exploits slack", "Haiku's lock problem started a lease clock before anyone held the lock; the trace only works in its model");
  c(3.45, "The tools run out", "SP1: 3 timeouts, 5 Z3 unknowns. Inventory: 2.7M states at size 6; from size 8 the budget runs out");
  s.addImage({ path: `${D}/inventory_panel.png`, x: 5.25, y: 1.25, w: 4.375, h: 3.18, altText: "States expanded to prove safety vs design size, inventory explodes, other designs flat" });
  T(s, "Llama could not write the formal language: its SP2 problem files left out about a third of the initial facts, and 70 of its 174 SP1 runs gave no usable spec.", { x: 0.375, y: 4.65, w: 9.25, h: 0.5, fontSize: 13 });
  s.addNotes("SP3 scores the translations. Sonnet and Opus wrote the exact gold initial state in all 90 main and stress problems, but translation is not free. Specs can inherit the bug, permissive problem files hand the planner shortcuts, and solvers time out. The symmetric inventory design explodes: 9k states at size 4, 2.7M at 6, and from size 8 the budget runs out. There Translate is undecided while Sonnet and Opus Direct still answer correctly, without proof. The standard remedies, symmetry reduction and inductive invariants, lie outside the course; we proved the inventory invariant by hand.");
}

// 14. The answer in brief (§6 opening)
{
  const s = base("The answer in brief", "What the results say about the course question");
  const a = (y, n, head, body) => {
    card(s, 0.375, y, 9.25, 1.1);
    s.addShape(pres.shapes.OVAL, { x: 0.6, y: y + 0.3, w: 0.5, h: 0.5, fill: { color: INK }, line: { color: INK } });
    T(s, n, { x: 0.6, y: y + 0.3, w: 0.5, h: 0.5, fontSize: 16, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
    T(s, head, { x: 1.35, y: y + 0.15, w: 8.05, h: 0.32, fontSize: 15, bold: true });
    T(s, body, { x: 1.35, y: y + 0.5, w: 8.05, h: 0.55, fontSize: 12, color: INK2 });
  };
  a(1.2, "1", "Strong models: the arms nearly tie, consistent with recognition, not search",
    "Sonnet 5.5 and Opus 5.5 were never wrong on designs in either arm, up to 51 events and with names hidden.");
  a(2.45, "2", "Translation moves the error into the specification; it does not remove it",
    "It cuts Haiku's false alarms (12 to 7 of 20 correct designs; 19 to 9 with names hidden) but cannot rescue Llama, which cannot write the formal language.");
  a(3.7, "3", "Only the tools can certify \"no failure\", and that is where they run out",
    "Inventory's safe design from size 8: Translate is undecided, while Sonnet and Opus Direct answer correctly, without proof.");
  s.addNotes("So, the answer in brief. One: with a strong model the two arms nearly tie, consistent with recognising patterns rather than searching. Two: translation moves part of the error into the specification rather than removing it, so it helps only a model that writes the formal language reliably: Haiku yes, Llama no. Three: only the tools can certify that there is no failure, and that is exactly where they run out of budget.");
}

// 15. Trade-offs and when to use which (§6)
{
  const s = base("Direct vs Translate: trade-offs and when to use which", "A maximum-expected-utility choice: the cost of a false alarm vs the cost of a miss");
  const rows = [
    [hcell(""), hcell("Direct", BLUE), hcell("Translate", ORANGE)],
    [lab("Strong models"), "≈ every failure, 0 false alarms", "≈ every failure, 0 false alarms"],
    [lab("Mid-tier (Haiku)"), "Misreads designs: false alarms on 60% of correct ones", "35% false alarms, fewer misses, lower cost"],
    [lab("Weak (Llama)"), "Fabricates: false alarms on 76% of correct functions", "Quieter, not better: broken problem files miss 29 of 40 design failures"],
    [lab("Proof of absence"), "None", "Yes, with an audit trail (bounded, as translated)"],
    [lab("Needs"), "The model (plus, in SP2, the same event rules)", "Solver, encoder, model fluent in the spec language"],
    [lab("Fails by"), "Pattern-matching the wrong design", "Bad spec, loose problem file, timeouts"],
    [lab("Use when"), "Strong model, small review, complete spec; an answer without proof is fine",
      "Absence must be certified or audited, or a mid-tier model misreads designs but writes the formal language well. Always replay the witness"],
  ];
  s.addTable(rows, { x: 0.375, y: 1.15, w: 9.25, colW: [1.6, 3.65, 4.0], fontFace: F, fontSize: 11, color: INK,
    border: { type: "solid", pt: 0.75, color: "E4E3DF" }, rowH: 0.3, margin: 0.05, valign: "middle" });
  T(s, [{ text: "Example (Haiku, SP2 main set): ", options: { bold: true } },
    { text: "Translate has fewer false alarms (35% vs 60%), fewer misses (6 vs 9 of 40), nothing undecided and a lower cost (US$0.051 vs 0.062 per design), so at these point estimates it wins for any share of flawed designs and any positive costs." }],
    { x: 0.375, y: 4.4, w: 9.25, h: 0.7, fontSize: 12 });
  s.addNotes("What does this mean in practice? With strong models the arms tie. The mid-tier model gains from translation; the weak one only goes quiet. Choosing an arm is a maximum-expected-utility decision: weigh the cost of a false alarm against the cost of a miss. For Haiku on designs, Translate has fewer false alarms, fewer misses and costs less, so it wins whatever the mix. Qwen 3.8 27B nearly matched the 5.5 models where it ran, so an open-weight model can do this locally.");
}

// 16. Limitations and will this change (§6)
{
  const s = base("Limitations, and will this change?", "What these results do not show, and the second half of the course question");
  bullets(s, [
    "Scaffolding: SP2 gives both arms the failure mechanisms as named events; writing the event model is untested",
    "Bugs are mostly single-change mutants, docstrings are complete, and functions were chosen to be encodable (integers, Booleans, lists)",
    "Ceiling effect: most cells are at or near 100%, so these benchmarks cannot rank the strongest models",
    "Public benchmarks and textbook designs may be in training data; hiding names removes only lexical cues",
  ], { x: 0.375, y: 1.2, w: 9.25, h: 2.2, fontSize: 13, paraSpaceAfter: 6 });
  card(s, 0.375, 3.2, 9.25, 0.95);
  T(s, "Will this change?", { x: 0.6, y: 3.3, w: 8.8, h: 0.3, fontSize: 14, bold: true });
  T(s, "Direct will likely keep improving on small, recognisable problems (Haiku 4.5 to the 5.5 models), but worst-case hardness and the missing certificate remain.",
    { x: 0.6, y: 3.63, w: 8.8, h: 0.48, fontSize: 12 });
  T(s, [{ text: "In practice: ", options: { bold: true } },
    { text: "Direct suffices when the spec is explicit and the model strong; Translate adds a no-failure certificate, valid only if the translation is correct and the solver finishes." }],
    { x: 0.375, y: 4.4, w: 9.25, h: 0.6, fontSize: 13 });
  s.addNotes("What this does not show. SP2 hands both arms the failure mechanisms as named events; writing the event model is untested. Most cells are at or near 100%, so we cannot rank the strongest models. Will this change? Direct will likely keep improving on small, recognisable problems, but worst-case hardness and the missing certificate remain. In practice: Direct suffices when the spec is explicit and the model strong; Translate adds a certificate, valid only if the translation is right and the solver finishes. Thank you.");
}

pres.writeFile({ fileName: `${D}/premortem_slides.pptx` }).then(f => console.log("wrote", f));
