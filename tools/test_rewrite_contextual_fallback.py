import unittest

from rewrite_contextual_fallback import classify_context


class RewriteContextualFallbackTest(unittest.TestCase):
    def test_genealogy_context_is_more_specific_than_a_generic_label(self):
        self.assertEqual(
            classify_context({"word": "塞特", "partOfSpeech": "名词"}, "亚当生塞特；"),
            "本节族系记录中的父系传承对象",
        )

    def test_worship_context_is_classified(self):
        self.assertEqual(
            classify_context({"word": "祭坛", "partOfSpeech": "名词"}, "祭司在会幕献祭。"),
            "本节礼仪场景中的相关角色或事物",
        )


if __name__ == "__main__":
    unittest.main()
