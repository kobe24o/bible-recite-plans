#!/usr/bin/env python3
"""Regression checks for restoring all safe quiz candidates."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class QuizBankRestorationTest(unittest.TestCase):
    def test_bank_preserves_all_pre_sanitization_candidates(self) -> None:
        root = json.loads(Path("quiz-bank.json").read_text(encoding="utf-8"))
        questions = root["questions"]

        self.assertEqual(62_025, len(questions))
        self.assertTrue(
            all(str(question["word"]) not in str(question["meaning"]) for question in questions),
        )


if __name__ == "__main__":
    unittest.main()
