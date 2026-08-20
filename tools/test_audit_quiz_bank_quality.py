#!/usr/bin/env python3
"""Tests for rejecting incomplete words and generic meanings."""

from __future__ import annotations

import unittest

from audit_quiz_bank_quality import audit_questions
from quiz_lexicon import LexiconTerm


TERMS = (
    LexiconTerm(
        term="以色列",
        aliases=(),
        kind="nation",
        meaning="雅各后裔形成的民族及其国家称谓",
        source="test",
    ),
)
RULES = {"forbiddenExactMeanings": ["人名", "地名"]}


def question(word: str, start: int, end: int, *, meaning: str = "具体含义") -> dict[str, object]:
    return {
        "translationId": "cmn-cu89s",
        "bookId": "GEN",
        "chapter": 1,
        "verse": 1,
        "start": start,
        "end": end,
        "word": word,
        "partOfSpeech": "名词",
        "meaning": meaning,
        "reference": "创世记 1:1",
    }


class AuditQuizBankQualityTest(unittest.TestCase):
    def test_partial_name_is_critical(self) -> None:
        findings = audit_questions(
            [question("色列", 1, 3)], {"GEN:1:1": "以色列人"}, TERMS, RULES
        )

        self.assertEqual(
            [(item.severity, item.code) for item in findings],
            [("critical", "partial_lexicon_term")],
        )

    def test_bare_generic_meaning_is_critical(self) -> None:
        findings = audit_questions(
            [question("城", 0, 1, meaning=" 地名 ")], {"GEN:1:1": "城"}, TERMS, RULES
        )

        self.assertEqual(
            [(item.severity, item.code) for item in findings],
            [("critical", "generic_meaning")],
        )

    def test_answer_leaking_meaning_is_critical(self) -> None:
        findings = audit_questions(
            [question("以色列", 0, 3, meaning="以色列这个民族")],
            {"GEN:1:1": "以色列人"},
            TERMS,
            RULES,
        )

        self.assertEqual(
            [(item.severity, item.code) for item in findings],
            [("critical", "answer_leaking_meaning")],
        )


if __name__ == "__main__":
    unittest.main()
