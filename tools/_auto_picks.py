#!/usr/bin/env python3
"""
Auto-generate quiz picks for verses needing a second question.
Extracts meaningful candidate words from scripture, picks one at a different
position than existing questions, and outputs entries for _resolve_batch.py.
"""
import argparse, json, os, sqlite3, sys
from pathlib import Path

SCRIPTURE_DB = Path(__file__).resolve().parent.parent / "scripture" / "cmn-cu89s" / "scripture.sqlite"

FUNCTION_CHARS = set("的了在是我你不他她它们这那有着和与或但如果因为所以虽然只是也就都还要到被把给从比对让向于")


def load_scripture(book: str):
    with sqlite3.connect(SCRIPTURE_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT u.osis_book_id AS book_id, u.chapter, u.start_verse AS verse, u.text "
            "FROM verse_unit u WHERE u.status = 'present' AND u.start_verse = u.end_verse "
            "AND u.osis_book_id = ? ORDER BY u.chapter, u.start_verse",
            (book,),
        ).fetchall()
    return [dict(r) for r in rows]


def is_valid_pick(word: str, verse_text: str) -> bool:
    if len(word) < 2 or len(word) > 8:
        return False
    if word[0] in FUNCTION_CHARS or word[-1] in FUNCTION_CHARS:
        return False
    if word not in verse_text:
        return False
    return True


def extract_candidates(text: str) -> list[str]:
    candidates = []
    seen = set()
    for length in range(2, min(9, len(text) + 1)):
        for i in range(len(text) - length + 1):
            w = text[i:i + length]
            if w not in seen and is_valid_pick(w, text):
                candidates.append(w)
                seen.add(w)
    return candidates


def get_existing_picks(bank: list[dict], book: str, chapter: int, verse: int):
    words = set()
    starts = set()
    for q in bank:
        if q["bookId"] == book and q["chapter"] == chapter and q["verse"] == verse:
            words.add(q["word"])
            starts.add(q["start"])
    return words, starts


def utf16_length(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", required=True)
    parser.add_argument("--start-ch", type=int, required=True)
    parser.add_argument("--end-ch", type=int, required=True)
    parser.add_argument("--bank", default="quiz-bank.json")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    bank = json.load(open(args.bank))["questions"]
    verses = load_scripture(args.book)

    picks = []
    for v in verses:
        if not (args.start_ch <= v["chapter"] <= args.end_ch):
            continue
        text = v["text"]
        existing_words, existing_starts = get_existing_picks(bank, args.book, v["chapter"], v["verse"])
        candidates = extract_candidates(text)
        candidates = [w for w in candidates if w not in existing_words]

        best_word = None
        best_start = None

        for word in candidates:
            byte_pos = text.find(word)
            if byte_pos < 0:
                continue
            start16 = utf16_length(text[:byte_pos])
            end16 = start16 + utf16_length(word)

            overlaps = False
            for q in bank:
                if (q["bookId"] == args.book and q["chapter"] == v["chapter"]
                        and q["verse"] == v["verse"] and q["start"] in existing_starts):
                    e_start = q["start"]
                    e_end = q["end"]
                    if not (end16 <= e_start or start16 >= e_end):
                        overlaps = True
                        break

            if not overlaps:
                best_word = word
                best_start = start16
                break

        if best_word:
            pos = "名词"
            meaning = f"{best_word}：{best_word}"
            for q in bank:
                if q["bookId"] == args.book and q["word"] == best_word:
                    pos = q["partOfSpeech"]
                    break

            picks.append({
                "reference": f"{v['chapter']}:{v['verse']}",
                "word": best_word,
                "partOfSpeech": pos,
                "meaning": meaning,
            })

    out = args.output or f"/tmp/auto_picks_{args.book.lower()}_{args.start_ch}_{args.end_ch}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(picks, f, ensure_ascii=False, indent=2)

    print(f"Generated {len(picks)} picks for {args.book} {args.start_ch}-{args.end_ch}")
    print(f"Output: {out}")


if __name__ == "__main__":
    main()
