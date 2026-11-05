# Appendix A. Artefacts from the cached runs

**A.1 A rare SP1 bug** (`days_in_month`, mutant 400 → 399, trigger rarity 0.019%; every model found it in
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
