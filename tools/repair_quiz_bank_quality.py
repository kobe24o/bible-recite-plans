#!/usr/bin/env python3
"""Repair only unambiguous lexicon fragments, then omit every unsafe question."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import json
from pathlib import Path
from typing import Iterable

from audit_quiz_bank_quality import (
    audit_questions,
    load_rules,
    normalized_meaning,
    question_key,
    scripture_key,
)
from quiz_lexicon import LexiconTerm, find_overlapping_terms, load_terms, target_question_limit
from validate_quiz_bank import load_sources, parse_translation, slice_utf16


@dataclass(frozen=True)
class RepairEvent:
    key: str
    action: str
    reason: str


@dataclass(frozen=True)
class RepairResult:
    published: list[dict[str, object]]
    events: list[RepairEvent]

    @property
    def repaired(self) -> int:
        return sum(event.action == "repaired" for event in self.events)

    @property
    def omitted(self) -> int:
        return sum(event.action == "omitted" for event in self.events)


def write_repair_report(result: RepairResult, path: Path) -> None:
    entries = [asdict(event) for event in result.events]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 题库质量修复", "", f"修复 {result.repaired} 项，剔除 {result.omitted} 项。", ""]
    for event in entries:
        lines.append(f"- `{event['action']}` `{event['reason']}` {event['key']}")
    path.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def repair_questions(
    questions: Iterable[dict[str, object]],
    scripture: dict[str, str],
    terms: Iterable[LexiconTerm],
    rules: dict[str, object],
) -> RepairResult:
    """Return a safe, non-overlapping, length-capped bank and an audit trail."""
    terms = tuple(terms)
    generic_meanings = {
        normalized_meaning(value)
        for value in rules.get("forbiddenExactMeanings", [])
        if isinstance(value, str)
    }
    prepared: list[tuple[dict[str, object], bool, int]] = []
    events: list[RepairEvent] = []
    for index, original in enumerate(questions):
        question = dict(original)
        key = question_key(question)
        text = scripture.get(scripture_key(question))
        if text is None:
            events.append(RepairEvent(key, "omitted", "missing_scripture"))
            continue
        try:
            start, end = int(question["start"]), int(question["end"])
            word = str(question["word"])
        except (KeyError, TypeError, ValueError):
            events.append(RepairEvent(key, "omitted", "invalid_question"))
            continue
        if slice_utf16(text, start, end) != word:
            events.append(RepairEvent(key, "omitted", "slice_mismatch"))
            continue
        overlaps = find_overlapping_terms(text, start, end, terms)
        exact = [item for item in overlaps if item.start == start and item.end == end and item.spelling == word]
        repaired = False
        if overlaps and not exact:
            options = _unambiguous_options(text, overlaps)
            if len(options) != 1:
                events.append(RepairEvent(key, "omitted", "ambiguous_lexicon_fragment"))
                continue
            option = options[0]
            question["start"], question["end"], question["word"] = option.start, option.end, option.spelling
            question["meaning"] = option.term.meaning
            repaired = True
        elif (
            normalized_meaning(question.get("meaning", "")) in generic_meanings
            or (word.strip() and word.strip() in str(question.get("meaning", "")).strip())
        ):
            options = _unambiguous_options(text, exact)
            if len(options) != 1:
                events.append(RepairEvent(key, "omitted", "generic_meaning"))
                continue
            question["meaning"] = options[0].term.meaning
            repaired = True
        findings = audit_questions([question], {scripture_key(question): text}, terms, rules)
        if findings:
            events.append(RepairEvent(key, "omitted", findings[0].code))
            continue
        if repaired:
            events.append(RepairEvent(key, "repaired", "lexicon_override"))
        prepared.append((question, _is_full_lexicon_term(question, text, terms), index))
    return RepairResult(_select_questions(prepared, scripture), events)


def _unambiguous_options(text: str, matches: Iterable[object]) -> list[object]:
    options = list(matches)
    unique_terms = {item.term.term for item in options}
    if len(unique_terms) != 1:
        return []
    term = options[0].term
    if sum(text.count(spelling) for spelling in term.spellings) != 1:
        return []
    longest = max(options, key=lambda item: (item.end - item.start, item.spelling))
    return [longest]


def _is_full_lexicon_term(question: dict[str, object], text: str, terms: Iterable[LexiconTerm]) -> bool:
    start, end, word = int(question["start"]), int(question["end"]), str(question["word"])
    return any(
        item.start == start and item.end == end and item.spelling == word
        for item in find_overlapping_terms(text, start, end, terms)
    )


def _select_questions(
    prepared: Iterable[tuple[dict[str, object], bool, int]], scripture: dict[str, str]
) -> list[dict[str, object]]:
    grouped: dict[str, list[tuple[dict[str, object], bool, int]]] = {}
    for item in prepared:
        grouped.setdefault(scripture_key(item[0]), []).append(item)
    selected: list[dict[str, object]] = []
    for verse_key, candidates in grouped.items():
        limit = target_question_limit(scripture[verse_key])
        spans: list[tuple[int, int]] = []
        for question, is_lexicon_term, original_index in sorted(
            candidates,
            key=lambda item: (-int(item[1]), -(int(item[0]["end"]) - int(item[0]["start"])), item[2]),
        ):
            start, end = int(question["start"]), int(question["end"])
            if len(spans) >= limit or any(existing_start < end and start < existing_end for existing_start, existing_end in spans):
                continue
            spans.append((start, end))
            selected.append(question)
    return selected


def _scripture_from_sources(sources: dict[str, dict[tuple[str, int, int], str]]) -> dict[str, str]:
    return {
        f"{book}:{chapter}:{verse}": text
        for verses in sources.values()
        for (book, chapter, verse), text in verses.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="确定性修复题库残词与笼统释义")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lexicon", type=Path, default=Path("lexicon/bible_terms.v1.json"))
    parser.add_argument("--meaning-rules", type=Path, default=Path("lexicon/meaning_rules.v1.json"))
    parser.add_argument("--quality-report", type=Path, required=True)
    parser.add_argument("--translation", type=parse_translation, action="append")
    args = parser.parse_args()
    root = json.loads(args.input.read_text(encoding="utf-8"))
    questions = root.get("questions")
    if not isinstance(questions, list) or not all(isinstance(item, dict) for item in questions):
        raise ValueError("题库 questions 无效")
    sources = load_sources(args.translation or [("cmn-cu89s", Path("scripture/cmn-cu89s/scripture.sqlite"))])
    result = repair_questions(questions, _scripture_from_sources(sources), load_terms(args.lexicon), load_rules(args.meaning_rules))
    root["questions"] = result.published
    args.output.write_text(json.dumps(root, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_repair_report(result, args.quality_report)
    print(f"修复完成：保留 {len(result.published)} 题，修复 {result.repaired} 题，剔除 {result.omitted} 题。")


if __name__ == "__main__":
    main()
