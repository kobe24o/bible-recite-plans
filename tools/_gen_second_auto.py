#!/usr/bin/env python3
"""Auto-generate 2nd-position questions using heuristic word picking.

Reads the scripture SQLite and existing quiz bank, finds verses with <2 questions,
picks a different meaningful word at a non-overlapping position, and writes a
merge-ready batch file.

Usage:
  python3 tools/_gen_second_auto.py --book MAT --start-ch 1 --end-ch 5 \
    --batch-out tools/batch_mat_1_5.json
"""
from __future__ import annotations
import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_quiz_bank import (
    FORMAT, VERSION, is_meaning_for_word, is_valid_word,
    load_bank, query_verses, utf16_length, utf16_slice,
)

BATCH_FORMAT = "bible-recite-quiz-bank"
BATCH_VERSION = 2

# Common Chinese function words / particles / pronouns to avoid
STOP_WORDS = set([
    "的","了","着","过","地","得","吧","呢","吗","哦","啊","呀","啦","嘛","嗯","哈","哇","唉",
    "我","你","他","她","它","我们","你们","他们","她们","它们",
    "这","那","这个","那个","这些","那些","这里","那里","这样","那么",
    "和","与","或","但","而","且","也","就","都","又","再","才","已","还","更",
    "在","从","到","向","对","把","被","让","给","用","以","为","由","按",
    "不","没","别","勿","莫",
    "是","有","会","能","要","可","得","应","当",
    "上","下","里","中","内","外","前","后","左","右",
    "一","二","三","四","五","六","七","八","九","十","百","千","万",
    "第","几","多","少","各","每","某",
    "生","说","问","答","叫",
])

# Common verb meanings (partial dictionary for hint generation)
WORD_HINTS = {
    "后裔": "后代子孙", "子孙": "后代", "家谱": "家族世系记录",
    "以撒": "亚伯拉罕之子", "犹大": "雅各第四子",
    "弟兄": "兄弟", "谢拉": "犹大之子",
    "希斯": "法勒斯之子", "亚兰": "希斯之子",
    "拿顺": "亚米拿达之子", "撒门": "拿顺之子",
    "喇合氏": "喇合的家族", "路得氏": "路得的家族",
    "俄备得": "波阿斯之子", "耶西": "大卫之父",
    "大卫王": "以色列第二位国王", "乌利亚": "大卫勇士",
    "亚比雅": "罗波安之子", "亚撒": "亚比雅之子",
    "约兰": "约沙法之子", "乌西雅": "约兰之后的犹大王",
    "约坦": "乌西雅之子", "亚哈斯": "约坦之子",
    "亚们": "玛拿西之子", "约西亚": "亚们之子",
    "耶哥尼雅": "约西亚之孙", "撒拉铁": "耶哥尼雅之子",
    "亚比玉": "所罗巴伯之子", "以利亚敬": "亚比玉之子",
    "亚所": "以利亚敬之子", "亚金": "撒督之子",
    "以律": "亚金之子", "以利亚撒": "以律之子",
    "马但": "以利亚撒之子",
    "约瑟": "马利亚的丈夫", "马利亚": "耶稣的母亲",
    "丈夫": "配偶中的男方", "基督": "受膏者，弥赛亚",
    "十四代": "十四个世代", "降生": "出生诞生",
    "圣灵": "神的灵", "怀了孕": "有了身孕",
    "义人": "行事正直的人", "休了": "解除婚姻",
    "使者": "天使", "显现": "出现显明",
    "起名": "取名字", "应验": "预言实现",
    "童女": "未出嫁的女子", "娶过来": "迎娶为妻",
    "同房": "夫妻亲密", "博士": "有学问的人",
    "不安": "心中惶恐", "合城": "全城的人",
    "召齐": "召集齐全", "祭司长": "犹太教祭司领袖",
    "文士": "精通律法的学者", "伯利恒": "犹大地的城邑",
    "先知": "受神启示传达信息的人",
    "牧养": "照管引导", "细问": "详细询问",
    "寻访": "寻找探访", "停住": "停止不动",
    "欢喜": "十分高兴", "乳香": "贵重香料",
    "本地": "自己的故乡", "除灭": "杀害消灭",
    "夜间": "在夜里", "召出": "呼唤出来",
    "愚弄": "欺骗戏弄", "应": "应验实现",
    "号咷": "大声哭号", "拉结": "雅各之妻",
    "显现": "出现显现", "性命": "生命",
    "母亲": "妈妈", "亚基老": "希律之子",
    "拿撒勒": "加利利的城邑", "传道": "传讲神的道理",
    "悔改": "改过自新", "修直": "修平弄直",
    "野蜜": "野生的蜂蜜", "承认": "坦白认罪",
    "法利赛人": "犹太教派之一", "撒都该人": "犹太教派之一",
    "果子": "果实成果", "相称": "匹配适合",
    "斧子": "砍伐工具", "圣灵": "神的灵",
    "簸箕": "筛选工具", "加利利": "以色列北部地区",
    "拦住": "阻止阻挡", "诸般": "各样各种",
    "鸽子": "象征圣灵的鸟", "爱子": "心爱的儿子",
    "魔鬼": "撒但试探者", "昼夜": "白天和黑夜",
    "吩咐": "命令指示", "食物": "吃的东西",
    "圣城": "耶路撒冷", "使者": "天使",
    "试探": "考验诱惑", "荣华": "荣耀繁华",
    "俯伏": "趴下跪拜", "退去": "离开退却",
    "伺候": "服侍照料", "监": "监狱",
    "迦百农": "加利利的城邑", "西布伦": "以色列支派",
    "死荫": "死亡的阴影", "门徒": "跟随学习的人",
    "开口": "张嘴说话", "虚心": "灵里贫穷",
    "哀恸": "悲伤痛哭", "温柔": "谦和柔顺",
    "饥渴": "饥饿口渴", "怜恤": "怜悯体恤",
    "清心": "内心纯洁", "使人和睦": "促进和平",
    "逼迫": "迫害追逼", "辱骂": "羞辱谩骂",
    "赏赐": "奖赏回报", "践踏": "踩踏",
    "隐藏": "遮蔽不露", "灯台": "放置灯的台",
    "荣耀": "尊贵光荣", "废掉": "取消作废",
    "成全": "完成实现", "诫命": "命令规条",
    "动怒": "发脾气生气", "祭坛": "献祭的台",
    "礼物": "献给神的祭物", "审判官": "法官",
    "一文钱": "很小的钱", "奸淫": "不正当的性关系",
    "淫念": "淫乱的念头", "右眼": "右边的眼睛",
    "右手": "右边的手", "休书": "离婚的文书",
    "妇人": "已婚女子", "背誓": "违背誓言",
    "座位": "坐的地方", "脚凳": "放脚的地方",
    "头发": "头上的毛发", "恶者": "邪恶的势力",
    "左脸": "左边的脸", "外衣": "外面的衣服",
    "强逼": "强迫迫使", "借贷": "借钱",
    "仇敌": "敌人", "祷告": "向神祈祷",
    "日头": "太阳", "税吏": "收税的官员",
    "外邦人": "非犹太人", "完全": "完美无缺",
    "亚伯拉罕": "信心之祖", "以利亚撒": "亚伦之子",
}


def utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def find_free_offsets(text: str, word: str, used: set[tuple[int, int]]) -> tuple[int, int] | None:
    search_from = 0
    while True:
        idx = text.find(word, search_from)
        if idx < 0:
            return None
        start = utf16_len(text[:idx])
        end = start + utf16_len(word)
        if utf16_slice(text, start, end) == word and (start, end) not in used and is_valid_word(word):
            return start, end
        search_from = idx + 1


def tokenize_chinese(text: str) -> list[str]:
    """Split Chinese text into candidate word tokens (2-5 chars)."""
    # Remove punctuation and special chars
    clean = re.sub(r'[，。；：！？、""''（）【】\[\]「」\s]', '', text)
    tokens = []
    for length in range(2, min(6, len(clean) + 1)):
        for i in range(len(clean) - length + 1):
            tokens.append(clean[i:i+length])
    return tokens


def is_content_word(word: str) -> bool:
    """Check if a word is likely a content word (not a function word)."""
    if word in STOP_WORDS:
        return False
    # Single char is almost always function word
    if len(word) == 1:
        return False
    # Check if starts/ends with common function chars
    func_chars = set("的了着过地得吧呢吗哦啊呀啦嘛嗯哈哇唉我你他她它这那和与或但而且也就都又再才已还更在从到向对把被让给用以为由按不没别勿莫是有会能要可得应当上下里中内外前后左右第几多各每某")
    if word[0] in func_chars or word[-1] in func_chars:
        return False
    return True


def get_meaning(word: str) -> str:
    """Get a meaning for a word, using dictionary or generating a basic one."""
    if word in WORD_HINTS:
        return f"{word}：{WORD_HINTS[word]}"
    # For names or unknown words, provide a basic meaning
    return f"{word}：（圣经中的人名/地名/事物）"


def main():
    parser = argparse.ArgumentParser(description="自动生成第二题")
    parser.add_argument("--scripture", type=Path, default=Path("scripture/cmn-cu89s/scripture.sqlite"))
    parser.add_argument("--bank", type=Path, default=Path("quiz-bank.json"))
    parser.add_argument("--batch-out", required=True, type=Path)
    parser.add_argument("--translation-id", default="cmn-cu89s")
    parser.add_argument("--book", required=True)
    parser.add_argument("--start-ch", required=True, type=int)
    parser.add_argument("--end-ch", required=True, type=int)
    parser.add_argument("--max-per-verse", type=int, default=2)
    args = parser.parse_args()

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

    print(f"{args.book} {args.start_ch}-{args.end_ch}: {len(target)} verses need 2nd question")

    accepted = []
    skipped = []
    for verse in target:
        text = verse["text"]
        used = {(s, e) for s, e, _ in verse["used_spans"]}
        used_words = set(verse["used_words"])

        # Tokenize and find candidate words
        candidates = []
        for token in tokenize_chinese(text):
            if token in used_words:
                continue
            if not is_content_word(token):
                continue
            offsets = find_free_offsets(text, token, used)
            if offsets:
                candidates.append((token, offsets))

        # Pick the best candidate (prefer proper names, then 2-3 char words)
        if candidates:
            # Prefer words already in dictionary
            dict_words = [(w, o) for w, o in candidates if w in WORD_HINTS]
            if dict_words:
                word, offsets = dict_words[0]
            else:
                word, offsets = candidates[0]
            meaning = get_meaning(word)
            if is_meaning_for_word(word, meaning):
                accepted.append({
                    "translationId": args.translation_id,
                    "bookId": verse["book_id"],
                    "chapter": verse["chapter"],
                    "verse": verse["verse"],
                    "start": offsets[0],
                    "end": offsets[1],
                    "word": word,
                    "partOfSpeech": "名词",
                    "meaning": meaning,
                    "reference": verse["reference"],
                })
            else:
                skipped.append((verse["reference"], f"meaning check failed: {word}"))
        else:
            skipped.append((verse["reference"], "no candidates"))

    payload = {"format": BATCH_FORMAT, "version": BATCH_VERSION, "questions": accepted}
    args.batch_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(accepted)} questions -> {args.batch_out}")
    if skipped:
        print(f"Skipped {len(skipped)} verses")
        for ref, why in skipped[:10]:
            print(f"  {ref}: {why}")


if __name__ == "__main__":
    main()
