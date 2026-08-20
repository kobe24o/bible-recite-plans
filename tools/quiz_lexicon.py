"""Versioned Bible-term helpers used only while publishing a quiz bank."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable


@dataclass(frozen=True)
class LexiconTerm:
    term: str
    aliases: tuple[str, ...]
    kind: str
    meaning: str
    source: str

    @property
    def spellings(self) -> tuple[str, ...]:
        return (self.term, *self.aliases)


@dataclass(frozen=True)
class LocatedTerm:
    term: LexiconTerm
    start: int
    end: int
    spelling: str


def load_terms(path: Path) -> tuple[LexiconTerm, ...]:
    root = json.loads(path.read_text(encoding="utf-8"))
    if root.get("format") != "bible-recite-bible-terms" or root.get("version") != 1:
        raise ValueError("词典格式或版本无效")
    raw_terms = root.get("terms")
    if not isinstance(raw_terms, list):
        raise ValueError("词典 terms 必须是数组")
    terms: list[LexiconTerm] = []
    seen_spellings: set[str] = set()
    for item in raw_terms:
        if not isinstance(item, dict):
            raise ValueError("词典条目必须是对象")
        term = _non_empty_text(item, "term")
        aliases_raw = item.get("aliases", [])
        if not isinstance(aliases_raw, list) or not all(
            isinstance(value, str) and value.strip() for value in aliases_raw
        ):
            raise ValueError(f"词典条目 {term} 的 aliases 无效")
        lexicon_term = LexiconTerm(
            term=term,
            aliases=tuple(value.strip() for value in aliases_raw),
            kind=_non_empty_text(item, "kind"),
            meaning=_non_empty_text(item, "meaning"),
            source=_non_empty_text(item, "source"),
        )
        for spelling in lexicon_term.spellings:
            if spelling in seen_spellings:
                raise ValueError(f"词典词形重复：{spelling}")
            seen_spellings.add(spelling)
        terms.append(lexicon_term)
    return tuple(terms)


def find_overlapping_terms(
    text: str,
    start: int,
    end: int,
    terms: Iterable[LexiconTerm],
) -> list[LocatedTerm]:
    """Return full known terms whose UTF-16 span intersects the candidate."""
    if start < 0 or end <= start:
        return []
    boundaries = _utf16_boundaries(text)
    if end > boundaries[-1]:
        return []
    found: list[LocatedTerm] = []
    for term in terms:
        for spelling in term.spellings:
            code_point_start = text.find(spelling)
            while code_point_start >= 0:
                code_point_end = code_point_start + len(spelling)
                term_start = boundaries[code_point_start]
                term_end = boundaries[code_point_end]
                if term_start < end and start < term_end:
                    found.append(LocatedTerm(term, term_start, term_end, spelling))
                code_point_start = text.find(spelling, code_point_start + 1)
    return sorted(found, key=lambda item: (item.start, item.end, item.term.term))


def target_question_limit(text: str) -> int:
    """Choose a length-aware upper bound, never exceeding five questions."""
    cjk_count = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))
    if cjk_count < 20:
        return 1
    if cjk_count < 40:
        return 2
    if cjk_count < 70:
        return 3
    if cjk_count < 100:
        return 4
    return 5


def add_terms_to_jieba(terms: Iterable[LexiconTerm]) -> None:
    """Register custom terms for an optional offline audit; no runtime use."""
    import jieba

    for term in terms:
        for spelling in term.spellings:
            jieba.add_word(spelling)


def _utf16_boundaries(text: str) -> list[int]:
    boundaries = [0]
    for character in text:
        boundaries.append(boundaries[-1] + len(character.encode("utf-16-le")) // 2)
    return boundaries


def _non_empty_text(item: dict[str, Any], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"词典条目缺少 {field}")
    return value.strip()
