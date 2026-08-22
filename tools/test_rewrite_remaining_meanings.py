import unittest

from audit_quiz_bank_quality import load_rules
from rewrite_remaining_meanings import derive_consensus_meanings, rewrite_remaining


class RewriteRemainingMeaningsTest(unittest.TestCase):
    def setUp(self):
        self.rules = load_rules(__import__("pathlib").Path("lexicon/meaning_rules.v1.json"))

    def test_rewrites_high_confidence_specific_bible_relation(self):
        records = [
            {"key": "a", "question": {"word": "某王", "meaning": "南国犹大第一位王", "bookId": "2KI", "chapter": 1, "verse": 1}},
            {"key": "b", "question": {"word": "某王", "meaning": "南国犹大第一位王", "bookId": "2KI", "chapter": 1, "verse": 2}},
            {"key": "c", "question": {"word": "某王", "meaning": "南国犹大第一位王", "bookId": "2KI", "chapter": 1, "verse": 3}},
            {"key": "d", "question": {"word": "某王", "meaning": "专有名称或概念", "bookId": "2KI", "chapter": 1, "verse": 4}},
        ]
        consensus = derive_consensus_meanings(records)
        result = rewrite_remaining(records[-1:], consensus, self.rules)
        self.assertEqual(len(result.rewritten), 1)
        self.assertIn("南国犹大第一位王", result.rewritten[0]["question"]["meaning"])

    def test_skips_conflicting_meanings(self):
        records = [
            {"question": {"word": "同名", "meaning": "以色列的王", "bookId": "1SA", "chapter": 1, "verse": 1}},
            {"question": {"word": "同名", "meaning": "犹大的城", "bookId": "JOS", "chapter": 1, "verse": 1}},
            {"question": {"word": "同名", "meaning": "以色列的王", "bookId": "1SA", "chapter": 1, "verse": 2}},
        ]
        self.assertNotIn("同名", derive_consensus_meanings(records))


if __name__ == "__main__":
    unittest.main()
