#!/usr/bin/env python3
"""Tests for stable, replacement-style quiz snapshot publishing."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from publish_quiz_snapshot import publish_snapshot


def question(word: str, start: int) -> dict[str, object]:
    return {
        "translationId": "cmn-cu89s",
        "bookId": "GEN",
        "chapter": 1,
        "verse": 1,
        "start": start,
        "end": start + len(word),
        "word": word,
        "partOfSpeech": "名词",
        "meaning": "具体含义",
        "reference": "创世记 1:1",
    }


BANK = {
    "format": "bible-recite-quiz-bank",
    "version": 2,
    "questions": [question("起初", 0), question("创造", 3)],
}


class PublishQuizSnapshotTest(unittest.TestCase):
    def test_snapshot_has_replace_metadata_and_small_shards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            manifest = publish_snapshot(BANK, root, root / "quiz-bank.index.json", revision=702, max_bytes=4096)

            self.assertEqual(manifest["snapshotMode"], "replace")
            self.assertEqual(manifest["qualityVersion"], 3)
            self.assertTrue(manifest["shards"])
            self.assertTrue(all((root / item["path"]).stat().st_size < 4096 for item in manifest["shards"]))

    def test_snapshot_rejects_reused_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = root / "quiz-bank.index.json"
            index.write_text(json.dumps({"revision": 702}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "must exceed"):
                publish_snapshot(BANK, root, index, revision=702)

    def test_snapshot_rejects_an_over_limit_single_question_and_removes_stale_shard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stale = root / "quiz-bank-99.json"
            stale.write_text("old", encoding="utf-8")
            manifest = publish_snapshot(BANK, root, root / "quiz-bank.index.json", revision=702, max_bytes=4096)
            self.assertFalse(stale.exists())

            oversized = {**BANK, "questions": [question("甲" * 1000, 0)]}
            with self.assertRaisesRegex(ValueError, "single question"):
                publish_snapshot(oversized, root, root / "other.index.json", revision=1, max_bytes=2048)
            self.assertTrue(all((root / item["path"]).exists() for item in manifest["shards"]))


if __name__ == "__main__":
    unittest.main()
