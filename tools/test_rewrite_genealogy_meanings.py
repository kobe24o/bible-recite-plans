import unittest

from rewrite_genealogy_meanings import infer_genealogy_meaning


class RewriteGenealogyMeaningsTest(unittest.TestCase):
    def test_extracts_parent_from_explicit_son_relation(self):
        meaning = infer_genealogy_meaning("塞特", "亚当生塞特；塞特生以挪士；")
        self.assertEqual(meaning, "亚当的后代，家谱中承接父系传承")

    def test_extracts_named_parent_from_son_list(self):
        meaning = infer_genealogy_meaning("歌篾", "雅弗的儿子是歌篾、玛各、玛代。")
        self.assertEqual(meaning, "雅弗的后代，家谱中承接父系传承")

    def test_ignores_a_verse_without_a_genealogy_relation(self):
        self.assertIsNone(infer_genealogy_meaning("耶稣", "耶稣在加利利教训众人。"))


if __name__ == "__main__":
    unittest.main()
