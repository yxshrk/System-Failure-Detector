"""SP2 design families.

Each family is one STRIPS domain (the event vocabulary: client, server,
network, timer and crash events) plus a generator for problem instances and
the natural-language design document that describes them. Variants differ
*only* in initial-state design facts (e.g. ``(dedup-racy)``), as in the
proposal:

    flawed  -- the obvious design, violation reachable;
    subtle  -- a mitigation that looks right but still admits the violation;
    fixed   -- a correct mitigation (violation unreachable).

In every fixed variant the violating action stays reachable in the
delete-relaxation (h_FF is finite at the initial state), so proving the fix
correct requires the exhaustive forward search, not a static check.

``size`` (1..4) scales a timer or capacity in the design, which lengthens the
shortest failure trace.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

VARIANTS = ("flawed", "subtle", "fixed")
SIZES = (1, 2, 3, 4)
STRESS_SIZES = (6, 8)


@dataclass(frozen=True)
class Family:
    name: str
    domain: str
    goal: str
    question: str
    design_facts: dict[str, tuple[str, ...]]  # variant -> design facts in :init
    knob: Callable[[int], int]
    problem: Callable[[str, int], str]
    design: Callable[[str, int], str]
    naming: Callable[[str, int], str]


def _chain(prefix: str, n: int, pred: str) -> list[str]:
    return [f"({pred} {prefix}{i} {prefix}{i + 1})" for i in range(n)]


def _objs(prefix: str, n: int) -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def _problem(name: str, domain: str, objects: str, init: list[str], goal: str) -> str:
    body = "\n    ".join(init)
    return (f"(define (problem {name})\n  (:domain {domain})\n  (:objects {objects})\n"
            f"  (:init\n    {body})\n  (:goal {goal}))\n")


# ---------------------------------------------------------------------------
# 1. Payments: client retries + provider idempotency keys
# ---------------------------------------------------------------------------

PAYMENTS_DOMAIN = """\
(define (domain payments)
  (:requirements :strips :typing)
  (:types order attempt tick)
  (:predicates
    ;; --- design facts: exactly one deduplication mode holds ---
    (dedup-none)     ; the provider does not deduplicate requests
    (dedup-atomic)   ; the provider looks up and reserves the idempotency key in one atomic step
    (dedup-racy)     ; the provider looks up the key, but only records it after the charge succeeds
    ;; --- static counters ---
    (next-attempt ?a ?b - attempt)   ; attempt ?b is the retry that follows attempt ?a
    (next-tick ?t ?u - tick)         ; timer value ?u follows ?t
    (first-tick ?t - tick)           ; timer value right after a request is sent
    (timeout-tick ?t - tick)         ; timer value at which the client gives up waiting
    ;; --- client ---
    (ready ?o - order ?a - attempt)    ; client is about to send attempt ?a for order ?o
    (waiting ?o - order ?a - attempt)  ; client sent attempt ?a and awaits the response
    (clock ?o - order ?t - tick)       ; client's timer for the outstanding attempt
    (confirmed ?o - order)             ; client received a success response
    ;; --- network ---
    (in-flight ?o - order ?a - attempt) ; request of attempt ?a travelling to the provider
    (response ?o - order)               ; success response travelling back to the client
    ;; --- provider ---
    (approved ?o - order ?a - attempt)  ; provider accepted attempt ?a and will charge it
    (no-record ?o - order)              ; no idempotency record (and no reservation) for ?o yet
    (record ?o - order)                 ; idempotency record for ?o stored
    (uncharged ?o - order)
    (charged ?o - order)                ; card charged once
    (charged-twice ?o - order))         ; card charged a second time (the violation)

  (:action send
    :parameters (?o - order ?a - attempt ?t - tick)
    :precondition (and (ready ?o ?a) (first-tick ?t))
    :effect (and (not (ready ?o ?a)) (waiting ?o ?a) (in-flight ?o ?a) (clock ?o ?t)))
  (:action lose-request
    :parameters (?o - order ?a - attempt)
    :precondition (in-flight ?o ?a)
    :effect (not (in-flight ?o ?a)))
  (:action accept-no-dedup
    :parameters (?o - order ?a - attempt)
    :precondition (and (dedup-none) (in-flight ?o ?a))
    :effect (and (not (in-flight ?o ?a)) (approved ?o ?a)))
  (:action accept-new-atomic
    :parameters (?o - order ?a - attempt)
    :precondition (and (dedup-atomic) (in-flight ?o ?a) (no-record ?o))
    :effect (and (not (in-flight ?o ?a)) (not (no-record ?o)) (approved ?o ?a)))
  (:action accept-new-racy
    :parameters (?o - order ?a - attempt)
    :precondition (and (dedup-racy) (in-flight ?o ?a) (no-record ?o))
    :effect (and (not (in-flight ?o ?a)) (approved ?o ?a)))
  (:action replay-duplicate-atomic
    :parameters (?o - order ?a - attempt)
    :precondition (and (dedup-atomic) (in-flight ?o ?a) (record ?o))
    :effect (and (not (in-flight ?o ?a)) (response ?o)))
  (:action replay-duplicate-racy
    :parameters (?o - order ?a - attempt)
    :precondition (and (dedup-racy) (in-flight ?o ?a) (record ?o))
    :effect (and (not (in-flight ?o ?a)) (response ?o)))
  (:action charge
    :parameters (?o - order ?a - attempt)
    :precondition (and (approved ?o ?a) (uncharged ?o))
    :effect (and (not (approved ?o ?a)) (not (uncharged ?o)) (not (no-record ?o))
                 (charged ?o) (record ?o) (response ?o)))
  (:action charge-again
    :parameters (?o - order ?a - attempt)
    :precondition (and (approved ?o ?a) (charged ?o))
    :effect (and (not (approved ?o ?a)) (charged-twice ?o) (response ?o)))
  (:action lose-response
    :parameters (?o - order)
    :precondition (response ?o)
    :effect (not (response ?o)))
  (:action receive-response
    :parameters (?o - order ?a - attempt)
    :precondition (and (waiting ?o ?a) (response ?o))
    :effect (and (not (waiting ?o ?a)) (not (response ?o)) (confirmed ?o)))
  (:action tick
    :parameters (?o - order ?a - attempt ?t ?u - tick)
    :precondition (and (waiting ?o ?a) (clock ?o ?t) (next-tick ?t ?u))
    :effect (and (not (clock ?o ?t)) (clock ?o ?u)))
  (:action time-out-and-retry
    :parameters (?o - order ?a ?b - attempt ?t - tick)
    :precondition (and (waiting ?o ?a) (clock ?o ?t) (timeout-tick ?t) (next-attempt ?a ?b))
    :effect (and (not (waiting ?o ?a)) (not (clock ?o ?t)) (ready ?o ?b))))
"""

PAY_FACTS = {"flawed": ("dedup-none",), "subtle": ("dedup-racy",), "fixed": ("dedup-atomic",)}
PAY_RETRIES = 2


def pay_timeout(size: int) -> int:
    return 2 * size - 1


def pay_problem(variant: str, size: int) -> str:
    T = pay_timeout(size)
    init = [f"({f})" for f in PAY_FACTS[variant]]
    init += _chain("a", PAY_RETRIES, "next-attempt") + _chain("t", T, "next-tick")
    init += ["(first-tick t0)", f"(timeout-tick t{T})", "(ready o1 a0)", "(uncharged o1)", "(no-record o1)"]
    objects = f"o1 - order {_objs('a', PAY_RETRIES + 1)} - attempt {_objs('t', T + 1)} - tick"
    return _problem(f"payments-{variant}-{size}", "payments", objects, init, "(charged-twice o1)")


def pay_naming(variant: str, size: int) -> str:
    T = pay_timeout(size)
    return (f"Object names: the order is o1; attempts are a0 (first try), a1 and a2 (retries); "
            f"client timer values are t0 to t{T}.")


def pay_design(variant: str, size: int) -> str:
    T = pay_timeout(size)
    unit = "tick" if T == 1 else "ticks"
    common = f"""\
Checkout payment flow (design doc)

When a customer places order o1, the checkout service (the client) sends a charge request to an
external payment provider and waits for the reply. The network between them is unreliable: a request
or a response can be lost, and messages can be delayed arbitrarily, so a request may still be in
transit after the client has stopped waiting for it. The provider serves requests concurrently on
several worker threads, in whatever order they arrive, so the steps of different requests (looking up
records, charging, writing records) can interleave.

Each request is one attempt (a0 for the first try). After sending an attempt the client starts a
timer at t0; every clock tick advances it by one, and when it reaches t{T} ({T} {unit} after sending)
without a response the client gives up on that attempt and retries with the next attempt number
(a1, then a2). At most two retries are made. If a success response arrives while the client is still
waiting, the order is confirmed and no further attempts are made.
"""
    if variant == "flawed":
        mech = """
Charging. The provider treats every request it receives as a new payment: it approves the request
and charges the customer's card, then sends a success response. Requests carry the order number for
bookkeeping only; the provider does not use it to detect repeats.
"""
    elif variant == "subtle":
        mech = """
Charging and duplicate protection. Every attempt for an order carries the same idempotency key
(derived from the order number). When a request arrives, the provider looks the key up in its
idempotency table. If a record is found, the provider does not charge again; it just returns the
stored success response. If no record is found, the provider approves the request, charges the card,
and, once the charge has succeeded, writes the record for the key together with the response.
"""
    else:
        mech = """
Charging and duplicate protection. Every attempt for an order carries the same idempotency key
(derived from the order number). When a request arrives, the provider looks the key up and, in the
same atomic database operation, inserts a reservation if it is absent (an insert-if-absent with a
unique constraint). Only a request whose insert succeeded is approved and charged; when the charge
succeeds the reservation is completed with the stored response. A request whose key already has a
completed record gets the stored success response back without a new charge; a request that finds
only an unfinished reservation is not charged either.
"""
    return common + mech + "\nInitially the client is about to send attempt a0 for order o1; nothing has been charged and the provider has no record for o1.\n"


# ---------------------------------------------------------------------------
# 2. Inventory: stock decrement races and reservation expiry
# ---------------------------------------------------------------------------

INVENTORY_DOMAIN = """\
(define (domain inventory)
  (:requirements :strips :typing)
  (:types customer level tick)
  (:predicates
    ;; --- design facts ---
    (stock-racy)        ; checkout reads the stock level, then later writes back (value read - 1)
    (stock-atomic)      ; checkout decrements stock with one atomic conditional update
    (pay-checks-hold)   ; payment is accepted only while the customer's hold is still active
    (pay-ignores-hold)  ; payment is accepted even after the hold has expired
    ;; --- static counters ---
    (next-level ?lower ?higher - level)  ; stock level ?higher is one more than ?lower
    (zero-tick ?t - tick)
    (next-tick ?t ?u - tick)
    (hold-limit ?t - tick)               ; hold age at which a hold expires
    ;; --- state ---
    (stock ?q - level)                   ; current stock level
    (browsing ?c - customer)             ; customer has not started checkout
    (read-stock ?c - customer ?q - level) ; (racy) checkout of ?c read stock level ?q
    (holding ?c - customer)              ; customer holds one reserved unit
    (hold-age ?c - customer ?t - tick)
    (expired ?c - customer)              ; customer's hold expired and its unit went back to stock
    (sold ?c - customer))                ; customer's purchase is confirmed

  (:action read-stock
    :parameters (?c - customer ?q ?p - level)
    :precondition (and (stock-racy) (browsing ?c) (stock ?q) (next-level ?p ?q))
    :effect (and (not (browsing ?c)) (read-stock ?c ?q)))
  (:action write-stock
    :parameters (?c - customer ?q ?p ?cur - level ?t - tick)
    :precondition (and (read-stock ?c ?q) (next-level ?p ?q) (stock ?cur) (zero-tick ?t))
    :effect (and (not (read-stock ?c ?q)) (not (stock ?cur)) (stock ?p) (holding ?c) (hold-age ?c ?t)))
  (:action reserve-atomic
    :parameters (?c - customer ?q ?p - level ?t - tick)
    :precondition (and (stock-atomic) (browsing ?c) (stock ?q) (next-level ?p ?q) (zero-tick ?t))
    :effect (and (not (browsing ?c)) (not (stock ?q)) (stock ?p) (holding ?c) (hold-age ?c ?t)))
  (:action hold-ages
    :parameters (?c - customer ?t ?u - tick)
    :precondition (and (holding ?c) (hold-age ?c ?t) (next-tick ?t ?u))
    :effect (and (not (hold-age ?c ?t)) (hold-age ?c ?u)))
  (:action expire-hold
    :parameters (?c - customer ?t - tick ?q ?r - level)
    :precondition (and (holding ?c) (hold-age ?c ?t) (hold-limit ?t) (stock ?q) (next-level ?q ?r))
    :effect (and (not (holding ?c)) (not (hold-age ?c ?t)) (not (stock ?q)) (stock ?r) (expired ?c)))
  (:action pay
    :parameters (?c - customer ?t - tick)
    :precondition (and (holding ?c) (hold-age ?c ?t))
    :effect (and (not (holding ?c)) (not (hold-age ?c ?t)) (sold ?c)))
  (:action pay-after-expiry
    :parameters (?c - customer)
    :precondition (and (pay-ignores-hold) (expired ?c))
    :effect (and (not (expired ?c)) (sold ?c))))
"""

INV_FACTS = {"flawed": ("stock-racy", "pay-checks-hold"), "subtle": ("stock-atomic", "pay-ignores-hold"),
             "fixed": ("stock-atomic", "pay-checks-hold")}


def inv_problem(variant: str, size: int) -> str:
    S, H = size, size
    customers = [f"c{i}" for i in range(1, S + 2)]
    init = [f"({f})" for f in INV_FACTS[variant]]
    init += _chain("q", S, "next-level") + _chain("t", H, "next-tick")
    init += ["(zero-tick t0)", f"(hold-limit t{H})", f"(stock q{S})"] + [f"(browsing {c})" for c in customers]
    objects = f"{' '.join(customers)} - customer {_objs('q', S + 1)} - level {_objs('t', H + 1)} - tick"
    goal = "(and " + " ".join(f"(sold {c})" for c in customers) + ")"
    return _problem(f"inventory-{variant}-{size}", "inventory", objects, init, goal)


def inv_naming(variant: str, size: int) -> str:
    S = size
    return (f"Object names: customers c1 to c{S + 1}; stock levels q0 (empty) to q{S}; "
            f"hold ages t0 to t{size}.")


def inv_design(variant: str, size: int) -> str:
    S, H = size, size
    cust = ", ".join(f"c{i}" for i in range(1, S + 2))
    unit = "unit" if S == 1 else "units"
    common = f"""\
Limited-edition drop: stock reservation design (design doc)

The shop has {S} {unit} of a limited-edition item in stock, and {S + 1} customers ({cust}) try to buy
it at the same time. Each customer's checkout runs on its own server thread; the threads interleave
arbitrarily. A checkout first reserves a unit (a hold), then the customer pays to confirm the
purchase.

Holds are temporary: a hold that is not paid for expires after {H} clock {'tick' if H == 1 else 'ticks'}, and the unit goes
back into stock so that another customer can buy it. Customers can be slow to pay; the payment step
may happen at any later time.
"""
    if variant == "flawed":
        stock = """
Reserving. The checkout thread reads the current stock count from the database, checks that it is
above zero, and then, as a separate statement, writes back the count it read minus one. No lock or
transaction spans the read and the write.
"""
    else:
        stock = """
Reserving. The checkout thread reserves with a single atomic conditional update
(UPDATE stock SET count = count - 1 WHERE count > 0); if no row is updated the customer is told the
item is sold out.
"""
    if variant == "subtle":
        pay = """
Paying. The payment service charges the customer and marks the order confirmed. It looks the order
up by customer id; whether the hold is still active or has already expired is not checked at this
point (the hold is only a soft guarantee during browsing).
"""
    else:
        pay = """
Paying. The payment service confirms an order only if the customer's hold is still active; payment
for an expired hold is refused and the customer must start again.
"""
    return common + stock + pay + f"\nInitially all customers are browsing and the stock count is {S}.\n"


# ---------------------------------------------------------------------------
# 3. Distributed lock with leases (fencing tokens)
# ---------------------------------------------------------------------------

LOCK_DOMAIN = """\
(define (domain lease-lock)
  (:requirements :strips :typing)
  (:types client tick token)
  (:predicates
    ;; --- design facts ---
    (fencing)          ; storage rejects writes whose token is older than the newest it has seen
    (no-fencing)       ; storage accepts every write
    (checks-lease)     ; a client checks it still holds the lease right before writing
    (no-lease-check)   ; a client writes whenever it believes it holds the lock
    ;; --- static counters ---
    (next-tick ?t ?u - tick) (zero-tick ?t - tick)
    (lease-limit ?t - tick)              ; lease age at which the lock service expires the lease
    (next-token ?k ?l - token)           ; token ?l is issued after ?k
    (token-less ?k ?l - token)           ; ?k < ?l
    (token-leq ?k ?l - token)            ; ?k <= ?l
    ;; --- lock service ---
    (lock-free) (holder ?c - client) (lease-age ?t - tick) (last-issued ?k - token)
    ;; --- clients ---
    (idle ?c - client)                   ; has not acquired the lock yet
    (believes ?c - client)               ; client thinks it holds the lock
    (lease-expired ?c - client)          ; the service expired this client's lease
    (token-of ?c - client ?k - token)
    (may-write ?c - client)              ; client is about to write to storage
    ;; --- storage ---
    (max-seen ?k - token)                ; newest token storage has seen (used with fencing)
    (wrote ?k - token)                   ; a write with token ?k was applied
    (corrupted))                         ; an older holder's write was applied after a newer holder's write

  (:action acquire
    :parameters (?c - client ?k ?l - token ?t - tick)
    :precondition (and (idle ?c) (lock-free) (last-issued ?k) (next-token ?k ?l) (zero-tick ?t))
    :effect (and (not (idle ?c)) (not (lock-free)) (not (last-issued ?k)) (last-issued ?l)
                 (holder ?c) (believes ?c) (token-of ?c ?l) (lease-age ?t)))
  (:action tick
    :parameters (?t ?u - tick)
    :precondition (and (lease-age ?t) (next-tick ?t ?u))
    :effect (and (not (lease-age ?t)) (lease-age ?u)))
  (:action expire
    :parameters (?c - client ?t - tick)
    :precondition (and (holder ?c) (lease-age ?t) (lease-limit ?t))
    :effect (and (not (holder ?c)) (not (lease-age ?t)) (lock-free) (lease-expired ?c)))
  (:action prepare-write
    :parameters (?c - client)
    :precondition (and (no-lease-check) (believes ?c))
    :effect (may-write ?c))
  (:action check-lease-and-prepare-write
    :parameters (?c - client)
    :precondition (and (checks-lease) (believes ?c) (holder ?c))
    :effect (may-write ?c))
  (:action write-unfenced
    :parameters (?c - client ?k - token)
    :precondition (and (no-fencing) (may-write ?c) (token-of ?c ?k))
    :effect (and (not (may-write ?c)) (not (believes ?c)) (wrote ?k)))
  (:action write-unfenced-over-newer
    :parameters (?c - client ?k ?m - token)
    :precondition (and (no-fencing) (may-write ?c) (token-of ?c ?k) (wrote ?m) (token-less ?k ?m))
    :effect (and (not (may-write ?c)) (not (believes ?c)) (corrupted)))
  (:action write-fenced
    :parameters (?c - client ?k ?j - token)
    :precondition (and (fencing) (may-write ?c) (token-of ?c ?k) (max-seen ?j) (token-leq ?j ?k))
    :effect (and (not (may-write ?c)) (not (believes ?c)) (not (max-seen ?j)) (max-seen ?k) (wrote ?k)))
  (:action write-fenced-over-newer
    :parameters (?c - client ?k ?j ?m - token)
    :precondition (and (fencing) (may-write ?c) (token-of ?c ?k) (max-seen ?j) (token-leq ?j ?k)
                       (wrote ?m) (token-less ?k ?m))
    :effect (and (not (may-write ?c)) (not (believes ?c)) (corrupted)))
  (:action reject-stale-write
    :parameters (?c - client ?k ?j - token)
    :precondition (and (fencing) (may-write ?c) (token-of ?c ?k) (max-seen ?j) (token-less ?k ?j))
    :effect (and (not (may-write ?c)) (not (believes ?c)))))
"""

LOCK_FACTS = {"flawed": ("no-fencing", "no-lease-check"), "subtle": ("no-fencing", "checks-lease"),
              "fixed": ("fencing", "checks-lease")}
N_TOKENS = 3


def lock_lease(size: int) -> int:
    return 2 * size - 1


def lock_problem(variant: str, size: int) -> str:
    L = lock_lease(size)
    init = [f"({f})" for f in LOCK_FACTS[variant]]
    init += _chain("t", L, "next-tick") + ["(zero-tick t0)", f"(lease-limit t{L})"]
    init += _chain("k", N_TOKENS, "next-token")
    init += [f"(token-less k{i} k{j})" for i in range(N_TOKENS + 1) for j in range(i + 1, N_TOKENS + 1)]
    init += [f"(token-leq k{i} k{j})" for i in range(N_TOKENS + 1) for j in range(i, N_TOKENS + 1)]
    init += ["(lock-free)", "(last-issued k0)", "(max-seen k0)", "(idle c1)", "(idle c2)"]
    objects = f"c1 c2 - client {_objs('t', L + 1)} - tick {_objs('k', N_TOKENS + 1)} - token"
    return _problem(f"lock-{variant}-{size}", "lease-lock", objects, init, "(corrupted)")


def lock_naming(variant: str, size: int) -> str:
    L = lock_lease(size)
    return (f"Object names: clients c1 and c2; lease ages t0 to t{L}; tokens k0 (initial value, never "
            f"handed out) to k{N_TOKENS}.")


def lock_design(variant: str, size: int) -> str:
    L = lock_lease(size)
    common = f"""\
Report-generation job: leader lock design (design doc)

Two worker processes, c1 and c2, may both try to run the nightly job, which overwrites a shared file
in object storage. To make sure only one of them writes, a worker must first acquire a lock from the
lock service. The lock is a lease: it is granted for {L} clock {'tick' if L == 1 else 'ticks'}, after which the lock service
considers it expired and may grant it to the other worker. Each grant comes with a token from a
counter (k1 for the first grant, then k2, ...; k0 is the initial counter value and is never handed
out). Each worker writes the file at most once.

Workers can stall at any point for an unbounded time (garbage-collection pauses, VM migration,
slow network), and they learn nothing about lease expiry while stalled: a worker that has acquired
the lock keeps believing it holds it.
"""
    if variant == "flawed":
        mech = """
Writing. Once a worker holds the lock it writes the file. The storage service accepts any write;
the token is logged for auditing only.
"""
    elif variant == "subtle":
        mech = """
Writing. Right before writing, the worker asks the lock service whether it still holds an unexpired
lease, and writes only if the answer is yes; if the lease has expired it abandons the job. The
storage service accepts any write; the token is logged for auditing only.
"""
    else:
        mech = """
Writing. Right before writing, the worker asks the lock service whether it still holds an unexpired
lease, and writes only if the answer is yes. Every write carries the worker's token, and the storage
service remembers the highest token it has accepted: it rejects any write whose token is lower than
that (fencing), and accepts and records the others.
"""
    return common + mech + "\nInitially the lock is free, no token has been issued yet (the counter is at k0), the storage has seen token k0, and neither worker has acquired the lock.\n"


# ---------------------------------------------------------------------------
# 4. Message queue: at-least-once delivery and consumer deduplication
# ---------------------------------------------------------------------------

QUEUE_DOMAIN = """\
(define (domain queue)
  (:requirements :strips :typing)
  (:types message consumer tick)
  (:predicates
    ;; --- design facts: exactly one deduplication mode holds ---
    (dedup-none)      ; the consumer processes every delivery
    (dedup-durable)   ; processed ids are recorded in the database, atomically with the side effect
    (dedup-memory)    ; processed ids are recorded in an in-memory set of the consumer process
    ;; --- static counters ---
    (next-tick ?t ?u - tick) (zero-tick ?t - tick)
    (visibility-timeout ?t - tick)        ; age at which an unacknowledged message becomes visible again
    ;; --- queue ---
    (in-queue ?m - message) (visible ?m - message) (hidden ?m - message ?t - tick) (acked ?m - message)
    ;; --- consumer ---
    (idle ?w - consumer) (working ?w - consumer ?m - message) (handled ?w - consumer ?m - message)
    ;; --- effects of processing ---
    (unprocessed ?m - message) (processed ?m - message) (processed-twice ?m - message)
    (not-seen ?m - message) (seen ?m - message))

  (:action receive
    :parameters (?w - consumer ?m - message ?t - tick)
    :precondition (and (idle ?w) (visible ?m) (in-queue ?m) (zero-tick ?t))
    :effect (and (not (idle ?w)) (not (visible ?m)) (working ?w ?m) (hidden ?m ?t)))
  (:action process-without-dedup
    :parameters (?w - consumer ?m - message)
    :precondition (and (dedup-none) (working ?w ?m) (unprocessed ?m))
    :effect (and (not (working ?w ?m)) (not (unprocessed ?m)) (processed ?m) (handled ?w ?m)))
  (:action process-and-record-durably
    :parameters (?w - consumer ?m - message)
    :precondition (and (dedup-durable) (working ?w ?m) (unprocessed ?m) (not-seen ?m))
    :effect (and (not (working ?w ?m)) (not (unprocessed ?m)) (not (not-seen ?m)) (seen ?m)
                 (processed ?m) (handled ?w ?m)))
  (:action process-and-record-in-memory
    :parameters (?w - consumer ?m - message)
    :precondition (and (dedup-memory) (working ?w ?m) (unprocessed ?m) (not-seen ?m))
    :effect (and (not (working ?w ?m)) (not (unprocessed ?m)) (not (not-seen ?m)) (seen ?m)
                 (processed ?m) (handled ?w ?m)))
  (:action skip-duplicate
    :parameters (?w - consumer ?m - message)
    :precondition (and (working ?w ?m) (seen ?m))
    :effect (and (not (working ?w ?m)) (handled ?w ?m)))
  (:action process-again
    :parameters (?w - consumer ?m - message)
    :precondition (and (working ?w ?m) (processed ?m) (not-seen ?m))
    :effect (and (not (working ?w ?m)) (processed-twice ?m) (handled ?w ?m)))
  (:action ack
    :parameters (?w - consumer ?m - message ?t - tick)
    :precondition (and (handled ?w ?m) (hidden ?m ?t))
    :effect (and (not (handled ?w ?m)) (not (hidden ?m ?t)) (not (in-queue ?m)) (idle ?w) (acked ?m)))
  (:action tick
    :parameters (?m - message ?t ?u - tick)
    :precondition (and (hidden ?m ?t) (next-tick ?t ?u))
    :effect (and (not (hidden ?m ?t)) (hidden ?m ?u)))
  (:action reappear
    :parameters (?m - message ?t - tick)
    :precondition (and (hidden ?m ?t) (visibility-timeout ?t) (in-queue ?m))
    :effect (and (not (hidden ?m ?t)) (visible ?m)))
  (:action crash-restart
    :parameters (?w - consumer ?m - message)
    :precondition (handled ?w ?m)
    :effect (and (not (handled ?w ?m)) (idle ?w)))
  (:action crash-restart-losing-memory
    :parameters (?w - consumer ?m - message)
    :precondition (and (dedup-memory) (handled ?w ?m) (seen ?m))
    :effect (and (not (handled ?w ?m)) (not (seen ?m)) (not-seen ?m) (idle ?w))))
"""

QUEUE_FACTS = {"flawed": ("dedup-none",), "subtle": ("dedup-memory",), "fixed": ("dedup-durable",)}


def queue_timeout(size: int) -> int:
    return 2 * size - 1


def queue_problem(variant: str, size: int) -> str:
    V = queue_timeout(size)
    init = [f"({f})" for f in QUEUE_FACTS[variant]]
    init += _chain("t", V, "next-tick") + ["(zero-tick t0)", f"(visibility-timeout t{V})"]
    init += ["(in-queue m1)", "(visible m1)", "(unprocessed m1)", "(not-seen m1)", "(idle w1)"]
    objects = f"m1 - message w1 - consumer {_objs('t', V + 1)} - tick"
    return _problem(f"queue-{variant}-{size}", "queue", objects, init, "(processed-twice m1)")


def queue_naming(variant: str, size: int) -> str:
    V = queue_timeout(size)
    return f"Object names: the message is m1; the consumer process is w1; message ages t0 to t{V}."


def queue_design(variant: str, size: int) -> str:
    V = queue_timeout(size)
    common = f"""\
Payout worker: queue consumer design (design doc)

When a seller's balance is settled, a "send payout" message (m1) is put on a message queue. A
consumer process (w1) receives messages from the queue and, for each one, performs the payout by
crediting the amount to the seller's wallet balance, which is stored in the payments database (a
credit, once committed, is not reversed automatically), then acknowledges the message so the queue
deletes it.

The queue guarantees at-least-once delivery. A received message is hidden from consumers; if it is
not acknowledged within {V} clock {'tick' if V == 1 else 'ticks'} of being received (the visibility timeout) it becomes visible
again and will be delivered again. The consumer process can crash at any moment and is restarted
automatically, after which it continues receiving messages.
"""
    if variant == "flawed":
        mech = """
Processing. The consumer performs the payout for every message it receives, then acknowledges it.
"""
    elif variant == "subtle":
        mech = """
Processing and deduplication. The consumer keeps the ids of messages it has already paid out in a
set in its process memory. Before performing a payout it checks the set: if the id is there it skips
the payout and only acknowledges the message; otherwise it credits the wallet, adds the id to the
set, and acknowledges.
"""
    else:
        mech = """
Processing and deduplication. The consumer records the ids of messages it has already paid out in a
table in the payments database. The wallet credit and the id record are written in the same database
transaction, so either both are stored or neither is (a crash before the commit rolls both back).
Before performing a payout the consumer checks the table: if the id is there it skips the payout and
only acknowledges the message.
"""
    return common + mech + "\nInitially m1 is in the queue and visible, nothing has been paid out, and w1 is idle.\n"


# ---------------------------------------------------------------------------
# 5. Cache-aside: stale cache after concurrent update
# ---------------------------------------------------------------------------

CACHE_DOMAIN = """\
(define (domain cache-aside)
  (:requirements :strips :typing)
  (:types version)
  (:predicates
    ;; --- design facts ---
    (update-then-delete)   ; the writer updates the database, then deletes the cache entry
    (delete-then-update)   ; the writer deletes the cache entry, then updates the database
    (plain-set)            ; a reader that missed always stores the value it read
    (leased-set)           ; a reader may store its value only if its lease was not revoked by a delete
    ;; --- static ---
    (next-version ?v ?w - version) (older ?v ?w - version) (final-version ?v - version)
    ;; --- state ---
    (db ?v - version) (cache ?v - version) (cache-empty)
    (reader-idle) (reader-has ?v - version) (lease)
    (writer-start ?v - version)        ; writer is about to begin its updates (database at ?v)
    (writer-update ?v - version)       ; writer's next step: write the version after ?v to the database
    (writer-invalidate ?v - version)   ; writer's next step: delete the cache entry (database is at ?v)
    (writer-done)
    (stale))                           ; after the writer finished, the cache holds an older version than the database

  (:action read-miss
    :parameters (?v - version)
    :precondition (and (reader-idle) (cache-empty) (db ?v))
    :effect (and (not (reader-idle)) (reader-has ?v) (lease)))
  (:action fill-cache
    :parameters (?v - version)
    :precondition (and (plain-set) (reader-has ?v) (cache-empty))
    :effect (and (not (reader-has ?v)) (not (cache-empty)) (cache ?v) (reader-idle)))
  (:action fill-cache-with-lease
    :parameters (?v - version)
    :precondition (and (leased-set) (reader-has ?v) (cache-empty) (lease))
    :effect (and (not (reader-has ?v)) (not (cache-empty)) (not (lease)) (cache ?v) (reader-idle)))
  (:action abandon-fill
    :parameters (?v - version)
    :precondition (reader-has ?v)
    :effect (and (not (reader-has ?v)) (reader-idle)))
  (:action begin-update-first
    :parameters (?v - version)
    :precondition (and (update-then-delete) (writer-start ?v))
    :effect (and (not (writer-start ?v)) (writer-update ?v)))
  (:action begin-delete-first
    :parameters (?v - version)
    :precondition (and (delete-then-update) (writer-start ?v))
    :effect (and (not (writer-start ?v)) (writer-invalidate ?v)))
  (:action write-db
    :parameters (?v ?w - version)
    :precondition (and (writer-update ?v) (db ?v) (next-version ?v ?w))
    :effect (and (not (writer-update ?v)) (not (db ?v)) (db ?w) (writer-invalidate ?w)))
  (:action invalidate
    :parameters (?v ?x - version)
    :precondition (and (writer-invalidate ?v) (cache ?x))
    :effect (and (not (writer-invalidate ?v)) (not (cache ?x)) (not (lease)) (cache-empty) (writer-update ?v)))
  (:action invalidate-empty
    :parameters (?v - version)
    :precondition (and (writer-invalidate ?v) (cache-empty))
    :effect (and (not (writer-invalidate ?v)) (not (lease)) (writer-update ?v)))
  (:action finish-after-delete
    :parameters (?v - version)
    :precondition (and (update-then-delete) (writer-update ?v) (final-version ?v))
    :effect (and (not (writer-update ?v)) (writer-done)))
  (:action finish-after-update
    :parameters (?v - version)
    :precondition (and (delete-then-update) (writer-invalidate ?v) (final-version ?v))
    :effect (and (not (writer-invalidate ?v)) (writer-done)))
  (:action observe-stale
    :parameters (?v ?w - version)
    :precondition (and (writer-done) (cache ?v) (db ?w) (older ?v ?w))
    :effect (stale)))
"""

CACHE_FACTS = {"flawed": ("update-then-delete", "plain-set"), "subtle": ("delete-then-update", "plain-set"),
               "fixed": ("update-then-delete", "leased-set")}


def cache_updates(size: int) -> int:
    return size


def cache_problem(variant: str, size: int) -> str:
    W = cache_updates(size)
    init = [f"({f})" for f in CACHE_FACTS[variant]]
    init += _chain("v", W, "next-version")
    init += [f"(older v{i} v{j})" for i in range(W + 1) for j in range(i + 1, W + 1)]
    init += [f"(final-version v{W})", "(db v0)", "(cache-empty)", "(reader-idle)", "(writer-start v0)"]
    objects = f"{_objs('v', W + 1)} - version"
    return _problem(f"cache-{variant}-{size}", "cache-aside", objects, init, "(stale)")


def cache_naming(variant: str, size: int) -> str:
    W = cache_updates(size)
    return f"Object names: versions v0 (initial) to v{W}."


def cache_design(variant: str, size: int) -> str:
    W = cache_updates(size)
    common = f"""\
Product page cache (design doc)

Product details live in a database and are cached in a key-value cache using the cache-aside
pattern. One reader process serves product-page requests: on a cache hit it uses the cached value;
on a miss it reads the current value from the database and then stores what it read in the cache.
One writer process applies a batch of {W} price {'update' if W == 1 else 'updates'} to the product, one after another, moving
the database from version v0 to v{W}. Reader and writer steps interleave arbitrarily, and the reader
can be delayed for any amount of time between reading the database and storing into the cache.
Cache entries have no expiry time.
"""
    if variant == "flawed":
        mech = """
Writes. For each update the writer first writes the new version to the database and then deletes
the product's cache entry, so the next read misses and loads the new version. The reader always
stores the value it read after a miss.
"""
    elif variant == "subtle":
        mech = """
Writes. To make sure readers never see the old price once an update has started, for each update
the writer first deletes the product's cache entry and then writes the new version to the database.
The reader always stores the value it read after a miss.
"""
    else:
        mech = """
Writes. For each update the writer first writes the new version to the database and then deletes
the product's cache entry. On a miss the reader receives a lease token from the cache; a delete of
the entry revokes any outstanding lease, and the cache only accepts a store from a reader whose
lease is still valid (otherwise the reader drops its value).
"""
    return common + mech + "\nInitially the database holds v0, the cache is empty, the reader is idle, and the writer is about to start its first update.\n"


FAMILIES: dict[str, Family] = {
    "payments": Family("payments", PAYMENTS_DOMAIN, "(charged-twice o1)",
                       "Can the customer's card be charged twice for order o1?",
                       PAY_FACTS, pay_timeout, pay_problem, pay_design, pay_naming),
    "inventory": Family("inventory", INVENTORY_DOMAIN, "(and (sold c1) ... )",
                        "Can every one of the customers end up with a confirmed purchase, i.e. more items sold than were in stock?",
                        INV_FACTS, lambda s: s, inv_problem, inv_design, inv_naming),
    "lock": Family("lock", LOCK_DOMAIN, "(corrupted)",
                   "Can a write from a worker whose lease had expired be applied after the other worker's write (corrupting the file)?",
                   LOCK_FACTS, lock_lease, lock_problem, lock_design, lock_naming),
    "queue": Family("queue", QUEUE_DOMAIN, "(processed-twice m1)",
                    "Can the payout for message m1 be performed twice?",
                    QUEUE_FACTS, queue_timeout, queue_problem, queue_design, queue_naming),
    "cache": Family("cache", CACHE_DOMAIN, "(stale)",
                    "Can the cache be left holding an older version than the database after the writer has finished all its updates?",
                    CACHE_FACTS, cache_updates, cache_problem, cache_design, cache_naming),
}

def behavioural_predicates(domain_text: str) -> set[str]:
    """Predicates that occur in some action precondition (facts that can change behaviour)."""
    from ..planning import parse_domain
    dom = parse_domain(domain_text)
    return {atom.predicate for a in dom.actions.values() for atom in (*a.pre_pos, *a.pre_neg)}


def design_predicates(family: str) -> set[str]:
    """Nullary predicates declared as design facts in the domain (the facts SP3 scores)."""
    dom = FAMILIES[family].domain
    preds = set()
    in_design = False
    for line in dom.splitlines():
        s = line.strip()
        if s.startswith(";; --- design facts"):
            in_design = True
            continue
        if s.startswith(";; ---"):
            in_design = False
        if in_design and s.startswith("(") and " " not in s.split(")")[0]:
            preds.add(s[1:s.index(")")])
    return preds
