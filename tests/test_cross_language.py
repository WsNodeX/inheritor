#!/usr/bin/env python3
"""
Tests for the cross-language comment scan.

The point of these tests is the false-positive side, not the true-positive side.
Finding a real marker is easy; not finding `"http://x"`, `"// TODO"` inside a
string, or a marker that already names its exit condition is what makes the check
usable.

Fixtures live under tests/fixtures/, which the scanner skips when walking a tree
(test data contains violations on purpose). So the discovery tests copy fixtures
into a temporary directory rather than scanning them in place.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
FIXTURES = HERE / "fixtures" / "cross-language"

# Line numbers asserted below, named so the file passes its own rule 1.
JAVA_UNGUARDED = 8
JAVA_DATED = 12
JAVA_FIXME = 16
JAVA_ISSUE = 20
JAVA_STRING_URL = 3
JAVA_STRING_BLOCK = 6
JAVA_PRINTED = 26

TS_UNGUARDED = 1
TS_ISSUED = 4
TS_FIXME = 7
TS_TEMPLATE = 10
TS_URL = 11

# Two blank lines, then a block comment that opens on the third line.
BLOCK_COMMENT_OPENS_ON = 3


def load_checker():
    spec = importlib.util.spec_from_file_location("inheritance_check", SCRIPTS / "inheritance-check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ic = load_checker()


def lines_for(name: str) -> list[int]:
    path = FIXTURES / name
    return [f.line for f in ic.check_todos(path, path.name)]


class TestJavaComments(unittest.TestCase):
    def test_reports_unexplained_marker(self):
        self.assertIn(JAVA_UNGUARDED, lines_for("Sample.java"))

    def test_reports_ownerless_fixme(self):
        self.assertIn(JAVA_FIXME, lines_for("Sample.java"))

    def test_skips_marker_with_date(self):
        self.assertNotIn(JAVA_DATED, lines_for("Sample.java"),
                         "a marker naming a date has an exit condition")

    def test_skips_marker_with_issue_ref(self):
        self.assertNotIn(JAVA_ISSUE, lines_for("Sample.java"),
                         "a marker citing an issue number has an exit condition")

    def test_ignores_line_comment_inside_string(self):
        self.assertNotIn(JAVA_STRING_URL, lines_for("Sample.java"),
                         '"http://..." contains // but is not a comment')

    def test_ignores_block_comment_inside_string(self):
        self.assertNotIn(JAVA_STRING_BLOCK, lines_for("Sample.java"),
                         '"/* ... */" is a string, not a block comment')

    def test_ignores_marker_inside_printed_string(self):
        self.assertNotIn(JAVA_PRINTED, lines_for("Sample.java"),
                         "a printed string containing the marker is not a comment")


class TestTypeScriptComments(unittest.TestCase):
    def test_reports_unexplained_marker(self):
        self.assertIn(TS_UNGUARDED, lines_for("sample.ts"))

    def test_reports_ownerless_fixme(self):
        self.assertIn(TS_FIXME, lines_for("sample.ts"))

    def test_skips_marker_with_issue_ref(self):
        self.assertNotIn(TS_ISSUED, lines_for("sample.ts"))

    def test_ignores_template_literal(self):
        self.assertNotIn(TS_TEMPLATE, lines_for("sample.ts"),
                         "a backtick string containing the marker is not a comment")

    def test_ignores_url(self):
        self.assertNotIn(TS_URL, lines_for("sample.ts"),
                         '"https://example.com//not-a-comment" has no comment')


class TestBlockCommentLineNumber(unittest.TestCase):
    def test_reports_opening_line(self):
        source = "\n\n/*\n * TODO: spans lines\n */\n"
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "block.ts"
            path.write_text(source, encoding="utf-8")
            found = ic.check_todos(path, "block.ts")
            self.assertEqual([f.line for f in found], [BLOCK_COMMENT_OPENS_ON],
                             "a multi-line block comment reports the line it opens on")


class TestSourceDiscovery(unittest.TestCase):
    def test_picks_up_multiple_languages(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            shutil.copy(FIXTURES / "Sample.java", tmp / "Sample.java")
            shutil.copy(FIXTURES / "sample.ts", tmp / "sample.ts")
            names = {p.name for p in ic.iter_sources(tmp)}
            self.assertIn("Sample.java", names)
            self.assertIn("sample.ts", names)

    def test_skips_declarations_and_minified_output(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            for name in ("a.d.ts", "b.min.js", "c.tsx", "d.rs"):
                (tmp / name).write_text("// TODO: x\n", encoding="utf-8")
            names = {p.name for p in ic.iter_sources(tmp)}
            self.assertNotIn("a.d.ts", names, "type declarations are not hand-written prose")
            self.assertNotIn("b.min.js", names, "minified output is generated, not read")
            self.assertIn("c.tsx", names)
            self.assertIn("d.rs", names)

    def test_fixtures_directory_is_not_scanned(self):
        names = {p.name for p in ic.iter_sources(ROOT)}
        self.assertNotIn("Sample.java", names,
                         "test data contains violations on purpose and must be skipped")


class TestSelfCheck(unittest.TestCase):
    def test_checker_reports_nothing_against_itself(self):
        """The tool is held to its own rule 3 — its own comments must survive."""
        total = 0
        for path in ic.iter_sources(ROOT):
            if path.suffix.lower() in ic.PY_SUFFIXES:
                total += len(ic.check_todos(path, str(path)))
        self.assertEqual(total, 0, "the checker must not report itself")


if __name__ == "__main__":
    unittest.main(verbosity=2)
