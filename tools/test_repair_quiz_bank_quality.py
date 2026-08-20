#!/usr/bin/env python3
"""Tests for deterministic quiz-word and meaning repair."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from quiz_lexicon import LexiconTerm
from repair_quiz_bank_quality import repair_questions, write_repair_report


TERMS = (
    LexiconTerm(
        term="法利赛人",
        aliases=(),
        kind="group",
        meaning="犹太教中重视律法传统的宗教群体成员",
        source="test",
    ),
)
RULES = {"forbiddenExactMeanings": ["人名", "地名"]}


def question(word: str, start: int, end: int, *, meaning: str = "具体含义") -> dict[str, object]:
    return {
        "translationId": "cmn-cu89s",
        "bookId": "MAT",
        "chapter": 23,
        "verse": 1,
        "start": start,
        "end": end,
        "word": word,
        "partOfSpeech": "名词",
        "meaning": meaning,
        "reference": "马太福音 23:1",
    }


class RepairQuizBankQualityTest(unittest.TestCase):
    def test_unambiguous_fragment_is_repaired(self) -> None:
        result = repair_questions(
            [question("们法", 1, 3)], {"MAT:23:1": "你们法利赛人"}, TERMS, RULES
        )

        self.assertEqual(result.published[0]["word"], "法利赛人")
        self.assertEqual(
            result.published[0]["meaning"],
            "犹太教中重视律法传统的宗教群体成员",
        )
        self.assertEqual(result.repaired, 1)

    def test_bare_generic_meaning_is_removed(self) -> None:
        result = repair_questions(
            [question("城", 0, 1, meaning="地名")], {"MAT:23:1": "城"}, TERMS, RULES
        )

        self.assertEqual(result.published, [])
        self.assertEqual(result.omitted, 1)

    def test_full_lexicon_term_replaces_an_answer_leaking_meaning(self) -> None:
        result = repair_questions(
            [question("法利赛人", 2, 6, meaning="法利赛人的宗教群体")],
            {"MAT:23:1": "你们法利赛人"},
            TERMS,
            RULES,
        )

        self.assertEqual(result.published[0]["meaning"], TERMS[0].meaning)
        self.assertEqual(result.repaired, 1)

    def test_repair_report_writes_json_and_markdown_events(self) -> None:
        result = repair_questions(
            [question("城", 0, 1, meaning="地名")], {"MAT:23:1": "城"}, TERMS, RULES
        )
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "quality.json"

            write_repair_report(result, report)

            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))[0]["action"], "omitted")
            self.assertTrue(report.with_suffix(".md").is_file())


if __name__ == "__main__":
    unittest.main()
