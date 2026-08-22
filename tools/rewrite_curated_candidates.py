#!/usr/bin/env python3
"""Apply curated Bible facts to candidate questions without publishing them."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from audit_rewritten_meanings import audit_rewrite
from audit_quiz_bank_quality import load_rules
from bible_context import ContextFact, load_context_facts
from rewrite_historical_quiz_meanings import deterministic_draft


@dataclass(frozen=True)
class RewriteResult:
    rewritten: list[dict[str, object]]
    quarantine: list[dict[str, object]]


def _quarantine(record: dict[str, object], reasons: list[str]) -> dict[str, object]:
    return {"key": record.get("key", ""), "question": record.get("question", {}), "reasons": reasons}


def rewrite_candidates(
    candidates: list[dict[str, object]],
    facts: dict[str, ContextFact],
    rules: dict[str, object],
) -> RewriteResult:
    rewritten: list[dict[str, object]] = []
    quarantine: list[dict[str, object]] = []
    for record in candidates:
        question = record.get("question")
        if not isinstance(question, dict):
            quarantine.append(_quarantine(record, ["invalid_candidate"]))
            continue
        word = str(question.get("word", ""))
        fact = facts.get(word)
        if fact is None:
            quarantine.append(_quarantine(record, ["missing_context_fact"]))
            continue
        draft = deterministic_draft(question, fact)
        audit = audit_rewrite(question, draft, rules, fact)
        if not audit.accepted or draft.meaning is None:
            quarantine.append(_quarantine(record, list(audit.reasons) or ["rewrite_rejected"]))
            continue
        updated = dict(question)
        previous = updated["meaning"]
        updated["meaning"] = draft.meaning
        rewritten.append(
            {
                "key": record.get("key", ""),
                "question": updated,
                "previousMeaning": previous,
                "rewriteSource": draft.source,
                "evidenceReferences": list(draft.evidence_references),
            }
        )
    return RewriteResult(rewritten, quarantine)


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as target:
        for record in records:
            target.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="用版本化圣经事实重写候选题释义")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--context", type=Path, default=Path("lexicon/bible_context.v1.json"))
    parser.add_argument("--meaning-rules", type=Path, default=Path("lexicon/meaning_rules.v1.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    candidates = [json.loads(line) for line in args.candidates.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = rewrite_candidates(candidates, load_context_facts(args.context), load_rules(args.meaning_rules))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "rewritten-curated.jsonl", result.rewritten)
    _write_jsonl(args.output_dir / "quarantine-curated.jsonl", result.quarantine)
    (args.output_dir / "summary-curated.md").write_text(
        "# 第一批圣经事实释义重写\n\n"
        f"- 输入候选：{len(candidates)}\n"
        f"- 通过改写：{len(result.rewritten)}\n"
        f"- 隔离待补：{len(result.quarantine)}\n",
        encoding="utf-8",
    )
    print(f"输入 {len(candidates)} 道：完成改写 {len(result.rewritten)} 道，隔离 {len(result.quarantine)} 道。")


if __name__ == "__main__":
    main()
