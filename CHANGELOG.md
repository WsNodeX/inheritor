# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-11-10

### Added

- `SKILL.md` with the eight rules, each with a concrete test rather than a
  preference.
- `scripts/inheritance-check.py` — stdlib-only, `ast` + `tokenize` based. Checks
  rules 1, 3, 4, 5, 8 mechanically; leaves 2, 6, 7 to review because they need
  judgement.
- Five client integrations: Claude Code (plugin + slash command), Codex, Cursor,
  Cline, Gemini CLI.
- `references/patterns.md` — seven before/after pairs from real failure shapes.
- Hero image as SVG so it diffs in review and needs no binary tooling.
- CI that runs the checker against itself and fails if it reports findings.

### Tuned during development

Three passes were needed to get the false-positive rate low enough that the tool is
actually usable. Recorded here because the numbers are the argument:

| Version | Findings on `ember` (13 files, healthy) | Problem |
|---|---|---|
| v1 | **50** | Rule 6 fired on every undocumented function, including `sqrt()` and `build()`. Rule 8 fired on private helpers mutating their own local lists. |
| v2 | 16 | Rule 6 now requires ≥2 unannotated parameters; rule 8 only checks public functions. |
| v3 | 16 | Rule 1 now skips slice bounds, indexing, `range()` args, keyword arguments, and UPPER_CASE assignments — literals whose meaning is positional, not policy. Findings on `readme-forge` dropped 20 → 3. |

**A checker that cries wolf gets ignored.** The v1 numbers would have made the tool
worthless regardless of how correct its rules were.

### Fixed

- Rule 3 matched the word `TODO` inside docstrings and string literals, so the
  checker reported two findings against its own file — the docstring documenting
  rule 3 contains the word. Now reads real COMMENT tokens via `tokenize`. Same class
  of bug as readme-forge's use-vs-mention problem: citing a rule is not violating it.

[1.0.0]: https://github.com/WsNodeX/inheritor/releases/tag/v1.0.0
