"""Remove questions the app's local scripture validator cannot import."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def slice_utf16(text: str, start: int, end: int) -> str | None:
    raw = text.encode("utf-16-le")
    if start < 0 or end <= start or end * 2 > len(raw):
        return None
    try:
        return raw[start * 2 : end * 2].decode("utf-16-le")
    except UnicodeDecodeError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="移除本机无法导入的题目")
    parser.add_argument("--bank", type=Path, default=Path("quiz-bank.json"))
    parser.add_argument(
        "--scripture",
        type=Path,
        default=Path("scripture/cmn-cu89s/scripture.sqlite"),
    )
    args = parser.parse_args()
    root: dict[str, Any] = json.loads(args.bank.read_text(encoding="utf-8"))
    questions = root.get("questions")
    if not isinstance(questions, list):
        raise SystemExit("questions 必须是数组")
    with sqlite3.connect(args.scripture) as connection:
        verses = {
            (str(book), int(chapter), int(verse)): str(text)
            for book, chapter, verse, text in connection.execute(
                """SELECT osis_book_id, chapter, start_verse, text
                   FROM verse_unit
                   WHERE status = 'present' AND start_verse = end_verse"""
            )
        }
    retained: list[dict[str, Any]] = []
    removed = 0
    for question in questions:
        if not isinstance(question, dict):
            raise SystemExit("题目必须是对象")
        if question.get("translationId") != "cmn-cu89s":
            retained.append(question)
            continue
        text = verses.get(
            (str(question.get("bookId")), int(question.get("chapter", 0)), int(question.get("verse", 0)))
        )
        if text is None or slice_utf16(text, int(question.get("start", -1)), int(question.get("end", -1))) != question.get("word"):
            removed += 1
            continue
        retained.append(question)
    root["questions"] = retained
    args.bank.write_bytes((json.dumps(root, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"保留 {len(retained)} 道，移除 {removed} 道本机无法导入的题目。")


if __name__ == "__main__":
    main()
