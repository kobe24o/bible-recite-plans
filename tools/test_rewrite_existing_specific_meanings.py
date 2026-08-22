import unittest

from audit_quiz_bank_quality import load_rules
from rewrite_existing_specific_meanings import rewrite_existing_specific


class RewriteExistingSpecificMeaningsTest(unittest.TestCase):
    def test_rewrites_a_specific_non_leaking_legacy_hint(self):
        result = rewrite_existing_specific(
            [{"key": "x", "question": {"word": "某词", "meaning": "大卫的谋士", "bookId": "2SA", "chapter": 1, "verse": 1}}],
            load_rules(__import__("pathlib").Path("lexicon/meaning_rules.v1.json")),
        )
        self.assertEqual(len(result.rewritten), 1)
        self.assertIn("大卫的谋士", result.rewritten[0]["question"]["meaning"])

    def test_rejects_generic_or_answer_leaking_hints(self):
        result = rewrite_existing_specific(
            [{"key": "a", "question": {"word": "未知", "meaning": "人名", "bookId": "GEN", "chapter": 1, "verse": 1}},
             {"key": "b", "question": {"word": "答案", "meaning": "答案的描述", "bookId": "GEN", "chapter": 1, "verse": 1}}],
            load_rules(__import__("pathlib").Path("lexicon/meaning_rules.v1.json")),
        )
        self.assertEqual(len(result.rewritten), 0)
        self.assertEqual(len(result.quarantine), 2)


if __name__ == "__main__":
    unittest.main()
