#!/usr/bin/env python3
"""Versioned, reference-backed Bible facts for quiz meaning rewrites."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path


_REFERENCE = re.compile(r"^[A-Z0-9]{3,6}:\d+:\d+$")
_GENERIC_FACTS = {"人名", "地名", "人物", "地点", "群体", "事物", "专名"}


@dataclass(frozen=True)
class ContextFact:
    term: str
    kind: str
    facts: tuple[str, ...]
    references: tuple[str, ...]
    source: str


def _strings(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{name} 必须是非空字符串数组")
    return tuple(item.strip() for item in value)


def load_context_facts(path: Path) -> dict[str, ContextFact]:
    """Load specific, scripture-referenced facts and aliases by lookup term."""
    root = json.loads(path.read_text(encoding="utf-8"))
    if root.get("format") != "bible-recite-bible-context" or root.get("version") != 1:
        raise ValueError("圣经事实条目格式或版本无效")
    entries = root.get("entries")
    if not isinstance(entries, list):
        raise ValueError("entries 必须是数组")

    result: dict[str, ContextFact] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("事实条目必须是对象")
        term = entry.get("term")
        kind = entry.get("kind")
        source = entry.get("source")
        if not all(isinstance(value, str) and value.strip() for value in (term, kind, source)):
            raise ValueError("事实条目缺少 term、kind 或 source")
        facts = _strings(entry.get("facts"), "facts")
        if any(fact in _GENERIC_FACTS or len(fact) < 6 for fact in facts):
            raise ValueError("facts 必须包含具体事实，不能只写泛化类别")
        references = _strings(entry.get("references"), "references")
        if any(_REFERENCE.fullmatch(reference) is None for reference in references):
            raise ValueError("references 必须使用 OSIS:章:节格式")
        aliases_value = entry.get("aliases", [])
        if not isinstance(aliases_value, list) or not all(isinstance(alias, str) and alias.strip() for alias in aliases_value):
            raise ValueError("aliases 必须是字符串数组")

        fact = ContextFact(term.strip(), kind.strip(), facts, references, source.strip())
        for lookup in (fact.term, *(alias.strip() for alias in aliases_value)):
            existing = result.get(lookup)
            if existing is not None and existing != fact:
                raise ValueError(f"词条或别名重复：{lookup}")
            result[lookup] = fact
    return result
