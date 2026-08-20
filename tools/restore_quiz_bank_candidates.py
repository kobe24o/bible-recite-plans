#!/usr/bin/env python3
"""Restore quiz candidates while replacing their hints with safe generic meanings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sanitize_quiz_meanings import fallback_hint


def question_key(question: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(
        question[field]
        for field in (
            "translationId",
            "bookId",
            "chapter",
            "verse",
            "start",
            "end",
        )
    )


def restore_candidates(
    current_questions: list[dict[str, Any]],
    backup_questions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Rebuild the bank in backup order and safely restore absent candidates."""
    current_by_key = {question_key(question): question for question in current_questions}
    restored: list[dict[str, Any]] = []
    restored_count = 0

    for backup_question in backup_questions:
        current_question = current_by_key.pop(question_key(backup_question), None)
        if current_question is not None:
            restored.append(current_question)
            continue

        restored_question = dict(backup_question)
        restored_question["meaning"] = fallback_hint(
            str(restored_question["word"]),
            str(restored_question["partOfSpeech"]),
        )
        restored.append(restored_question)
        restored_count += 1

    if current_by_key:
        raise ValueError("当前题库含有备份题库中不存在的题目位置，拒绝覆盖")
    return restored, restored_count


def load_questions(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root = json.loads(path.read_text(encoding="utf-8"))
    questions = root.get("questions")
    if not isinstance(questions, list) or not all(isinstance(item, dict) for item in questions):
        raise ValueError(f"{path} 的 questions 必须是对象数组")
    return root, questions


def main() -> None:
    parser = argparse.ArgumentParser(description="恢复题库候选题并改写恢复题目的释义")
    parser.add_argument("--bank", type=Path, default=Path("quiz-bank.json"))
    parser.add_argument("--backup", type=Path, required=True, help="包含被删除题目的已验证题库")
    args = parser.parse_args()

    root, current_questions = load_questions(args.bank)
    _, backup_questions = load_questions(args.backup)
    questions, restored_count = restore_candidates(current_questions, backup_questions)
    root["questions"] = questions
    args.bank.write_text(
        json.dumps(root, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已恢复 {restored_count} 道题；题库现有 {len(questions)} 道题。")


if __name__ == "__main__":
    main()
