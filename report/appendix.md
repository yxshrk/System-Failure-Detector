# Appendix A. Artefacts from the cached runs

**A.1 A rare SP1 bug** (`days_in_month`, mutant 400 → 399, trigger rarity 0.019%; every model except Llama found it in
both arms):

```python
return y % 4 == 0 and (y % 100 != 0 or y % 399 == 0)
```

**A.2 Specification anchoring** (Translate, Haiku 4.5, mutant `y % 400 == 0 -> y % 400 != 0`). The
spec's helper copies the mutated line from the code under review, so Z3 reports no violation and the
soundness check against the reference fails. The `withdraw` miss is the same pattern (`new_balance <= 0`
copies the mutated boundary).

```python
def leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 != 0)
```

**A.3 A wrong specification yields a fabricated witness** (Translate, Haiku 4.5, `weekday`). After
`m += 12` for January and February, `t[m - 1]` is out of range, so `post` raises; the verifier counts
that as a violation and returns `{day: 1, month: 1, year: 1801}`, on which the code is correct.

```python
t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
if m < 3:
    m += 12
    y -= 1
sakamoto_result = (y + y // 4 - y // 100 + y // 400 + t[m - 1] + day) % 7
```

**A.4 A false alarm on a fixed design** (Direct, Haiku 4.5, `payments-fixed-1`; replay fails at step 2
because `(dedup-racy)` is false in this design):
`send o1 a0 t0` → `accept-new-racy o1 a0` → `tick o1 a0 t0 t1` → `time-out-and-retry o1 a0 a1 t1` →
`send o1 a1 t0` → `accept-new-racy o1 a1` → `charge o1 a0` → `lose-response o1` → `charge-again o1 a1`.

**A.5 The planner exploits translation slack** (Translate, Haiku 4.5). In `lock-flawed-3` the model's
`:init` adds `(lease-age t0)`, a lease clock running before anyone holds the lock; the planner's trace
starts `tick t0 t1` → `tick t1 t2` → …, legal only in the model's problem, and replay on gold fails at
step 1. In `queue-fixed-8`, 15 extra `(zero-tick …)` facts let the trace start `receive w1 m1 t15`,
skipping the visibility timeout.

**A.6 Gold shortest trace for `payments-subtle-1`** (SATPlan, 8 events; the retry passes the
idempotency lookup because the record is written only after a charge):
`send o1 a0 t0` → `accept-new-racy o1 a0` → `tick o1 a0 t0 t1` → `time-out-and-retry o1 a0 a1 t1` →
`send o1 a1 t0` → `accept-new-racy o1 a1` → `charge o1 a1` → `charge-again o1 a0`.

**A.7 A design document as the LLM sees it** (`payments-subtle-1`):

> Checkout payment flow (design doc)
>
> When a customer places order o1, the checkout service (the client) sends a charge request to an
> external payment provider and waits for the reply. The network between them is unreliable: a request
> or a response can be lost, and messages can be delayed arbitrarily, so a request may still be in
> transit after the client has stopped waiting for it. The provider serves requests concurrently on
> several worker threads, in whatever order they arrive, so the steps of different requests (looking up
> records, charging, writing records) can interleave.
>
> Each request is one attempt (a0 for the first try). After sending an attempt the client starts a
> timer at t0; every clock tick advances it by one, and when it reaches t1 (1 tick after sending)
> without a response the client gives up on that attempt and retries with the next attempt number
> (a1, then a2). At most two retries are made. If a success response arrives while the client is still
> waiting, the order is confirmed and no further attempts are made.
>
> Charging and duplicate protection. Every attempt for an order carries the same idempotency key
> (derived from the order number). When a request arrives, the provider looks the key up in its
> idempotency table. If a record is found, the provider does not charge again; it just returns the
> stored success response. If no record is found, the provider approves the request, charges the card,
> and, once the charge has succeeded, writes the record for the key together with the response.
>
> Initially the client is about to send attempt a0 for order o1; nothing has been charged and the provider has no record for o1.

**A.8 The inventory invariant behind the fixed label from size 8** (proved by hand, because search runs out of budget there). In every reachable state, stock + holding + sold = $S$. Initially stock = $S$; `reserve-atomic` moves a unit from stock to holding, `expire-hold` moves it back, `pay` moves it to sold, and the other actions change no count or are disabled by the fixed design facts; each customer leaves browsing once, so no count rises twice. Hence sold ≤ $S$ < $S + 1$.
