#!/usr/bin/env python3
"""Create an auditable complete-word candidate report from historical shards."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable

from audit_quiz_bank_quality import question_key
from historical_quiz_candidates import CandidateDecision, classify_question
from quiz_lexicon import LexiconTerm, load_terms
from audit_quiz_bank_quality import load_rules
from validate_quiz_bank import load_sources


@dataclass(frozen=True)
class CandidateReview:
    accepted: list[dict[str, object]]
    quarantine: list[dict[str, object]]

    @property
    def accepted_count(self) -> int:
        return len(self.accepted)

    @property
    def quarantine_count(self) -> int:
        return len(self.quarantine)


def _record(decision: CandidateDecision) -> dict[str, object]:
    return {
        "key": decision.key,
        "question": decision.question,
        "reasons": list(decision.reasons),
    }


def review_candidates(
    questions: Iterable[dict[str, object]],
    scripture: dict[str, str],
    terms: Iterable[LexiconTerm],
    rules: dict[str, object],
) -> CandidateReview:
    """Assign every input question once to accepted candidates or quarantine."""
    accepted: list[dict[str, object]] = []
    quarantine: list[dict[str, object]] = []
    accepted_keys: set[str] = set()
    for question in questions:
        decision = classify_question(question, scripture, terms, rules)
        if decision.accepted and decision.key in accepted_keys:
            quarantine.append(
                _record(CandidateDecision(decision.key, False, ("duplicate_position",), decision.question))
            )
            continue
        if decision.accepted:
            accepted_keys.add(decision.key)
            accepted.append(_record(decision))
        else:
            quarantine.append(_record(decision))
    return CandidateReview(accepted, quarantine)


def _git_show(repository: Path, revision: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        cwd=repository,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"无法读取历史输入 {revision}:{path}: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def load_historical_questions(repository: Path, revision: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Load and hash every shard explicitly referenced by a historical index."""
    index_bytes = _git_show(repository, revision, "quiz-bank.index.json")
    index = json.loads(index_bytes.decode("utf-8"))
    shards = index.get("shards")
    if not isinstance(shards, list) or not shards:
        raise ValueError("历史索引没有 shards")
    questions: list[dict[str, object]] = []
    manifest_shards: list[dict[str, object]] = []
    for shard in shards:
        if not isinstance(shard, dict) or not isinstance(shard.get("path"), str):
            raise ValueError("历史索引含有无效分片")
        path = shard["path"]
        data = _git_show(repository, revision, path)
        actual_sha = hashlib.sha256(data).hexdigest()
        if shard.get("sha256") != actual_sha:
            raise ValueError(f"历史分片哈希不匹配：{path}")
        if shard.get("bytes") != len(data):
            raise ValueError(f"历史分片大小不匹配：{path}")
        root = json.loads(data.decode("utf-8"))
        entries = root.get("questions")
        if not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
            raise ValueError(f"历史分片 questions 无效：{path}")
        questions.extend(entries)
        manifest_shards.append({"path": path, "sha256": actual_sha, "bytes": len(data), "questions": len(entries)})
    return (
        {
            "historicalRevision": revision,
            "indexSha256": hashlib.sha256(index_bytes).hexdigest(),
            "shards": manifest_shards,
            "totalQuestions": len(questions),
        },
        questions,
    )


def _write_jsonl(path: Path, records: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as target:
        for record in records:
            target.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _flatten_sources(sources: dict[str, dict[tuple[str, int, int], str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for verses in sources.values():
        for (book, chapter, verse), text in verses.items():
            result[f"{book}:{chapter}:{verse}"] = text
    return result


def _summary(review: CandidateReview, total: int) -> str:
    reasons = Counter(
        reason for record in review.quarantine for reason in record["reasons"] if isinstance(reason, str)
    )
    lines = [
        "# 历史题库完整词候选报告",
        "",
        f"- 输入题数：{total}",
        f"- 通过候选：{review.accepted_count}",
        f"- 隔离题目：{review.quarantine_count}",
        "",
        "## 隔离原因",
        "",
    ]
    lines.extend(f"- `{reason}`：{count}" for reason, count in sorted(reasons.items()))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="审阅历史分片中的完整词候选，不改写或发布题库")
    parser.add_argument("--historical-revision", default="e242fe2")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--lexicon", type=Path, default=Path("lexicon/bible_terms.v1.json"))
    parser.add_argument("--meaning-rules", type=Path, default=Path("lexicon/meaning_rules.v1.json"))
    parser.add_argument("--scripture", type=Path, default=Path("scripture/cmn-cu89s/scripture.sqlite"))
    args = parser.parse_args()
    manifest, questions = load_historical_questions(Path.cwd(), args.historical_revision)
    if args.limit is not None:
        questions = questions[: args.limit]
        manifest["limitedTo"] = len(questions)
    sources = load_sources([("cmn-cu89s", args.scripture)])
    review = review_candidates(questions, _flatten_sources(sources), load_terms(args.lexicon), load_rules(args.meaning_rules))
    if review.accepted_count + review.quarantine_count != len(questions):
        raise AssertionError("历史题目没有被唯一归类")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "input-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_jsonl(args.output_dir / "candidates.jsonl", review.accepted)
    _write_jsonl(args.output_dir / "quarantine.jsonl", review.quarantine)
    (args.output_dir / "summary.md").write_text(_summary(review, len(questions)), encoding="utf-8")
    print(f"历史题 {len(questions)} 道：完整词候选 {review.accepted_count}，隔离 {review.quarantine_count}。")


if __name__ == "__main__":
    main()
