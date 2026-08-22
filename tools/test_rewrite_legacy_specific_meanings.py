import unittest

from audit_quiz_bank_quality import load_rules
from rewrite_legacy_specific_meanings import rewrite_legacy_specific


class RewriteLegacySpecificMeaningsTest(unittest.TestCase):
    def test_expands_a_short_biblical_relation_without_leaking_answer(self):
        rules = load_rules(__import__("pathlib").Path("lexicon/meaning_rules.v1.json"))
        result = rewrite_legacy_specific(
            [{"key": "x", "question": {"word": "犹大", "meaning": "雅各第四子", "bookId": "GEN", "chapter": 29, "verse": 35}}],
            rules,
        )
        self.assertEqual(len(result.rewritten), 1)
        self.assertNotIn("犹大", result.rewritten[0]["question"]["meaning"])
        self.assertIn("第四个儿子", result.rewritten[0]["question"]["meaning"])

    def test_quarantines_unknown_or_leaking_template(self):
        rules = load_rules(__import__("pathlib").Path("lexicon/meaning_rules.v1.json"))
        result = rewrite_legacy_specific(
            [{"key": "x", "question": {"word": "未知", "meaning": "人名", "bookId": "GEN", "chapter": 1, "verse": 1}}],
            rules,
        )
        self.assertEqual(len(result.rewritten), 0)
        self.assertEqual(result.quarantine[0]["reasons"], ["no_legacy_specific_template"])


if __name__ == "__main__":
    unittest.main()
