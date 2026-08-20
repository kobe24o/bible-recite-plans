#!/usr/bin/env python3
"""Split a single quiz-bank.json into multiple shards smaller than 10MB.

Strategy: Fill earlier shards first. This minimizes the number of files that
change when new questions are added - typically only the last shard grows.

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
    """Split the quiz bank into shards and return index entries.
    
    Strategy: Fill shard 01 first, then shard 02, etc. This minimizes
    file changes when new questions are added - only the last shard grows.
    """
    root = json.loads(input_path.read_text(encoding="utf-8"))
    questions = root.get("questions", [])
    
    if not questions:
        raise SystemExit("No questions to split")
    
    # Calculate average bytes per question for estimation
    total_bytes = len(json.dumps(root, ensure_ascii=False, indent=2).encode("utf-8"))
    avg_bytes_per_q = total_bytes / len(questions)
    
    # Use 80% of max as target to leave safety margin
    target_bytes = int(max_bytes * 0.8)
    questions_per_shard = max(1, int(target_bytes / avg_bytes_per_q))
    
    # Build shards by filling earlier ones first
    shards_data: list[list[dict]] = []
    
    for i in range(0, len(questions), questions_per_shard):
        shard_questions = questions[i:i + questions_per_shard]
        shards_data.append(shard_questions)
    
    # Write shards
    shards = []
    for i, shard_questions in enumerate(shards_data, 1):
        shard_root = {
            "format": FORMAT,
            "version": VERSION,
            "questions": shard_questions,
        }
        
        shard_name = f"quiz-bank-{i:02d}.json"
        shard_path = output_dir / shard_name
        shard_path.write_text(
            json.dumps(shard_root, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        
        actual_bytes = shard_path.stat().st_size
        if actual_bytes > max_bytes:
            print(f"Warning: {shard_name} is {actual_bytes} bytes (>{max_bytes})")
        
        shards.append({
            "path": shard_name,
            "sha256": file_sha256(shard_path),
            "bytes": actual_bytes,
        })
        
        print(f"  {shard_name}: {len(shard_questions)} questions, {actual_bytes} bytes")
    
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
