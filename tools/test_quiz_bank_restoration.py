#!/usr/bin/env python3
"""Regression checks for restoring all safe quiz candidates."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class QuizBankRestorationTest(unittest.TestCase):
    def test_quality_snapshot_uses_all_index_shards_without_answer_leaks(self) -> None:
        index = json.loads(Path("quiz-bank.index.json").read_text(encoding="utf-8"))
        questions = [
            question
            for shard in index["shards"]
            for question in json.loads(Path(shard["path"]).read_text(encoding="utf-8"))["questions"]
        ]

        self.assertEqual(60_598, len(questions))
        self.assertTrue(
            all(str(question["word"]) not in str(question["meaning"]) for question in questions),
        )


if __name__ == "__main__":
    unittest.main()
