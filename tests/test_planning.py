"""Tests for premortem.planning: parsing, grounding, validation, SATPlan, search."""

from __future__ import annotations

import re
import time

import pytest

from premortem.planning import (
    GroundAction,
    PDDLError,
    applicable,
    apply,
    astar,
    bfs,
    domain_to_pddl,
    gbfs,
    ground,
    h_add,
    h_ff,
    h_max,
    parse_domain,
    parse_plan,
    parse_problem,
    problem_to_pddl,
    satplan,
    validate_plan,
)

# ---------------------------------------------------------------------------
# Domains and problems
# ---------------------------------------------------------------------------

BLOCKS = """
; 4-operator blocksworld
(define (domain BlocksWorld)
  (:requirements :strips :typing :equality)
  (:types block)
  (:predicates (on ?x - block ?y - block) (ontable ?x - block) (clear ?x - block)
               (handempty) (holding ?x - block))
  (:action pick-up
    :parameters (?x - block)
    :precondition (and (clear ?x) (ontable ?x) (handempty))
    :effect (and (not (ontable ?x)) (not (clear ?x)) (not (handempty)) (holding ?x)))
  (:action put-down
    :parameters (?x - block)
    :precondition (holding ?x)
    :effect (and (not (holding ?x)) (clear ?x) (handempty) (ontable ?x)))
  (:action stack
    :parameters (?x - block ?y - block)
    :precondition (and (holding ?x) (clear ?y) (not (= ?x ?y)))
    :effect (and (not (holding ?x)) (not (clear ?y)) (clear ?x) (handempty) (on ?x ?y)))
  (:action unstack
    :parameters (?x - block ?y - block)
    :precondition (and (on ?x ?y) (clear ?x) (handempty))
    :effect (and (holding ?x) (clear ?y) (not (clear ?x)) (not (handempty)) (not (on ?x ?y)))))
"""

SUSSMAN = """
(define (problem sussman) (:domain blocksworld)
  (:objects a b c - block)
  (:init (on c a) (ontable a) (ontable b) (clear c) (clear b) (handempty))
  (:goal (and (on a b) (on b c))))
"""

TOWER4 = """
(define (problem reverse-tower) (:domain blocksworld)
  (:objects a b c d - block)
  (:init (on a b) (on b c) (on c d) (ontable d) (clear a) (handempty))
  (:goal (and (on d c) (on c b) (on b a))))
"""

GRIPPER = """
(define (domain gripper-strips)
  (:predicates (room ?r) (ball ?b) (gripper ?g) (at-robby ?r) (at ?b ?r) (free ?g) (carry ?o ?g))
  (:action move
    :parameters (?from ?to)
    :precondition (and (room ?from) (room ?to) (at-robby ?from))
    :effect (and (at-robby ?to) (not (at-robby ?from))))
  (:action pick
    :parameters (?obj ?room ?gripper)
    :precondition (and (ball ?obj) (room ?room) (gripper ?gripper)
                       (at ?obj ?room) (at-robby ?room) (free ?gripper))
    :effect (and (carry ?obj ?gripper) (not (at ?obj ?room)) (not (free ?gripper))))
  (:action drop
    :parameters (?obj ?room ?gripper)
    :precondition (and (ball ?obj) (room ?room) (gripper ?gripper)
                       (carry ?obj ?gripper) (at-robby ?room))
    :effect (and (at ?obj ?room) (free ?gripper) (not (carry ?obj ?gripper)))))
"""

GRIPPER3 = """
(define (problem gripper-3) (:domain gripper-strips)
  (:objects rooma roomb ball1 ball2 ball3 left right)
  (:init (room rooma) (room roomb) (ball ball1) (ball ball2) (ball ball3)
         (gripper left) (gripper right) (at-robby rooma) (free left) (free right)
         (at ball1 rooma) (at ball2 rooma) (at ball3 rooma))
  (:goal (and (at ball1 roomb) (at ball2 roomb) (at ball3 roomb))))
"""

# Blocks that can be sealed only while on the table and can never be lifted once
# sealed: (sealed a) & (on a b) is relaxed-reachable but really unreachable, and
# h_ff is finite everywhere, so GBFS must exhaust the state space to prove it.
SEALED = """
(define (domain sealed-blocks)
  (:requirements :strips :typing :negative-preconditions)
  (:types block)
  (:predicates (on ?x ?y - block) (ontable ?x - block) (clear ?x - block)
               (handempty) (holding ?x - block) (sealed ?x - block))
  (:action pick-up
    :parameters (?x - block)
    :precondition (and (clear ?x) (ontable ?x) (handempty) (not (sealed ?x)))
    :effect (and (not (ontable ?x)) (not (clear ?x)) (not (handempty)) (holding ?x)))
  (:action put-down
    :parameters (?x - block)
    :precondition (holding ?x)
    :effect (and (not (holding ?x)) (clear ?x) (handempty) (ontable ?x)))
  (:action stack
    :parameters (?x ?y - block)
    :precondition (and (holding ?x) (clear ?y))
    :effect (and (not (holding ?x)) (not (clear ?y)) (clear ?x) (handempty) (on ?x ?y)))
  (:action unstack
    :parameters (?x ?y - block)
    :precondition (and (on ?x ?y) (clear ?x) (handempty) (not (sealed ?x)))
    :effect (and (holding ?x) (clear ?y) (not (clear ?x)) (not (handempty)) (not (on ?x ?y))))
  (:action seal
    :parameters (?x - block)
    :precondition (and (ontable ?x) (clear ?x) (handempty))
    :effect (sealed ?x)))
"""

SEALED_PROBLEM = """
(define (problem sealed-3) (:domain sealed-blocks)
  (:objects a b c - block)
  (:init (ontable a) (ontable b) (ontable c) (clear a) (clear b) (clear c) (handempty))
  (:goal (and (sealed a) (on a b))))
"""

# Delete interaction only: one token, two consumers, both effects needed.
TOKEN = """
(define (domain one-token)
  (:requirements :strips)
  (:predicates (token) (a-done) (b-done))
  (:action use-a :parameters () :precondition (token) :effect (and (a-done) (not (token))))
  (:action use-b :parameters () :precondition (token) :effect (and (b-done) (not (token)))))
"""

TOKEN_PROBLEM = """
(define (problem both) (:domain one-token) (:init (token)) (:goal (and (a-done) (b-done))))
"""

PAYMENTS = """
; A client charges an order; the response may be dropped; the client times out
; and retries; without an idempotency key the server charges again.
(define (domain payments)
  (:requirements :strips :typing :negative-preconditions)
  (:types client order)
  (:predicates
    (idle ?c - client ?o - order)
    (request-in-flight ?c - client ?o - order)
    (response-in-flight ?c - client ?o - order)
    (waiting ?c - client ?o - order)
    (timed-out ?c - client ?o - order)
    (done ?c - client ?o - order)
    (charged ?o - order)
    (charged-twice ?o - order)
    (idem-key))
  (:action send-charge
    :parameters (?c - client ?o - order)
    :precondition (idle ?c ?o)
    :effect (and (request-in-flight ?c ?o) (waiting ?c ?o) (not (idle ?c ?o))))
  (:action server-charge
    :parameters (?c - client ?o - order)
    :precondition (and (request-in-flight ?c ?o) (not (charged ?o)))
    :effect (and (charged ?o) (response-in-flight ?c ?o) (not (request-in-flight ?c ?o))))
  (:action server-charge-again
    :parameters (?c - client ?o - order)
    :precondition (and (request-in-flight ?c ?o) (charged ?o) (not (idem-key)))
    :effect (and (charged-twice ?o) (response-in-flight ?c ?o) (not (request-in-flight ?c ?o))))
  (:action server-dedupe
    :parameters (?c - client ?o - order)
    :precondition (and (request-in-flight ?c ?o) (charged ?o) (idem-key))
    :effect (and (response-in-flight ?c ?o) (not (request-in-flight ?c ?o))))
  (:action drop-response
    :parameters (?c - client ?o - order)
    :precondition (response-in-flight ?c ?o)
    :effect (not (response-in-flight ?c ?o)))
  (:action receive-response
    :parameters (?c - client ?o - order)
    :precondition (and (response-in-flight ?c ?o) (waiting ?c ?o))
    :effect (and (done ?c ?o) (not (waiting ?c ?o)) (not (response-in-flight ?c ?o))))
  (:action timeout
    :parameters (?c - client ?o - order)
    :precondition (and (waiting ?c ?o) (not (request-in-flight ?c ?o)) (not (response-in-flight ?c ?o)))
    :effect (and (timed-out ?c ?o) (not (waiting ?c ?o))))
  (:action retry
    :parameters (?c - client ?o - order)
    :precondition (timed-out ?c ?o)
    :effect (and (request-in-flight ?c ?o) (waiting ?c ?o) (not (timed-out ?c ?o)))))
"""


def payments_problem(idem_key: bool, clients: int = 1, orders: int = 1) -> str:
    cs = [f"c{i}" for i in range(1, clients + 1)]
    os_ = [f"o{i}" for i in range(1, orders + 1)]
    init = " ".join(f"(idle {c} {o})" for c in cs for o in os_) + (" (idem-key)" if idem_key else "")
    return f"""
    (define (problem double-charge) (:domain payments)
      (:objects {' '.join(cs)} - client {' '.join(os_)} - order)
      (:init {init})
      (:goal (charged-twice o1)))
    """


DOUBLE_CHARGE_PLAN = [
    "send-charge c1 o1", "server-charge c1 o1", "drop-response c1 o1",
    "timeout c1 o1", "retry c1 o1", "server-charge-again c1 o1",
]

LOCKS = """
(define (domain locks)
  (:requirements :strips :typing)
  (:types client lock order)
  (:predicates (holds ?c - client ?l - lock) (free ?l - lock) (paid ?o - order))
  (:action acquire :parameters (?c - client ?l - lock)
    :precondition (free ?l) :effect (and (holds ?c ?l) (not (free ?l))))
  (:action release :parameters (?c - client ?l - lock)
    :precondition (holds ?c ?l) :effect (and (free ?l) (not (holds ?c ?l))))
  (:action pay :parameters (?c - client ?o - order)
    :precondition (and) :effect (paid ?o)))
"""


def locks_problem(init: str, goal: str = "(holds c1 l1)", domain: str = "locks") -> str:
    return f"""
    (define (problem lp) (:domain {domain})
      (:objects c1 c2 - client l1 - lock o1 - order)
      (:init {init})
      (:goal {goal}))
    """


def task_of(domain_text: str, problem_text: str):
    domain = parse_domain(domain_text)
    return ground(domain, parse_problem(problem_text, domain))


SOLVABLE = {
    "sussman": (BLOCKS, SUSSMAN),
    "tower4": (BLOCKS, TOWER4),
    "gripper3": (GRIPPER, GRIPPER3),
    "double-charge": (PAYMENTS, payments_problem(idem_key=False)),
    "double-charge-2x2": (PAYMENTS, payments_problem(idem_key=False, clients=2, orders=2)),
}
UNSOLVABLE = {
    "sealed": (SEALED, SEALED_PROBLEM),
    "token": (TOKEN, TOKEN_PROBLEM),
    "idem-key": (PAYMENTS, payments_problem(idem_key=True)),
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def test_parse_domain_basics():
    d = parse_domain(BLOCKS)
    assert d.name == "blocksworld"  # case-insensitive
    assert d.requirements == (":strips", ":typing", ":equality")
    assert d.types == {"block": "object"}
    assert set(d.actions) == {"pick-up", "put-down", "stack", "unstack"}
    stack = d.actions["stack"]
    assert stack.parameters == (("?x", "block"), ("?y", "block"))
    assert [str(a) for a in stack.pre_neg] == ["(= ?x ?y)"]
    assert parse_domain(SEALED).predicates["on"] == (("?x", "block"), ("?y", "block"))


def test_type_hierarchy_and_constants():
    dom = parse_domain("""
    (define (domain fleet)
      (:requirements :strips :typing)
      (:types truck car - vehicle location)
      (:constants depot - location)
      (:predicates (at ?v - vehicle ?l - location) (parked ?v - vehicle))
      (:action park :parameters (?v - vehicle)
        :precondition (at ?v depot) :effect (parked ?v)))
    """)
    assert dom.is_subtype("truck", "vehicle") and dom.is_subtype("truck", "object")
    assert not dom.is_subtype("vehicle", "truck")
    prob = parse_problem("""
    (define (problem f1) (:domain fleet)
      (:objects t1 - truck k1 - car home - location)
      (:init (at t1 depot) (at k1 home))
      (:goal (and (parked t1))))
    """, dom)
    task = ground(dom, prob)
    assert [a.name for a in task.actions] == ["park t1"]  # "park k1" is relaxed-unreachable
    assert bfs(task).plan == ["park t1"]


def test_problem_round_trip():
    for domain_text, problem_text in [*SOLVABLE.values(), *UNSOLVABLE.values(),
                                      (LOCKS, locks_problem("(free l1)"))]:
        domain = parse_domain(domain_text)
        problem = parse_problem(problem_text, domain)
        assert parse_problem(problem_to_pddl(problem), domain) == problem
        assert parse_domain(domain_to_pddl(domain)) == domain


@pytest.mark.parametrize("init, expected", [
    ("(free l1) (has-key c1)", "unknown predicate 'has-key' in :init (known: free, holds, paid)"),
    ("(free l1) (holds c1)", "predicate 'holds' expects 2 arguments, got 1 in (holds c1)"),
    ("(holds c3 l1)", "unknown object 'c3' in :init fact (holds c3 l1)"),
    ("(holds o1 l1)", "object 'o1' has type order but parameter ?c of predicate holds needs client"),
    ("(not (free l1))", "negative literal (not (free l1)) in :init"),
    ("(holds ?c l1)", "variable '?c' in :init fact (holds ?c l1)"),
])
def test_problem_errors_in_init(init, expected):
    with pytest.raises(PDDLError, match=re.escape(expected)):
        parse_problem(locks_problem(init), parse_domain(LOCKS))


def test_problem_errors_elsewhere():
    dom = parse_domain(LOCKS)
    cases = [
        (locks_problem("(free l1)", domain="lock"),
         "problem refers to domain 'lock' but the given domain is named 'locks'"),
        (locks_problem("(free l1)", goal="(and (holds c1 l1) (owns c1 l1))"), "unknown predicate 'owns' in :goal"),
        (locks_problem("(free l1)", goal="(not (holds c1 l1))"), "requires :negative-preconditions"),
        (locks_problem("(free l1)", goal="(or (holds c1 l1) (holds c2 l1))"), "unsupported construct 'or' in :goal"),
        ("(define (problem p) (:domain locks) (:objects c1 - clinet) (:init) (:goal (and)))",
         "unknown type 'clinet' for object 'c1' in :objects (known types: client, lock, object, order)"),
        ("(define (problem p) (:domain locks) (:init (free l1)) (:goal (and))",
         "unbalanced parentheses in the problem: 1 '(' never closed"),
    ]
    for text, expected in cases:
        with pytest.raises(PDDLError, match=re.escape(expected)):
            parse_problem(text, dom)


@pytest.mark.parametrize("edit, expected", [
    (("(holds ?c ?l) :effect", "(holds ?c ?k) :effect"),
     "unknown variable '?k' in (holds ?c ?k) (precondition of action release); parameters are: ?c, ?l"),
    (("(free ?l) :effect", "(not (holds ?c ?l)) :effect"),
     "negative precondition (not (holds ?c ?l)) in action acquire requires :negative-preconditions"),
    (("(free ?l - lock)", "(free ?l - lok)"), "unknown type 'lok' for ?l in declaration of predicate 'free'"),
    ((":strips :typing", ":strips :typing :adl"), "unsupported requirement ':adl'"),
    (("(free ?l) :effect", "(or (free ?l) (holds ?c ?l)) :effect"), "unsupported construct 'or'"),
    (("(and (holds ?c ?l) (not (free ?l)))", "(and (holds ?c) (not (free ?l)))"),
     "predicate 'holds' expects 2 arguments, got 1 in (holds ?c)"),
    (("(paid ?o)))", "(paid ?c)))"), "variable ?c has type client but parameter ?o of predicate paid needs order"),
])
def test_domain_errors(edit, expected):
    old, new = edit
    assert old in LOCKS
    with pytest.raises(PDDLError, match=re.escape(expected)):
        parse_domain(LOCKS.replace(old, new, 1))


# ---------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------

def test_grounding_prunes_with_static_facts():
    task = task_of(GRIPPER, GRIPPER3)
    # move: 2x2 rooms; pick/drop: 3 balls x 2 rooms x 2 grippers each.
    assert len(task.actions) == 4 + 12 + 12
    assert "pick ball1 rooma left" in {a.name for a in task.actions}
    assert all(not a.name.startswith("pick left") for a in task.actions)


def test_equality_and_add_after_delete():
    blocks = task_of(BLOCKS, SUSSMAN)
    assert blocks.action("stack a a") is None and blocks.action("stack a b") is not None
    move = task_of(GRIPPER, GRIPPER3).action("move rooma rooma")
    assert move is not None and "at-robby rooma" not in move.delete
    act = GroundAction("noop-ish", frozenset({"p"}), frozenset({"q"}), frozenset({"p", "r"}), frozenset())
    assert applicable(frozenset({"p"}), act) and not applicable(frozenset({"p", "q"}), act)
    assert apply(frozenset({"p", "s"}), act) == frozenset({"p", "r", "s"})


def test_grounding_scales_with_static_join():
    locs = [f"l{i}" for i in range(1, 21)]
    roads = " ".join(f"(road {a} {b}) (road {b} {a})" for a, b in zip(locs, locs[1:] + locs[:1]))
    cities = " ".join(f"(in-city {loc} c{i % 2})" for i, loc in enumerate(locs))
    domain = """
    (define (domain ring)
      (:requirements :strips :typing)
      (:types truck location city)
      (:predicates (at ?t - truck ?l - location) (road ?a ?b - location)
                   (in-city ?l - location ?c - city) (visited ?c - city))
      (:action drive :parameters (?t - truck ?from ?to - location ?c - city)
        :precondition (and (at ?t ?from) (road ?from ?to) (in-city ?to ?c))
        :effect (and (at ?t ?to) (not (at ?t ?from)) (visited ?c))))
    """
    problem = f"""
    (define (problem ring20) (:domain ring)
      (:objects t1 t2 t3 - truck {' '.join(locs)} - location c0 c1 - city)
      (:init (at t1 l1) (at t2 l5) (at t3 l9) {roads} {cities})
      (:goal (and (at t1 l11) (at t2 l15))))
    """
    start = time.perf_counter()
    task = task_of(domain, problem)
    assert time.perf_counter() - start < 2.0
    assert len(task.actions) == 3 * 40  # trucks x directed roads
    result = gbfs(task)
    assert result.status == "solved" and validate_plan(task, result.plan).valid


# ---------------------------------------------------------------------------
# Plan parsing and validation
# ---------------------------------------------------------------------------

def test_parse_plan_formats():
    text = """
    ; found by a planner
    1. (send-charge c1 o1)
    0: (SERVER-CHARGE c1 o1)
    drop-response(c1, o1)
    timeout(c1,o1)

    step 5: retry c1 o1
    (server-charge-again c1 o1) ; cost = 6 (unit cost)
    """
    assert parse_plan(text) == DOUBLE_CHARGE_PLAN
    assert parse_plan(["(pay c1 o1)", "pay c1 o1", "pay(c1, o1)", "Pay(C1,O1)", "", ("pay", "c1", "o1")]) \
        == ["pay c1 o1"] * 5
    assert parse_plan('["(pay c1 o1)", "retry(c1, o1)"]') == ["pay c1 o1", "retry c1 o1"]
    assert parse_plan("0.000: (pay c1 o1) [1.000]\n1.000: (retry c1 o1) [1.000]") == ["pay c1 o1", "retry c1 o1"]
    with pytest.raises(PDDLError, match="cannot parse plan line 2"):
        parse_plan("(pay c1 o1)\n(retry c1 o1")


def test_validate_reports_failing_step():
    task = task_of(PAYMENTS, payments_problem(idem_key=False))
    ok = validate_plan(task, DOUBLE_CHARGE_PLAN)
    assert ok.valid and ok.goal_reached_at == 6 and len(ok.states_visited) == 7

    early = validate_plan(task, ["send-charge c1 o1", "server-charge c1 o1", "retry c1 o1"])
    assert not early.valid and not early.executable and early.failed_step == 3
    assert early.message == "step 3 (retry c1 o1): precondition (timed-out c1 o1) is false"

    neg = validate_plan(task, ["(send-charge c1 o1)", "(timeout c1 o1)"])
    assert neg.failed_step == 2
    assert neg.message == "step 2 (timeout c1 o1): precondition (not (request-in-flight c1 o1)) is false"

    unknown = validate_plan(task, ["send-charge c1 o1", "refund c1 o1"])
    assert unknown.failed_step == 2
    assert "unknown action 'refund' (known action names: drop-response, receive-response, retry" in unknown.message

    short = validate_plan(task, DOUBLE_CHARGE_PLAN[:2])
    assert short.executable and not short.goal_reached and short.failed_step is None
    assert short.message == "plan executed but goal (charged-twice o1) not reached"

    trailing = validate_plan(task, DOUBLE_CHARGE_PLAN + ["drop-response c1 o1"])
    assert trailing.valid and trailing.goal_reached_at == 6 and len(trailing.plan) == 7

    broken_tail = validate_plan(task, DOUBLE_CHARGE_PLAN + ["retry c1 o1"])
    assert not broken_tail.valid and broken_tail.failed_step == 7 and broken_tail.goal_reached_at == 6
    assert "goal was already reached after step 6" in broken_tail.message


def test_validate_type_and_arity_errors():
    task = task_of(LOCKS, locks_problem("(free l1)"))
    bad_type = validate_plan(task, ["pay o1 o1"])
    assert bad_type.failed_step == 1
    assert "object 'o1' has type order but parameter ?c of action pay needs client" in bad_type.message
    assert "action 'acquire' expects 2 arguments" in validate_plan(task, ["acquire c1"]).message
    assert "unknown object 'c3'" in validate_plan(task, ["acquire c3 l1"]).message
    # Well-typed but statically inapplicable (pruned) actions are still explained.
    blocked = validate_plan(task, ["acquire c1 l1", "acquire c2 l1"])
    assert blocked.failed_step == 2 and blocked.goal_reached_at == 1
    assert blocked.message.startswith("step 2 (acquire c2 l1): precondition (free l1) is false")


# ---------------------------------------------------------------------------
# Planners
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", list(SOLVABLE))
def test_planners_agree_on_solvable(name):
    task = task_of(*SOLVABLE[name])
    shortest = bfs(task)
    assert shortest.status == "solved"
    sat = satplan(task, t_max=20)
    assert sat.status == "solved" and sat.length == len(shortest.plan)
    assert [s.sat for s in sat.stats] == [False] * sat.length + [True]
    greedy = gbfs(task)
    optimal = astar(task)
    assert greedy.status == "solved" and optimal.length == shortest.length
    for plan in (sat.plan, shortest.plan, greedy.plan, optimal.plan):
        assert validate_plan(task, plan).valid


def test_known_optimal_lengths():
    assert satplan(task_of(BLOCKS, SUSSMAN), 10).length == 6
    assert satplan(task_of(PAYMENTS, payments_problem(idem_key=False)), 10).plan == DOUBLE_CHARGE_PLAN
    assert bfs(task_of(GRIPPER, GRIPPER3)).length == 9


@pytest.mark.parametrize("name", list(UNSOLVABLE))
def test_planners_prove_unsolvable(name):
    task = task_of(*UNSOLVABLE[name])
    assert satplan(task, t_max=10).status == "no_plan_within_bound"
    exhaustive = bfs(task)
    greedy = gbfs(task)
    assert exhaustive.status == "unsolvable" and greedy.status == "unsolvable"
    assert astar(task).status == "unsolvable"


def test_gbfs_exhausts_relaxed_reachable_unsolvable():
    task = task_of(SEALED, SEALED_PROBLEM)
    assert h_ff(task, task.init) < float("inf")  # not detectable by the relaxation
    greedy, exhaustive = gbfs(task), bfs(task)
    assert greedy.dead_ends == 0 and greedy.expanded == exhaustive.expanded > 50


def test_double_charge_needs_missing_idempotency_key():
    vulnerable = task_of(PAYMENTS, payments_problem(idem_key=False))
    fixed = task_of(PAYMENTS, payments_problem(idem_key=True))
    assert gbfs(vulnerable).status == "solved"
    assert gbfs(fixed).status == "unsolvable"
    assert satplan(fixed, 10).status == "no_plan_within_bound"
    assert h_ff(fixed, fixed.init) == float("inf")


def test_heuristic_sanity():
    task = task_of(BLOCKS, SUSSMAN)
    hmax, hff, hadd = h_max(task, task.init), h_ff(task, task.init), h_add(task, task.init)
    assert 0 < hmax <= hff <= 6 and hmax <= hadd
    goal_state = validate_plan(task, satplan(task, 10).plan).states_visited[-1]
    assert h_ff(task, goal_state) == h_max(task, goal_state) == h_add(task, goal_state) == 0


def test_satplan_bounds_solvers_and_timeout():
    task = task_of(BLOCKS, SUSSMAN)
    assert satplan(task, t_max=5).status == "no_plan_within_bound"
    assert satplan(task, t_max=10, solver_name="g4").length == 6
    assert satplan(task, t_max=10, time_limit=0.0).status == "timeout"
    assert satplan(task, t_max=10, time_limit=30.0).length == 6


def test_search_limits_and_custom_heuristic():
    task = task_of(BLOCKS, TOWER4)
    assert gbfs(task, max_expansions=1).status == "limit"
    assert bfs(task, max_expansions=1).status == "limit"
    goal_count = gbfs(task, h=lambda t, state: len(t.goal_pos - state))
    assert goal_count.status == "solved" and validate_plan(task, goal_count.plan).valid
