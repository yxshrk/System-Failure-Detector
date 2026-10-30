# Appendix A. Worked examples (from the cached runs)

**A.1 A rare SP1 bug found by both arms.** In `days_in_month`, mutant `400 → 399` inside the leap-year
helper changes the result only for February of years divisible by 400 (none of which is divisible by 399): 7 of the 3,000 years. Its trigger
rarity is 0.019%. Every model, in both arms, produced a valid witness. Random testing with 1,000 inputs
finds it with probability 18%.

**A.2 Specification anchoring (Translate, Haiku 4.5).** For the mutant `y % 400 == 0 → y % 400 != 0`,
the model was asked to specify the *docstring*. Instead its postcondition re-implemented the code's
leap test, bug included:

```python
def leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 != 0)   # copied from the code under review
```

Because the specification agrees with the bug, Z3 correctly reports "no violation", and the bug is
missed. The `withdraw` miss is the same pattern: the spec's `new_balance <= 0` copies the mutated
boundary. In both cases the soundness check (does the *reference* satisfy the spec?) fails, so the
error is detectable whenever a trusted reference exists. It is not detectable in deployment.

**A.3 A fabricated SP1 witness from a wrong specification (Translate, Haiku 4.5).** For `weekday`,
the model specified the answer via Sakamoto's algorithm but indexed its month table with `m - 1` after
shifting January to month 13. That raises `IndexError` for January and February. Our verifier treats an
exception in `post` as a violation, so it returned 1 January 1801, on which the code is correct.

**A.4 A false alarm on a fixed design (Direct, Haiku 4.5).** For `payments-fixed-1` (atomic
insert-if-absent), the model's 9-step trace uses `accept-new-racy`. That event belongs to the racy
variant, and its precondition `(dedup-racy)` is false in this design. The model recognised the
well-known check-then-act race and applied it to a design that explicitly rules it out. Replay on the
gold problem fails at step 2.

**A.5 The planner exploits translation slack (Translate, Haiku 4.5).** In `lock-flawed-3` the model's
problem file declared `(lease-age t0)` in the initial state, i.e. a lease clock running before anyone
holds the lock. SATPlan's shortest trace starts with `(tick t0 t1)`, which is legal only in the model's
problem, so replay on the gold problem fails at step 1. In `queue-fixed-8` extra `(zero-tick …)` facts
let the planner skip the visibility timeout. Classical planners are adversarial towards their model:
every over-permissive fact becomes a shortcut.

**A.6 Gold shortest trace for `payments-subtle-1` (SATPlan, 8 events).**
`send o1 a0 t0` → `accept-new-racy o1 a0` → `tick o1 a0 t0 t1` → `time-out-and-retry o1 a0 a1 t1` →
`send o1 a1 t0` → `accept-new-racy o1 a1` → `charge o1 a1` → `charge-again o1 a0`.

In words: the provider accepts the first request, but before it charges, the client times out and retries. The retry also passes the idempotency lookup, because the record is only written once a charge succeeds, so both requests are charged.
