---
description: Find and fix code that withholds what a future reader needs
argument-hint: <path or file>
---

Load the `inheritor` skill from `.agents/skills/inheritor/SKILL.md` and apply it to: $ARGUMENTS

Work in this order:

1. **Run the checker first.** `python scripts/inheritance-check.py --path <path>`.
   Show the raw output. Do not start editing before I see it.
2. **Triage.** Group findings by rule. Say which ones a reader would actually
   stumble on and which are noise in this codebase. Be specific — "R1 at line 47
   decides a batch size, that matters; R1 at line 12 is a polynomial coefficient,
   that does not".
3. **Fix only what earns it.** For each real finding, add the missing fact — a
   name, a source for the number, an exit condition, an actionable message. Do not
   restructure working code.
4. **Re-run the checker** on the files you touched. Report before/after counts.

Hard rules:

- Never add a comment that restates the code. If the fix for an unclear line is a
  comment, the fix is usually a better name.
- Never invent the reason for a number. If you cannot find its source in the repo,
  git history, or the issue tracker, say so and ask — do not guess.
- Never fix the whole codebase in one commit. The diff is the review unit.

Show me the diff, not the whole file.
