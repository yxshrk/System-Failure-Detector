// Builds results/figures/slides/premortem_slides.pptx from the slide PNGs.
// Usage: node experiments/deck.js results/figures/slides   (needs pptxgenjs: npm install pptxgenjs)
const pptxgen = require("pptxgenjs");
const D = process.argv[2];
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "AI Pre-Mortems";
const INK = "0B0B0B", INK2 = "52514E", BG = "FCFCFB", BLUE = "2A78D6", ORANGE = "EB6834", CARD = "F4F3F0";
const F = "Arial";
const T = (s, text, o) => s.addText(text, Object.assign({ fontFace: F, color: INK, margin: 0, isTextBox: true, valign: "top" }, o));

function base(title, sub) {
  const s = pres.addSlide();
  s.background = { color: BG };
  T(s, title, { x: 0.375, y: 0.28, w: 9.25, h: 0.45, fontSize: 22, bold: true });
  if (sub) T(s, sub, { x: 0.375, y: 0.74, w: 9.25, h: 0.3, fontSize: 12, color: INK2 });
  return s;
}
function bullets(s, items, o) {
  T(s, items.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < items.length - 1 } })),
    Object.assign({ fontSize: 14, paraSpaceAfter: 8 }, o));
}
function image(file, alt, notes) {
  const s = pres.addSlide();
  s.background = { color: BG };
  s.addImage({ path: `${D}/${file}`, x: 0, y: 0, w: 10, h: 5.625, altText: alt });
  s.addNotes(notes);
}

// 1. Title
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
  s.addNotes("Introduce the team. The question: can an LLM act as a pre-mortem reviewer, finding how a function or a system design will fail before it ships? We compare two ways of using it, Direct and Translate, on two scales: single functions (SP1) and system designs (SP2).");
}

// 2. Motivation
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
  s.addNotes("Open with the news. In July 2026 Coinkite disclosed that since March 2021 its Coldcard wallets had generated seed phrases from a predictable software fallback instead of the hardware random chip. Coinkite says it ran AI-assisted code review on that firmware weeks before the exploit and the review missed it; that is Coinkite's own account. It suspects the attackers used AI to find the bug first, but that is unproven. Reported losses vary widely by outlet and date, from about US$38M in the first wave to over US$114M. The lesson: an AI reviewer that silently says 'looks fine' is dangerous. Real failures are rare and deep, like DynamoDB's 35-step bug. So the assistant only helps if it gives concrete, checkable failures and stays quiet on correct code. That is the course question: direct LLM reasoning vs translating to a solver. Sources: Decrypt (decrypt.co/374766), Coinkite's entropy technical backgrounder (blog.coinkite.com/entropy-technical-backgrounder), Unchained (unchainedcrypto.com), Forbes 4 Aug 2026, Blockhead 3 Aug 2026, OECD AI Incidents Monitor.");
}

// 3. Method
image("method.png", "Direct vs Translate pipeline diagram",
  "Two approaches. Direct: the LLM reads the code or design and outputs the failure itself. Translate: the LLM writes a formal spec, a solver searches, errors go back for repair. Both are scored the same way: the witness only counts if it reproduces on the gold model. Research questions: which finds more valid witnesses as failures get harder to reach, and which raises more false alarms on correct inputs?");

// 4. SP1 formulation
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

// 5. SP2 formulation
{
  const s = base("SP2 formulation: a design as a STRIPS planning problem", "Does some order of events reach a violation?");
  bullets(s, [
    "Facts F: system state, e.g. (no-record o1)",
    "Actions A: events, including timeouts, retries, lost messages and crashes",
    "Initial state I: the design facts, e.g. (dedup-racy)",
    "Goal G: the violation, e.g. (charged-twice o1)",
    "SATPlan finds a shortest trace. GBFS + h_FF searches exhaustively and certifies \"safe\"",
    "Both arms get the event rules (actions). Translate: the LLM writes only the initial state",
  ], { x: 0.375, y: 1.25, w: 4.6, h: 3.9 });
  s.addImage({ path: `${D}/sp2_trace.png`, x: 5.25, y: 1.25, w: 4.375, h: 3.9, altText: "Shortest failure trace for payments-subtle-1: eight events ending in charged-twice" });
  s.addNotes("SP2 is classical planning. The planner controls every event, including failures, so a plan is a counterexample, not a course of action: planning used as model checking of a safety property. Walk through the payments trace: the retry passes the duplicate check because the record is written only after charging, so the card is charged twice.");
}

// 6. Guarantees and complexity
{
  const s = base("What the solvers guarantee, and what it costs", "Why a solver's answer can be trusted, and where it stops");
  const h = (t, c) => ({ text: t, options: { bold: true, color: c || INK, fill: { color: "EBEAE6" } } });
  const lab = t => ({ text: t, options: { bold: true } });
  const sup = (a, b, c) => ({ text: [{ text: a }, { text: b, options: { superscript: true } }, { text: c }] });
  const rows = [
    [h(""), h("SP1: Z3 on a CSP", BLUE), h("SP2: SATPlan + GBFS on STRIPS", ORANGE)],
    [lab("Encoding"), "Bounded symbolic execution: one formula for all paths, loops unrolled k times",
      "A variable per fact and action per step; effects, explanatory frame axioms, exactly one action per step"],
    [lab("Encoding is correct"), "Lemma 1: within the bounds, the formula returns what Python returns (tested on 25 random inputs per function)",
      "Lemma 2: these clauses equal the textbook successor-state axioms"],
    [lab("\"Failure found\" means"), "Theorem 1: every Z3 answer is an input that breaks the spec",
      "Theorem 2: satisfiable at horizon T iff a T-step trace reaches G; the first such T gives a shortest trace"],
    [lab("\"No failure\" means"), "Theorem 1: none within the input and loop bounds; otherwise \"undecided\"",
      "Theorem 3: GBFS exhausted every reachable state, so G is unreachable at this size"],
    [lab("Worst case"), "Finite CSP: NP-complete. Non-linear integers: Z3 can answer \"unknown\"",
      sup("PlanSAT: PSPACE-complete; each SATPlan call is NP-complete. Up to 2", "218", " states at size 8")],
  ];
  s.addTable(rows, { x: 0.375, y: 1.15, w: 9.25, colW: [1.6, 3.8, 3.85], fontFace: F, fontSize: 11, color: INK,
    border: { type: "solid", pt: 0.75, color: "E4E3DF" }, rowH: [0.3, 0.62, 0.62, 0.62, 0.46, 0.46], margin: 0.06, valign: "middle" });
  T(s, [{ text: "h" }, { text: "FF", options: { subscript: true } },
    { text: " only prunes dead ends, which is safe because ignoring deletes only adds behaviour (1.2× to 3.8× fewer states than BFS). Every witness is replayed on the real code or gold problem before it counts." }],
    { x: 0.375, y: 4.55, w: 9.25, h: 0.6, fontSize: 12 });
  s.addNotes("Why trust the solver? For SP1 we proved the encoding matches Python on every input within the loop bounds, so a Z3 answer is a real failing input, and unsatisfiable means no failure within those bounds. A finite CSP is NP-complete, and with non-linear arithmetic Z3 can answer unknown, which we score as undecided. For SP2, our SATPlan clauses are equivalent to the successor-state axioms, so the first satisfiable horizon gives a shortest failure trace. To certify safety, greedy best-first search visits every reachable state; the FF heuristic only prunes dead ends. Planning is PSPACE-complete, so this is where the tools can run out, as inventory shows later.");
}

// 7. Problem instances
{
  const s = base("Problem instances", "Built and labelled automatically, scored by exact replay on the gold model");
  const col = (x, head, big, lines, color) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.25, w: 4.5, h: 3.05, rectRadius: 0.08, fill: { color: CARD }, line: { color: CARD } });
    T(s, head, { x: x + 0.3, y: 1.45, w: 3.9, h: 0.3, fontSize: 14, bold: true, color });
    T(s, big, { x: x + 0.3, y: 1.8, w: 3.9, h: 0.7, fontSize: 40, bold: true });
    bullets(s, lines, { x: x + 0.3, y: 2.6, w: 3.9, h: 1.6, fontSize: 13, paraSpaceAfter: 5 });
  };
  col(0.375, "SP1: functions", "174", [
    "37 functions (27 base, 10 hard), renamed, docstrings rewritten",
    "115 bugs from 808 auto mutants + 42 hand-written, picked by rarity",
    "59 controls: 37 clean, 22 provably equivalent",
  ], BLUE);
  col(5.125, "SP2: designs", "162", [
    "60 main: 5 families × 3 variants (flawed, subtle, fixed) × 4 sizes",
    "+ 30 stress (17–27 events), 60 names hidden, 12 long (30–51 events)",
    "Gold labels from SATPlan and GBFS (inventory fixed, size 8: hand proof)",
  ], ORANGE);
  T(s, [{ text: "Models: ", options: { bold: true } }, { text: "Haiku 4.5, Sonnet 5.5, Opus 5.5 (Claude), Qwen 3.8 27B and Llama 3.1 8B (open-weight, SoCLaaS)" }],
    { x: 0.375, y: 4.55, w: 9.25, h: 0.5, fontSize: 13 });
  s.addNotes("SP1: 174 instances. Bugs are single-line mutants plus hand-written bugs, chosen to cover common through very rare triggers; controls include equivalent mutants that look buggy but are not. SP2: 60 main designs, plus stress, hidden-name and long-trace sets. Five models from small open-weight to frontier. Scoring is exact: a witness counts only if it replays on the gold model.");
}

// 8. Worked example
image("worked_example.png", "Worked example: leap-year bug with 399 instead of 400",
  "One mutated constant, 400 to 399. Only 7 of 36,000 inputs fail, so 1,000 random tests catch it 18% of the time. Opus Direct reasons its way to February 2000. Opus Translate writes the spec from the docstring and Z3 finds February 2400 in 0.01 s. Both are confirmed against the reference.");

// 9. Scoreboard
image("scoreboard.png", "Scoreboard heatmap of all models and arms",
  "Headline results. The 5.5 models and Qwen 27B are near-perfect on the sets they ran with zero false alarms. Haiku 4.5 is fine on functions but struggles on designs, especially false alarms with names hidden. Llama 8B fails everywhere: in Direct it fabricates, 45 of 59 false alarms on correct code.");

// 10. Harder failures
{
  const s = base("Harder failures do not hurt the strong models", "SP1: rarer triggering inputs. SP2: longer failure traces");
  s.addImage({ path: `${D}/hardness_panel.png`, x: 0.375, y: 1.2, w: 9.25, h: 3.4, altText: "Left: failures found vs rarity for random testing and LLM arms. Right: valid traces vs trace length for Sonnet, Opus and Haiku" });
  T(s, "Rarity defeats random testing (5% of very rare bugs at 100 inputs) far more than the LLMs. The 5.5 models stay perfect up to 51-event traces.", { x: 0.375, y: 4.8, w: 9.25, h: 0.5, fontSize: 14 });
  s.addNotes("RQ1. Random testing falls off as bugs get rarer; Direct finds all of them, Translate 29 of 32 very rare pairs (two bugs, so a hint). On designs, trace length from 6 to 51 events does not hurt Sonnet or Opus; Haiku stays near 80% with no length trend. This looks like recognition rather than search.");
}

// 11. False alarms
image("false_alarms.png", "Slope chart: false alarms Direct vs Translate",
  "RQ2. Translation helps weaker models: Haiku false alarms 12 to 7, and 19 to 9 with names hidden. The strong models stay at zero. Caveat on Llama: on the 20 correct main designs, Llama Translate said safe 16 times, raised 2 false alarms and gave no answer twice. Its problem files left out facts, so the planner found no violation; that is not better reasoning.");

// 12. Where Translate breaks
{
  const s = base("Where Translate breaks", "Translation moves the error into the specification, and the tools have limits");
  const card = (y, head, body) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.375, y, w: 4.6, h: 0.98, rectRadius: 0.08, fill: { color: CARD }, line: { color: CARD } });
    T(s, head, { x: 0.55, y: y + 0.12, w: 4.25, h: 0.3, fontSize: 14, bold: true });
    T(s, body, { x: 0.55, y: y + 0.42, w: 4.25, h: 0.5, fontSize: 12, color: INK2 });
  };
  card(1.25, "The spec copies the bug", "Haiku's spec reused the mutated leap() line, so Z3 found nothing");
  card(2.35, "The planner exploits slack", "Haiku's lock problem started a lease clock before anyone held the lock; the trace only works in its model");
  card(3.45, "The tools run out", "SP1: 3 timeouts, 5 Z3 unknowns. Inventory: 2.7M states at size 6, search capped at 8");
  s.addImage({ path: `${D}/inventory_panel.png`, x: 5.25, y: 1.25, w: 4.375, h: 3.18, altText: "States expanded to prove safety vs design size, inventory explodes, other designs flat" });
  T(s, "Llama could not write the formal language: its SP2 problem files left out about a third of the initial facts, and 70 of its 174 SP1 runs gave no usable spec.", { x: 0.375, y: 4.65, w: 9.25, h: 0.5, fontSize: 13 });
  s.addNotes("Translate is not free. Specs can inherit the bug, permissive problem files hand the planner shortcuts, and solvers time out. Certification is exhaustive search, and the symmetric inventory design explodes: 9k states at size 4, 2.7M at 6, and the search is capped at 8 (that label rests on a hand-proved invariant), where Translate is undecided while Sonnet and Opus Direct still answer correctly, without proof.");
}

// 13. Trade-offs
{
  const s = base("Direct vs Translate: trade-offs", "Evidence from both scales");
  const h = (t, c) => ({ text: t, options: { bold: true, color: c || INK, fill: { color: "EBEAE6" } } });
  const rows = [
    [h(""), h("Direct", BLUE), h("Translate", ORANGE)],
    ["Strong models", "≈ every failure, 0 false alarms", "≈ every failure, 0 false alarms"],
    ["Weaker models", "Misreads designs, fabricates", "About half the false alarms (Haiku)"],
    ["Proof of absence", "None", "Yes, with an audit trail (bounded, as translated)"],
    ["Needs", "The model (plus, in SP2, the same event rules)", "Solver, encoder, model fluent in the spec language"],
    ["Fails by", "Pattern-matching the wrong design", "Bad spec, loose problem file, timeouts"],
  ];
  s.addTable(rows, { x: 0.375, y: 1.2, w: 9.25, colW: [2.0, 3.4, 3.85], fontFace: F, fontSize: 12, color: INK,
    border: { type: "solid", pt: 0.75, color: "E4E3DF" }, rowH: 0.36, margin: 0.06, valign: "middle" });
  T(s, "Practical variations", { x: 0.375, y: 3.8, w: 9.25, h: 0.3, fontSize: 14, bold: true });
  bullets(s, [
    "Solver availability: our encoder covers integers, Booleans and lists only (no strings, floats, recursion)",
    "Open-weight model: Qwen 3.8 27B matches the 5.5 models on SP1 and the SP2 main set (the only sets it ran), so it can run locally",
    "Input type: hiding names pushed Haiku Direct false alarms from 60% to 95%; Translate held 45%",
  ], { x: 0.375, y: 4.12, w: 9.25, h: 1.2, fontSize: 12, paraSpaceAfter: 4 });
  s.addNotes("The brief asks for advantages and disadvantages. With strong models the two tie. Translate's unique value is certifying absence, but only for the problem as translated. Direct needs only the model, though in SP2 both arms got the same authored event rules. Practical points: solver coverage limits what Translate can check, an open-weight model is good enough here, and inputs without helpful names hurt Direct more. Beyond the course: random testing and fuzzing, model checkers like TLA+, symmetry reduction and inductive invariants.");
}

// 14. Conclusion
{
  const s = base("When to use which", "A maximum-expected-utility choice: cost of a false alarm vs cost of a miss");
  const box = (x, head, color, lines) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.25, w: 4.5, h: 2.0, rectRadius: 0.08, fill: { color: CARD }, line: { color: CARD } });
    T(s, head, { x: x + 0.3, y: 1.42, w: 3.9, h: 0.3, fontSize: 16, bold: true, color });
    bullets(s, lines, { x: x + 0.3, y: 1.85, w: 3.9, h: 1.35, fontSize: 13, paraSpaceAfter: 4 });
  };
  box(0.375, "Use Direct", BLUE, ["Strong model, small review", "Complete specification", "An answer without proof is fine"]);
  box(5.125, "Use Translate", ORANGE, ["Absence must be certified or audited", "Mid-tier model that misreads designs", "Always replay the witness"]);
  T(s, "Limitations", { x: 0.375, y: 3.5, w: 9.25, h: 0.3, fontSize: 14, bold: true });
  bullets(s, [
    "SP2 gives the failure mechanisms as named events; writing the event model is untested",
    "Bugs are mostly single-line mutants, docstrings are complete, benchmarks may be in training data",
    "Will this change? Direct keeps improving on small, recognisable problems; worst-case hardness and the missing certificate remain",
  ], { x: 0.375, y: 3.85, w: 9.25, h: 1.5, fontSize: 12, paraSpaceAfter: 4 });
  s.addNotes("Wrap up. Strong models nearly tie, consistent with recognising patterns rather than searching. Translation moves the error into the spec, so it only helps a model that writes the formal language well. Only the tools can certify absence, and that is exactly where they run out of budget. Then take questions.");
}

pres.writeFile({ fileName: `${D}/premortem_slides.pptx` }).then(f => console.log("wrote", f));
