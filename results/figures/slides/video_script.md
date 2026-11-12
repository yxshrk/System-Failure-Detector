# Pre-Mortems video script

Read this slide by slide while recording: Joshua presents slides 1 to 6, Hein 7 to 12 and Yash 13 to 18. The words are the deck's checked speaker notes, about 1,372 words, roughly 10:33 at 130 words a minute.

## Who presents what

Each of you reads six slides, and the handovers come after slides 6 and 12. Swap blocks freely; the words do not change.

| Presenter | Slides | Steps | Words | Speaking time |
| --- | --- | --- | --- | --- |
| Joshua | 1 to 6 | Question | 316 | 2:26 |
| Hein | 7 to 12 | Formulation, Experiment | 427 | 3:17 |
| Yash | 13 to 18 | Results, Answer | 629 | 4:50 |
| All three | 18 | | 1,372 | 10:33 |

Times assume 130 words a minute. At 120 words a minute the total is 11:26, against the 10:00 limit, so keep a steady pace and do not pause long between slides.

## If the run-through goes past 9:30

Make these cuts in this order, rather than improvising: each drops a point that is already on screen, so no claim is lost. All six save 80 words, bringing the total to 1,292 words (9:56 at 130 words a minute, 10:46 at 120).

| Order | Slide | Presenter | Cut | Words saved |
| --- | --- | --- | --- | --- |
| 1 | 7 | Hein | "Here it finds February 2400." | 5 |
| 2 | 2 | Joshua | "Should it find the failure directly, or translate for a solver?" | 11 |
| 3 | 10 | Hein | "Our solvers supply the ground truth, so what Translate tests is the translation." | 13 |
| 4 | 9 | Hein | "and test it on 25 random inputs per function" (and the comma before it) | 9 |
| 5 | 14 | Yash | "Llama's drop is not, because its problem files leave out facts, so the planner finds no violation in 29 of the 40 flawed designs." | 24 |
| 6 | 16 | Yash | Say the three points more briefly, after "So what is our answer?": "With a strong model, both arms nearly tie. Translating doesn't remove errors; it moves them into the spec the LLM writes. And only a solver can prove there is no failure, but that proof is exactly where the tools run out." | 18 |

## Saying the terms

Say these abbreviations, names and numbers the same way across all three parts.

| Written | Say it as |
| --- | --- |
| Z3 | "Z three" (the solver) |
| SATPlan | "sat plan" |
| SP1, SP2, SP3 | "S-P one", "S-P two", "S-P three" |
| RQ1, RQ2 | "R-Q one", "R-Q two" |
| LLM | "L-L-M" |
| Qwen | "chwen" |
| dedup-racy | "dee-dupe racy" |
| Coinkite, Coldcard | "coin kite", "cold card" |
| 5.5 models | "five point five models" |
| Llama | "lah-ma" |
| DynamoDB | "dynamo D-B" |
| 2000, 2400, 399 | "two thousand", "twenty-four hundred", "three ninety-nine" |

## Part 1 · Joshua · slides 1 to 6 · the question

### Slide 1 · AI Pre-Mortems

*Starts at 0:00 · 56 words · On screen: the title, the two sub-problems (SP1, SP2), and Direct against Translate.*

We're Group 19: Yash, Joshua and Hein. Our question: can an LLM act as a pre-mortem reviewer, finding how a function or a system design will fail before it ships? We compare two ways of using it, Direct and Translate, on functions and on designs. Our short answer: it depends on how strong the model is.

### Slide 2 · AI code reviews

*Starts at 0:26 · 69 words · On screen: the bullets on the left; point to the timeline as you mention the disclosure.*

In July 2026 Coinkite disclosed that since 2021 its Coldcard wallets had generated seed phrases from a predictable fallback; by its own account, an AI-assisted review missed it. Real failures are rare and deep, like DynamoDB's 35-step trace that passed every review. So an AI reviewer helps only if it gives a checkable witness and never invents failures. Should it find the failure directly, or translate for a solver?

### Slide 3 · Subproblems

*Starts at 0:58 · 44 words · On screen: the SP1 example on the left, then the SP2 example on the right; end on the two black result bars.*

Two kinds of review. For a function, the AI must find an input that breaks it: February 2000 gets 28 days, not 29. For a system design, an order of events that breaks it: here, a card charged twice. Either way, we replay it.

### Slide 4 · Direct vs Translate

*Starts at 1:18 · 54 words · On screen: the diagram, Direct along the top and Translate along the bottom, both into the check on the right.*

We compare two ways of using the AI, which we call arms. Direct: the AI finds the failure itself. Translate: the AI writes the problem down formally, and a solver then searches for the failure. Either way, we run the answer on the real code or design, and it counts only if it fails.

### Slide 5 · Two research questions, and one check

*Starts at 1:43 · 37 words · On screen: RQ1, RQ2 and SP3, top to bottom.*

With the arms defined, here is what we measure. RQ1 asks whether one arm finds more real failures, especially the hard-to-reach ones. RQ2 asks which arm invents failures that are not there. SP3 checks the translations themselves.

### Slide 6 · Worked example: a bug random testing misses

*Starts at 2:00 · 56 words · On screen: the highlighted 399 line, then the three cards from top to bottom.*

Here is one bug through both arms. One mutated constant, 400 to 399. Only 7 of 36,000 inputs fail, so 1,000 random tests catch it 18% of the time. Opus Direct answers February 2000. Opus Translate writes the spec from the docstring and Z3 finds February 2400 in 0.01 seconds. Both are confirmed against the reference.

*Hand over to Hein.*

## Part 2 · Hein · slides 7 to 12 · formulation and experiment

### Slide 7 · SP1 as a CSP: a solution is a failing input

*Starts at 2:26 · 78 words · On screen: the table on the left; the diagram on the right from top to bottom, ending at Satisfiable.*

How does Translate turn this into a solver problem? SP1 is constraint satisfaction: month and year are variables with finite domains, and the constraint is that the code's result breaks the requirement. Symbolic execution turns the code into one formula; the LLM writes the requirement from the docstring, and Z3 searches for an input where both hold. Here it finds February 2400. Underneath is entailment: the code meets its requirement exactly when code and not requirement is unsatisfiable.

*Reading note: say "code and not requirement" as one phrase, then pause briefly before "is unsatisfiable".*

### Slide 8 · SP2 as a planning problem: a plan is a failure trace

*Starts at 3:02 · 82 words · On screen: the table on the left; the eight-step trace on the right, with steps 2 and 6 highlighted.*

SP2 is classical planning: facts are the state, actions are events including failures, the initial state encodes the design, and the goal is the violation. The planner chooses every event, so a plan is a counterexample: planning as model checking. Here the retry passes the duplicate check because the record is written only after charging. Both arms are given these actions; in Translate the model writes only the initial state. Names like dedup-racy give the mechanism away, so one set replaces them.

### Slide 9 · What a solver's answer proves, and what it costs

*Starts at 3:40 · 84 words · On screen: the table row by row; do not read every cell.*

Why should we trust a solver's answer? For SP1 we show the encoding matches Python on every input within the loop bounds, and test it on 25 random inputs per function. So every Z3 answer is an input that breaks the spec, and unsatisfiable means no input within those bounds breaks it. For SP2, our SATPlan clauses are equivalent to the successor-state axioms, so the first satisfiable horizon gives a shortest trace. To certify safety, greedy best-first search runs until its queue is empty.

### Slide 10 · Problem instances, each with a known answer

*Starts at 4:18 · 65 words · On screen: the two cards, functions then designs.*

Now the experiment, starting with what we tested. SP1 has 174 instances from 37 functions: bugs from common to very rare triggers, plus controls, including equivalent mutants that look buggy but are not. SP2 has five services, each flawed, subtle or fixed; size scales a timer or capacity, so failures get longer. Our solvers supply the ground truth, so what Translate tests is the translation.

### Slide 11 · Method: five models, the same inputs, exact scoring

*Starts at 4:48 · 54 words · On screen: the tier table, then the four bullets.*

Then how we ran it. Five models in three tiers: strong, mid-tier Haiku, and weak Llama. Direct runs with all tools disabled, so it must reason rather than execute. Translate gets up to two repairs. Every answer gets exactly one label, and a tool that runs out of budget is undecided, never no failure.

*Reading note: stress the two labels, "undecided" and "no failure".*

### Slide 12 · Strong models are near-perfect; Haiku and Llama are not

*Starts at 5:13 · 64 words · On screen: the scoreboard, strong models at the top, Haiku in the middle, Llama at the bottom.*

Now the results, first at a glance. The 5.5 models and Qwen are near-perfect on the sets they ran, with zero false alarms; Qwen's three invalid traces in Direct were format slips, not misreadings. Haiku is fine on functions but struggles on designs, especially false alarms with names hidden. Llama fails everywhere: in Direct it fabricates, with 45 false alarms on 59 correct functions.

*Hand over to Yash.*

## Part 3 · Yash · slides 13 to 18 · results and answer

### Slide 13 · Strong models find nearly every failure, even the hardest

*Starts at 5:43 · 101 words · On screen: the left panel (functions), then the right panel (designs); each line is labelled at its end.*

RQ1 asked whether harder-to-reach failures hurt either arm. On the left, random testing finds fewer bugs as they get rarer, because a rare bug needs a lucky input, yet both arms keep finding them. On the right, longer traces don't hurt Sonnet or Opus, and Haiku stays near 80%. That matters, because a search has to explore more states as traces get longer. But while the traces got several times longer, the answers from Sonnet and Opus grew by only about a quarter. That fits recognising a familiar bug pattern rather than searching, though we did not measure how they reasoned.

### Slide 14 · Translation cuts the mid-tier model's false alarms

*Starts at 6:30 · 137 words · On screen: Haiku's solid line in each panel, then the two lines under the chart.*

So the strong models find the failures. RQ2 asks the opposite: which arm invents failures that aren't there? On correct designs, translating cuts Haiku's false alarms from 12 to 7 of 20. Why? In Direct, Haiku recognises a famous failure, like the double charge on a retry, and reports it even when this design prevents it. In Translate, it must first write down this design's facts. Every event is a planning action with preconditions. So if the facts say this design prevents an event, the planner can never use it, and the false failure cannot be built. And the drop is a real gain, because Haiku still finds 34 of 40 real failures. Llama's drop is not, because its problem files leave out facts, so the planner finds no violation in 29 of the 40 flawed designs.

### Slide 15 · Translate fails through its specification or its tools

*Starts at 7:33 · 110 words · On screen: the four cards, then the inventory chart.*

Translating helps Haiku, but it can also fail, and SP3 asks how. We saw four ways. First, if the LLM copies the buggy line into the requirement, code and requirement agree, so Z3 finds no failing input. Second, if the problem file allows things the real design doesn't, the planner finds a failure that exists only in that wrong problem. Third, a weak model can't write the formal language reliably, so the solver often gets no usable spec. Fourth, to prove a design safe, the planner must rule out every route to a violation. For inventory that means millions of states, so from size 8 it runs out of budget.

### Slide 16 · The answer in brief

*Starts at 8:24 · 64 words · On screen: the three numbered cards.*

So what is our answer? One: with a strong model, both arms nearly tie. Two: translating doesn't remove errors; it moves them into the spec the LLM writes, so it helps only a model that writes the formal language well. Three: only a solver can prove there is no failure, but that proof needs exhaustive search, which is exactly where the tools run out.

### Slide 17 · Trade-offs, and when to use which arm

*Starts at 8:53 · 129 words · On screen: the two cards, then the formula, then the Haiku table.*

So which arm should you use? As in the course, this is a maximum-expected-utility choice: pick the arm whose mistakes cost less on average. Take Haiku. With readable names, Translate makes fewer mistakes of both kinds and is cheaper to run, so it wins outright. With names hidden, it's a trade-off. Out of 20 correct designs, Translate raises 9 false alarms instead of 19, so it saves 10. Out of 40 flawed designs, it finds 25 failures instead of 27, so it misses 1 more for every 20. So picture a review of 20 correct and 20 flawed designs: Translate would save ten false alarms but miss one more failure. Ignoring running costs, that makes Translate the better choice unless one missed failure is worse than ten false alarms.

### Slide 18 · Limitations, and will this change?

*Starts at 9:53 · 88 words · On screen: the two columns, then the Will this change? card.*

Finally, how far can you trust this answer? Both arms were given the failure mechanisms as named events, so we have not tested a model writing the event model itself. We also chose functions that can be encoded, which favours Translate. Will the answer change? Direct will likely keep improving on small, recognisable problems. But it still cannot prove there is no failure, and for the solvers, search can still take exponential time in the worst case. So the value of translating depends on the model. Thank you.

*End of the video, at about 10:33.*

## Before recording

- [ ] Record from `results/figures/slides/premortem_slides.pptx` on main, opened once in PowerPoint to check nothing shifted
- [ ] Do one timed run-through with all three of you; stop at 10:00 at the latest
- [ ] Record at 1080p or higher, so the 11 pt tables on slides 9 and 17 stay legible
- [ ] Put the video, `report/report.pdf` and the source code in Group19.zip
- [ ] Record the slide show, not the presenter view, so the speaker notes stay off screen
