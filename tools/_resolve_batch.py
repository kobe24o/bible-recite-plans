#!/usr/bin/env python3
"""Local helper (not committed): resolve authored entries into a v2 batch.

Input JSON: a list of {"reference": "13:1", "word": "晓谕", "partOfSpeech":
"动词", "meaning": "晓谕：明白地告诉"}.  For each entry the word is located in
the bundled scripture at the first UTF-16 span that is NOT already used by
quiz-bank.json for that verse, then every rule from generate_quiz_bank.py is
applied.  Output: a v2 bank-format batch file ready for merge_quiz_banks.py.

Usage: python3 tools/_resolve_batch.py --input A.json --batch tools/batch_B.json --book NUM
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_quiz_bank import (  # noqa: E402
    is_meaning_for_word,
    is_valid_word,
    load_bank,
    query_verses,
    utf16_length,
    utf16_slice,
)

BATCH_FORMAT = "bible-recite-quiz-bank"
BATCH_VERSION = 2


def find_free_offsets(text: str, word: str, used: set[tuple[int, int]]) -> tuple[int, int] | None:
    needle = word
    search_from = 0
    while True:
        index = text.find(needle, search_from)
        if index < 0:
            return None
        start = utf16_length(text[:index])
        end = start + utf16_length(needle)
        if utf16_slice(text, start, end) == needle and (start, end) not in used and is_valid_word(needle):
            return start, end
        search_from = index + 1


def main() -> None:
    parser = argparse.ArgumentParser(description="把手工词条解析为 v2 批次文件")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--scripture", type=Path, default=Path("scripture/cmn-cu89s/scripture.sqlite"))
    parser.add_argument("--bank", type=Path, default=Path("quiz-bank.json"))
    parser.add_argument("--book", required=True, help="OSIS 卷名")
    parser.add_argument("--translation-id", default="cmn-cu89s")
    args = parser.parse_args()

    entries = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise SystemExit("input 必须是数组")

    existing = load_bank(args.bank)
    used: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for q in existing:
        if q["bookId"] == args.book:
            used.setdefault((q["chapter"], q["verse"]), []).append((q["start"], q["end"]))

    verses = query_verses(args.scripture, args.book, None, None, None)
    by_reference = {}
    for verse in verses:
        verse["reference"] = f"{verse['chapter']}:{verse['verse']}"
        by_reference[verse["reference"]] = verse

    accepted: list[dict[str, Any]] = []
    seen: set[str] = set()
    skipped: list[tuple[str, str]] = []
    for entry in entries:
        reference = str(entry.get("reference", ""))
        word = str(entry.get("word", "")).strip()
        pos = str(entry.get("partOfSpeech", "")).strip()
        meaning = str(entry.get("meaning", "")).strip()
        source = by_reference.get(reference)
        if source is None:
            skipped.append((reference, "原文无此节"))
            continue
        if reference in seen:
            skipped.append((reference, "重复"))
            continue
        if not word or not pos or not is_meaning_for_word(word, meaning):
            skipped.append((reference, f"字段不完整/释义无前缀 word:{word}"))
            continue
        used_set = set(used.get((source["chapter"], source["verse"]), []))
        offsets = find_free_offsets(source["text"], word, used_set)
        if offsets is None:
            skipped.append((reference, f"无空闲位置 word:{word}"))
            continue
        start, end = offsets
        accepted.append({
            "translationId": args.translation_id, "bookId": source["book_id"], "chapter": source["chapter"],
            "verse": source["verse"], "start": start, "end": end, "word": word,
            "partOfSpeech": pos, "meaning": meaning, "reference": reference,
        })
        seen.add(reference)

    payload = {"format": BATCH_FORMAT, "version": BATCH_VERSION, "questions": accepted}
    args.batch.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"词条 {len(entries)} 条，通过 {len(accepted)} 道 -> {args.batch}")
    for ref, why in skipped:
        print(f"  跳过 {ref}  {why}")


if __name__ == "__main__":
    main()
