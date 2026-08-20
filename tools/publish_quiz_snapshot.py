#!/usr/bin/env python3
"""Publish a complete, revisioned replacement snapshot from one quiz bank."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any


FORMAT = "bible-recite-quiz-bank"
VERSION = 2
INDEX_FORMAT = "bible-recite-quiz-bank-index"
INDEX_VERSION = 1
DEFAULT_MAX_BYTES = 10 * 1024 * 1024
SAFETY_MARGIN_BYTES = 1024


def publish_snapshot(
    input_bank: dict[str, Any] | Path,
    output_dir: Path,
    index_path: Path,
    revision: int,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    """Stage and publish a complete replacement bank with a strictly newer revision."""
    bank = _load_bank(input_bank)
    if revision < 1:
        raise ValueError("revision must be positive")
    if index_path.exists():
        existing = json.loads(index_path.read_text(encoding="utf-8"))
        if revision <= int(existing.get("revision", 0)):
            raise ValueError("revision must exceed the published revision")
    if max_bytes <= SAFETY_MARGIN_BYTES:
        raise ValueError("max_bytes must exceed the safety margin")
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".quiz-snapshot-", dir=output_dir.parent))
    try:
        shards = _write_staged_shards(bank["questions"], staging, max_bytes)
        manifest = {
            "format": INDEX_FORMAT,
            "version": INDEX_VERSION,
            "revision": revision,
            "snapshotMode": "replace",
            "qualityVersion": 3,
            "shards": shards,
        }
        staged_index = staging / index_path.name
        staged_index.write_bytes(_json_bytes(manifest))
        _activate_staged_snapshot(staging, output_dir, index_path, shards)
        return manifest
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _load_bank(input_bank: dict[str, Any] | Path) -> dict[str, Any]:
    root = json.loads(input_bank.read_text(encoding="utf-8")) if isinstance(input_bank, Path) else input_bank
    if root.get("format") != FORMAT or root.get("version") != VERSION:
        raise ValueError("input bank must be bible-recite-quiz-bank v2")
    if not isinstance(root.get("questions"), list):
        raise ValueError("input bank questions must be a list")
    return root


def _write_staged_shards(questions: list[dict[str, Any]], staging: Path, max_bytes: int) -> list[dict[str, Any]]:
    limit = max_bytes - SAFETY_MARGIN_BYTES
    shards: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for question in questions:
        candidate = [*current, question]
        if len(_shard_bytes(candidate)) <= limit:
            current = candidate
            continue
        if not current:
            raise ValueError("a single question exceeds the shard size limit")
        shards.append(_write_shard(staging, len(shards) + 1, current, max_bytes))
        if len(_shard_bytes([question])) > limit:
            raise ValueError("a single question exceeds the shard size limit")
        current = [question]
    if current:
        shards.append(_write_shard(staging, len(shards) + 1, current, max_bytes))
    if not shards:
        raise ValueError("input bank has no questions")
    return shards


def _write_shard(staging: Path, number: int, questions: list[dict[str, Any]], max_bytes: int) -> dict[str, Any]:
    name = f"quiz-bank-{number:02d}.json"
    payload = _shard_bytes(questions)
    if len(payload) >= max_bytes:
        raise ValueError("staged shard exceeds the configured size limit")
    path = staging / name
    path.write_bytes(payload)
    return {"path": name, "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}


def _shard_bytes(questions: list[dict[str, Any]]) -> bytes:
    return _json_bytes({"format": FORMAT, "version": VERSION, "questions": questions})


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _activate_staged_snapshot(
    staging: Path, output_dir: Path, index_path: Path, shards: list[dict[str, Any]]
) -> None:
    published = {str(item["path"]) for item in shards}
    for name in published:
        os.replace(staging / name, output_dir / name)
    os.replace(staging / index_path.name, index_path)
    for stale in output_dir.glob("quiz-bank-*.json"):
        if stale.name not in published:
            stale.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="发布稳定的质量 v3 题库快照")
    parser.add_argument("--input", type=Path, default=Path("quiz-bank.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument("--index", type=Path, default=Path("quiz-bank.index.json"))
    parser.add_argument("--revision", type=int, required=True)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args()
    manifest = publish_snapshot(args.input, args.output_dir, args.index, args.revision, max_bytes=args.max_bytes)
    print(f"已发布 revision {manifest['revision']}，{len(manifest['shards'])} 个 replace 分片。")


if __name__ == "__main__":
    main()
