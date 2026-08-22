#!/usr/bin/env python3
"""Derive non-generic meanings from explicit genealogy relations in the verse."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import re
import sqlite3
from pathlib import Path

from audit_quiz_bank_quality import load_rules
from audit_rewritten_meanings import audit_rewrite
from bible_context import ContextFact
from rewrite_historical_quiz_meanings import RewriteDraft


_GENERIC_MEANINGS = {
    "圣经中的人物、地点或具体事物",
    "专有名称或概念",
    "人名",
    "地名",
    "表示一个动作或状态",
}
_CLAUSE_BREAKS = "；。"


@dataclass(frozen=True)
class GenealogyRewriteResult:
    rewritten: list[dict[str, object]]
    quarantine: list[dict[str, object]]


def _compact(value: object) -> str:
    return "".join(str(value or "").split())


def _reference(question: dict[str, object]) -> str:
    return f"{question.get('bookId', '')}:{question.get('chapter', '')}:{question.get('verse', '')}"


def _strip_marks(text: str) -> str:
    return text.replace("[", "").replace("]", "")


def infer_genealogy_meaning(word: str, verse_text: str) -> str | None:
    """Return a relation-specific hint only when the verse states the relation."""
    clean = _strip_marks(verse_text)
    if not word or word not in clean:
        return None
    start = clean.rfind("；", 0, clean.find(word))
    start = max(start, clean.rfind("。", 0, clean.find(word))) + 1
    end_candidates = [index for mark in _CLAUSE_BREAKS if (index := clean.find(mark, clean.find(word))) >= 0]
    end = min(end_candidates) if end_candidates else len(clean)
    clause = clean[start:end]
    escaped = re.escape(word)

    child_patterns = (
        rf"(?P<parent>[\u4e00-\u9fff]{{1,8}})的儿子是[^；。]*?{escaped}",
        rf"(?P<parent>[\u4e00-\u9fff]{{1,8}})的儿女是[^；。]*?{escaped}",
    )
    for pattern in child_patterns:
        match = re.search(pattern, clause)
        if match:
            parent = match.group("parent")
            if word not in parent:
                return f"{parent}的后代，家谱中承接父系传承"

    parent_match = re.search(rf"(?P<parent>[\u4e00-\u9fff]{{1,8}})生{escaped}", clause)
    if parent_match:
        parent = parent_match.group("parent")
        if word not in parent:
            return f"{parent}的后代，家谱中承接父系传承"

    if re.search(rf"{escaped}生", clause):
        return "家谱中记载的父系先祖"
    return None


def _load_verses(path: Path) -> dict[tuple[str, int, int], str]:
    connection = sqlite3.connect(path)
    try:
        return {
            (book, chapter, verse): text
            for book, chapter, verse, text in connection.execute(
                "SELECT verse_slot.osis_book_id, verse_slot.chapter, verse_slot.verse, verse_unit.text "
                "FROM verse_slot JOIN verse_unit ON verse_slot.unit_id = verse_unit.unit_id"
            )
        }
    finally:
        connection.close()


def _quarantine(record: dict[str, object], reasons: list[str]) -> dict[str, object]:
    return {"key": record.get("key", ""), "question": record.get("question", {}), "reasons": reasons}


def rewrite_genealogy(
    records: list[dict[str, object]],
    verses: dict[tuple[str, int, int], str],
    rules: dict[str, object],
) -> GenealogyRewriteResult:
    rewritten: list[dict[str, object]] = []
    quarantine: list[dict[str, object]] = []
    for record in records:
        question = record.get("question")
        if not isinstance(question, dict):
            quarantine.append(_quarantine(record, ["invalid_candidate"]))
            continue
        old = _compact(question.get("meaning"))
        if old not in _GENERIC_MEANINGS:
            quarantine.append(_quarantine(record, ["not_genealogy_placeholder"]))
            continue
        key = (str(question.get("bookId", "")), int(question.get("chapter", 0)), int(question.get("verse", 0)))
        relation = infer_genealogy_meaning(_compact(question.get("word")), verses.get(key, ""))
        if relation is None:
            quarantine.append(_quarantine(record, ["no_explicit_genealogy_relation"]))
            continue
        word = _compact(question.get("word"))
        meaning = f"经文家谱中，{relation}"
        reference = _reference(question)
        fact = ContextFact(word, "genealogy-relation", (relation,), (reference,), "genealogy-context-v1")
        draft = RewriteDraft(record.get("key", ""), meaning, "genealogy-context", (reference,))
        audit = audit_rewrite(question, draft, rules, fact)
        if not audit.accepted:
            quarantine.append(_quarantine(record, list(audit.reasons)))
            continue
        updated = dict(question)
        updated["meaning"] = meaning
        rewritten.append({
            "key": record.get("key", ""),
            "question": updated,
            "previousMeaning": question.get("meaning", ""),
            "rewriteSource": draft.source,
            "evidenceReferences": [reference],
        })
    return GenealogyRewriteResult(rewritten, quarantine)


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as target:
        for record in records:
            target.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="从经文明确家谱关系中重写占位释义")
    parser.add_argument("--remaining", type=Path, required=True)
    parser.add_argument("--scripture", type=Path, default=Path("scripture/cmn-cu89s/scripture.sqlite"))
    parser.add_argument("--meaning-rules", type=Path, default=Path("lexicon/meaning_rules.v1.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    remaining = [json.loads(line) for line in args.remaining.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = rewrite_genealogy(remaining, _load_verses(args.scripture), load_rules(args.meaning_rules))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "rewritten-genealogy.jsonl", result.rewritten)
    _write_jsonl(args.output_dir / "quarantine-genealogy.jsonl", result.quarantine)
    (args.output_dir / "summary-genealogy.md").write_text(
        "# 家谱关系释义重写\n\n"
        f"- 输入待补题目：{len(remaining)}\n"
        f"- 通过重写：{len(result.rewritten)}\n"
        f"- 继续隔离：{len(result.quarantine)}\n",
        encoding="utf-8",
    )
    print(f"输入 {len(remaining)} 道：完成家谱关系重写 {len(result.rewritten)} 道，继续隔离 {len(result.quarantine)} 道。")


if __name__ == "__main__":
    main()
