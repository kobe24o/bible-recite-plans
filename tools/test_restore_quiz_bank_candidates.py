#!/usr/bin/env python3
"""Tests for restoring removed candidates without retaining answer-leaking hints."""

from __future__ import annotations

import unittest

from restore_quiz_bank_candidates import restore_candidates


def question(*, word: str, start: int, meaning: str) -> dict[str, object]:
    return {
        "translationId": "cmn-cu89s",
        "bookId": "GEN",
        "chapter": 1,
        "verse": 1,
        "start": start,
        "end": start + len(word),
        "word": word,
        "partOfSpeech": "名词",
        "meaning": meaning,
        "reference": "1:1",
    }


class RestoreQuizBankCandidatesTest(unittest.TestCase):
    def test_restores_missing_candidate_with_a_safe_generic_meaning(self) -> None:
        retained = question(word="起初", start=0, meaning="开始的时候")
        removed = question(word="创造", start=3, meaning="上帝创造万物的动作")

        restored, changed = restore_candidates([retained], [retained, removed])

        self.assertEqual(1, changed)
        self.assertEqual([retained, {**removed, "meaning": "专有名称或概念"}], restored)
        self.assertNotIn(removed["word"], restored[1]["meaning"])

    def test_keeps_existing_question_and_does_not_duplicate_it(self) -> None:
        retained = question(word="起初", start=0, meaning="开始的时候")

        restored, changed = restore_candidates([retained], [retained])

        self.assertEqual(0, changed)
        self.assertEqual([retained], restored)


if __name__ == "__main__":
    unittest.main()
