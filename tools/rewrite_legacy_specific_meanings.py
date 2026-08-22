#!/usr/bin/env python3
"""Normalize specific legacy meanings that already contain a biblical relation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path

from audit_quiz_bank_quality import load_rules
from audit_rewritten_meanings import audit_rewrite
from bible_context import ContextFact
from rewrite_historical_quiz_meanings import RewriteDraft


_REWRITES = {
    "雅各第四子": "雅各的第四个儿子，成为以色列支派的先祖",
    "犹大王": "南国王室中的君王",
    "马利亚的丈夫": "在耶稣幼年保护家庭的义人丈夫",
    "大卫之子": "以色列王大卫的儿子",
    "耶稣的母亲": "弥赛亚降生故事中的母亲",
    "亚伦之子": "祭司家族祖先的儿子",
    "迦南居民": "神应许之地的当地居民",
    "耶稣的门徒": "跟随耶稣并受差遣作见证的人",
    "亚伯拉罕的家乡": "族长蒙召前居住的两河流域城市",
    "保罗的同工": "与使徒保罗一同传道的同工",
    "先知": "奉神传达启示、劝勉或警告的人",
    "外邦先知": "以色列以外民族中宣告神谕的人",
    "以色列士师": "王政前带领以色列抵御仇敌的领袖",
    "大卫勇士": "跟随大卫作战并立功的勇士",
    "犹大末代王": "南国覆亡前最后一位君王",
    "非利士城邑": "沿海民族控制的古代城邑",
    "亚伯拉罕之妻": "蒙应许生子的族长妻子",
    "敌基督的象征": "启示文学中与基督敌对的象征",
    "以色列王": "联合王国或北国历史中的君王",
    "罗马总督": "代表帝国治理犹太地区的总督",
    "犹大人": "南国支派及其被掳归回的族群",
    "信心之祖的原名": "族长改名前所使用的名字",
    "后代子孙": "由先祖延续而来的后代群体",
    "造方舟的人": "洪水前按神吩咐造方舟的义人",
    "摩押王": "约旦河东邻邦的君王",
    "扫罗的元帅": "以色列第一位君王麾下的元帅",
    "约伯的朋友": "在苦难中前来辩论并劝慰约伯的人",
    "分隔圣所的布幕": "会幕或圣殿中分隔圣所与至圣所的帷幕",
    "大卫之父": "受膏王的父亲",
    "基甸之子": "士师基甸的儿子",
    "亚兰首都": "以色列北方邻国的首都",
    "愤怒": "因罪恶或冒犯而产生的强烈情绪",
    "迦南城邑": "应许之地的古代城邑",
    "对未来的期待": "等候神应许将要成就的盼望",
    "施洗约翰之父": "祭司家族中预言儿子使命的父亲",
    "士兵": "参加军队并承担作战任务的人",
    "清晨": "日出前后的清早时段",
    "家畜": "由人饲养、可用于食物或献祭的牲畜",
    "归回者家族": "被掳后返回耶路撒冷的家族",
    "咒骂大卫的人": "王逃亡时公开羞辱他的敌对者",
    "大卫的勇士": "在王的军队中随大卫争战的勇士",
    "有翅膀的活物": "异象中具有翅膀的受造者",
    "腓尼基城邑": "地中海沿岸的腓尼基城",
    "以扫的后裔": "以扫后代形成的民族或家族",
    "以色列平原": "以色列中部适于耕作的平原地区",
    "尸体": "生命结束后留下的身体",
    "订立盟约": "以誓言或礼仪确认双方关系和责任",
    "派遣": "差派出去传道、作见证或完成使命",
    "女先知": "奉神传达信息的女性先知",
    "烧毁": "以火焚烧，使物件或城邑遭到毁灭",
    "大卫的祭司": "在大卫王朝中事奉圣所的祭司",
    "罪恶之城": "因持续悖逆而受神审判的城市",
    "波斯省份": "波斯帝国治理下的行政区域",
    "消灭": "从地上彻底除去，不留下存续者",
    "权力": "治理群体或执行命令的权柄",
    "符合神标准的品行": "按神公义要求生活的品格",
    "以色列北部高原": "北方支派居住的高地地区",
    "抽签": "在神面前以签决定分配或选择",
    "波斯王": "统治归回时期帝国的君王",
    "约书亚之父": "后来带领以色列进入应许之地的领袖之父",
    "女仆": "在家庭中承担服事工作的女性仆役",
    "受试炼的义人": "在苦难中仍持守信仰的人",
    "地名，犹大支派的城": "犹大支派所得的城邑",
    "对人的关爱": "向邻舍施行的爱与怜悯",
    "欢喜快乐": "因神的作为或拯救而有的喜乐",
    "答应": "承诺或应允一个请求",
    "抛弃": "离弃原有关系、责任或对象",
    "服侍": "以行动事奉神或帮助他人",
    "追逐": "持续追赶敌人或目标",
    "小羊": "可作献祭或群体饲养的幼羊",
    "雄性的绵羊": "畜群中的公羊，也可用于献祭",
    "大卫姐姐": "以色列王家族中的女性亲属",
    "接近": "从远处走到某人或某处附近",
    "王冠": "象征君王权柄和尊荣的冠冕",
    "返回": "从外地回到原居地或先前位置",
    "犹大城邑": "南国支派范围内的城邑",
    "探子回报之地": "窥探者返回后报告的应许之地",
    "殿役家族": "在圣殿承担杂役和辅助工作的家族",
    "犹大之子": "犹大支派族长的后代",
    "存放十诫的柜子": "会幕中存放法版的约柜",
    "光亮": "照明之光，也可象征神的荣耀",
    "诅咒": "求神降祸或宣告不蒙福",
    "拖延": "把应当完成的事延后",
    "恳切请求": "迫切而持续地向神祈求",
    "摩西同工": "协助出埃及领袖完成使命的人",
    "冒犯": "得罪或触犯神、人或所立的约",
    "答应允诺": "承诺照所说的话去实行",
    "尊贵荣耀": "显出高贵、尊荣和应受敬重的地位",
    "拆除毁坏": "拆掉建筑、城墙或敬拜偶像的设施",
    "靠近": "向某人、城邑或圣所走近",
    "亚伯拉罕侄子": "与族长一同迁移并住在平原城邑的亲属",
    "希斯伦之子": "家谱中记载的希斯伦后代",
    "生气": "因冒犯或罪恶而发怒",
    "祈求福分": "向神求赐保护、产业或福分",
    "吩咐命令": "有权柄者发出的应遵行指示",
    "排行第一的儿子": "家族中承受长子名分的儿子",
    "大卫的谋士": "在王朝中为大卫提供谋略的顾问",
    "盼望": "等候神应许实现的信靠",
    "纯金": "会幕或圣殿器物所用的精炼金属",
    "亚哈之妻": "推广巴力崇拜并影响北国君王的王后",
    "召集": "把人召来共同敬拜、商议或行动",
    "撕破": "将衣物或其他物体撕裂",
    "轻视": "把神、盟约或人的尊严看得不重要",
    "惊慌恐惧": "因危险或审判而战兢不安",
    "停止": "不再继续某项行动或进程",
}


@dataclass(frozen=True)
class LegacyRewriteResult:
    rewritten: list[dict[str, object]]
    quarantine: list[dict[str, object]]


def _compact(value: object) -> str:
    return "".join(str(value or "").split())


def _reference(question: dict[str, object]) -> str:
    return f"{question.get('bookId', '')}:{question.get('chapter', '')}:{question.get('verse', '')}"


def _quarantine(record: dict[str, object], reasons: list[str]) -> dict[str, object]:
    return {"key": record.get("key", ""), "question": record.get("question", {}), "reasons": reasons}


def rewrite_legacy_specific(records: list[dict[str, object]], rules: dict[str, object]) -> LegacyRewriteResult:
    rewritten: list[dict[str, object]] = []
    quarantine: list[dict[str, object]] = []
    for record in records:
        question = record.get("question")
        if not isinstance(question, dict):
            quarantine.append(_quarantine(record, ["invalid_candidate"]))
            continue
        old = _compact(question.get("meaning"))
        replacement = _REWRITES.get(old)
        if replacement is None:
            quarantine.append(_quarantine(record, ["no_legacy_specific_template"]))
            continue
        word = _compact(question.get("word"))
        if not word or word in replacement:
            quarantine.append(_quarantine(record, ["legacy_template_answer_leak"]))
            continue
        meaning = f"经文背景中的{replacement}"
        reference = _reference(question)
        fact = ContextFact(word, "legacy-specific", (replacement,), (reference,), "legacy-specific-template-v1")
        draft = RewriteDraft(record.get("key", ""), meaning, "legacy-specific-template", (reference,))
        audit = audit_rewrite(question, draft, rules, fact)
        if not audit.accepted:
            quarantine.append(_quarantine(record, list(audit.reasons)))
            continue
        updated = dict(question)
        updated["meaning"] = meaning
        rewritten.append({
            "key": record.get("key", ""),
            "question": updated,
            "previousMeaning": question.get("meaning", ""),
            "rewriteSource": draft.source,
            "evidenceReferences": [reference],
        })
    return LegacyRewriteResult(rewritten, quarantine)


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as target:
        for record in records:
            target.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="规范化已有具体圣经关系的旧释义")
    parser.add_argument("--remaining", type=Path, required=True)
    parser.add_argument("--meaning-rules", type=Path, default=Path("lexicon/meaning_rules.v1.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    remaining = [json.loads(line) for line in args.remaining.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = rewrite_legacy_specific(remaining, load_rules(args.meaning_rules))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "rewritten-legacy-specific.jsonl", result.rewritten)
    _write_jsonl(args.output_dir / "quarantine-legacy-specific.jsonl", result.quarantine)
    (args.output_dir / "summary-legacy-specific.md").write_text(
        "# 第三批具体关系旧释义规范化\n\n"
        f"- 输入待补题目：{len(remaining)}\n"
        f"- 通过规范化：{len(result.rewritten)}\n"
        f"- 继续隔离：{len(result.quarantine)}\n",
        encoding="utf-8",
    )
    print(f"输入 {len(remaining)} 道：完成规范化 {len(result.rewritten)} 道，继续隔离 {len(result.quarantine)} 道。")


if __name__ == "__main__":
    main()
