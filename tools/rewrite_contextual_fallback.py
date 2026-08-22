#!/usr/bin/env python3
"""Create explicitly marked contextual drafts for unresolved placeholders."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sqlite3

from audit_quiz_bank_quality import load_rules
from audit_rewritten_meanings import audit_rewrite
from bible_context import ContextFact
from rewrite_historical_quiz_meanings import RewriteDraft


_PLACEHOLDERS = {
    "圣经中的人物、地点或具体事物",
    "专有名称或概念",
    "人名",
    "地名",
    "表示一个动作或状态",
    "数量为",
}

_LEGACY_LABEL_REWRITES = {
    "地名": "本节地理叙事中的区域称谓",
    "山名": "本节地理叙事中的山地称谓",
    "城名": "本节地理叙事中的城邑称谓",
    "城市": "本节地理叙事中的城邑及其居民环境",
    "河名": "本节地理叙事中的水域称谓",
    "树木名": "本节自然环境中的树木称谓",
    "人名": "本节叙事中的人物称谓",
    "鸟名": "本节受造界中的鸟类称谓",
    "勇士名": "本节战争叙事中的勇士称谓",
    "支派名": "本节族谱或支派记载中的群体称谓",
    "天使长": "本节属灵争战叙事中的天使领袖",
    "撒冷王": "本节族长时代城邦中的君王身份",
    "以色列王": "本节以色列历史中的王权身份",
    "会幕所在地": "本节旷野敬拜中的会幕驻扎地点",
    "迦南地的民族": "本节应许之地中的当地族群",
}


@dataclass(frozen=True)
class ContextualFallbackResult:
    rewritten: list[dict[str, object]]
    quarantine: list[dict[str, object]]


def _compact(value: object) -> str:
    return "".join(str(value or "").split())


def _reference(question: dict[str, object]) -> str:
    return f"{question.get('bookId', '')}:{question.get('chapter', '')}:{question.get('verse', '')}"


def classify_context(question: dict[str, object], verse_text: str) -> str:
    text = verse_text.replace("[", "").replace("]", "")
    word = _compact(question.get("word"))
    pos = _compact(question.get("partOfSpeech"))
    candidates: list[tuple[bool, str]] = [
        ((("生" in text and ("儿子" in text or "后代" in text or "家谱" in text)) or re.search(r"[\u4e00-\u9fff]{1,8}生[\u4e00-\u9fff]", text)) is not None, "本节族系记录中的父系传承对象"),
        (any(marker in text for marker in ("祭司", "会幕", "圣殿", "献祭", "祭坛")), "本节礼仪场景中的相关角色或事物"),
        (any(marker in text for marker in ("王", "国", "统治", "君")), "本节历史叙事中的治理关系"),
        (any(marker in text for marker in ("先知", "耶和华", "预言", "晓谕")), "本节先知宣告中的对象或行动"),
        (any(marker in text for marker in ("城", "地", "山", "河", "海", "旷野")) or word.endswith(("城", "地", "山", "河", "海")), "本节地理叙事中的区域或地貌称谓"),
        (word.endswith("人"), "本节所述民族或居民的群体称谓"),
        ("动词" in pos or pos in {"动", "Verb"}, "本节叙事中推动事件发展的动作"),
        ("形容" in pos or "副词" in pos, "本节叙事中描述状态或性质的词语"),
        ("代词" in pos or "介词" in pos or "连词" in pos, "本节语句中表示关系或指代的词语"),
    ]
    for matches, category in candidates:
        if matches and word not in category:
            return category
    return "本节叙事中承载具体语义的表达"


def legacy_meaning(question: dict[str, object], verse_text: str) -> str:
    """Turn a surviving short legacy gloss into a reviewable contextual gloss."""
    old = _compact(question.get("meaning"))
    word = _compact(question.get("word"))
    if old in _LEGACY_LABEL_REWRITES:
        candidate = _LEGACY_LABEL_REWRITES[old]
    elif old in _PLACEHOLDERS or not old:
        candidate = classify_context(question, verse_text)
    else:
        # Preserve the useful lexical hint while explicitly anchoring it to the
        # verse. If the old gloss would reveal the answer, fall back to context.
        candidate = f"与{old}有关的含义"
        if word and word in candidate:
            candidate = classify_context(question, verse_text)
    forbidden = ("人名", "地名", "人物", "地点", "专名", "某人", "某地")
    if (word and word in candidate) or any(token in candidate for token in forbidden):
        for safe in ("本节所述的语义表达", "本段叙事中的相关表达", "经文里的相关用语", "本节中的词语"):
            if (not word or word not in safe) and not any(token in safe for token in forbidden):
                candidate = safe
                break
    prefix = "经文语境中，"
    if word and word in prefix:
        prefix = "本节中，"
    return f"{prefix}{candidate}"


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


def rewrite_contextual_fallback(
    records: list[dict[str, object]],
    verses: dict[tuple[str, int, int], str],
    rules: dict[str, object],
    include_all: bool = False,
) -> ContextualFallbackResult:
    rewritten: list[dict[str, object]] = []
    quarantine: list[dict[str, object]] = []
    for record in records:
        question = record.get("question")
        if not isinstance(question, dict):
            quarantine.append(_quarantine(record, ["invalid_candidate"]))
            continue
        old = _compact(question.get("meaning"))
        if not include_all and old not in _PLACEHOLDERS:
            quarantine.append(_quarantine(record, ["not_contextual_placeholder"]))
            continue
        word = _compact(question.get("word"))
        if not word:
            quarantine.append(_quarantine(record, ["missing_word"]))
            continue
        key = (str(question.get("bookId", "")), int(question.get("chapter", 0)), int(question.get("verse", 0)))
        meaning = legacy_meaning(question, verses.get(key, ""))
        reference = _reference(question)
        fact = ContextFact(word, "contextual-fallback", (meaning,), (reference,), "contextual-fallback-v1")
        draft = RewriteDraft(record.get("key", ""), meaning, "contextual-fallback", (reference,))
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
            "confidence": "contextual-fallback",
        })
    return ContextualFallbackResult(rewritten, quarantine)


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as target:
        for record in records:
            target.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="为剩余占位释义生成带置信度标记的经文语境草稿")
    parser.add_argument("--remaining", type=Path, required=True)
    parser.add_argument("--scripture", type=Path, default=Path("scripture/cmn-cu89s/scripture.sqlite"))
    parser.add_argument("--meaning-rules", type=Path, default=Path("lexicon/meaning_rules.v1.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--include-all", action="store_true", help="将输入中的所有剩余记录生成低置信度语境释义")
    args = parser.parse_args()
    remaining = [json.loads(line) for line in args.remaining.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = rewrite_contextual_fallback(remaining, _load_verses(args.scripture), load_rules(args.meaning_rules), args.include_all)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "rewritten-contextual.jsonl", result.rewritten)
    _write_jsonl(args.output_dir / "quarantine-contextual.jsonl", result.quarantine)
    (args.output_dir / "summary-contextual.md").write_text(
        "# 经文语境兜底释义草稿\n\n"
        f"- 输入待补题目：{len(remaining)}\n"
        f"- 生成草稿：{len(result.rewritten)}\n"
        f"- 继续隔离：{len(result.quarantine)}\n"
        "\n> 该批次标记为 contextual-fallback，须与高置信释义分开复核后才能发布。\n",
        encoding="utf-8",
    )
    print(f"输入 {len(remaining)} 道：生成语境草稿 {len(result.rewritten)} 道，继续隔离 {len(result.quarantine)} 道。")


if __name__ == "__main__":
    main()
