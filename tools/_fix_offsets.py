#!/usr/bin/env python3
"""Local helper (not committed): auto-fix start/end offsets for a batch.

For each question, find the first occurrence of q["word"] in the verse whose
span is not already used in quiz-bank.json and whose word passes is_valid_word.
Overwrites the batch file with corrected offsets. Prints problems.
"""
from __future__ import annotations

import json
import sqlite3
import sys

sys.path.insert(0, "tools")
from generate_quiz_bank import is_valid_word  # noqa: E402

path = sys.argv[1]
qs = json.load(open(path, encoding="utf-8"))["questions"]

con = sqlite3.connect("scripture/cmn-cu89s/scripture.sqlite")
bank = json.load(open("quiz-bank.json", encoding="utf-8"))["questions"]
used = set()
for q in bank:
    used.add((q["bookId"], q["chapter"], q["verse"], q["start"], q["end"]))

fixed = 0
bad = []
for q in qs:
    row = con.execute(
        "SELECT text FROM verse_unit WHERE osis_book_id=? AND chapter=? AND start_verse=? "
        "AND end_verse=start_verse AND status='present'",
        (q["bookId"], q["chapter"], q["verse"]),
    ).fetchone()
    if not row:
        bad.append((q["bookId"], q["chapter"], q["verse"], "MISSING VERSE"))
        continue
    text = row[0]
    word = q["word"]
    found = None
    start = 0
    while True:
        idx = text.find(word, start)
        if idx == -1:
            break
        if (q["bookId"], q["chapter"], q["verse"], idx, idx + len(word)) not in used and is_valid_word(word):
            found = (idx, idx + len(word))
            break
        start = idx + 1
    if not found:
        bad.append((q["bookId"], q["chapter"], q["verse"], f"NO SPAN for {word!r}"))
        continue
    q["start"], q["end"] = found
    fixed += 1

json.dump(
    {"format": "bible-recite-quiz-bank", "version": 2, "questions": qs},
    open(path, "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=2,
)
print("fixed", fixed, "of", len(qs), "bad", len(bad))
for b in bad:
    print(b)
