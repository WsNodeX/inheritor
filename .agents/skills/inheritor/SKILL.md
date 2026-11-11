---
name: inheritor
description: >
  Write and review code for the person who will read it later — usually the
  author, three months on, at 3am, with no memory of writing it. Use when code
  needs to be made maintainable, when a function's intent is unclear from its
  name, when comments restate the code, when error messages describe a failure
  without saying what to do about it, when a TODO has no owner or condition, or
  when asked to "make this readable" / "clean this up" / "explain what I wrote".
license: MIT
---

# inheritor

The person who reads this code is not the person who wrote it.

It is the same person, three months later, woken at 3am by a page, with no memory
of the decision that produced line 47. Every rule below exists because that person
cannot ask the author — the author is asleep.

Write for that person. It is the cheapest form of self-interest available.

## The test

Before writing or keeping a line, ask:

> If this breaks at 3am, does the code tell me what it was trying to do?

Code that passes answers three questions without a git archaeology session:

1. **What was this supposed to do?**
2. **What did the author assume that turned out to be false?**
3. **Where do I look next?**

Most code fails all three. Most code is also fixable in the same edit.

## Eight rules

### 1. Name for the search box, not for the author's head

A name is a search query someone will type in six months.

```python
# Fails: unfindable. Grepping "d" or "tmp" returns the entire codebase.
d = compute(ts, tmp)

# Passes: the name is the query.
retry_backoff_ms = compute_backoff(attempt_index, base_delay_ms)
```

If you cannot grep for it by name and land on the right place, the name is wrong.

### 2. Comments answer *why*. Code answers *what*.

```python
# Fails: the comment is a slower copy of the code.
i += 1          # increment i

# Passes: the comment carries a fact the code cannot.
page = (page - 1) * size    # API is 1-indexed; our storage is 0-indexed
```

A comment that survives deleting the line it describes was never a comment — it
was a substitute for a better name. Delete it and rename instead.

Keep comments for: external constraints, workarounds with a root cause, invariants
that are not locally verifiable, and decisions that were obviously wrong until you
knew the reason.

### 3. Every number gets a source

A bare literal is a decision with its justification deleted.

```java
// Fails: why 1000? Who decided? Can I change it?
if (batch.size() > 1000) flush();

// Passes: the constraint is visible.
// 1000 is the vendor's documented max for a single write; over it returns 413.
static final int MAX_BATCH = 1000;
```

Timing constants, sizes, timeouts, retry counts, tolerances — all of them. If the
number came from a benchmark, name the benchmark.

### 4. An error message that cannot be acted on is not an error message

```python
# Fails: the reader knows something failed, not what to do.
raise Exception("Failed")

# Passes: what happened, where, and the next probe.
raise BillingTimeout(
    f"billing-api did not answer within {timeout}s "
    f"(account={account_id!r}); check the upstream health page, "
    f"then retry — this path is idempotent"
)
```

Include: the operation, the inputs that matter, and what the reader should check
next. Never include secrets in the interpolated values.

### 5. A TODO without a condition is a lie

```python
# Fails: nobody will ever know when this is safe to remove.
# TODO: fix this later

# Passes: the exit condition is testable.
# TODO: drop the retry loop once billing-api v2 ships idempotency keys
#       (tracked in TEAM-1234). Until then, duplicate charges are possible
#       on timeout, and this loop is what prevents them.
```

Every TODO needs: what is wrong, why it is not fixed now, and what makes it safe
to remove. If you cannot write the third part, you do not yet know the bug.

### 6. Give each module a map

A reader opening a file should learn, within the first ten lines, where the data
comes from, where it goes, and where to enter.

```python
"""Order reconciliation.

Entry point:  reconcile() — called once per hour by the scheduler.
Input:        orders table (source of truth) + payment gateway settlement report.
Output:       writes to the discrepancies table; never mutates orders.
Invariant:    a settled order's amount never changes — if it does, we stop and page.
"""
```

That header saves an hour. It costs two minutes.

### 7. The commit message explains why; the diff explains what

The diff already shows which lines changed. Repeating it wastes the only moment
someone has your full context.

```
# Fails: tells the reader what they can already see.
fix typo in config

# Passes: tells the reader what they cannot.
Increase pool size to 20 because 10 starved under concurrent uploads

Observed 3-8s waits on /upload when more than 8 workers were active; the pool
capped at 10 and the queue never drained. 20 is still under the 25-connection
limit enforced by the RDS proxy.
```

If the change is trivial and the reason is obvious, one line is enough. "Trivial"
means a reader would not wonder why.

### 8. Never leave an implicit contract

If a function assumes its input is sorted, non-empty, ASCII, or idempotent, that
assumption is part of the API whether or not it is written down. Unwritten
assumptions are the most expensive bugs to find, because nothing looks wrong.

```python
# Fails: the caller cannot know this mutates the argument.
def normalize(records):
    records.sort()
    return records

# Passes: the contract is in the signature and enforced.
def normalize(records: list[Record]) -> list[Record]:
    """Return a sorted copy. Does not mutate the input.

    Raises ValueError if any record lacks an 'id' field.
    """
    missing = [r for r in records if "id" not in r]
    if missing:
        raise ValueError(f"{len(missing)} records missing 'id'; first={missing[0]!r}")
    return sorted(records, key=lambda r: r["id"])
```

Type hints, docstring contracts, and input validation are three ways to write the
same sentence. Use whichever the codebase already speaks.

## Workflow

### 1. Find the debt

```
python scripts/inheritance-check.py --path src/
```

Reports, per file:

- bare numeric literals that are not assigned to a named constant
- comments that restate the following line
- TODO/FIXME without a condition, owner or issue reference
- raise/throw with a message under 20 characters
- functions with no docstring whose name does not explain its contract
- error messages that do not name the operation

**Language coverage.** Rules 1, 4, 6 and 8 need a Python AST and run on `.py` only.
The TODO rule reads comments directly, so it also covers `.java`, `.ts`, `.tsx`,
`.js`, `.jsx`, `.go`, `.rs`, `.c`, `.h`, `.cpp`, `.hpp`, `.cs`, `.kt` and `.swift`
— comments only, not code. When reviewing a non-Python file, apply rules 1, 4, 6
and 8 by reading, and never claim the checker verified them.

### 2. Fix by evidence, not by taste

For each finding, the question is not "is this ugly" but "can a reader recover the
intent". A clever one-liner with a clear name and one honest comment beats a
six-line expansion nobody can follow.

Do not restructure working code to satisfy a rule. Add the missing fact.

### 3. Re-run

The check must come back clean for the files you touched. Do not fix the whole
codebase in one commit — the diff is the review unit, and a 40-file rename diff
gets rubber-stamped, not read.

## What this skill is not

It is not a formatter. Formatting is mechanical and tools already do it.

It is not a refactoring guide. Refactoring changes structure; this changes what a
future reader can learn from the structure that exists.

It is not a comment-density rule. More comments is not the goal — a comment that
restates the code is worse than none, because it will rot while looking
authoritative.

## Reference files

| File | Load when |
|---|---|
| `references/patterns.md` | you want before/after pairs for each of the eight rules |
| `references/checker-rules.md` | you need the exact machine-checkable rule set |
| `references/review-checklist.md` | you are reviewing someone else's PR |
