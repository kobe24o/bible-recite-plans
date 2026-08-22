#!/usr/bin/env python3
"""Create fact-backed, non-leaking meaning drafts for historical quiz entries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from audit_quiz_bank_quality import question_key
from bible_context import ContextFact


@dataclass(frozen=True)
class RewriteDraft:
    key: str
    meaning: str | None
    source: str
    evidence_references: tuple[str, ...]


def _normalized(value: str) -> str:
    return "".join(value.strip().split())


def build_rewrite_prompt(question: dict[str, object], fact: ContextFact) -> str:
    """Build a constrained model prompt for facts without a deterministic draft."""
    return (
        "为背诵填空题写一句简洁中文释义。不得包含答案原文、其别名或本节经文的逐字片段；"
        "不得仅写人名、地名、人物、地点等泛化类别。只能根据提供的具体圣经事实说明角色、关系、"
        "事件、地点用途或概念作用；事实不足则返回 null。"
        f"\n答案原文：{question['word']}"
        f"\n词类：{question['partOfSpeech']}"
        f"\n具体事实：{'；'.join(fact.facts)}"
        f"\n事实出处：{','.join(fact.references)}"
        "\n仅返回 JSON 对象：{\"meaning\": string|null, \"evidenceReferences\": [string]}。"
    )


def deterministic_draft(question: dict[str, object], fact: ContextFact) -> RewriteDraft:
    """Use a curated fact directly when it does not expose the answer."""
    word = _normalized(str(question.get("word", "")))
    meaning = next((item for item in fact.facts if word and word not in _normalized(item)), None)
    return RewriteDraft(
        key=question_key(question),
        meaning=meaning,
        source="context" if meaning is not None else "quarantine",
        evidence_references=fact.references,
    )
