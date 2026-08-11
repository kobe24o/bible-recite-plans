#!/usr/bin/env python3
"""Validate BibleRecite quiz-bank data and optional source/index consistency."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

FORMAT = "bible-recite-quiz-bank"
FUNCTION_WORDS = {"的", "了", "着", "过", "吗", "呢", "啊", "呀", "和", "与", "及", "而", "但", "且", "或", "在", "把", "被", "给", "从", "向", "对", "以", "于", "是", "有", "就", "都", "也", "又", "很", "更", "还", "不", "没", "要", "会", "能", "之", "其", "这", "那", "等", "并", "则", "却", "才", "再", "便", "因", "为", "由", "到", "上", "下", "里", "中", "乃"}


def parse_translation(value: str) -> tuple[str, Path]:
    identifier, separator, location = value.partition("=")
    if not separator or not identifier or not location:
        raise argparse.ArgumentTypeError("格式应为译本ID=原文SQLite路径")
    return identifier, Path(location)


def slice_utf16(value: str, start: int, end: int) -> str | None:
    raw = value.encode("utf-16-le")
    if start < 0 or end <= start or end * 2 > len(raw):
        return None
    try:
        return raw[start * 2 : end * 2].decode("utf-16-le")
    except UnicodeDecodeError:
        return None


def git_bytes(path: Path) -> bytes:
    """Use the LF bytes GitHub serves rather than local CRLF checkout bytes."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def load_sources(specifications: list[tuple[str, Path]]) -> dict[str, dict[tuple[str, int, int], str]]:
    result: dict[str, dict[tuple[str, int, int], str]] = {}
    for identifier, path in specifications:
        with sqlite3.connect(path) as connection:
            result[identifier] = {
                (str(book), int(chapter), int(verse)): str(text)
                for book, chapter, verse, text in connection.execute("""
                    SELECT osis_book_id, chapter, start_verse, text
                    FROM verse_unit WHERE status = 'present' AND start_verse = end_verse
                """)
            }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="校验 BibleRecite 题库格式、去重与原文位置")
    parser.add_argument("--bank", type=Path, default=Path("quiz-bank.json"))
    parser.add_argument("--index", type=Path, help="同时校验索引中的大小与 SHA-256")
    parser.add_argument("--translation", type=parse_translation, action="append", help="可重复指定：译本ID=原文SQLite路径")
    args = parser.parse_args()
    root = json.loads(args.bank.read_text(encoding="utf-8"))
    errors: list[str] = []
    if root.get("format") != FORMAT or root.get("version") != 2:
        errors.append("题库必须是 bible-recite-quiz-bank v2")
    questions = root.get("questions")
    if not isinstance(questions, list):
        errors.append("questions 必须是数组")
        questions = []
    sources = load_sources(args.translation or [("cmn-cu89s", Path("scripture/cmn-cu89s/scripture.sqlite"))])
    seen: set[tuple[Any, ...]] = set()
    for index, question in enumerate(questions):
        prefix = f"第 {index + 1} 题"
        if not isinstance(question, dict):
            errors.append(f"{prefix} 不是对象")
            continue
        if "verseText" in question:
            errors.append(f"{prefix} 不得保存 verseText")
        try:
            translation, book = str(question["translationId"]), str(question["bookId"])
            chapter, verse = int(question["chapter"]), int(question["verse"])
            start, end = question["start"], question["end"]
            word, pos, meaning = str(question["word"]), str(question["partOfSpeech"]), str(question["meaning"])
            reference = str(question["reference"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{prefix} 缺少必填字段或字段类型无效")
            continue
        if not isinstance(start, int) or not isinstance(end, int) or chapter < 1 or verse < 1 or start < 0 or end <= start:
            errors.append(f"{prefix} 位置无效")
            continue
        key = (translation, book, chapter, verse, start, end)
        if key in seen:
            errors.append(f"{prefix} 与前题位置重复：{book} {chapter}:{verse} {start}-{end}")
        seen.add(key)
        if not word.strip() or not pos.strip() or not meaning.strip() or not reference.strip():
            errors.append(f"{prefix} 含空的答案、词性、解释或引用")
        if word.strip() in FUNCTION_WORDS:
            errors.append(f"{prefix} 答案是无意义功能词：{word}")
        if meaning.strip().startswith((f"{word}：", f"{word}:")):
            errors.append(f"{prefix} meaning 不得重复答案词前缀")
        source = sources.get(translation)
        if source is not None:
            text = source.get((book, chapter, verse))
            if text is None:
                errors.append(f"{prefix} 不在本机原文范围：{book} {chapter}:{verse}")
            elif slice_utf16(text, start, end) != word:
                errors.append(f"{prefix} UTF-16 位置与原文答案不一致：{book} {chapter}:{verse}")
    if args.index:
        index_root = json.loads(args.index.read_text(encoding="utf-8"))
        bank_bytes = git_bytes(args.bank)
        expected = next((item for item in index_root.get("shards", []) if item.get("path") == args.bank.as_posix()), None)
        if expected is None:
            errors.append("索引没有当前题库分片")
        else:
            digest = hashlib.sha256(bank_bytes).hexdigest()
            if expected.get("bytes") != len(bank_bytes) or expected.get("sha256") != digest:
                errors.append("索引的 bytes 或 SHA-256 与题库不一致")
    if errors:
        for error in errors:
            print(f"错误：{error}")
        raise SystemExit(1)
    print(f"校验通过：{len(questions)} 道题，{len(seen)} 个唯一位置。")


if __name__ == "__main__":
    main()
