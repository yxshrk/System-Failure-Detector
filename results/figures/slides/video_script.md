# Pre-Mortems video script

Read this slide by slide while recording: Joshua presents slides 1 to 5, Hein 6 to 11 and Yash 12 to 17. The words are the deck's checked speaker notes, about 1,375 words, roughly 10:35 at 130 words a minute.

## Who presents what

Joshua reads five slides and Hein and Yash six each; the handovers come after slides 5 and 11. Swap blocks freely; the words do not change.

| Presenter | Slides | Steps | Words | Speaking time |
| --- | --- | --- | --- | --- |
| Joshua | 1 to 5 | Question | 301 | 2:19 |
| Hein | 6 to 11 | Formulation, Experiment | 445 | 3:25 |
| Yash | 12 to 17 | Results, Answer | 629 | 4:50 |
| All three | 17 | | 1,375 | 10:35 |

Times assume 130 words a minute. At 120 words a minute the total is 11:28, against the 10:00 limit, so keep a steady pace and do not pause long between slides.

## If the run-through goes past 9:30

Make these cuts in this order, rather than improvising: each drops a point that is already on screen, so no claim is lost. All five save 69 words, bringing the total to 1,306 words (10:03 at 130 words a minute, 10:53 at 120).

| Order | Slide | Presenter | Cut | Words saved |
| --- | --- | --- | --- | --- |
| 1 | 6 | Hein | "Here it finds February 2400." | 5 |
| 2 | 9 | Hein | "Our solvers supply the ground truth, so what Translate tests is the translation." | 13 |
| 3 | 8 | Hein | "and test it on 25 random inputs per function" (and the comma before it) | 9 |
| 4 | 13 | Yash | "Llama's drop is not, because its problem files leave out facts, so the planner finds no violation in 29 of the 40 flawed designs." | 24 |
| 5 | 15 | Yash | Say the three points more briefly, after "So what is our answer?": "With a strong model, both arms nearly tie. Translating doesn't remove errors; it moves them into the spec the LLM writes. And only a solver can prove there is no failure, but that proof is exactly where the tools run out." | 18 |

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

## Part 1 · Joshua · slides 1 to 5 · the question

### Slide 1 · AI Pre-Mortems

*Starts at 0:00 · 51 words · On screen: the title, the two sub-problems (SP1, SP2), and Direct against Translate.*

We're Group 19, comprising myself, Yash and Colin. Our project asks: can an AI review code and system designs, and tell us how they will break before they ship? We tested two ways of using the AI, Direct and Translate, on two kinds of problems, from Python functions to system designs.

### Slide 2 · AI code reviews

*Starts at 0:24 · 66 words · On screen: the bullets on the left; point to the timeline as you mention the disclosure.*

So this is what motivated this project. A while back, Coinkite, the maker of Coldcard bitcoin wallets, was hit by an attack that stole over 100 million dollars in bitcoin. In their own internal investigation, Coinkite said its AI-assisted security reviews had failed to flag the bug beforehand. From this catastrophe, we can see how important it is to create accurate AI reviews in today's age.

### Slide 3 · Subproblems

*Starts at 0:54 · 54 words · On screen: the SP1 code on the left, then the SP2 description on the right.*

We broke down the problem into two sub-problems. First, SP1, a function: given Python code, the AI tries to find an input where the output is wrong. For SP2, a system design, the AI tries to find a sequence of events that causes an error, such as a retry that charges a card twice.

### Slide 4 · Direct vs Translate

*Starts at 1:19 · 81 words · On screen: the diagram, Direct along the top and Translate along the bottom, both into the check on the right.*

There were two ways that we compared using the AI. The first way, Direct, we just got the AI to read the code and actually point out the failure itself. In the second way, Translate, the AI actually writes the problem down formally, and then a separate solver searches for this failure. Either way, we run the failing case it found on the real code or design, and this helps us decide whether the failure was real or a made-up one.

### Slide 5 · Research questions

*Starts at 1:56 · 49 words · On screen: RQ1, RQ2 and SP3, top to bottom.*

To help us solve the project's problem, we broke it down into two research questions. Which approach finds more real failures, especially the hard-to-find ones? And which one makes up failures that aren't there? And we added one more sub-problem for Translate: how accurate are the AI's formal write-ups?

*Hand over to Hein.*

## Part 2 · Hein · slides 6 to 11 · formulation and experiment

### Slide 6 · SP1 as a CSP: a solution is a failing input

*Starts at 2:19 · 96 words · On screen: the table on the left; the diagram on the right from top to bottom, ending at Satisfiable.*

How does Translate turn the leap-year bug into a solver problem? Random testing catches it only 18% of the time, since just 7 of 36,000 inputs fail. For SP1, we turn it into a constraint as you can see on the left. In practice, this is what it's going to look like: we have a buggy line of code. Our symbolic execution turns the code into one formula and then feed it to our solver Z3; the LLM also writes a similar requirement but from the docstring that correctly describes the desired behavior rather than from the buggy code. Z3 then solves the CSP which is where the condition is that these two disagree. This exact instance is then verified by the actual correct code.  

*Reading note: say "code and not requirement" as one phrase, then pause briefly before "is unsatisfiable".*

### Slide 7 · SP2 as a planning problem: a plan is a failure trace

*Starts at 3:03 · 82 words · On screen: the table on the left; the eight-step trace on the right, with steps 2 and 6 highlighted.*

Similarly, SP2 is modeled as a planning problem but our goal condition would be the condition where the design fails. Here's how translation is gonna work. We first have a gold model of states and actions; this will be fed to our solvers SATPlan and GBFS; we will definitely find a failure if it exists because best first search is complete within reasonable sizes. On the other hand, LLM will read the expected system behavior and will write out initial states based on its interpretation. This will also be fed to the solver to find if a path to failure exists. LLM results will then be compared with the results of our gold model to see if the LLM correctly spot an error if it exists.  


### Slide 8 · What a solver's answer proves, and what it costs

*Starts at 3:41 · 84 words · On screen: the table row by row; do not read every cell.*

You may notice that our experiment depends on solvers working properly. How do we make sure? For SP1 we ensure that the result from our formula and Z3 agrees with the verified python code and test it on 25 random inputs per function. For SP2, our planning problem is modeled exactly as in lecture; including successor-state axioms, so we know that it is decidable and the first satisfiable horizon gives a shortest trace. To certify safety, greedy best-first search also runs until its queue is empty.

### Slide 9 · Problem instances, each with a known answer

*Starts at 4:20 · 65 words · On screen: the two cards, functions then designs.*

Now the experiment, here's what we tested. SP1 has 174 instances from 37 functions: bugs range from common to very rare triggers; we also have controls that are actually correct, including equivalent mutants that look buggy but are not. SP2 has five design scenarios, each flawed, subtle or fixed versions; we also have a variation in length for how many steps it takes to reach a failure goal. One thing to note is that our solvers supply the ground truth correctly, so in translate, whether LLM gets it right or wrong hinges entirely on how well it could translate.

### Slide 10 · Method: five models, the same inputs, exact scoring

*Starts at 4:50 · 54 words · On screen: the tier table, then the four bullets.*

And here's how we ran it. Five models in three tiers: strong, mid-tier Haiku, and weak Llama. Direct runs with all tools disabled, so it must reason rather than execute. For translation, our LLMs can refine their work up to 2 times. Every test instance gets exactly one label. For our labels, undecided happens when a tool overan its reasonble resource constraints.

*Reading note: stress the two labels, "undecided" and "no failure".*

### Slide 11 · Strong models are near-perfect; Haiku and Llama are not

*Starts at 5:15 · 64 words · On screen: the scoreboard, strong models at the top, Haiku in the middle, Llama at the bottom.*

Now the results, first at a glance. The 5.5 models and Qwen are near-perfect on the sets they ran, with zero false alarms; Qwen's had three invalid traces in Direct but they were formatting slips, and not misreadings. Haiku is fine on SP1 functions but struggles on SP2 designs; it is particularly prone to false alarms when the test names are covered to stop giving hints. Llama fails everywhere: in Direct it fabricates, with 45 false alarms on 59 correct functions; and its translation is also poor. 

*Hand over to Yash.*

## Part 3 · Yash · slides 12 to 17 · results and answer

### Slide 12 · Strong models find nearly every failure, even the hardest

*Starts at 5:44 · 101 words · On screen: the left panel (functions), then the right panel (designs); each line is labelled at its end.*

RQ1 asked whether harder-to-reach failures hurt either arm. On the left, random testing finds fewer bugs as they get rarer, because a rare bug needs a lucky input, yet both arms keep finding them. On the right, longer traces don't hurt Sonnet or Opus, and Haiku stays near 80%. That matters, because a search has to explore more states as traces get longer. But while the traces got several times longer, the answers from Sonnet and Opus grew by only about a quarter. That fits recognising a familiar bug pattern rather than searching, though we did not measure how they reasoned.

### Slide 13 · Translation cuts the mid-tier model's false alarms

*Starts at 6:31 · 137 words · On screen: Haiku's solid line in each panel, then the two lines under the chart.*

So the strong models find the failures. RQ2 asks the opposite: which arm invents failures that aren't there? On correct designs, translating cuts Haiku's false alarms from 12 to 7 of 20. Why? In Direct, Haiku recognises a famous failure, like the double charge on a retry, and reports it even when this design prevents it. In Translate, it must first write down this design's facts. Every event is a planning action with preconditions. So if the facts say this design prevents an event, the planner can never use it, and the false failure cannot be built. And the drop is a real gain, because Haiku still finds 34 of 40 real failures. Llama's drop is not, because its problem files leave out facts, so the planner finds no violation in 29 of the 40 flawed designs.

### Slide 14 · Translate fails through its specification or its tools

*Starts at 7:34 · 110 words · On screen: the four cards, then the inventory chart.*

Translating helps Haiku, but it can also fail, and SP3 asks how. We saw four ways. First, if the LLM copies the buggy line into the requirement, code and requirement agree, so Z3 finds no failing input. Second, if the problem file allows things the real design doesn't, the planner finds a failure that exists only in that wrong problem. Third, a weak model can't write the formal language reliably, so the solver often gets no usable spec. Fourth, to prove a design safe, the planner must rule out every route to a violation. For inventory that means millions of states, so from size 8 it runs out of budget.

### Slide 15 · The answer in brief

*Starts at 8:25 · 64 words · On screen: the three numbered cards.*

So what is our answer? One: with a strong model, both arms nearly tie. Two: translating doesn't remove errors; it moves them into the spec the LLM writes, so it helps only a model that writes the formal language well. Three: only a solver can prove there is no failure, but that proof needs exhaustive search, which is exactly where the tools run out.

### Slide 16 · Trade-offs, and when to use which arm

*Starts at 8:54 · 129 words · On screen: the two cards, then the formula, then the Haiku table.*

So which arm should you use? As in the course, this is a maximum-expected-utility choice: pick the arm whose mistakes cost less on average. Take Haiku. With readable names, Translate makes fewer mistakes of both kinds and is cheaper to run, so it wins outright. With names hidden, it's a trade-off. Out of 20 correct designs, Translate raises 9 false alarms instead of 19, so it saves 10. Out of 40 flawed designs, it finds 25 failures instead of 27, so it misses 1 more for every 20. So picture a review of 20 correct and 20 flawed designs: Translate would save ten false alarms but miss one more failure. Ignoring running costs, that makes Translate the better choice unless one missed failure is worse than ten false alarms.

### Slide 17 · Limitations, and will this change?

*Starts at 9:54 · 88 words · On screen: the two columns, then the Will this change? card.*

Finally, how far can you trust this answer? Both arms were given the failure mechanisms as named events, so we have not tested a model writing the event model itself. We also chose functions that can be encoded, which favours Translate. Will the answer change? Direct will likely keep improving on small, recognisable problems. But it still cannot prove there is no failure, and for the solvers, search can still take exponential time in the worst case. So the value of translating depends on the model. Thank you.

*End of the video, at about 10:35.*

## Before recording

- [ ] Record from `results/figures/slides/premortem_slides.pptx` on main, opened once in PowerPoint to check nothing shifted
- [ ] Do one timed run-through with all three of you; stop at 10:00 at the latest
- [ ] Record at 1080p or higher, so the 11 pt tables on slides 8 and 16 stay legible
- [ ] Put the video, `report/report.pdf` and the source code in Group19.zip
- [ ] Record the slide show, not the presenter view, so the speaker notes stay off screen
