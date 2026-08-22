#!/usr/bin/env python3
"""Deterministic acceptance checks for rewritten quiz meanings."""

from __future__ import annotations

from dataclasses import dataclass

from bible_context import ContextFact
from rewrite_historical_quiz_meanings import RewriteDraft


@dataclass(frozen=True)
class MeaningAudit:
    accepted: bool
    reasons: tuple[str, ...]


def _normalized(value: object) -> str:
    return "".join(str(value).strip().split())


def audit_rewrite(
    question: dict[str, object],
    draft: RewriteDraft,
    rules: dict[str, object],
    fact: ContextFact | None,
) -> MeaningAudit:
    """Reject leaks, vague labels and claims that lack cited Bible facts."""
    meaning = _normalized(draft.meaning or "")
    word = _normalized(question.get("word", ""))
    reasons: list[str] = []
    if not meaning:
        reasons.append("missing_meaning")
    elif word and word in meaning:
        reasons.append("answer_leak")
    else:
        patterns = tuple(
            _normalized(value)
            for value in rules.get("forbiddenGenericPatterns", [])
            if isinstance(value, str)
        )
        exact = tuple(
            _normalized(value)
            for value in rules.get("forbiddenExactMeanings", [])
            if isinstance(value, str)
        )
        is_generic = meaning in exact or any(pattern and pattern in meaning for pattern in patterns)
        if is_generic:
            reasons.append("generic_meaning")
        minimum = rules.get("minimumMeaningChars", 1)
        if not isinstance(minimum, int) or minimum < 1:
            raise ValueError("minimumMeaningChars 必须是正整数")
        if not is_generic and len(meaning) < minimum:
            reasons.append("meaning_too_short")
    if fact is None or not draft.evidence_references or not set(draft.evidence_references).issubset(fact.references):
        reasons.append("unsupported_bible_fact")
    return MeaningAudit(not reasons, tuple(reasons))
