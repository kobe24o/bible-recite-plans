#!/usr/bin/env python3
"""Local helper (not committed): generate a 2nd question per verse.

For each verse in a book/chapter range that already has fewer than
--max-per-verse questions, ask an OpenAI-compatible model to pick a word at a
position that does NOT overlap any already-used span. Offsets are resolved
locally against the bundled scripture (UTF-16 aware); every existing rule from
generate_quiz_bank.py is re-applied. Writes a v2 bank-format batch file with
prefixed meanings, ready for tools/merge_quiz_banks.py.

Usage:
  QUIZ_MODEL_API_KEY=... python3 tools/_gen_second.py \
    --book NUM --start-ch 13 --end-ch 15 \
    --base-url https://open.bigmodel.cn/api/paas/v4 --model glm-4.7-flash \
    --batch-out tools/batch_num_13_15.json
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_quiz_bank import (  # noqa: E402
    FORMAT,
    VERSION,
    is_meaning_for_word,
    is_valid_word,
    load_bank,
    query_verses,
    utf16_length,
    utf16_slice,
)

BATCH_FORMAT = "bible-recite-quiz-bank"
BATCH_VERSION = 2


def find_free_offsets(text: str, word: str, used: set[tuple[int, int]]) -> tuple[int, int] | None:
    """First UTF-16 span of word in text not overlapping any used span."""
    needle = word
    search_from = 0
    while True:
        index = text.find(needle, search_from)
        if index < 0:
            return None
        start = utf16_length(text[:index])
        end = start + utf16_length(needle)
        if utf16_slice(text, start, end) == needle and (start, end) not in used and is_valid_word(needle):
            return start, end
        search_from = index + 1


def build_prompt() -> str:
    return """你是一位严格的圣经经文出题助手。根据用户提供的每节经文，挑选一个语义丰富、可朗读的词作为隐藏词，用于“听词填空”练习。
只返回 JSON 数组，不要输出其他文字。每一节输入经文恰好一题；字段固定为 reference、word、partOfSpeech、meaning。
reference 必须一字不差来自输入；word 必须是该节原文里真实存在的一个连续片段，且不能与输入中标注的“已选词”所在位置重叠（不能是同一个词，也不能包含已选词）。
只选择人物、地点、具体事物、重要事件、核心动词或形容词等可独立表达具体意义、适合朗读回答的实词。
绝不选择连接词、介词、助词、语气词、代词、标点、数字、无完整意义的片段，也不要选择“某人说”“某人回答”“某人吩咐/告诉”这类发话标签或整句；不要选择以“你/我/他/她/它/的/了/着/上/下/里/中/不/以/为/那/这/和/与/从/对/把/被/给/到/在/是/有/就/都/也/又/会/能/要/等”等虚词开头或结尾的词，也不要选单个虚词。
meaning 必须严格为“word：简短字面解释”，且只能解释 word 本身，不能解释相邻经文、动作或上下文。
如果该节确实没有合适的第二词可选，就跳过该节，不要返回该项。先核验词是否真实存在于原文；不准确就不返回该项。只输出 JSON。"""


def call_model(base_url: str, api_key: str, model: str, verses: list[dict[str, Any]], timeout: int) -> list[dict[str, Any]]:
    import urllib.error
    import urllib.request

    lines = []
    for item in verses:
        used_words = "；".join(item["used_words"]) if item["used_words"] else "无"
        lines.append(f"{item['reference']}：{item['text']}（已选词：{used_words}）")
    user = "经文语言版本：cmn-cu89s\n每一节恰好生成一题（没有合适第二词的节跳过）；只返回 JSON 数组。\n经文列表：\n" + "\n".join(lines)
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": build_prompt()}, {"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": 4096,
        "thinking": {"type": "disabled"},
    }, ensure_ascii=False).encode("utf-8")
    endpoint = base_url.rstrip("/") + "/chat/completions"
    request = urllib.request.Request(endpoint, data=body, method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json", "Authorization": f"Bearer {api_key}",
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"模型返回 HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"无法连接模型：{error.reason}") from error
    content = payload.get("choices", [{}])[0].get("message", {}).get("content")
    if not isinstance(content, str):
        raise RuntimeError("模型响应没有 message.content")
    left, right = content.find("["), content.rfind("]")
    if left < 0 or right <= left:
        raise RuntimeError("模型响应没有 JSON 数组")
    result = json.loads(content[left : right + 1])
    if not isinstance(result, list):
        raise RuntimeError("模型响应不是数组")
    return [item for item in result if isinstance(item, dict)]


def main() -> None:
    parser = argparse.ArgumentParser(description="为每节生成位置不同的第二题")
    parser.add_argument("--scripture", type=Path, default=Path("scripture/cmn-cu89s/scripture.sqlite"))
    parser.add_argument("--bank", type=Path, default=Path("quiz-bank.json"))
    parser.add_argument("--batch-out", required=True, type=Path)
    parser.add_argument("--translation-id", default="cmn-cu89s")
    parser.add_argument("--book", required=True, help="OSIS 卷名，例如 NUM")
    parser.add_argument("--start-ch", required=True, type=int)
    parser.add_argument("--end-ch", required=True, type=int)
    parser.add_argument("--max-per-verse", type=int, default=2)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key-env", default="QUIZ_MODEL_API_KEY")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        parser.error(f"未设置环境变量 {args.api_key_env}；不要把 API Key 写进命令、代码或题库。")

    existing = load_bank(args.bank)
    used_spans: dict[tuple[int, int], list[tuple[int, int, str]]] = {}
    for q in existing:
        if q["bookId"] == args.book and args.start_ch <= q["chapter"] <= args.end_ch:
            used_spans.setdefault((q["chapter"], q["verse"]), []).append((q["start"], q["end"], q["word"]))

    verses = query_verses(args.scripture, args.book, None, None, None)
    target = []
    for verse in verses:
        if not (args.start_ch <= verse["chapter"] <= args.end_ch):
            continue
        verse["reference"] = f"{verse['chapter']}:{verse['verse']}"
        spans = used_spans.get((verse["chapter"], verse["verse"]), [])
        if len(spans) < args.max_per_verse:
            verse["used_spans"] = spans
            verse["used_words"] = sorted({w for _, _, w in spans})
            target.append(verse)
    print(f"{args.book} {args.start_ch}-{args.end_ch}：{len(target)} 节需要第 {args.max_per_verse} 题")

    raw = call_model(args.base_url, api_key, args.model, target, args.timeout)
    by_reference = {verse["reference"]: verse for verse in target}

    accepted: list[dict[str, Any]] = []
    seen: set[str] = set()
    skipped: list[tuple[str, str]] = []
    for item in raw:
        reference = str(item.get("reference", ""))
        source = by_reference.get(reference)
        if source is None or reference in seen:
            continue
        word = str(item.get("word", "")).strip()
        pos = str(item.get("partOfSpeech", "")).strip()
        meaning = str(item.get("meaning", "")).strip()
        if not word or not pos or not is_meaning_for_word(word, meaning):
            skipped.append((reference, f"字段不完整/释义无前缀 word:{word}"))
            continue
        used = {(s, e) for s, e, _ in source["used_spans"]}
        offsets = find_free_offsets(source["text"], word, used)
        if offsets is None:
            skipped.append((reference, f"无空闲位置 word:{word}"))
            continue
        start, end = offsets
        accepted.append({
            "translationId": args.translation_id, "bookId": source["book_id"], "chapter": source["chapter"],
            "verse": source["verse"], "start": start, "end": end, "word": word,
            "partOfSpeech": pos, "meaning": meaning,
            "reference": reference,
        })
        seen.add(reference)

    payload = {"format": BATCH_FORMAT, "version": BATCH_VERSION, "questions": accepted}
    args.batch_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"模型返回 {len(raw)} 道，通过校验 {len(accepted)} 道 -> {args.batch_out}")
    if skipped:
        print("跳过：")
        for ref, why in skipped:
            print(f"  {ref}  {why}")
    missing = [v["reference"] for v in target if v["reference"] not in seen]
    if missing:
        print(f"模型未返回的节（{len(missing)}）：{', '.join(missing[:30])}")


if __name__ == "__main__":
    main()
