#!/usr/bin/env python3
"""Rewrite remaining historical candidates from conservative Bible-context consensus."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path

from audit_quiz_bank_quality import load_rules
from audit_rewritten_meanings import audit_rewrite
from bible_context import ContextFact
from rewrite_historical_quiz_meanings import RewriteDraft


_GENERIC_MARKERS = (
    "人名", "地名", "人物", "地点", "专名", "某人", "某地",
    "专有名称或概念", "圣经中的人物、地点或具体事物",
    "表示一个动作或状态", "表示一种状态", "表示一个动作",
    "数量为", "表示数量", "某种",
)
_BIBLE_MARKERS = (
    "以色列", "犹大", "耶稣", "耶和华", "圣经", "先知", "祭司", "君王",
    "国王", "王", "支派", "族长", "门徒", "使徒", "教会", "圣殿", "会幕",
    "律法", "约柜", "约旦", "迦南", "埃及", "巴比伦", "大卫", "雅各",
    "亚伯拉罕", "摩西", "亚伦", "撒但", "天使", "犹太", "外邦", "祭", "献祭",
    "赎罪", "士师", "城", "民", "后裔",
)


@dataclass(frozen=True)
class ConsensusMeaning:
    meaning: str
    occurrences: int
    observations: int


@dataclass(frozen=True)
class RemainingRewriteResult:
    rewritten: list[dict[str, object]]
    quarantine: list[dict[str, object]]


def _compact(value: object) -> str:
    return "".join(str(value or "").split())


def _specific_meaning(word: str, meaning: object) -> str | None:
    value = _compact(meaning)
    if len(value) < 8 or not word or word in value:
        return None
    if any(marker in value for marker in _GENERIC_MARKERS):
        return None
    if value.startswith(("表示", "指", "形容", "泛指")):
        return None
    if not any(marker in value for marker in _BIBLE_MARKERS):
        return None
    return value


def derive_consensus_meanings(records: list[dict[str, object]]) -> dict[str, ConsensusMeaning]:
    """Keep only one high-confidence, Bible-specific meaning per answer word."""
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    observations: Counter[str] = Counter()
    for record in records:
        question = record.get("question")
        if not isinstance(question, dict):
            continue
        word = _compact(question.get("word"))
        meaning = _specific_meaning(word, question.get("meaning"))
        if meaning is None:
            continue
        counts[word][meaning] += 1
        observations[word] += 1

    result: dict[str, ConsensusMeaning] = {}
    for word, meanings in counts.items():
        meaning, occurrences = meanings.most_common(1)[0]
        total = observations[word]
        if occurrences < 3 or occurrences / total < 0.8:
            continue
        result[word] = ConsensusMeaning(meaning, occurrences, total)
    return result


def _reference(question: dict[str, object]) -> str:
    return f"{question.get('bookId', '')}:{question.get('chapter', '')}:{question.get('verse', '')}"


def _quarantine(record: dict[str, object], reasons: list[str]) -> dict[str, object]:
    return {"key": record.get("key", ""), "question": record.get("question", {}), "reasons": reasons}


def rewrite_remaining(
    records: list[dict[str, object]],
    consensus: dict[str, ConsensusMeaning],
    rules: dict[str, object],
) -> RemainingRewriteResult:
    rewritten: list[dict[str, object]] = []
    quarantine: list[dict[str, object]] = []
    for record in records:
        question = record.get("question")
        if not isinstance(question, dict):
            quarantine.append(_quarantine(record, ["invalid_candidate"]))
            continue
        word = _compact(question.get("word"))
        entry = consensus.get(word)
        if entry is None:
            quarantine.append(_quarantine(record, ["no_high_confidence_bible_consensus"]))
            continue
        meaning = f"经文背景中的{entry.meaning}"
        reference = _reference(question)
        fact = ContextFact(word, "historical-consensus", (entry.meaning,), (reference,), "historical-consensus-v1")
        draft = RewriteDraft(record.get("key", ""), meaning, "historical-consensus", (reference,))
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
            "consensusOccurrences": entry.occurrences,
            "consensusObservations": entry.observations,
        })
    return RemainingRewriteResult(rewritten, quarantine)


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as target:
        for record in records:
            target.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="用高置信圣经关系共识重写剩余候选题释义")
    parser.add_argument("--all-candidates", type=Path, required=True)
    parser.add_argument("--remaining", type=Path, required=True)
    parser.add_argument("--meaning-rules", type=Path, default=Path("lexicon/meaning_rules.v1.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    all_candidates = [json.loads(line) for line in args.all_candidates.read_text(encoding="utf-8").splitlines() if line.strip()]
    remaining = [json.loads(line) for line in args.remaining.read_text(encoding="utf-8").splitlines() if line.strip()]
    consensus = derive_consensus_meanings(all_candidates + remaining)
    result = rewrite_remaining(remaining, consensus, load_rules(args.meaning_rules))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "rewritten-consensus.jsonl", result.rewritten)
    _write_jsonl(args.output_dir / "quarantine-consensus.jsonl", result.quarantine)
    (args.output_dir / "summary-consensus.md").write_text(
        "# 第二批圣经关系共识释义重写\n\n"
        f"- 输入待补题目：{len(remaining)}\n"
        f"- 高置信词条：{len(consensus)}\n"
        f"- 通过改写：{len(result.rewritten)}\n"
        f"- 继续隔离：{len(result.quarantine)}\n",
        encoding="utf-8",
    )
    print(f"输入 {len(remaining)} 道：完成改写 {len(result.rewritten)} 道，继续隔离 {len(result.quarantine)} 道。")


if __name__ == "__main__":
    main()
