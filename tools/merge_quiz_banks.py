#!/usr/bin/env python3
"""Merge BibleRecite quiz-bank JSON files without carrying scripture text.

The first occurrence of a translation/book/chapter/verse/start/end position
wins. Version 1 exports are accepted, but their verseText field is ignored.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FORMAT = "bible-recite-quiz-bank"
VERSION = 2


def compact_meaning(word: str, meaning: str) -> str:
    value = meaning.strip()
    for prefix in (f"{word}：", f"{word}:", f"【{word}】：", f"【{word}】:"):
        if value.startswith(prefix):
            return value[len(prefix) :].strip()
    return value


def read_bank(path: Path) -> list[dict[str, Any]]:
    root = json.loads(path.read_text(encoding="utf-8"))
    if root.get("format") != FORMAT or root.get("version") not in (1, 2):
        raise ValueError(f"{path} 不是 BibleRecite 题库")
    questions = root.get("questions")
    if not isinstance(questions, list):
        raise ValueError(f"{path} questions 无效")
    result: list[dict[str, Any]] = []
    required = (
        "translationId", "bookId", "chapter", "verse", "start", "end",
        "word", "partOfSpeech", "meaning", "reference",
    )
    for item in questions:
        if not isinstance(item, dict) or any(name not in item for name in required):
            raise ValueError(f"{path} 含有格式不完整的题目")
        start, end = item["start"], item["end"]
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
            raise ValueError(f"{path} 含有无效题目位置")
        word = str(item["word"]).strip()
        if not word:
            raise ValueError(f"{path} 含有空答案")
        meaning = compact_meaning(word, str(item["meaning"]))
        if not meaning or word in meaning:
            raise ValueError(f"{path} 的 meaning 不得包含答案词：{word}")
        result.append({
            "translationId": str(item["translationId"]).strip(),
            "bookId": str(item["bookId"]).strip(),
            "chapter": int(item["chapter"]),
            "verse": int(item["verse"]),
            "start": start,
            "end": end,
            "word": word,
            "partOfSpeech": str(item["partOfSpeech"]).strip(),
            "meaning": meaning,
            "reference": str(item["reference"]).strip(),
        })
    return result


def key(question: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(question[name] for name in (
        "translationId", "bookId", "chapter", "verse", "start", "end",
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description="合并 BibleRecite 题库并去重")
    parser.add_argument("inputs", nargs="+", type=Path, help="一个或多个题库 JSON")
    parser.add_argument("-o", "--output", required=True, type=Path)
    args = parser.parse_args()

    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    total = 0
    for path in args.inputs:
        questions = read_bank(path)
        total += len(questions)
        for question in questions:
            merged.setdefault(key(question), question)
    ordered = sorted(merged.values(), key=key)
    args.output.write_bytes((
        json.dumps({"format": FORMAT, "version": VERSION, "questions": ordered}, ensure_ascii=False, indent=2)
        + "\n"
    ).encode("utf-8"))
    print(f"输入 {total} 道，保留 {len(ordered)} 道，去重 {total - len(ordered)} 道：{args.output}")


if __name__ == "__main__":
    main()
