#!/usr/bin/env python3
"""Tests for the read-only historical quiz candidate review."""

from __future__ import annotations

import unittest

from quiz_lexicon import LexiconTerm
from review_historical_quiz_bank import review_candidates


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


def question(word: str, start: int, end: int) -> dict[str, object]:
    return {
        "translationId": "cmn-cu89s",
        "bookId": "GEN",
        "chapter": 1,
        "verse": 1,
        "start": start,
        "end": end,
        "word": word,
        "partOfSpeech": "名词",
        "meaning": "旧释义",
        "reference": "创世记 1:1",
    }


class ReviewHistoricalQuizBankTest(unittest.TestCase):
    def test_assigns_each_question_to_candidate_or_quarantine_once(self) -> None:
        result = review_candidates(
            [question("以色列", 0, 3), question("色列", 1, 3)],
            {"GEN:1:1": "以色列人"},
            TERMS,
            RULES,
        )

        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(result.quarantine_count, 1)
        self.assertEqual(result.quarantine[0]["reasons"], ["partial_lexicon_term"])

    def test_quarantines_a_later_duplicate_position(self) -> None:
        result = review_candidates(
            [question("以色列", 0, 3), question("以色列", 0, 3)],
            {"GEN:1:1": "以色列人"},
            TERMS,
            RULES,
        )

        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(result.quarantine_count, 1)
        self.assertEqual(result.quarantine[0]["reasons"], ["duplicate_position"])


if __name__ == "__main__":
    unittest.main()
