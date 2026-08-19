#!/usr/bin/env python3
"""Generate validated BibleRecite v2 questions from the bundled scripture.

This is deliberately a sequential OpenAI-compatible client: it does not put
multiple model calls in flight, which keeps it usable with one-concurrency
model accounts. It never saves the scripture text in the output bank.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

FORMAT = "bible-recite-quiz-bank"
VERSION = 2
PROGRESS_FORMAT = "bible-recite-generation-progress"
FUNCTION_WORDS = {
    "的", "了", "着", "过", "吗", "呢", "啊", "呀", "和", "与", "及", "而", "但", "且", "或",
    "在", "把", "被", "给", "从", "向", "对", "以", "于", "是", "有", "就", "都", "也", "又",
    "很", "更", "还", "不", "没", "要", "会", "能", "之", "其", "这", "那", "等", "并", "则",
    "却", "才", "再", "便", "因", "为", "由", "到", "上", "下", "里", "中", "乃",
}
BOUNDARY_WORDS = FUNCTION_WORDS | {"你", "我", "他", "她", "它"}
REPORTING = re.compile(r"^[\u4e00-\u9fff]{1,8}(?:说|说道|回答|吩咐|告诉)$")


def utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def utf16_slice(value: str, start: int, end: int) -> str | None:
    raw = value.encode("utf-16-le")
    if start < 0 or end <= start or end * 2 > len(raw):
        return None
    try:
        return raw[start * 2 : end * 2].decode("utf-16-le")
    except UnicodeDecodeError:
        return None


def compact_meaning(word: str, meaning: str) -> str:
    value = meaning.strip()
    for prefix in (f"{word}：", f"{word}:", f"【{word}】：", f"【{word}】:"):
        if value.startswith(prefix):
            return value[len(prefix) :].strip()
    return value


def is_meaning_for_word(word: str, meaning: str) -> bool:
    """Return whether a hint describes a word without exposing the answer."""
    value = compact_meaning(word, meaning)
    return bool(value) and word not in value


def is_valid_word(word: str) -> bool:
    value = word.strip()
    if not value or value in FUNCTION_WORDS:
        return False
    if re.fullmatch(r"[\W_]+", value, flags=re.UNICODE) or REPORTING.match(value):
        return False
    if len(value) >= 2 and (value[0] in BOUNDARY_WORDS or value[-1] in BOUNDARY_WORDS):
        return False
    return True


def load_bank(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    root = json.loads(path.read_text(encoding="utf-8"))
    if root.get("format") != FORMAT or root.get("version") not in (1, 2):
        raise ValueError(f"{path} 不是 BibleRecite 题库")
    questions = root.get("questions")
    if not isinstance(questions, list):
        raise ValueError(f"{path} questions 无效")
    required = (
        "translationId", "bookId", "chapter", "verse", "start", "end",
        "word", "partOfSpeech", "meaning", "reference",
    )
    normalized: list[dict[str, Any]] = []
    for item in questions:
        if not isinstance(item, dict) or any(name not in item for name in required):
            raise ValueError(f"{path} 含有格式不完整的题目")
        word = str(item["word"]).strip()
        start, end = item["start"], item["end"]
        if (not word or not isinstance(start, int) or not isinstance(end, int)
                or start < 0 or end <= start or int(item["chapter"]) < 1
                or int(item["verse"]) < 1 or not str(item["partOfSpeech"]).strip()
                or not compact_meaning(word, str(item["meaning"]))):
            raise ValueError(f"{path} 含有无效题目")
        normalized.append({
            "translationId": str(item["translationId"]).strip(), "bookId": str(item["bookId"]).strip(),
            "chapter": int(item["chapter"]), "verse": int(item["verse"]), "start": start, "end": end,
            "word": word, "partOfSpeech": str(item["partOfSpeech"]).strip(),
            "meaning": compact_meaning(word, str(item["meaning"])), "reference": str(item["reference"]).strip(),
        })
    return normalized


def question_key(question: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(question[name] for name in (
        "translationId", "bookId", "chapter", "verse", "start", "end",
    ))


def write_bank(path: Path, questions: Iterable[dict[str, Any]]) -> None:
    ordered = sorted(questions, key=question_key)
    payload = json.dumps({"format": FORMAT, "version": VERSION, "questions": ordered}, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload.encode("utf-8"))
    temporary.replace(path)


def load_progress(path: Path, translation_id: str) -> tuple[str, int, int] | None:
    if not path.exists():
        return None
    root = json.loads(path.read_text(encoding="utf-8"))
    if root.get("format") != PROGRESS_FORMAT or root.get("version") != 1:
        raise ValueError(f"{path} 进度文件格式无效")
    if root.get("translationId") != translation_id:
        return None
    last = root.get("lastSuccessful")
    if not isinstance(last, dict):
        return None
    book, chapter, verse = last.get("bookId"), last.get("chapter"), last.get("verse")
    if not isinstance(book, str) or not isinstance(chapter, int) or not isinstance(verse, int):
        raise ValueError(f"{path} 最后成功位置无效")
    return book, chapter, verse


def write_progress(path: Path, translation_id: str, verse: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": PROGRESS_FORMAT,
        "version": 1,
        "translationId": translation_id,
        "lastSuccessful": {
            "bookId": verse["book_id"], "chapter": verse["chapter"], "verse": verse["verse"],
        },
        "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    temporary.replace(path)


def query_verses(database: Path, book: str | None, chapter: int | None,
                  start: int | None, end: int | None) -> list[dict[str, Any]]:
    clauses = ["u.status = 'present'", "u.start_verse = u.end_verse"]
    values: list[Any] = []
    if book:
        clauses.append("u.osis_book_id = ?")
        values.append(book.upper())
    if chapter:
        clauses.append("u.chapter = ?")
        values.append(chapter)
    if start:
        clauses.append("u.start_verse >= ?")
        values.append(start)
    if end:
        clauses.append("u.start_verse <= ?")
        values.append(end)
    sql = """
      SELECT b.ordinal AS book_ordinal, u.osis_book_id AS book_id, u.chapter,
             u.start_verse AS verse, u.text
      FROM verse_unit u JOIN books b ON b.osis_id = u.osis_book_id
      WHERE %s ORDER BY b.ordinal, u.chapter, u.start_verse
    """ % " AND ".join(clauses)
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(sql, values)]


def parse_reference(value: str) -> tuple[str, int, int]:
    parts = value.upper().split(":")
    if len(parts) != 3 or not parts[0]:
        raise argparse.ArgumentTypeError("格式应为卷:章:节，例如 GEN:1:1")
    try:
        chapter, verse = int(parts[1]), int(parts[2])
    except ValueError as error:
        raise argparse.ArgumentTypeError("章和节必须是正整数") from error
    if chapter < 1 or verse < 1:
        raise argparse.ArgumentTypeError("章和节必须是正整数")
    return parts[0], chapter, verse


def filter_from(verses: Iterable[dict[str, Any]], start: tuple[str, int, int]) -> list[dict[str, Any]]:
    start_book, start_chapter, start_verse = start
    matched = False
    result: list[dict[str, Any]] = []
    for item in verses:
        if item["book_id"] == start_book and item["chapter"] == start_chapter and item["verse"] == start_verse:
            matched = True
        if matched:
            result.append(item)
    if not matched:
        raise ValueError(f"起点 {start_book}:{start_chapter}:{start_verse} 不存在于原文数据库")
    return result


def filter_after(verses: Iterable[dict[str, Any]], last: tuple[str, int, int]) -> list[dict[str, Any]]:
    book, chapter, verse = last
    result = list(verses)
    for index, item in enumerate(result):
        if item["book_id"] == book and item["chapter"] == chapter and item["verse"] == verse:
            return result[index + 1 :]
    raise ValueError(f"进度位置 {book}:{chapter}:{verse} 不存在于原文数据库")


def prompt() -> str:
    return """你是一位严格的圣经经文出题助手。根据用户提供的每节经文，挑选语义丰富、可朗读的词作为隐藏词，用于“听词填空”练习。
只返回 JSON 数组，不要输出其他文字。每一节输入经文恰好一题；字段固定为 reference、word、start、end、length、partOfSpeech、meaning。
reference 必须一字不差来自输入；word 必须等于原文从 start 到 end 的 UTF-16 切片；start 含、end 不含，length=end-start。
只选择人物、地点、具体事物、重要事件、核心动词或形容词等可独立表达具体意义、适合朗读回答的实词。
绝不选择连接词、介词、助词、语气词、代词、标点、数字、无完整意义的片段，也不要选择“某人说”“某人回答”“某人吩咐/告诉”这类发话标签或整句。
meaning 必须是简短、独立的释义；不得包含或重复 word 的任何文字，不得写“word：…”，不得引用、复述或改写本节原文，也不能用上下文直接泄露答案。
释义只能说明这个词本身；人名、地名或专名不确定时，可写不含答案的类别提示，例如“经文中的人物、地点或具体事物”。
先核验下标、长度和解释对象；不准确就不返回该项。只输出 JSON。"""


def call_model(base_url: str, api_key: str, model: str, verses: list[dict[str, Any]], timeout: int) -> list[dict[str, Any]]:
    user = "经文语言版本：cmn-cu89s\n每一节恰好生成一题；只返回 JSON 数组。\n经文列表：\n" + "\n".join(
        f"{item['reference']}：{item['text']}" for item in verses
    )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": prompt()}, {"role": "user", "content": user}],
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


def validate(items: Iterable[dict[str, Any]], verses: list[dict[str, Any]], translation_id: str) -> list[dict[str, Any]]:
    by_reference = {item["reference"]: item for item in verses}
    accepted: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        reference = item.get("reference")
        source = by_reference.get(reference)
        if source is None or reference in seen:
            continue
        start, end, length = item.get("start"), item.get("end"), item.get("length")
        word, pos, meaning = item.get("word"), item.get("partOfSpeech"), item.get("meaning")
        if not all(isinstance(value, int) for value in (start, end, length)) or not all(isinstance(value, str) for value in (word, pos, meaning)):
            continue
        sliced = utf16_slice(source["text"], start, end)
        if sliced != word or length != end - start or not is_valid_word(word) or not pos.strip() or not is_meaning_for_word(word, meaning):
            continue
        accepted.append({
            "translationId": translation_id, "bookId": source["book_id"], "chapter": source["chapter"],
            "verse": source["verse"], "start": start, "end": end, "word": word,
            "partOfSpeech": pos.strip(), "meaning": compact_meaning(word, meaning), "reference": reference,
        })
        seen.add(reference)
    return accepted


def main() -> None:
    parser = argparse.ArgumentParser(description="使用 OpenAI 兼容模型批量生成 BibleRecite 题库")
    parser.add_argument("--scripture", type=Path, default=Path("scripture/cmn-cu89s/scripture.sqlite"))
    parser.add_argument("--output", type=Path, default=Path("quiz-bank.json"))
    parser.add_argument("--progress", type=Path, default=Path("tools/generation_progress.json"),
                        help="保存最后连续成功位置的本地进度文件")
    parser.add_argument("--translation-id", default="cmn-cu89s")
    parser.add_argument("--base-url", required=True, help="例如 https://open.bigmodel.cn/api/paas/v4")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key-env", default="QUIZ_MODEL_API_KEY")
    parser.add_argument("--from", dest="start_at", type=parse_reference,
                        help="从此卷:章:节开始，随后按全书顺序处理，例如 GEN:1:1")
    parser.add_argument("--book", help="只处理一个 OSIS 卷名，例如 GEN 或 JHN")
    parser.add_argument("--chapter", type=int)
    parser.add_argument("--start-verse", type=int)
    parser.add_argument("--end-verse", type=int)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--max-per-verse", type=int, default=1,
                        help="每节达到此题数即跳过；默认先每节一题")
    parser.add_argument("--limit", type=int, help="最多请求多少节")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    if args.batch_size < 1 or args.max_per_verse < 1:
        parser.error("batch-size 和 max-per-verse 必须大于 0")
    if args.start_at and any(value is not None for value in (args.book, args.chapter, args.start_verse, args.end_verse)):
        parser.error("--from 不能与 --book、--chapter、--start-verse 或 --end-verse 同时使用")
    api_key = os.environ.get(args.api_key_env, "")
    if not args.dry_run and not api_key:
        parser.error(f"未设置环境变量 {args.api_key_env}；不要把 API Key 写进命令、代码或题库。")

    existing = load_bank(args.output)
    counts = Counter((q.get("translationId"), q.get("bookId"), q.get("chapter"), q.get("verse")) for q in existing)
    candidates = []
    verses = query_verses(
        args.scripture, args.book, args.chapter, args.start_verse, args.end_verse,
    )
    if args.start_at:
        verses = filter_from(verses, args.start_at)
        print(f"使用指定起点：{args.start_at[0]}:{args.start_at[1]}:{args.start_at[2]}")
    elif not args.book and not args.chapter:
        last = load_progress(args.progress, args.translation_id)
        if last:
            verses = filter_after(verses, last)
            print(f"从上次连续成功位置之后继续：{last[0]}:{last[1]}:{last[2]}")
    for verse in verses:
        verse["reference"] = f"{verse['chapter']}:{verse['verse']}"
        key = (args.translation_id, verse["book_id"], verse["chapter"], verse["verse"])
        if counts[key] < args.max_per_verse:
            candidates.append(verse)
    if args.limit is not None:
        candidates = candidates[:args.limit]
    print(f"已有 {len(existing)} 道，待处理 {len(candidates)} 节；每次最多 {args.batch_size} 节，串行调用。")
    if args.dry_run:
        return
    merged = {question_key(q): q for q in existing}
    for offset in range(0, len(candidates), args.batch_size):
        batch = candidates[offset : offset + args.batch_size]
        raw = call_model(args.base_url, api_key, args.model, batch, args.timeout)
        valid = validate(raw, batch, args.translation_id)
        for question in valid:
            merged.setdefault(question_key(question), question)
        # Persist every successful model response before moving the cursor.
        write_bank(args.output, merged.values())
        accepted_refs = {question["reference"] for question in valid}
        last_contiguous = None
        for verse in batch:
            if verse["reference"] not in accepted_refs:
                break
            last_contiguous = verse
        if last_contiguous is not None:
            write_progress(args.progress, args.translation_id, last_contiguous)
        print(f"{offset + 1}-{offset + len(batch)} 节：模型返回 {len(raw)} 道，通过本机校验 {len(valid)} 道")
        if last_contiguous is not batch[-1]:
            print("本批存在未通过校验的节；已保存通过题目，但不越过断点，请下次从进度位置继续。")
            break
    questions = sorted(merged.values(), key=question_key)
    print(f"写入 {args.output}：新增 {len(questions) - len(existing)} 道，合计 {len(questions)} 道。随后运行 tools/update_quiz_bank_index.py。")


if __name__ == "__main__":
    main()
