#!/usr/bin/env python3
"""Import manually authored (human/LLM) questions into the quiz bank.

Reads a batch JSON file, one entry per verse:

  [{"reference": "13:1", "word": "老迈", "partOfSpeech": "形容词", "meaning": "老迈：年老体衰"}, ...]

The word must be a real, contiguous UTF-16 slice of the verse in the bundled
scripture: start/end are located in the source text and every validation rule
from generate_quiz_bank.py is re-applied locally. Only questions that pass are
merged; the first occurrence of a position wins (same rule as
merge_quiz_banks.py). No scripture text is ever written into the bank.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_quiz_bank import (  # noqa: E402
    load_bank,
    question_key,
    query_verses,
    utf16_length,
    utf16_slice,
    validate,
    write_bank,
    write_progress,
)


def find_word_offsets(text: str, word: str) -> tuple[int, int] | None:
    index = text.find(word)
    if index < 0:
        return None
    start = utf16_length(text[:index])
    end = start + utf16_length(word)
    if utf16_slice(text, start, end) != word:
        return None
    return start, end


def main() -> None:
    parser = argparse.ArgumentParser(description="把人工/LLM 生成的题目导入题库")
    parser.add_argument("--batch", required=True, type=Path, help="题目批次 JSON")
    parser.add_argument("--scripture", type=Path, default=Path("scripture/cmn-cu89s/scripture.sqlite"))
    parser.add_argument("--output", type=Path, default=Path("quiz-bank.json"))
    parser.add_argument("--progress", type=Path, default=Path("tools/generation_progress.json"))
    parser.add_argument("--book", required=True, help="OSIS 卷名，例如 2KI")
    parser.add_argument("--translation-id", default="cmn-cu89s")
    args = parser.parse_args()

    entries = json.loads(args.batch.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise SystemExit("batch 必须是数组")

    verses = query_verses(args.scripture, args.book, None, None, None)
    for verse in verses:
        verse["reference"] = f"{verse['chapter']}:{verse['verse']}"
    by_reference = {verse["reference"]: verse for verse in verses}

    items: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        reference = str(entry.get("reference", ""))
        word = str(entry.get("word", "")).strip()
        source = by_reference.get(reference)
        if source is None:
            print(f"跳过：{reference} 原文无此节")
            continue
        offsets = find_word_offsets(source["text"], word)
        if offsets is None:
            print(f"跳过：{reference} 原文中找不到词「{word}」")
            continue
        start, end = offsets
        items.append({
            "reference": reference,
            "start": start,
            "end": end,
            "length": end - start,
            "word": word,
            "partOfSpeech": str(entry.get("partOfSpeech", "")).strip(),
            "meaning": str(entry.get("meaning", "")).strip(),
        })

    valid = validate(items, verses, args.translation_id)
    accepted_refs = {question["reference"] for question in valid}
    for item in items:
        if item["reference"] not in accepted_refs:
            print(f"未通过校验：{item['reference']}「{item['word']}」")

    existing = load_bank(args.output)
    merged = {question_key(q): q for q in existing}
    added = 0
    for question in valid:
        key = question_key(question)
        if key not in merged:
            merged[key] = question
            added += 1
    write_bank(args.output, merged.values())

    bank_has = set(merged)
    last_contiguous = None
    for verse in verses:
        key = (args.translation_id, verse["book_id"], verse["chapter"], verse["verse"])
        if key in bank_has:
            last_contiguous = verse
        else:
            break
    if last_contiguous is not None:
        write_progress(args.progress, args.translation_id, last_contiguous)

    print(f"批次 {len(entries)} 条，新增 {added} 道，题库合计 {len(merged)} 道。")


if __name__ == "__main__":
    main()
