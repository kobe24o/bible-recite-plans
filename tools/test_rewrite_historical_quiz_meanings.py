#!/usr/bin/env python3
"""Tests for fact-backed historical quiz meaning drafts."""

from __future__ import annotations

import unittest

from bible_context import ContextFact
from rewrite_historical_quiz_meanings import build_rewrite_prompt, deterministic_draft


def candidate(word: str) -> dict[str, object]:
    return {
        "translationId": "cmn-cu89s",
        "bookId": "MAT",
        "chapter": 23,
        "verse": 2,
        "start": 0,
        "end": len(word),
        "word": word,
        "partOfSpeech": "名词",
        "meaning": "旧释义",
        "reference": "马太福音 23:2",
    }


PHARISEES = ContextFact(
    term="法利赛人",
    kind="group",
    facts=("新约中重视口传传统的犹太宗教群体",),
    references=("MRK:7:3",),
    source="test",
)


class RewriteHistoricalQuizMeaningsTest(unittest.TestCase):
    def test_prompt_forbids_answer_and_requires_fact_backed_meaning(self) -> None:
        prompt = build_rewrite_prompt(candidate("法利赛人"), PHARISEES)

        self.assertIn("不得包含答案原文", prompt)
        self.assertIn("事实不足则返回 null", prompt)
        self.assertIn("MRK:7:3", prompt)

    def test_deterministic_draft_uses_specific_non_leaking_fact(self) -> None:
        draft = deterministic_draft(candidate("法利赛人"), PHARISEES)

        self.assertEqual(draft.source, "context")
        self.assertNotIn("法利赛人", draft.meaning)
        self.assertIn("犹太", draft.meaning)
        self.assertEqual(draft.evidence_references, ("MRK:7:3",))


if __name__ == "__main__":
    unittest.main()
