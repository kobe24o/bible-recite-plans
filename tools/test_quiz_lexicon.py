#!/usr/bin/env python3
"""Regression tests for the versioned Bible term lexicon."""

from __future__ import annotations

import unittest

from quiz_lexicon import LexiconTerm, find_overlapping_terms, target_question_limit


TERMS = (
    LexiconTerm(
        term="以色列",
        aliases=(),
        kind="nation",
        meaning="雅各后裔形成的民族及其国家称谓",
        source="test",
    ),
    LexiconTerm(
        term="法利赛人",
        aliases=(),
        kind="group",
        meaning="犹太教中重视律法传统的宗教群体成员",
        source="test",
    ),
)


class QuizLexiconTest(unittest.TestCase):
    def test_suffix_candidate_finds_complete_israel_term(self) -> None:
        found = find_overlapping_terms("以色列人出埃及", 1, 3, TERMS)

        self.assertEqual(
            [(item.term.term, item.start, item.end) for item in found],
            [("以色列", 0, 3)],
        )

    def test_pronoun_prefixed_fragment_finds_complete_pharisee_term(self) -> None:
        found = find_overlapping_terms("你们法利赛人", 1, 3, TERMS)

        self.assertEqual(
            [(item.term.term, item.start, item.end) for item in found],
            [("法利赛人", 2, 6)],
        )

    def test_target_count_uses_every_length_band_and_caps_at_five(self) -> None:
        self.assertEqual(1, target_question_limit("短句"))
        self.assertEqual(1, target_question_limit("甲" * 19))
        self.assertEqual(2, target_question_limit("甲" * 20))
        self.assertEqual(3, target_question_limit("甲" * 40))
        self.assertEqual(4, target_question_limit("甲" * 70))
        self.assertEqual(5, target_question_limit("甲" * 100))
        self.assertEqual(5, target_question_limit("甲" * 120))


if __name__ == "__main__":
    unittest.main()
