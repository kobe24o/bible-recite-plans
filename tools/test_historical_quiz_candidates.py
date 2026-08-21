#!/usr/bin/env python3
"""Tests for high-confidence historical quiz word candidates."""

from __future__ import annotations

import unittest

from historical_quiz_candidates import classify_question
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


class HistoricalQuizCandidatesTest(unittest.TestCase):
    def test_accepts_a_complete_dictionary_term_at_its_exact_position(self) -> None:
        decision = classify_question(
            question("以色列", 0, 3), {"GEN:1:1": "以色列人"}, TERMS, RULES
        )

        self.assertTrue(decision.accepted)
        self.assertEqual(decision.reasons, ())

    def test_quarantines_a_fragment_of_a_dictionary_term(self) -> None:
        decision = classify_question(
            question("色列", 1, 3), {"GEN:1:1": "以色列人"}, TERMS, RULES
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reasons, ("partial_lexicon_term",))

    def test_quarantines_a_word_whose_utf16_position_is_wrong(self) -> None:
        decision = classify_question(
            question("以色列", 1, 4), {"GEN:1:1": "以色列人"}, TERMS, RULES
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reasons, ("slice_mismatch",))

    def test_quarantines_a_function_word_even_when_its_position_is_exact(self) -> None:
        decision = classify_question(
            question("的", 2, 3), {"GEN:1:1": "神的国"}, TERMS, RULES
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reasons, ("function_word",))


if __name__ == "__main__":
    unittest.main()
