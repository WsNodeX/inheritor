# Patterns — before and after

Each pair is a real failure shape. The "after" is not longer; it is more
informative per line.

---

## 1. The unnamed literal

```python
# Before
if len(batch) > 1000:
    flush()
```

```python
# After
# 1000 is the vendor's documented max for a single write; over it returns 413,
# and the whole batch has to be resent.
MAX_BATCH = 1000

if len(batch) > MAX_BATCH:
    flush()
```

Three extra lines buy: what the number is, who imposed it, and what happens if you
change it. **The rule is not "no literals" — it is "no unexplained decisions".**

A literal in a slice (`text[:4]`) or a loop bound (`range(10)`) is positional, not
policy. Leave those alone.

---

## 2. The comment that restates the code

```python
# Before
i += 1                      # increment i
records.sort()              # sort the records
```

```python
# After
i += 1

# Ledger entries must be ordered by settled_at before reconciliation, because
# the diff walk assumes monotonic time and silently mismatches if it is not.
records.sort(key=lambda r: r.settled_at)
```

The first version's comment is a slower copy of the code. Delete it — it will rot
while looking authoritative.

The second version's comment carries a fact the code cannot: an invariant the
sorting satisfies, and what breaks without it.

---

## 3. The error nobody can act on

```python
# Before
except TimeoutError:
    raise Exception("Failed")
```

```python
# After
except TimeoutError as e:
    raise BillingTimeout(
        f"billing-api did not answer within {timeout_s}s "
        f"(account={account_id}, attempt={attempt}); "
        f"this path is idempotent, so retry is safe — "
        f"if it recurs, check the upstream status page"
    ) from e
```

Answers: what happened, with which input, whether retry is safe, what to check
next. Keeps the original traceback via `from e`.

Never interpolate tokens, passwords, or full request bodies into the message.

---

## 4. The TODO that will never be resolved

```python
# Before
# TODO: fix this later
```

```python
# After
# TODO: drop the retry loop once billing-api v2 ships idempotency keys
# (TEAM-1234). Until then duplicate charges are possible on timeout, and this
# loop is the only thing preventing them.
```

A TODO needs three parts: what is wrong, why it is not fixed now, what makes it
safe to remove. If you cannot write the third, you do not yet understand the bug —
which means the TODO is hiding a design question, not a task.

---

## 5. The implicit contract

```python
# Before
def normalize(records):
    records.sort()
    return records
```

```python
# After
def normalize(records: list[Record]) -> list[Record]:
    """Return a copy sorted by id. Does not mutate the input.

    Raises ValueError if any record lacks an 'id' key — silent skips would make
    the output length differ from the input, which callers rely on.
    """
    missing = [r for r in records if "id" not in r]
    if missing:
        raise ValueError(
            f"{len(missing)} of {len(records)} records have no 'id'; "
            f"first offender: {missing[0]!r}"
        )
    return sorted(records, key=lambda r: r["id"])
```

The before version has three undocumented behaviours: it mutates its argument, it
requires an `id` key, and it fails with a bare `KeyError` nobody can trace.

Type hints, a docstring contract, and a real exception are three ways to write the
same sentence. Use whichever the codebase already speaks.

---

## 6. The module with no map

```python
# Before
import asyncio
from . import db, gateway
```

```python
# After
"""Order reconciliation.

Entry point:  reconcile() — called hourly by the scheduler.
Input:        orders table (source of truth) + gateway settlement report.
Output:       writes only to the discrepancies table; never mutates orders.
Invariant:    a settled order's amount never changes. If it does, we stop and
              page rather than reconcile — a changed amount means the source of
              truth is wrong, and continuing would write garbage downstream.
"""
import asyncio
from . import db, gateway
```

Ten lines at the top of a file save the next reader an hour of reading the body to
reconstruct the data flow.

---

## 7. The commit message that repeats the diff

```
# Before
fix config
```

```
# After
Raise connection pool to 20 — 10 starved under concurrent uploads

Observed 3-8s waits on /upload whenever more than 8 workers were active. The pool
capped at 10 and the queue never drained. 20 is still under the 25-connection
limit enforced by the RDS proxy, so this does not risk exhausting it.
```

The diff already shows which lines changed. The commit message is the only place
with room for why, and the only moment someone has your full context.

---

## What these have in common

None of the "after" versions add behaviour. Every one of them records a decision
that existed only in the author's head, at the moment the author still had it.

That is the entire trade: two minutes now, against an hour of archaeology later —
usually by the same person, who will not remember.
