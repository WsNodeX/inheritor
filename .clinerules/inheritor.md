# inheritor

Write code for the person who reads it next — usually you, three months on, at 3am.

## Check first

```
python scripts/inheritance-check.py --path .
```

## Eight rules

1. Name for the search box, not for your head.
2. Comments answer why. Code answers what.
3. Every number gets a source.
4. An error message that cannot be acted on is not an error message.
5. A TODO without an exit condition is a lie.
6. Give each module a map: entry, inputs, outputs, invariants.
7. The commit message explains why; the diff explains what.
8. Never leave an implicit contract.

## Never

- Add a comment that restates the next line
- Invent the reason for a literal
- Fix the whole codebase in one commit

R1 (literals) and R6 (docstrings) are advisory. Fix the ones a reader would
actually stumble on.
