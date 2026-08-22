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

    def test_jieba_detects_a_fragment_without_a_dictionary_entry(self) -> None:
        findings = audit_questions(
            [question("色列", 1, 3)],
            {"GEN:1:1": "以色列人出埃及"},
            (),
            RULES,
        )

        self.assertEqual(
            [(item.severity, item.code) for item in findings],
            [("critical", "partial_segmented_term")],
        )

    def test_jieba_does_not_reject_a_full_name_for_overlapping_short_tokens(self) -> None:
        findings = audit_questions(
            [question("玛土撒拉", 0, 4)],
            {"GEN:1:1": "玛土撒拉"},
            (),
            RULES,
        )

        self.assertEqual(findings, [])

    def test_jieba_does_not_reject_a_full_dictionary_term_before_a_particle(self) -> None:
        findings = audit_questions(
            [question("以色列", 0, 3)],
            {"GEN:1:1": "以色列的国"},
            TERMS,
            RULES,
        )

        self.assertEqual(findings, [])

    def test_jieba_rejects_a_word_crossing_token_boundaries(self) -> None:
        second = question("们厌", 1, 3)
        second["verse"] = 2
        findings = audit_questions(
            [
                question("谷之", 1, 3),
                second,
            ],
            {"GEN:1:1": "荒谷之间", "GEN:1:2": "他们厌恶我"},
            (),
            RULES,
        )

        self.assertEqual(
            [(item.severity, item.code) for item in findings],
            [
                ("critical", "partial_segmented_term"),
                ("critical", "partial_segmented_term"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
