#!/usr/bin/env python3
"""Compatibility entry point for the stable quality-v3 snapshot publisher."""

from __future__ import annotations

import argparse
from pathlib import Path

from publish_quiz_snapshot import DEFAULT_MAX_BYTES, publish_snapshot


def split_quiz_bank(input_path: Path, output_dir: Path, index_path: Path, revision: int, max_bytes: int) -> list[dict]:
    """Publish replacement shards; callers must supply one new global revision."""
    return publish_snapshot(
        input_path,
        output_dir,
        index_path,
        revision,
        max_bytes=max_bytes,
    )["shards"]


def main() -> None:
    parser = argparse.ArgumentParser(description="发布稳定的 replace 题库分片（兼容旧命令名）")
    parser.add_argument("--input", type=Path, default=Path("quiz-bank.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--index", type=Path, default=Path("quiz-bank.index.json"))
    parser.add_argument("--revision", type=int, required=True, help="必须大于当前已发布 revision")
    args = parser.parse_args()
    shards = split_quiz_bank(args.input, args.output_dir, args.index, args.revision, args.max_bytes)
    print(f"已发布 {len(shards)} 个 quality-v3 replace 分片，revision {args.revision}。")


if __name__ == "__main__":
    main()
