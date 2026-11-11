#!/usr/bin/env python3
"""
inheritance-check — find the debt that costs the reader at 3am.

Checks the machine-verifiable half of the eight rules in
.agents/skills/inheritor/SKILL.md. The other half (naming, module maps,
commit messages) needs judgement and is left to review.

Rules checked:
  1  bare numeric literals that were never named
  3  TODO/FIXME with no exit condition or issue reference
  4  error messages too short to act on
  6  functions with no docstring and a name that does not state the contract
  8  functions that mutate an argument without saying so

Usage:
    python scripts/inheritance-check.py --path src/
    python scripts/inheritance-check.py --path . --json
    python scripts/inheritance-check.py --path . --strict

Exit codes: 0 = clean (or only warnings), 1 = findings over threshold.
Requires only the standard library.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Numbers that carry no decision worth documenting.
BENIGN_NUMBERS = {0, 1, 2, -1, 10, 100}

# A TODO is actionable when it names a condition or a tracker id.
EXIT_CONDITION = re.compile(
    r"\b(when|once|until|after|before|if|unless|blocked|switch|migrate)\b"
    r"|#[0-9]+|[A-Z]{2,}-[0-9]+",
    re.IGNORECASE,
)

MIN_ERROR_MESSAGE = 20

# Names that already state a contract.
SELF_DOCUMENTING = re.compile(
    r"^(__\w+__|_?\w{1,3})$"          # dunders and 1-3 char privates are exempt
)

SKIP_DIRS = {
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", ".venv", "venv", "build", "dist", "target", "site-packages",
    "examples",
    # Test fixtures contain the violations on purpose — scanning them reports the
    # test data as defects. Same reason `examples` is here.
    "fixtures",
}


class Finding:
    __slots__ = ("path", "line", "rule", "severity", "message", "snippet")

    def __init__(self, path, line, rule, severity, message, snippet=""):
        self.path = path
        self.line = line
        self.rule = rule
        self.severity = severity
        self.message = message
        self.snippet = snippet

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


# Extensions the text-level rules can read. Only rule 3 works without a parser;
# the other four need an AST and are Python-only. Claiming more would be a lie
# the tool cannot back up — and the comment above deliberately avoids naming the
# marker word, because this file is scanned by itself and would report it.
PY_SUFFIXES = {".py"}
C_STYLE_SUFFIXES = {".java", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".c", ".h", ".cpp", ".hpp", ".cs", ".kt", ".swift"}
SCAN_SUFFIXES = PY_SUFFIXES | C_STYLE_SUFFIXES


def iter_sources(root: Path):
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() not in SCAN_SUFFIXES:
            continue
        if SKIP_DIRS & set(p.parts):
            continue
        # A .d.ts or generated file is not something a person reads to understand
        # intent; skip the usual build-output suffixes.
        if p.name.endswith((".min.js", ".bundle.js", ".d.ts")):
            continue
        yield p


def c_style_comments(text: str) -> list[tuple[int, str]]:
    """
    Pull `//` and `/* */` comments out of a C-family source file.

    Written as a small state machine rather than a regex because a regex cannot
    tell a comment from the inside of a string: `url = "http://x"` contains `//`,
    and `s = "/* not a comment */"` contains a block-comment opener. Both appear
    constantly in real code, and both produce false positives if you scan lines.

    Returns (1-based line number, comment text) pairs.
    """
    out: list[tuple[int, str]] = []
    i = 0
    line = 1
    n = len(text)
    # Quote characters that start a string in this family of languages.
    quotes = "\"'`"

    while i < n:
        ch = text[i]

        if ch == "\n":
            line += 1
            i += 1
            continue

        # String literal: consume to its closing quote, honouring backslash escapes.
        if ch in quotes:
            q = ch
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == q:
                    i += 1
                    break
                if text[i] == "\n":
                    line += 1
                i += 1
            continue

        # Line comment.
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            start = i
            while i < n and text[i] != "\n":
                i += 1
            out.append((line, text[start:i]))
            continue

        # Block comment — may span lines.
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            start_line = line
            i += 2
            start = i
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                if text[i] == "\n":
                    line += 1
                i += 1
            out.append((start_line, text[start:i]))
            i += 2
            continue

        i += 1

    return out


def _literals_that_need_no_name(tree: ast.AST) -> set[int]:
    """
    Collect ids() of Constant nodes that are already contextualised.

    ast gives no parent pointers, so this pre-pass records every literal whose
    meaning is fixed by position rather than by a name:

      * slice bounds        text[:4]           -> the 4 is an offset, not a policy
      * indexing            cache[2]           -> positional
      * range() arguments   range(10)          -> loop bounds
      * keyword arguments   retries=3          -> the name is right there
      * UPPER_CASE assigns  MAX_RETRIES = 5    -> already a named constant

    Without this, every list slice and loop bound is reported and the tool is
    useless. The rule is about *unexplained decisions*, not about digits.
    """
    allowed: set[int] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            for sub in ast.walk(node.slice):
                if isinstance(sub, ast.Constant):
                    allowed.add(id(sub))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    for sub in ast.walk(node.value):
                        if isinstance(sub, ast.Constant):
                            allowed.add(id(sub))
        elif isinstance(node, ast.keyword):
            if node.value is not None:
                for sub in ast.walk(node.value):
                    if isinstance(sub, ast.Constant):
                        allowed.add(id(sub))
        elif isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
            if name in {"range", "enumerate", "zip", "round", "sleep", "Timeout"}:
                for arg in node.args:
                    for sub in ast.walk(arg):
                        if isinstance(sub, ast.Constant):
                            allowed.add(id(sub))

    return allowed


def check_bare_numbers(tree: ast.AST, path: str) -> list[Finding]:
    """Rule 1 — a literal no one named, in a position that carries a decision."""
    allowed = _literals_that_need_no_name(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        if id(node) in allowed:
            continue
        if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
            continue
        if node.value in BENIGN_NUMBERS:
            continue
        out.append(Finding(
            path, getattr(node, "lineno", 0), "R1", "warn",
            f"literal {node.value!r} decides behaviour — name it or say where it came from",
        ))
    return out


def check_todos(path: Path, rel: str) -> list[Finding]:
    """
    Rule 3 — a TODO with no exit condition.

    Python goes through real COMMENT tokens via tokenize. A line-based scan also
    matches the word TODO inside docstrings and string literals — including this
    file's own docstring, which explains the rule and would otherwise report
    itself. Citing a rule is not violating it.

    Every other supported language goes through c_style_comments(), which is the
    same idea implemented by hand: string literals are consumed before comments
    are looked for, so a URL in a string is not read as a comment.
    """
    out = []
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out

    if path.suffix.lower() in PY_SUFFIXES:
        import io
        import tokenize

        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        except (tokenize.TokenError, IndentationError):
            return out
        candidates = [(tok.start[0], tok.string) for tok in tokens if tok.type == tokenize.COMMENT]
    else:
        candidates = c_style_comments(source)

    for lineno, text in candidates:
        if not re.search(r"\b(TODO|FIXME|XXX|HACK)\b", text, re.IGNORECASE):
            continue
        if EXIT_CONDITION.search(text):
            continue
        out.append(Finding(
            rel, lineno, "R3", "warn",
            "TODO has no exit condition — add when it is safe to remove",
            text.strip()[:90],
        ))
    return out


def check_error_messages(tree: ast.AST, path: str) -> list[Finding]:
    """Rule 4 — an error message that cannot be acted on."""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        call = node.exc
        if not isinstance(call, ast.Call):
            continue
        if not call.args:
            msg = ""
        else:
            first = call.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                msg = first.value
            else:
                continue  # f-string or expression — assume it carries context
        if len(msg) < MIN_ERROR_MESSAGE:
            name = ""
            if isinstance(call.func, ast.Name):
                name = call.func.id
            elif isinstance(call.func, ast.Attribute):
                name = call.func.attr
            out.append(Finding(
                path, getattr(node, "lineno", 0), "R4", "warn",
                f"{name}({msg!r}) is too short to act on — say what happened "
                f"and what to check next",
            ))
    return out


def check_missing_docstring(tree: ast.AST, path: str) -> list[Finding]:
    """
    Rule 6 — a public function whose name does not state its contract.

    Deliberately conservative. Reporting every undocumented function produces
    dozens of hits on any healthy codebase, and a tool that cries wolf is
    ignored. Only flags functions that a reader must guess at: two or more
    parameters, no type annotations, no docstring, public name.
    """
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        if SELF_DOCUMENTING.match(node.name):
            continue
        if ast.get_docstring(node):
            continue
        params = [a for a in node.args.args + node.args.kwonlyargs if a.arg != "self"]
        if len(params) < 2:
            continue
        annotated = sum(1 for a in params if a.annotation is not None)
        if annotated == len(params):
            continue  # the signature already states the contract
        out.append(Finding(
            path, node.lineno, "R6", "warn",
            f"{node.name}() takes {len(params)} unannotated parameters and has no "
            f"docstring — a reader cannot tell what it assumes",
        ))
    return out


def check_unsignalled_mutation(tree: ast.AST, path: str) -> list[Finding]:
    """
    Rule 8 — mutating an argument without saying so.

    Only public functions. A private helper mutating its argument is an internal
    detail between two lines of the same file; a public one is a contract a
    caller can be surprised by.
    """
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        args = {a.arg for a in node.args.args + node.args.kwonlyargs}
        if not args:
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute):
                base = inner.func.value
                if isinstance(base, ast.Name) and base.id in args:
                    if inner.func.attr in {
                        "append", "extend", "insert", "remove", "pop", "clear",
                        "sort", "reverse", "update", "setdefault", "popitem",
                    }:
                        doc = ast.get_docstring(node) or ""
                        if "mutat" in doc.lower() or "in place" in doc.lower():
                            continue
                        out.append(Finding(
                            path, getattr(inner, "lineno", node.lineno), "R8", "warn",
                            f"{node.name}() mutates argument "
                            f"{base.id!r} via .{inner.func.attr}() — say so in "
                            f"the docstring, or copy first",
                        ))
    return out


def analyze(path: Path, rel: str) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(check_todos(path, rel))

    # Rules 1, 4, 6 and 8 need an AST. For a non-Python file the text-level rule
    # above is the whole check — saying so is part of the report, not a footnote.
    if path.suffix.lower() not in PY_SUFFIXES:
        return findings

    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except SyntaxError as e:
        return findings + [Finding(rel, e.lineno or 0, "SYNTAX", "fail", f"cannot parse: {e.msg}")]
    findings.extend(check_bare_numbers(tree, rel))
    findings.extend(check_error_messages(tree, rel))
    findings.extend(check_missing_docstring(tree, rel))
    findings.extend(check_unsignalled_mutation(tree, rel))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description="Find code debt that hurts the next reader")
    ap.add_argument("--path", default=".", help="file or directory to scan")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="warnings also fail")
    ap.add_argument("--max-warn", type=int, default=10_000,
                    help="exit 1 if warnings exceed this (default: never)")
    args = ap.parse_args()

    root = Path(args.path).resolve()
    files = [root] if root.is_file() else list(iter_sources(root))
    if not files:
        print("[ERR] no Python files found", file=sys.stderr)
        return 1

    findings: list[Finding] = []
    for f in files:
        rel = str(f.relative_to(root)) if f != root else f.name
        findings.extend(analyze(f, rel))

    if args.json:
        print(json.dumps([f.as_dict() for f in findings], ensure_ascii=False, indent=2))
    else:
        by_rule: dict[str, int] = {}
        for f in findings:
            by_rule[f.rule] = by_rule.get(f.rule, 0) + 1
            print(f"{f.path}:{f.line}  [{f.rule}] {f.message}")
            if f.snippet:
                print(f"    {f.snippet}")
        fails = [f for f in findings if f.severity == "fail"]
        warns = [f for f in findings if f.severity == "warn"]
        print()
        print(f"{len(files)} files · {len(fails)} fail · {len(warns)} warn")
        if by_rule:
            print("by rule: " + "  ".join(f"{k}={v}" for k, v in sorted(by_rule.items())))
        if warns:
            print("\nR1 literals and R6 docstrings are advisory — fix the ones a reader")
            print("would actually stumble on. Blanket-fixing produces noise.")

    if any(f.severity == "fail" for f in findings):
        return 1
    if args.strict and findings:
        return 1
    if len([f for f in findings if f.severity == "warn"]) > args.max_warn:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
