#!/usr/bin/env python3
"""Classify historical quiz entries as complete-word candidates or quarantine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from audit_quiz_bank_quality import audit_questions, question_key
from generate_quiz_bank import FUNCTION_WORDS
from quiz_lexicon import LexiconTerm, find_overlapping_terms


_OLD_MEANING_FINDINGS = {"answer_leaking_meaning", "generic_meaning"}


@dataclass(frozen=True)
class CandidateDecision:
    key: str
    accepted: bool
    reasons: tuple[str, ...]
    question: dict[str, object]


def _is_complete_lexicon_term(
    question: dict[str, object], terms: Iterable[LexiconTerm]
) -> bool:
    try:
        start, end = int(question["start"]), int(question["end"])
        word = str(question["word"])
    except (KeyError, TypeError, ValueError):
        return False
    text = str(question.get("_scripture_text", ""))
    return any(
        item.start == start and item.end == end and item.spelling == word
        for item in find_overlapping_terms(text, start, end, terms)
    )


def classify_question(
    question: dict[str, object],
    scripture: dict[str, str],
    terms: Iterable[LexiconTerm],
    rules: dict[str, object],
) -> CandidateDecision:
    """Return a conservative decision without altering the input question."""
    copied = dict(question)
    word = str(copied.get("word", "")).strip()
    if word in FUNCTION_WORDS:
        return CandidateDecision(question_key(copied), False, ("function_word",), copied)

    scripture_text = scripture.get(
        ":".join(str(copied.get(field, "")) for field in ("bookId", "chapter", "verse"))
    )
    if scripture_text is not None:
        copied["_scripture_text"] = scripture_text
    findings = audit_questions([copied], scripture, terms, rules)
    complete_term = _is_complete_lexicon_term(copied, terms)
    reasons = tuple(
        finding.code
        for finding in findings
        if finding.code not in _OLD_MEANING_FINDINGS
        and not (complete_term and finding.code == "partial_segmented_term")
    )
    copied.pop("_scripture_text", None)
    return CandidateDecision(question_key(copied), not reasons, reasons, copied)
