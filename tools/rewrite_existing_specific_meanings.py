#!/usr/bin/env python3
"""Rewrite remaining non-placeholder meanings that already carry specific information."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path

from audit_quiz_bank_quality import load_rules
from audit_rewritten_meanings import audit_rewrite
from bible_context import ContextFact
from rewrite_historical_quiz_meanings import RewriteDraft


_FORBIDDEN = ("人名", "地名", "人物", "地点", "专名", "某人", "某地")
_PLACEHOLDERS = {
    "圣经中的人物、地点或具体事物",
    "专有名称或概念",
    "人名",
    "地名",
    "表示一个动作或状态",
    "数量为",
}


@dataclass(frozen=True)
class ExistingSpecificResult:
    rewritten: list[dict[str, object]]
    quarantine: list[dict[str, object]]


def _compact(value: object) -> str:
    return "".join(str(value or "").split())


def _reference(question: dict[str, object]) -> str:
    return f"{question.get('bookId', '')}:{question.get('chapter', '')}:{question.get('verse', '')}"


def _quarantine(record: dict[str, object], reasons: list[str]) -> dict[str, object]:
    return {"key": record.get("key", ""), "question": record.get("question", {}), "reasons": reasons}


def rewrite_existing_specific(records: list[dict[str, object]], rules: dict[str, object]) -> ExistingSpecificResult:
    rewritten: list[dict[str, object]] = []
    quarantine: list[dict[str, object]] = []
    for record in records:
        question = record.get("question")
        if not isinstance(question, dict):
            quarantine.append(_quarantine(record, ["invalid_candidate"]))
            continue
        word = _compact(question.get("word"))
        old = _compact(question.get("meaning"))
        if old in _PLACEHOLDERS or any(marker in old for marker in _FORBIDDEN):
            quarantine.append(_quarantine(record, ["not_specific_legacy_meaning"]))
            continue
        if len(old) < 4 or not word or word in old or old.startswith(("表示", "指", "形容", "泛指")):
            quarantine.append(_quarantine(record, ["legacy_meaning_not_safe_to_rewrite"]))
            continue
        meaning = f"经文背景中的{old}"
        reference = _reference(question)
        fact = ContextFact(word, "existing-specific", (old,), (reference,), "existing-specific-v1")
        draft = RewriteDraft(record.get("key", ""), meaning, "existing-specific", (reference,))
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
            "confidence": "existing-specific",
        })
    return ExistingSpecificResult(rewritten, quarantine)


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as target:
        for record in records:
            target.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="保留并规范化剩余具体旧释义")
    parser.add_argument("--remaining", type=Path, required=True)
    parser.add_argument("--meaning-rules", type=Path, default=Path("lexicon/meaning_rules.v1.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    remaining = [json.loads(line) for line in args.remaining.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = rewrite_existing_specific(remaining, load_rules(args.meaning_rules))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "rewritten-existing-specific.jsonl", result.rewritten)
    _write_jsonl(args.output_dir / "quarantine-existing-specific.jsonl", result.quarantine)
    (args.output_dir / "summary-existing-specific.md").write_text(
        "# 具体旧释义规范化\n\n"
        f"- 输入待补题目：{len(remaining)}\n"
        f"- 通过重写：{len(result.rewritten)}\n"
        f"- 继续隔离：{len(result.quarantine)}\n",
        encoding="utf-8",
    )
    print(f"输入 {len(remaining)} 道：完成具体旧释义重写 {len(result.rewritten)} 道，继续隔离 {len(result.quarantine)} 道。")


if __name__ == "__main__":
    main()
