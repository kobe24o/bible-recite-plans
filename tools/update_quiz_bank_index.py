#!/usr/bin/env python3
"""Recalculate quiz-bank.index.json after quiz-bank.json changes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def git_bytes(path: Path) -> bytes:
    """Use the LF bytes Git publishes, even from a Windows CRLF checkout."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="更新 BibleRecite 题库索引")
    parser.add_argument("--bank", type=Path, default=Path("quiz-bank.json"))
    parser.add_argument("--index", type=Path, default=Path("quiz-bank.index.json"))
    parser.add_argument("--revision", type=int, help="显式指定 revision；默认在原值上加一")
    args = parser.parse_args()

    bank_bytes = git_bytes(args.bank)
    root = json.loads(args.index.read_text(encoding="utf-8")) if args.index.exists() else {
        "format": "bible-recite-quiz-bank-index", "version": 1, "revision": 0, "shards": []
    }
    if root.get("format") != "bible-recite-quiz-bank-index" or root.get("version") != 1:
        raise ValueError("现有 index 格式无效")
    path = args.bank.as_posix()
    digest = hashlib.sha256(bank_bytes).hexdigest()
    shard = {"path": path, "sha256": digest, "bytes": len(bank_bytes)}
    shards = [item for item in root.get("shards", []) if item.get("path") != path]
    shards.append(shard)
    root["shards"] = sorted(shards, key=lambda item: item["path"])
    root["revision"] = args.revision if args.revision is not None else int(root.get("revision", 0)) + 1
    args.index.write_bytes((json.dumps(root, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"revision {root['revision']}，{path}：{len(bank_bytes)} bytes，sha256 {digest}")


if __name__ == "__main__":
    main()
