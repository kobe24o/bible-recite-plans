#!/usr/bin/env python3
"""Split a single quiz-bank.json into multiple shards smaller than 10MB.

Usage:
  python tools/split_quiz_bank.py --input quiz-bank.json --output-dir . --max-bytes 10000000
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FORMAT = "bible-recite-quiz-bank"
VERSION = 2
INDEX_FORMAT = "bible-recite-quiz-bank-index"
INDEX_VERSION = 1
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10MB


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_quiz_bank(input_path: Path, output_dir: Path, max_bytes: int) -> list[dict]:
    """Split the quiz bank into shards and return index entries."""
    root = json.loads(input_path.read_text(encoding="utf-8"))
    questions = root.get("questions", [])
    
    if not questions:
        raise SystemExit("No questions to split")
    
    # Try to split evenly across multiple shards
    # Estimate: we need ceil(total_bytes / max_bytes) shards
    total_bytes = len(json.dumps(root, ensure_ascii=False, indent=2).encode("utf-8"))
    num_shards = max(1, (total_bytes + max_bytes - 1) // max_bytes)
    questions_per_shard = (len(questions) + num_shards - 1) // num_shards
    
    shards = []
    shard_index = 1
    
    for i in range(0, len(questions), questions_per_shard):
        shard_questions = questions[i:i + questions_per_shard]
        shard_root = {
            "format": FORMAT,
            "version": VERSION,
            "questions": shard_questions,
        }
        
        # Write shard
        shard_name = f"quiz-bank-{shard_index:02d}.json"
        shard_path = output_dir / shard_name
        shard_path.write_text(
            json.dumps(shard_root, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        
        # Check actual size
        actual_bytes = shard_path.stat().st_size
        if actual_bytes > max_bytes:
            print(f"Warning: {shard_name} is {actual_bytes} bytes (>{max_bytes})")
        
        shards.append({
            "path": shard_name,
            "sha256": file_sha256(shard_path),
            "bytes": actual_bytes,
        })
        
        print(f"  {shard_name}: {len(shard_questions)} questions, {actual_bytes} bytes")
        shard_index += 1
    
    return shards


def main():
    parser = argparse.ArgumentParser(description="Split quiz bank into <10MB shards")
    parser.add_argument("--input", type=Path, default=Path("quiz-bank.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--index", type=Path, default=Path("quiz-bank.index.json"))
    args = parser.parse_args()
    
    print(f"Splitting {args.input} into shards (max {args.max_bytes} bytes)...")
    shards = split_quiz_bank(args.input, args.output_dir, args.max_bytes)
    
    # Read existing index to get current revision
    if args.index.exists():
        index_root = json.loads(args.index.read_text(encoding="utf-8"))
        revision = index_root.get("revision", 0)
    else:
        revision = 0
    
    # Write index
    index_root = {
        "format": INDEX_FORMAT,
        "version": INDEX_VERSION,
        "revision": revision,
        "shards": shards,
    }
    args.index.write_text(
        json.dumps(index_root, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Updated {args.index} (revision {revision}, {len(shards)} shards)")


if __name__ == "__main__":
    main()
