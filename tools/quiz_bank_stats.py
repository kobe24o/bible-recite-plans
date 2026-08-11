#!/usr/bin/env python3
"""Report quiz coverage and question density for every supplied translation."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


def parse_translation(value: str) -> tuple[str, Path]:
    identifier, separator, location = value.partition("=")
    if not separator or not identifier or not location:
        raise argparse.ArgumentTypeError("格式应为译本ID=原文SQLite路径")
    return identifier, Path(location)


def load_bank(path: Path) -> list[dict[str, Any]]:
    root = json.loads(path.read_text(encoding="utf-8"))
    if root.get("format") != "bible-recite-quiz-bank" or root.get("version") not in (1, 2):
        raise ValueError(f"{path} 不是 BibleRecite 题库")
    questions = root.get("questions")
    if not isinstance(questions, list):
        raise ValueError("questions 无效")
    return [item for item in questions if isinstance(item, dict)]


def source_verses(database: Path) -> set[tuple[str, int, int]]:
    with sqlite3.connect(database) as connection:
        return {
            (str(book), int(chapter), int(verse))
            for book, chapter, verse in connection.execute("""
                SELECT osis_book_id, chapter, start_verse
                FROM verse_unit
                WHERE status = 'present' AND start_verse = end_verse
            """)
        }


def make_stats(identifier: str, database: Path, questions: list[dict[str, Any]]) -> dict[str, Any]:
    verses = source_verses(database)
    counts: Counter[tuple[str, int, int]] = Counter()
    invalid = 0
    for question in questions:
        if question.get("translationId") != identifier:
            continue
        try:
            key = (str(question["bookId"]), int(question["chapter"]), int(question["verse"]))
        except (KeyError, TypeError, ValueError):
            invalid += 1
            continue
        if key not in verses:
            invalid += 1
            continue
        counts[key] += 1
    total = len(verses)
    covered = len(counts)
    total_questions = sum(counts.values())
    return {
        "translationId": identifier,
        "source": str(database),
        "availableVerses": total,
        "coveredVerses": covered,
        "coverage": 0 if total == 0 else covered / total,
        "questions": total_questions,
        "averageQuestionsPerAllVerse": 0 if total == 0 else total_questions / total,
        "averageQuestionsPerCoveredVerse": 0 if covered == 0 else total_questions / covered,
        "versesWithFiveOrMoreQuestions": sum(1 for value in counts.values() if value >= 5),
        "questionsOutsideSource": invalid,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="统计 BibleRecite 题库节覆盖率与题目密度")
    parser.add_argument("--bank", type=Path, default=Path("quiz-bank.json"))
    parser.add_argument(
        "--translation", type=parse_translation, action="append",
        help="可重复指定：译本ID=原文SQLite路径；默认使用简体和合本",
    )
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = parser.parse_args()
    translations = args.translation or [
        ("cmn-cu89s", Path("scripture/cmn-cu89s/scripture.sqlite")),
    ]
    questions = load_bank(args.bank)
    report = [make_stats(identifier, source, questions) for identifier, source in translations]
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    for item in report:
        print(f"{item['translationId']}（{item['source']}）")
        print(f"  节覆盖率：{item['coveredVerses']}/{item['availableVerses']} ({item['coverage']:.2%})")
        print(f"  题目数：{item['questions']}；平均每节：{item['averageQuestionsPerAllVerse']:.3f}（全量） / {item['averageQuestionsPerCoveredVerse']:.3f}（已覆盖节）")
        print(f"  达到 5 题的节：{item['versesWithFiveOrMoreQuestions']}；原文范围外题目：{item['questionsOutsideSource']}")


if __name__ == "__main__":
    main()
