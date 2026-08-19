"""Remove answer-revealing text from existing BibleRecite quiz hints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def fallback_hint(word: str, part_of_speech: str) -> str:
    candidates = (
        ("表示一个动作或状态", "描述性质、状态或程度")
        if "动词" in part_of_speech or "形容" in part_of_speech
        else ("专有名称或概念", "相关对象或概念")
    ) + ("语义提示", "简要说明", "通用释义")
    return next(value for value in candidates if word not in value)


def sanitize(word: str, part_of_speech: str, meaning: str) -> str:
    """Keep a useful residual definition when possible, never the answer."""
    value = meaning.strip()
    for prefix in (f"{word}：", f"{word}:", f"【{word}】：", f"【{word}]:"):
        if value.startswith(prefix):
            value = value[len(prefix) :].strip()
            break
    if word in value:
        value = value.replace(word, "").strip(" ：:，,；;、。.")
    return value if len(value) >= 2 and word not in value else fallback_hint(word, part_of_speech)


def main() -> None:
    parser = argparse.ArgumentParser(description="清理会泄露答案的题库释义")
    parser.add_argument("--bank", type=Path, default=Path("quiz-bank.json"))
    args = parser.parse_args()
    root: dict[str, Any] = json.loads(args.bank.read_text(encoding="utf-8"))
    questions = root.get("questions")
    if not isinstance(questions, list):
        raise SystemExit("questions 必须是数组")
    changed = 0
    for question in questions:
        if not isinstance(question, dict):
            raise SystemExit("题目必须是对象")
        word = str(question.get("word", "")).strip()
        meaning = str(question.get("meaning", "")).strip()
        if not word or word not in meaning:
            continue
        sanitized = sanitize(word, str(question.get("partOfSpeech", "")), meaning)
        if sanitized != meaning:
            question["meaning"] = sanitized
            changed += 1
    args.bank.write_bytes((json.dumps(root, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"已清理 {changed} 条会泄露答案的释义。")


if __name__ == "__main__":
    main()
