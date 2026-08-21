#!/usr/bin/env python3
"""Tests for versioned Bible context facts used in meaning rewrites."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from bible_context import load_context_facts


def write_context(payload: dict[str, object], directory: Path) -> Path:
    path = directory / "context.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


class BibleContextTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)

    def test_rejects_a_bare_category_without_reference(self) -> None:
        path = write_context(
            {
                "format": "bible-recite-bible-context",
                "version": 1,
                "entries": [{"term": "某城", "kind": "place", "facts": ["地名"], "references": [], "source": "test"}],
            }, self.directory
        )

        with self.assertRaisesRegex(ValueError, "具体事实"):
            load_context_facts(path)

    def test_resolves_aliases_to_a_specific_fact_with_reference(self) -> None:
        path = write_context(
            {
                "format": "bible-recite-bible-context",
                "version": 1,
                "entries": [
                    {
                        "term": "法利赛人",
                        "aliases": ["法利赛派"],
                        "kind": "group",
                        "facts": ["新约中重视口传传统的犹太宗教群体"],
                        "references": ["MRK:7:3"],
                        "source": "test",
                    }
                ],
            }, self.directory
        )

        facts = load_context_facts(path)

        self.assertEqual(facts["法利赛派"].kind, "group")
        self.assertEqual(facts["法利赛人"].references, ("MRK:7:3",))


if __name__ == "__main__":
    unittest.main()
