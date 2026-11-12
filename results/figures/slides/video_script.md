# Pre-Mortems video script

Read this slide by slide while recording: Joshua presents slides 1 to 6, Hein 7 to 12 and Yash 13 to 18. The words are the deck's checked speaker notes, about 1,260 words, roughly 9:42 at 130 words a minute.

## Who presents what

Each of you reads six slides, and the handovers come after slides 6 and 12. Swap blocks freely; the words do not change.

| Presenter | Slides | Steps | Words | Speaking time |
| --- | --- | --- | --- | --- |
| Joshua | 1 to 6 | Question | 316 | 2:26 |
| Hein | 7 to 12 | Formulation, Experiment | 427 | 3:17 |
| Yash | 13 to 18 | Results, Answer | 517 | 3:59 |
| All three | 18 | | 1,260 | 9:42 |

Times assume 130 words a minute. At 120 words a minute the total is 10:30, against the 10:00 limit, so keep a steady pace and do not pause long between slides.

## If the run-through goes past 9:30

Cut these five sentences in this order, rather than improvising: each repeats what is already on screen, so no claim is lost. All five save 46 words, bringing the total to 1,214 words (9:20 at 130 words a minute, 10:07 at 120).

| Order | Slide | Presenter | Cut | Words saved |
| --- | --- | --- | --- | --- |
| 1 | 7 | Hein | "Here it finds February 2400." | 5 |
| 2 | 2 | Joshua | "Should it find the failure directly, or translate for a solver?" | 11 |
| 3 | 10 | Hein | "Our solvers supply the ground truth, so what Translate tests is the translation." | 13 |
| 4 | 9 | Hein | "and test it on 25 random inputs per function" (and the comma before it) | 9 |
| 5 | 18 | Yash | "Bottom line: translation's value depends on the model." | 8 |

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

### Slide 2 · The failures that matter are the ones review misses

*Starts at 0:26 · 69 words · On screen: the bullets on the left; point to the timeline as you mention the disclosure.*

In July 2026 Coinkite disclosed that since 2021 its Coldcard wallets had generated seed phrases from a predictable fallback; by its own account, an AI-assisted review missed it. Real failures are rare and deep, like DynamoDB's 35-step trace that passed every review. So an AI reviewer helps only if it gives a checkable witness and never invents failures. Should it find the failure directly, or translate for a solver?

### Slide 3 · Two tasks: how a function fails, and how a design fails

*Starts at 0:58 · 44 words · On screen: the two cards, SP1 on the left and SP2 on the right.*

To answer it, we need tasks whose answers can be checked. SP1 asks for an input that breaks a function's docstring; SP2 asks for an order of events that breaks a design's safety property. Either way, the answer is a witness anyone can replay.

### Slide 4 · Direct: the LLM answers itself. Translate: a solver searches

*Starts at 1:18 · 54 words · On screen: the diagram, Direct along the top and Translate along the bottom, both into the gold check.*

We find witnesses in two ways, which we call arms. Direct: the LLM finds the failure itself. Translate: the LLM writes the problem formally as a specification, a solver searches, and errors go back for repair. Both arms are scored the same way: a witness counts only if it replays on the gold reference.

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

*Starts at 5:43 · 75 words · On screen: the left panel (functions), then the right panel (designs); each line is labelled at its end.*

RQ1 asks whether harder-to-reach failures hurt either arm. On the left, random testing finds fewer bugs as they get rarer, because a rare bug needs a lucky input. Both arms keep finding them; Translate misses only a handful. On the right, longer traces don't hurt Sonnet or Opus, and Haiku stays near 80%. If the models were searching, harder failures would hurt them. They don't, which fits recognising a familiar bug pattern rather than searching.

### Slide 14 · Translation cuts the mid-tier model's false alarms

*Starts at 6:18 · 106 words · On screen: Haiku's solid line in each panel, then the interval line under the chart.*

RQ2 is about false alarms. On correct designs, translating cuts Haiku's false alarms from 12 to 7, and from 19 to 9 with names hidden. In Direct, Haiku matches a familiar failure pattern to a design that rules it out: 16 of its traces used an event from a different version of the design. In Translate it must write down this design's facts, and those facts decide which events the planner can use. Haiku's drop is a real gain: it still finds 34 of 40 real failures. Llama's is not: its problem files leave out facts, so the planner finds no violation even in flawed designs.

### Slide 15 · Translate fails through its specification or its tools

*Starts at 7:06 · 104 words · On screen: the four cards, then the inventory chart.*

SP3 asks how good the translations were. Where translation failed, it failed in four ways. First, the LLM writes the requirement; if it copies the buggy line from the code, code and requirement agree, so Z3 finds no failing input. Second, if the problem file allows things the real design doesn't, the planner finds a failure that exists only in that wrong problem. Third, a weak model can't write the formal language reliably. Fourth, proving a design safe means searching every reachable state; for inventory that explodes, and from size 8 we run out of budget. Fixes like symmetry reduction lie outside the course.

### Slide 16 · The answer in brief

*Starts at 7:54 · 71 words · On screen: the three numbered cards.*

So, the answer. One: with a strong model, both arms nearly tie, which fits recognising patterns, not searching. Two: translating doesn't remove errors, it moves them into the spec the LLM writes, so it helps only a model that writes the formal language well, like Haiku, not Llama. Three: only a solver can prove there's no failure, but that proof needs exhaustive search, and that's exactly where the tools run out.

### Slide 17 · Trade-offs, and when to use which arm

*Starts at 8:27 · 75 words · On screen: the two cards, then the formula, then the Haiku table.*

Choosing an arm is a maximum-expected-utility decision, as in the course: weigh what a false alarm costs against what a missed failure costs. For Haiku with readable names, Translate is better on every term, so at these estimates it wins whatever the costs. With names hidden, it finds two fewer failures but raises half the false alarms, so at an even mix it wins as long as a miss costs less than ten false alarms.

### Slide 18 · Limitations, and will this change?

*Starts at 9:02 · 86 words · On screen: the two columns, then the Will this change? card.*

Finally, the limits, and whether this will change. Both arms were given the failure mechanisms as named events, so writing the event model is untested. Functions were chosen to be encodable, which favours Translate, and most scores are at or near 100%, so we cannot rank the strongest models. Will this change? Direct will likely keep improving on small, recognisable problems, but it still cannot prove there is no failure, and the hardest searches stay hard. Bottom line: translation's value depends on the model. Thank you.

*End of the video, at about 9:42.*

## Before recording

- [ ] Record from `results/figures/slides/premortem_slides.pptx` on main, opened once in PowerPoint to check nothing shifted
- [ ] Do one timed run-through with all three of you; stop at 10:00 at the latest
- [ ] Record at 1080p or higher, so the 11 pt tables on slides 9 and 17 stay legible
- [ ] Put the video, `report/report.pdf` and the source code in Group19.zip
- [ ] Record the slide show, not the presenter view, so the speaker notes stay off screen
