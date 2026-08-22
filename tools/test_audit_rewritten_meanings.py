#!/usr/bin/env python3
"""Tests for accepting only specific, fact-backed rewritten meanings."""

from __future__ import annotations

import unittest

from audit_rewritten_meanings import audit_rewrite
from bible_context import ContextFact
from rewrite_historical_quiz_meanings import RewriteDraft


RULES = {
    "forbiddenExactMeanings": ["人名", "地名"],
    "forbiddenGenericPatterns": ["人名", "地名", "人物", "地点", "专名", "某人", "某地"],
    "minimumMeaningChars": 6,
}
JERUSALEM = ContextFact(
    term="耶路撒冷",
    kind="place",
    facts=("犹大地区的圣城，所罗门曾在此建造圣殿",),
    references=("1KI:6:1",),
    source="test",
)


def question(word: str) -> dict[str, object]:
    return {"word": word, "translationId": "cmn-cu89s", "bookId": "JHN", "chapter": 2, "verse": 13, "start": 0, "end": len(word)}


class AuditRewrittenMeaningsTest(unittest.TestCase):
    def test_rejects_answer_leak_and_bare_category(self) -> None:
        leaking = audit_rewrite(
            question("耶路撒冷"),
            RewriteDraft("key", "耶路撒冷的城市", "context", ("1KI:6:1",)),
            RULES,
            JERUSALEM,
        )
        generic = audit_rewrite(
            question("耶路撒冷"),
            RewriteDraft("key", "重要地名", "context", ("1KI:6:1",)),
            RULES,
            JERUSALEM,
        )

        self.assertEqual(leaking.reasons, ("answer_leak",))
        self.assertEqual(generic.reasons, ("generic_meaning",))

    def test_accepts_a_specific_fact_backed_place_meaning(self) -> None:
        result = audit_rewrite(
            question("耶路撒冷"),
            RewriteDraft("key", "犹大地区设立圣殿敬拜的圣城", "context", ("1KI:6:1",)),
            RULES,
            JERUSALEM,
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.reasons, ())


if __name__ == "__main__":
    unittest.main()
