#!/usr/bin/env python3
"""Audit quiz questions for lexical-boundary and meaning quality."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from quiz_lexicon import LexiconTerm, find_overlapping_terms, load_terms
from validate_quiz_bank import load_sources, parse_translation, slice_utf16


@dataclass(frozen=True)
class QualityFinding:
    index: int
    key: str
    severity: str
    code: str
    message: str


def question_key(question: dict[str, object]) -> str:
    return ":".join(
        str(question.get(field, ""))
        for field in ("translationId", "bookId", "chapter", "verse", "start", "end")
    )


def scripture_key(question: dict[str, object]) -> str:
    return ":".join(
        str(question.get(field, "")) for field in ("bookId", "chapter", "verse")
    )


def normalized_meaning(value: object) -> str:
    return "".join(str(value).strip().split())


def audit_questions(
    questions: Iterable[dict[str, object]],
    scripture: dict[str, str],
    terms: Iterable[LexiconTerm],
    rules: dict[str, object],
) -> list[QualityFinding]:
    """Return critical findings for wrong slices, lexical fragments and vague hints."""
    terms = tuple(terms)
    generic_meanings = {
        normalized_meaning(value)
        for value in rules.get("forbiddenExactMeanings", [])
        if isinstance(value, str)
    }
    findings: list[QualityFinding] = []
    for index, question in enumerate(questions):
        key = question_key(question)
        try:
            start, end = int(question["start"]), int(question["end"])
            word = str(question["word"])
        except (KeyError, TypeError, ValueError):
            findings.append(QualityFinding(index, key, "critical", "invalid_question", "题目字段无效"))
            continue
        text = scripture.get(scripture_key(question))
        if text is None:
            findings.append(QualityFinding(index, key, "critical", "missing_scripture", "找不到对应经文"))
            continue
        if slice_utf16(text, start, end) != word:
            findings.append(QualityFinding(index, key, "critical", "slice_mismatch", "答案与原文 UTF-16 切片不一致"))
            continue
        overlaps = find_overlapping_terms(text, start, end, terms)
        is_full_term = any(
            item.start == start and item.end == end and item.spelling == word for item in overlaps
        )
        if overlaps and not is_full_term:
            findings.append(QualityFinding(index, key, "critical", "partial_lexicon_term", "答案只覆盖已知词条的一部分"))
            continue
        if _is_partial_segmented_term(text, start, end, word):
            findings.append(QualityFinding(index, key, "critical", "partial_segmented_term", "答案只覆盖结巴识别词语的一部分"))
            continue
        if word.strip() and word.strip() in str(question.get("meaning", "")).strip():
            findings.append(QualityFinding(index, key, "critical", "answer_leaking_meaning", "释义直接包含答案词"))
            continue
        if normalized_meaning(question.get("meaning", "")) in generic_meanings:
            findings.append(QualityFinding(index, key, "critical", "generic_meaning", "释义过于笼统"))
    return findings


def write_quality_report(findings: Iterable[QualityFinding], path: Path) -> None:
    entries = [asdict(finding) for finding in findings]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = path.with_suffix(".md")
    lines = ["# 题库质量审计", "", f"共 {len(entries)} 项。", ""]
    for item in entries:
        lines.append(f"- `{item['severity']}` `{item['code']}` {item['key']}：{item['message']}")
    markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _is_partial_segmented_term(text: str, start: int, end: int, word: str) -> bool:
    """Use Jieba only as a conservative fragment detector, never as a repair source."""
    import jieba

    boundaries = [0]
    for character in text:
        boundaries.append(boundaries[-1] + len(character.encode("utf-16-le")) // 2)
    for token, code_start, code_end in jieba.tokenize(text):
        token_start, token_end = boundaries[code_start], boundaries[code_end]
        if len(token.strip()) < 2 or not (token_start <= start and end <= token_end):
            continue
        if token_start == start and token_end == end and token == word:
            continue
        return True
    return False


def load_rules(path: Path) -> dict[str, object]:
    root = json.loads(path.read_text(encoding="utf-8"))
    if root.get("format") != "bible-recite-meaning-rules" or root.get("version") != 1:
        raise ValueError("释义规则格式或版本无效")
    return root


def _scripture_from_sources(sources: dict[str, dict[tuple[str, int, int], str]]) -> dict[str, str]:
    return {
        f"{book}:{chapter}:{verse}": text
        for verses in sources.values()
        for (book, chapter, verse), text in verses.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="审计题库中的残词和笼统释义")
    parser.add_argument("--bank", type=Path, required=True)
    parser.add_argument("--lexicon", type=Path, default=Path("lexicon/bible_terms.v1.json"))
    parser.add_argument("--meaning-rules", type=Path, default=Path("lexicon/meaning_rules.v1.json"))
    parser.add_argument("--quality-report", type=Path, required=True)
    parser.add_argument("--translation", type=parse_translation, action="append")
    args = parser.parse_args()
    root = json.loads(args.bank.read_text(encoding="utf-8"))
    questions = root.get("questions")
    if not isinstance(questions, list) or not all(isinstance(item, dict) for item in questions):
        raise ValueError("题库 questions 无效")
    sources = load_sources(args.translation or [("cmn-cu89s", Path("scripture/cmn-cu89s/scripture.sqlite"))])
    findings = audit_questions(questions, _scripture_from_sources(sources), load_terms(args.lexicon), load_rules(args.meaning_rules))
    write_quality_report(findings, args.quality_report)
    critical = [item for item in findings if item.severity == "critical"]
    print(f"审计完成：{len(findings)} 项，严重 {len(critical)} 项。")
    if critical:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
