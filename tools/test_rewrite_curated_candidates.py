#!/usr/bin/env python3
"""Tests for applying curated Bible facts to candidate questions."""

from __future__ import annotations

import unittest

from bible_context import ContextFact
from rewrite_curated_candidates import rewrite_candidates


FACTS = {
    "耶和华": ContextFact(
        "耶和华", "deity-name", ("以色列圣约中称呼独一真神的名字",), ("EXO:3:15",), "test"
    )
}
RULES = {
    "forbiddenExactMeanings": ["人名", "地名"],
    "forbiddenGenericPatterns": ["人名", "地名", "人物", "地点", "专名", "某人", "某地"],
    "minimumMeaningChars": 6,
}


def record(word: str, meaning: str = "旧释义") -> dict[str, object]:
    return {
        "key": f"cmn-cu89s:GEN:1:1:0:{len(word)}",
        "question": {
            "translationId": "cmn-cu89s",
            "bookId": "GEN",
            "chapter": 1,
            "verse": 1,
            "start": 0,
            "end": len(word),
            "word": word,
            "partOfSpeech": "名词",
            "meaning": meaning,
            "reference": "创世记 1:1",
        },
        "reasons": [],
    }


class RewriteCuratedCandidatesTest(unittest.TestCase):
    def test_rewrites_known_term_and_quarantines_unknown_term(self) -> None:
        result = rewrite_candidates([record("耶和华"), record("陌生词")], FACTS, RULES)

        self.assertEqual(len(result.rewritten), 1)
        self.assertEqual(result.rewritten[0]["question"]["meaning"], "以色列圣约中称呼独一真神的名字")
        self.assertEqual(result.quarantine[0]["reasons"], ["missing_context_fact"])


if __name__ == "__main__":
    unittest.main()
