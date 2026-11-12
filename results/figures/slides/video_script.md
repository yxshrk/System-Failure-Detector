# Pre-Mortems video script

Read this slide by slide while recording: Joshua presents slides 1 to 6, Hein 7 to 12 and Yash 13 to 18. The words are the deck's checked speaker notes on main (035d7e0), about 1,200 words, roughly 9 minutes 15 seconds at 130 words a minute.

## Who presents what

Each of you reads six slides, and the handovers come after slides 6 and 12. Swap blocks freely; the words do not change.

| Presenter | Slides | Steps | Words | Speaking time |
| --- | --- | --- | --- | --- |
| Joshua | 1 to 6 | Question | 316 | 2:26 |
| Hein | 7 to 12 | Formulation, Experiment | 427 | 3:17 |
| Yash | 13 to 18 | Results, Answer | 457 | 3:31 |
| All three | 18 | | 1,200 | 9:14 |

Times assume 130 words a minute. At 120 words a minute the total reaches 10:00, the limit, so keep a steady pace and do not pause long between slides.

## If the run-through goes past 9:30

Cut these five sentences in this order, rather than improvising: each repeats what is already on screen, so no claim is lost. All five save 46 words, bringing the total to 1,154 words (8:53 at 130 words a minute, 9:37 at 120).

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

How does Translate turn this into a solver problem? For SP1, we turn it into a constraint as you can see on the left. In practice, this is what it's going to look like: we have a buggy line of code. Our symbolic execution turns the code into one formula and then feed it to our solver Z3; the LLM also writes a similar requirement but from the docstring that correctly describes the desired behavior rather than from the buggy code. Z3 then solves the CSP which is where the condition is that these two disagree. This exact instance is then verified by the actual correct code.  

*Reading note: say "code and not requirement" as one phrase, then pause briefly before "is unsatisfiable".*

### Slide 8 · SP2 as a planning problem: a plan is a failure trace

*Starts at 3:02 · 82 words · On screen: the table on the left; the eight-step trace on the right, with steps 2 and 6 highlighted.*

Similarly, SP2 is modeled as a planning problem but our goal condition would be the condition where the design fails. Here's how translation is gonna work. We first have a gold model of states and actions; this will be fed to our solvers SATPlan and GBFS; we will definitely find a failure if it exists because best first search is complete within reasonable sizes. On the other hand, LLM will read the expected system behavior and will write out initial states based on its interpretation. This will then be compared with the results of our gold model to see if the LLM correctly spotted an error if it exists.  


### Slide 9 · What a solver's answer proves, and what it costs

*Starts at 3:40 · 84 words · On screen: the table row by row; do not read every cell.*

You may notice that our experiment depends on solvers working properly. How do we ensure that? For SP1 we ensure that the result from our formula and Z3 agrees with the verified python code and test it on 25 random inputs per function. For SP2, our planning problem is modeled exactly as in lecture; including successor-state axioms, so we know that it is decidable and the first satisfiable horizon gives a shortest trace. To certify safety, greedy best-first search also runs until its queue is empty.

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

*Starts at 5:43 · 59 words · On screen: the left panel (functions), then the right panel (designs).*

RQ1 first. Random testing falls off as bugs get rarer; Direct finds all of them, and Translate misses three of 32 very rare pairs, all from two bugs. On designs, trace length from 6 to 51 events does not hurt Sonnet or Opus, and Haiku stays near 80% with no length trend. This looks like recognition rather than search.

### Slide 14 · Translation cuts the mid-tier model's false alarms

*Starts at 6:10 · 98 words · On screen: Haiku's solid line in each panel, then the interval line under the chart.*

RQ2. On correct designs, translation helps the mid-tier model: Haiku's false alarms fall from 12 to 7 of 20, and from 19 to 9 with names hidden. Why? Sixteen of Haiku's Direct traces on the main set used an event from another design variant. It applies a familiar pattern to designs that rule it out. Writing the initial state forces it to commit to the actual facts. It still raises 7, yet finds 34 of 40 failures, so this is not silence. Llama's drop is silence: its problem files left out facts, so the planner found no violation.

### Slide 15 · Translate fails through its specification or its tools

*Starts at 6:55 · 89 words · On screen: the four table rows from top to bottom, then the inventory chart.*

SP3 asks how good the translations were. Sonnet and Opus wrote the exact initial state in all 90 main and stress designs, but translation can fail four ways. A specification can copy the bug. A permissive problem file hands the planner shortcuts. Llama cannot write the formal language. And the solver can run out: inventory needs 2.7 million states at size 6 and exceeds the budget from size 8, where Translate is undecided on the safe design. The standard remedies, symmetry reduction and inductive invariants, lie outside the course.

### Slide 16 · The answer in brief

*Starts at 7:36 · 55 words · On screen: the three numbered cards.*

Putting the results together. First, strong models nearly tie, consistent with recognising patterns rather than searching. Second, translation moves the error into the specification, so it helps only a model that writes the formal language reliably: Haiku yes, Llama no. Third, only the tools can certify no failure, and that is where they run out.

### Slide 17 · Trade-offs, and when to use which arm

*Starts at 8:02 · 76 words · On screen: the table, then the formula, then the two Haiku lines.*

So which arm should you use? Choosing is a maximum-expected-utility decision: weigh the cost of a false alarm against the cost of a miss. For Haiku with readable names, Translate is better on every term, so at these estimates it wins at any costs. With names hidden it finds slightly fewer failures but raises half the false alarms, so at an even mix, counting errors alone, it wins while a miss costs under ten false alarms.

### Slide 18 · Limitations, and will this change?

*Starts at 8:37 · 80 words · On screen: the four limitations, then the Will this change? card.*

Finally, what this does not show, and whether it will change. SP2 hands both arms the failure mechanisms as named events; writing the event model is untested. Functions were chosen to be encodable, which favours Translate. Most cells are at or near 100%, so we cannot rank the strongest models. Will this change? Direct will likely keep improving on small, recognisable problems, but worst-case hardness and the missing certificate remain. Bottom line: translation's value depends on the model. Thank you.

*End of the video, at about 9:14.*

## Before recording

- [ ] Record from `results/figures/slides/premortem_slides.pptx` on main (035d7e0), opened once in PowerPoint to check nothing shifted
- [ ] Do one timed run-through with all three of you; stop at 10:00 at the latest
- [ ] Record at 1080p or higher, so the 11 pt tables on slides 9 and 17 stay legible
- [ ] Put the video, `report/report.pdf` and the source code in Group19.zip
- [ ] Record the slide show, not the presenter view, so the speaker notes stay off screen
