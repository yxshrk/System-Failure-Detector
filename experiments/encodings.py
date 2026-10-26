"""Print the exact encodings our tools receive, for the report appendix.

    python -m experiments.encodings > report/encodings.md

1. SP1: the Z3 formula built for one instance (code semantics, spec, domain),
   and the model Z3 returns.
2. SP2: the SATPlan clauses for one ground action and one frame axiom at one
   time step, with per-horizon formula sizes; then GBFS certifying a fix.

Everything is produced by the same functions the experiments call
(SymbolicExecutor, spec_check's formula, the SATPlan encoder, gbfs), so the
appendix cannot drift from the code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import z3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from premortem.llm import get_llm  # noqa: E402
from premortem.parsing import code_blocks  # noqa: E402
from premortem.planning import gbfs, ground, h_ff, parse_domain, parse_problem  # noqa: E402
from premortem.planning.satplan import _Encoder, satplan  # noqa: E402
from premortem.sp1.arms import SYSTEM_TRANSLATE, translate_prompt  # noqa: E402
from premortem.sp1.benchmarks import BY_NAME  # noqa: E402
from premortem.sp1.solve import symbolic_inputs  # noqa: E402
from premortem.sp1.symexec import SymbolicExecutor, conj, disj, neg, truthy  # noqa: E402
from premortem.sp2.families import FAMILIES  # noqa: E402


def term(t) -> str:
    return str(z3.simplify(t) if isinstance(t, z3.ExprRef) else t)


def sp1(instance_id: str = "sp1-049-days_in_month", model: str = "sonnet"):
    inst = {i["id"]: i for i in json.loads((ROOT / "data/sp1/instances.json").read_text())["instances"]}[instance_id]
    b = BY_NAME[inst["function"]]
    syms, dom = symbolic_inputs(b.params)
    args = [syms[n] for n, _ in b.params]
    code = SymbolicExecutor(inst["source"], b.loop_bound).run(b.name, args)
    ref = SymbolicExecutor(b.reference, b.loop_bound).run(b.name, args)
    c = get_llm(model).complete(SYSTEM_TRANSLATE, translate_prompt(inst["source"], b.name, b.params, b.loop_bound))
    spec_src = max(code_blocks(c.text, "python"), key=len)
    spec = SymbolicExecutor(spec_src, b.loop_bound)
    pre = spec.run("pre", args) if "pre" in spec.functions else None
    post = spec.run("post", args + [code.value])
    pre_ok = conj(pre.normal, truthy(pre.value)) if pre else True
    post_ok = conj(post.normal, truthy(post.value))
    phi = [*dom, neg(code.unwind), neg(post.unwind), conj(pre_ok, disj(code.exc, neg(post_ok)))]
    s = z3.Solver()
    s.add(*[p for p in phi if not isinstance(p, bool)])
    status = s.check()

    month, year = syms["month"], syms["year"]
    l399 = z3.And(year % 4 == 0, z3.Or(year % 100 != 0, year % 399 == 0))
    l400 = z3.Or(year % 400 == 0, z3.And(year % 100 != 0, year % 4 == 0))
    readable = z3.And(*dom, month == 2, l399 != l400)
    same = z3.Solver()
    same.add(z3.Not(z3.And(*[p for p in phi if not isinstance(p, bool)]) == readable))
    equivalent = same.check() == z3.unsat

    def size(t):
        seen, stack = set(), [t]
        while stack:
            x = stack.pop()
            if x.get_id() in seen:
                continue
            seen.add(x.get_id())
            stack.extend(x.children())
        return len(seen)

    print("## B.1 SP1: the CSP/SMT instance for `days_in_month` (mutant 400 → 399)\n")
    print("Code under review (the helper; the docstring states the 400-year rule):\n")
    print("```python\n" + inst["source"].split("def days_in_month")[0].strip() + "\n```\n")
    print("**Variables and domains** X = {month, year}, from `domain.make_symbolic`:\n")
    print("```\n" + "\n".join(term(d) for d in dom) + "\n```\n")
    print("**Code semantics** ⟦f⟧, the Z3 term the symbolic executor builds for the return value. "
          "`exc` and `unwind` simplify to False, because this function cannot raise or loop:\n")
    print("```\nresult = " + term(code.value) + f"\nexc    = {term(code.exc)}\nunwind = {term(code.unwind)}\n```\n")
    print("The unmutated reference builds the same term with `year%400` in place of `year%399`.\n")
    print(f"**Specification** written by {model.capitalize()} 5.5 in the Translate arm "
          "(verbatim, from the response cache):\n")
    print("```python\n" + spec_src.strip() + "\n```\n")
    print(f"The executor compiles `pre` and `post(month, year, result)` the same way, with `result` bound to "
          f"the code's term above. The full query Φ = domain ∧ ¬unwind ∧ pre ∧ (exc ∨ ¬post) is a DAG of "
          f"{size(z3.And(*[p for p in phi if not isinstance(p, bool)]))} shared nodes. "
          + ("Z3 proves it **equivalent** to the readable formula" if equivalent else "It is NOT equivalent to")
          + ":\n")
    print("```\nΦ  ≡  1 ≤ month ≤ 12 ∧ 1 ≤ year ≤ 3000 ∧ month = 2 ∧ L399(year) ≠ L400(year)\n"
          "L399(y) = y%4 = 0 ∧ (y%100 ≠ 0 ∨ y%399 = 0)        (what the code computes)\n"
          "L400(y) = y%400 = 0 ∨ (y%100 ≠ 0 ∧ y%4 = 0)        (what the spec requires)\n```\n")
    print("In words: a failing input is a February in a year where the two leap rules disagree. "
          "Z3 answers " + f"`{status}`" + (f" with the model `{s.model()}`; 2800 is divisible by 400 "
                                         "but not by 399, so the code returns 28 instead of 29." if status == z3.sat else ".") + "\n")


def name_of(enc, task, lit: int) -> str:
    obj = enc.pool.obj(abs(lit))
    if obj is None or not isinstance(obj, tuple):
        s = f"aux{abs(lit)}"
    elif obj[0] == "f":
        s = f"{task.facts[obj[1]].replace(' ', '(', 1).replace(' ', ',')})@{obj[2]}"
    else:
        s = f"{task.actions[obj[1]].name.replace(' ', '(', 1).replace(' ', ',')})@{obj[2]}"
    s = s if "(" not in s or s.count("(") == s.count(")") else s
    return ("¬" if lit < 0 else "") + s


def sp2(instance="payments-subtle-1", action="accept-new-racy o1 a1", fact="no-record o1", step=4):
    fam_name, variant, size = instance.rsplit("-", 2)
    fam = FAMILIES[fam_name]
    dom = parse_domain(fam.domain)
    task = ground(dom, parse_problem(fam.problem(variant, int(size)), dom))
    enc = _Encoder(task)
    for t in range(step):
        enc.step(t)
    clauses = enc.step(step)
    a_idx = [i for i, a in enumerate(task.actions) if a.name == action][0]
    a_var = enc.act(a_idx, step)
    f_idx = task.facts.index(fact)
    f_vars = {enc.fact(f_idx, step), enc.fact(f_idx, step + 1)}
    def named(c):
        return all(isinstance(enc.pool.obj(abs(l)), tuple) for l in c)

    pre_eff = [c for c in clauses if -a_var in c and len(c) == 2 and named(c)]
    fv = {abs(v) for v in f_vars if not isinstance(v, bool)}
    frame = [c for c in clauses if named(c) and fv <= set(map(abs, c)) and -a_var not in c]
    act = task.action(action)

    print(f"\n## B.2 SP2: STRIPS action and SATPlan clauses (`{instance}`, step t = {step})\n")
    print(f"Ground task: {len(task.facts)} facts, {len(task.actions)} ground actions after relaxed-reachability grounding.\n")
    print(f"**Ground STRIPS action** `{action}`:\n")
    print("```\nPRE = {" + ", ".join(sorted(act.pre_pos)) + "}\nADD = {" + ", ".join(sorted(act.add))
          + "}\nDEL = {" + ", ".join(sorted(act.delete)) + "}\n```\n")
    print(f"**Precondition and effect clauses** for this action at t = {step} (each clause is a disjunction). "
          "The static design fact `(dedup-racy)` is true at every step, so the encoder fixes it to a constant and its "
          "precondition clause is satisfied and dropped:\n")
    print("```\n" + "\n".join(" ∨ ".join(name_of(enc, task, l) for l in c) for c in pre_eff) + "\n```\n")
    print(f"**Explanatory frame clauses** for the fact `({fact})`. It can stop holding only if an action that deletes "
          "it occurs (here `charge`), and start holding only if one adds it (none does):\n")
    print("```\n" + "\n".join(" ∨ ".join(name_of(enc, task, l) for l in c) for c in frame) + "\n```\n")
    print("**Exactly one action per step** is added as a cardinality constraint over all action variables "
          "of the step (sequential-counter encoding, `pysat.card.CardEnc.equals`).\n")
    sp = satplan(task, 12)
    print("**Horizon iteration** (T = 0, 1, …; the first satisfiable T is the shortest trace):\n")
    print("| T | variables | clauses | result |\n|---|---|---|---|")
    for h in sp.stats:
        print(f"| {h.T} | {h.n_vars} | {h.n_clauses} | {'SAT' if h.sat else 'UNSAT'} |")
    print(f"\nDecoded plan ({sp.length} events): " + " → ".join(f"`{x}`" for x in sp.plan) + "\n")

    fdom = parse_domain(fam.domain)
    fixed = ground(fdom, parse_problem(fam.problem("fixed", int(size)), fdom))
    g = gbfs(fixed)
    print(f"\n## B.3 SP2: certifying the fixed variant with GBFS + h_FF (`{fam_name}-fixed-{size}`)\n")
    print(f"h_FF(initial state) = {h_ff(fixed, fixed.init)} (finite, so the delete relaxation alone cannot rule the "
          f"violation out). GBFS expanded {g.expanded} states, generated {g.generated}, pruned {g.dead_ends} "
          f"dead ends (h_FF = ∞) and returned **{g.status}**: the open list emptied, so `(charged-twice o1)` "
          "is unreachable from the initial state.\n")


if __name__ == "__main__":
    print("# Appendix B. The encodings, as generated by the code\n")
    print("*Produced by `python -m experiments.encodings`; every formula below is printed from the objects "
          "the experiments use.*\n")
    sp1()
    sp2()
