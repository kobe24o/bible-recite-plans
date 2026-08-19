#!/usr/bin/env python3
"""Local helper (not committed): print verses with used spans for reasoning.

Usage: python3 tools/_dump_work.py BOOK START_CH END_CH
Reads quiz-bank.json to list spans already used per verse.
"""
from __future__ import annotations

import json
import sqlite3
import sys

BOOKS_ORDER = None


def main() -> None:
    book = sys.argv[1].upper()
    start_ch = int(sys.argv[2])
    end_ch = int(sys.argv[3])

    root = json.loads(open("quiz-bank.json", encoding="utf-8").read())
    questions = root["questions"]
    used = {}
    for q in questions:
        if q["bookId"] == book and start_ch <= q["chapter"] <= end_ch:
            used.setdefault((q["chapter"], q["verse"]), []).append(
                (q["start"], q["end"], q["word"])
            )

    con = sqlite3.connect("scripture/cmn-cu89s/scripture.sqlite")
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """SELECT u.chapter AS chapter, u.start_verse AS verse, u.text AS text
           FROM verse_unit u
           WHERE u.status='present' AND u.start_verse=u.end_verse
             AND u.osis_book_id=? AND u.chapter BETWEEN ? AND ?
           ORDER BY u.chapter, u.start_verse""",
        (book, start_ch, end_ch),
    ).fetchall()
    for row in rows:
        spans = used.get((row["chapter"], row["verse"]), [])
        spans_txt = " | ".join(f"{s}:{e}={w}" for s, e, w in spans) or "-"
        print(f"{row['chapter']}:{row['verse']}\t{row['text']}\t[{spans_txt}]")


if __name__ == "__main__":
    main()
