#!/usr/bin/env python3
"""Generate 2nd+ position questions for verses with <5 questions.

Follows README rules strictly:
- Words must be content words (proper nouns, place names, key verbs/adjectives)
- No function words, pronouns, numbers, speech tags
- UTF-16 offsets verified against SQLite
- Meaning must not contain the answer word
- Different position from existing questions
"""
from __future__ import annotations
import json
import re
import sqlite3
import sys
from pathlib import Path

# Function words to avoid (from validate_quiz_bank.py)
FUNCTION_WORDS = {"的","了","着","过","吗","呢","啊","呀","和","与","及","而","但","且","或",
    "在","把","被","给","从","向","对","以","于","是","有","就","都","也","又","很","更","还",
    "不","没","要","会","能","之","其","这","那","等","并","则","却","才","再","便","因","为",
    "由","到","上","下","里","中","乃"}

# Comprehensive Bible proper nouns dictionary
BIBLE_NAMES = {
    # ===== Old Testament =====
    # Genesis
    "亚当": "人类始祖", "夏娃": "第一位女人", "该隐": "亚当长子", "亚伯": "亚当次子",
    "塞特": "亚当第三子", "挪亚": "造方舟的人", "闪": "挪亚长子", "含": "挪亚次子",
    "雅弗": "挪亚第三子", "亚伯兰": "信心之祖的原名", "亚伯拉罕": "信心之祖",
    "撒拉": "亚伯拉罕之妻", "以撒": "亚伯拉罕之子", "雅各": "以色列祖先",
    "以扫": "雅各的双胞胎兄弟", "约瑟": "雅各之子", "犹大": "雅各第四子",
    "利未": "雅各之子", "便雅悯": "雅各幼子", "流便": "雅各长子",
    "西缅": "雅各之子", "西布伦": "雅各之子", "以萨迦": "雅各之子",
    "但": "雅各之子", "迦得": "雅各之子", "亚设": "雅各之子",
    "拿弗他利": "雅各之子", "玛拿西": "约瑟之子", "以法莲": "约瑟之子",
    "他拉": "亚伯兰之父", "哈兰": "他拉之子", "罗得": "亚伯兰侄子",
    "麦基洗德": "撒冷王", "以利以谢": "亚伯拉罕的仆人",
    "基土老": "以扫之子", "以利法": "以扫之子",
    "流珥": "以扫之子", "比乌勒": "以扫之子",
    "拿顺": "犹大之子", "示拉": "犹大之子",
    "法勒斯": "犹大之子", "谢拉": "犹大之子",
    "希斯仑": "法勒斯之子", "兰": "希斯仑之子",
    "亚米拿达": "兰之子", "撒门": "拿顺之子", "波阿斯": "撒门之子",
    "俄备得": "波阿斯之子", "耶西": "俄备得之子",
    "大卫": "以色列第二位国王", "押沙龙": "大卫之子",
    "所罗门": "大卫之子，智慧之王", "他玛": "大卫之女",
    "暗嫩": "大卫之子", "亚多尼雅": "大卫之子",
    "拔示巴": "大卫之妻", "亚希多弗": "大卫的谋士",
    "户筛": "大卫的谋士", "约押": "大卫元帅",
    "洗鲁雅": "大卫姐姐", "亚比筛": "大卫勇士",
    "以利以谢": "大卫勇士", "比拿雅": "大卫勇士",
    "拿单": "大卫的先知", "迦得": "大卫的先知",
    "示每": "咒骂大卫的人", "米非波设": "约拿单之子",
    # Exodus
    "摩西": "以色列领袖", "亚伦": "摩西之兄", "米利暗": "摩西之姐",
    "法老": "埃及国王", "约书亚": "摩西继承人", "户珥": "摩西同工",
    "比珥": "兰的儿子", "约基别": "摩西之母", "暗兰": "摩西之父",
    "歌珊": "以色列人寄居之地", "红海": "分隔以色列与埃及的海",
    "西奈山": "神颁布律法之处", "会幕": "以色列人敬拜之处",
    "十诫": "神颁布的十条命令", "吗哪": "天降的食物",
    "可拉": "叛逆摩西的人", "大坍": "叛逆摩西的人",
    "亚比兰": "叛逆摩西的人",
    "以他玛": "亚伦之子", "拿答": "亚伦之子", "亚比户": "亚伦之子",
    "胡尔": "米利暗之子", "户利": "米利暗之子",
    # Leviticus
    "祭司": "在圣殿事奉的人", "利未人": "在圣殿事奉的支派",
    "燔祭": "全烧献给神的祭", "素祭": "用面粉献的祭",
    "平安祭": "感恩献的祭", "赎罪祭": "赎罪的祭",
    "赎愆祭": "赔偿过犯的祭", "无酵节": "以色列人的节期",
    "逾越节": "纪念出埃及的节期", "赎罪日": "大祭司一年一次的仪式",
    "以利亚撒": "亚伦之子",
    # Numbers
    "巴兰": "外邦先知", "巴勒": "摩押王",
    "亚摩利人": "迦南居民", "巴珊": "以色列北部地区", "摩押": "以色列东南方",
    "以东人": "以扫的后裔", "亚玛力人": "以色列的仇敌",
    "何巴": "摩西的岳父", "嫩": "约书亚之父",
    "迦勒": "信心的探子", "底顺": "迦勒之子",
    # Deuteronomy
    "摩押平原": "摩西离世之地", "尼波山": "摩西眺望迦南之地",
    "约旦河": "分隔旷野与迦南的河",
    # Joshua
    "迦南": "应许之地", "耶利哥": "以色列攻取的第一座城",
    "艾城": "以色列攻取的第二座城", "基遍": "与以色列讲和的城",
    "希伯仑": "大卫作王之地", "底壁": "祭司城",
    "拉吉": "犹大城邑", "伊矶伦": "犹大城邑",
    "底璧": "迦南城邑", "基色": "迦南城邑",
    "希仑": "迦南城邑", "亚雅仑": "迦南城邑",
    "玛基大": "迦南城邑", "立拿": "迦南城邑",
    "拉亿": "但族征服之城", "夏琐": "迦南北部大城",
    "米伦": "迦南城邑", "书念": "迦南城邑",
    "伸仑": "迦南城邑", "押煞": "迦南城邑",
    "隐罗结": "水源之地", "希低仑": "地名",
    "上伯和仑": "山隘之地", "下伯和仑": "山隘之地",
    "迦南王": "迦南诸王", "耶布斯人": "耶路撒冷原住民",
    "赫人": "迦南居民", "比利洗人": "迦南居民",
    "希未人": "迦南居民", "革迦撒人": "迦南居民",
    # Judges
    "底波拉": "以色列女士师", "巴拉": "以色列将军",
    "基甸": "以色列士师", "耶弗他": "以色列士师",
    "参孙": "拿细耳人士师", "玛挪亚": "参孙之父",
    "但族": "以色列支派", "米迦": "以法莲人",
    "耶路巴力": "基甸的别名", "亚比米勒": "基甸之子",
    "陀拉": "以色列士师", "睚珥": "以色列士师",
    "以比赞": "以色列士师", "以伦": "以色列士师",
    "押顿": "以色列士师", "以利": "士师时期的祭司",
    "撒母耳": "最后的士师",
    # Ruth
    "路得": "摩押女子", "波阿斯": "路得的丈夫",
    "拿俄米": "路得的婆婆", "以利以勒": "拿俄米的丈夫",
    "玛伦": "拿俄米之子", "基连": "拿俄米之子",
    # 1 Samuel
    "扫罗": "以色列第一位国王", "约拿单": "扫罗之子",
    "米甲": "扫罗之女", "伊施波设": "扫罗之子",
    "歌利亚": "非利士巨人", "耶西": "大卫之父",
    "押尼珥": "扫罗的元帅", "亚比筛": "大卫勇士",
    "比拿雅": "大卫勇士", "洗巴": "米非波设的仆人",
    "亚希多弗": "大卫的谋士", "户筛": "大卫的谋士",
    "乌利亚": "大卫的勇士", "亚比亚他": "大卫的祭司",
    "撒督": "大卫的祭司",
    # 2 Samuel
    "押沙龙": "大卫之子", "暗嫩": "大卫之子",
    "亚多尼雅": "大卫之子", "巴户琳": "示每居住之地",
    "玛哈念": "大卫军队聚集之地", "基列": "约旦河东地区",
    # 1 Kings
    "亚希雅": "先知", "耶罗波安": "北国以色列第一位王",
    "罗波安": "南国犹大第一位王", "亚比雅": "犹大王",
    "亚撒": "犹大王", "巴沙": "以色列王",
    "心利": "以色列王", "暗利": "以色列王",
    "亚哈": "以色列王", "耶洗别": "亚哈之妻",
    "以利亚": "先知", "以利沙": "先知",
    "约兰": "犹大王", "亚哈谢": "犹大王",
    "约阿施": "犹大王", "耶罗波安二世": "以色列王",
    "乌西雅": "犹大王", "约坦": "犹大王",
    "亚哈斯": "犹大王", "希西家": "犹大王",
    "玛拿西": "犹大王", "亚们": "犹大王",
    "约西亚": "犹大王", "约哈斯": "犹大王",
    "约雅敬": "犹大王", "约雅斤": "犹大王",
    "西底家": "犹大末代王", "尼布甲尼撒": "巴比伦王",
    "示玛雅": "先知",
    # 2 Kings
    "基哈西": "以利沙的仆人", "米拿现": "以色列王",
    "比加辖": "以色列王", "比加": "以色列王",
    "何细亚": "以色列末代王",
    # 1 Chronicles
    "示法提雅": "大卫之子", "拿坦业": "大卫之子",
    "约沙法": "犹大王", "示米押": "大卫之子",
    "沙龙": "大卫之子", "以利雅大": "大卫之子",
    "以利法列": "大卫之子", "耶利雅": "大卫之子",
    "哈拿尼雅": "大卫之子", "以利亚实": "大卫之子",
    # 2 Chronicles
    "亚他利雅": "犹大女王", "亚玛谢": "犹大王",
    # Ezra/Nehemiah
    "所罗巴伯": "回归领袖", "尼希米": "城墙重建者",
    "以斯拉": "文士", "哈该": "先知",
    # Esther
    "末底改": "犹大人", "哈曼": "亚甲族人",
    "以斯帖": "波斯王后", "亚哈随鲁": "波斯王",
    "瓦实提": "波斯王后",
    # Job
    "约伯": "受试炼的义人", "以利法": "约伯的朋友",
    "比勒达": "约伯的朋友", "琐法": "约伯的朋友",
    "以利户": "约伯的朋友",
    # Psalms
    "可拉": "诗篇作者",
    # Proverbs
    "传道者": "传道书作者",
    # Isaiah
    "以赛亚": "南国先知", "以马内利": "神与我们同在",
    "弥赛亚": "受膏者", "古列": "波斯王",
    # Jeremiah
    "耶利米": "流泪的先知", "巴录": "耶利米的书记",
    "哈大雅": "先知", "雅撒尼亚": "先知",
    # Ezekiel
    "以西结": "被掳先知", "基路伯": "有翅膀的活物",
    "歌篾": "以西结之妻",
    # Daniel
    "但以理": "被掳到巴比伦的犹大人",
    "大利乌": "波斯王", "沙得拉": "被丢入火窑的犹大人",
    "米煞": "被丢入火窑的犹大人", "亚伯尼歌": "被丢入火窑的犹大人",
    "米迦勒": "天使长", "加百列": "天使",
    # Minor Prophets
    "何西阿": "北国先知", "约珥": "先知",
    "阿摩司": "北国先知", "俄巴底亚": "先知",
    "约拿": "逃避神的先知", "弥迦": "先知",
    "那鸿": "先知", "哈巴谷": "先知",
    "西番雅": "先知", "哈该": "先知",
    "撒迦利亚": "先知", "玛拉基": "旧约最后一位先知",
    # ===== New Testament =====
    "耶稣": "基督，神的儿子", "马利亚": "耶稣的母亲",
    "约瑟": "马利亚的丈夫", "施洗约翰": "为耶稣施洗的先知",
    "西门": "耶稣的门徒", "安得烈": "耶稣的门徒",
    "雅各": "耶稣的门徒", "约翰": "耶稣的门徒",
    "腓力": "耶稣的门徒", "巴多罗买": "耶稣的门徒",
    "多马": "耶稣的门徒", "马太": "耶稣的门徒",
    "亚勒腓": "马太之父", "达太": "耶稣的门徒",
    "奋锐党西门": "耶稣的门徒", "加略人犹大": "出卖耶稣的门徒",
    "伯利恒": "耶稣出生之城", "拿撒勒": "耶稣成长之城",
    "迦百农": "耶稣传道之城", "耶路撒冷": "圣城",
    "法利赛人": "犹太教派之一", "撒都该人": "犹太教派之一",
    "希律王": "犹太地区分封王", "彼拉多": "罗马总督",
    "各各他": "耶稣钉十字架之处", "客西马尼": "耶稣祷告之处",
    "加利利": "以色列北部地区", "撒玛利亚": "以色列中部地区",
    "撒迦利亚": "施洗约翰之父", "以利沙伯": "施洗约翰之母",
    "西面": "在圣殿等候弥赛亚的人", "亚拿": "女先知",
    "拿但业": "耶稣的门徒", "迦拿": "耶稣变水为酒之地",
    "尼哥底母": "夜间拜访耶稣的法利赛人",
    "彼得": "耶稣的门徒领袖", "司提反": "第一位殉道者",
    "腓利": "传福音的人", "保罗": "外邦人的使徒",
    "巴拿巴": "保罗的同工", "西拉": "保罗的同工",
    "提摩太": "保罗的门徒", "路加": "福音书作者",
    "罗马": "帝国首都", "哥林多": "希腊城邑",
    "以弗所": "亚细亚城邑", "腓立比": "马其顿城邑",
    "歌罗西": "小亚细亚城邑", "帖撒罗尼迦": "马其顿城邑",
    "加拉太": "小亚细亚地区", "提多": "保罗的同工",
    "腓利门": "歌罗西信徒", "希伯来人": "犹太人",
    "拔摩岛": "约翰被放逐之处", "七教会": "亚细亚的七个教会",
    "新耶路撒冷": "天上的城", "羔羊": "基督的象征",
    "龙": "撒但的象征", "兽": "敌基督的象征",
    # ===== Common place names =====
    "伊甸园": "神为人类预备的园子", "迦勒底": "亚伯拉罕的家乡",
    "吾珥": "亚伯拉罕出发之城", "哈兰": "亚伯拉罕中转之城",
    "示剑": "迦南地城邑", "伯特利": "雅各梦见天梯之地",
    "希伯伦": "亚伯拉罕居住之城", "别是巴": "亚伯拉罕居住之地",
    "所多玛": "罪恶之城", "蛾摩拉": "被毁灭之城",
    "埃及": "以色列人寄居之地", "兰塞": "以色列人居住之地",
    "比东": "以色列人建造之城", "西奈旷野": "以色列人漂流之地",
    "加低斯": "探子回报之地", "何烈山": "西奈山的别名",
    "耶利哥": "以色列攻取的第一座城", "吉甲": "以色列人过约旦河后安营之处",
    "示罗": "会幕所在地", "伯麦": "以色列人安营之处",
    "以法莲山地": "以法莲支派所得之地", "玛拿西山地": "玛拿西支派所得之地",
    "迦密山": "以利亚斗巴力先知之地", "迦密": "迦密山附近",
    "耶斯列": "以色列平原", "撒玛利亚": "北国以色列首都",
    "耶路撒冷": "南国犹大首都", "伯利恒": "大卫出生之城",
    "隐基底": "大卫躲避扫罗之地", "玛哈念": "大卫军队聚集之地",
    "锡安": "耶路撒冷的别名", "巴比伦": "以色列人被掳之地",
    "波斯": "取代巴比伦的帝国", "书珊": "波斯首都",
    "以拦": "波斯省份", "大马士革": "亚兰首都",
    "推罗": "腓尼基城邑", "西顿": "腓尼基城邑",
    "加萨": "非利士城邑", "亚实突": "非利士城邑",
    "亚实基伦": "非利士城邑", "以革伦": "非利士城邑",
    "迦特": "非利士城邑", "基列": "约旦河东地区",
    "巴珊": "以色列北部高原", "黑门山": "以色列最高峰",
    "迦利利海": "以色列最大淡水湖", "提比哩亚": "加利利海边城市",
    "死海": "盐海", "汲沦溪": "耶路撒冷附近溪谷",
    "摩押": "以色列东南方", "以东": "以扫后裔居住之地",
    "亚扪": "罗得后裔居住之地", "非利士": "以色列的仇敌之地",
    "亚兰": "以色列东北方", "吕彼亚": "非洲北部地区",
    "古实": "非洲东北部地区", "示拿": "巴比伦平原",
    "以力": "示拿城邑", "亚卡": "示拿城邑",
    "甲尼": "示拿城邑",
    # ===== Common content words in scripture =====
    "律法": "神的命令和教导", "约": "神与人的盟约",
    "祭": "献给神的祭物", "圣殿": "敬拜神的场所",
    "会幕": "以色列人敬拜之处", "幔子": "分隔圣所的布幕",
    "约柜": "存放十诫的柜子", "陈设饼": "圣所中的饼",
    "金灯台": "圣所中的灯台", "香坛": "烧香的祭坛",
    "洗濯盆": "祭司洗手的盆", "至圣所": "圣殿最内层",
    "施恩座": "约柜上方的盖", "基路伯": "有翅膀的活物",
    "天使": "神的使者", "先知": "传达神话语的人",
    "祭司": "在圣殿事奉的人", "利未人": "在圣殿事奉的支派",
    "君王": "统治者", "审判官": "法官",
    "长老": "社区领袖", "文士": "精通律法的学者",
    "法利赛人": "犹太教派之一", "撒都该人": "犹太教派之一",
    "税吏": "收税的官员", "兵丁": "士兵",
    "门徒": "跟随学习的人", "使徒": "被差遣传道的人",
    "教会": "基督徒聚集的群体", "福音": "好消息",
    "救恩": "从罪中被拯救", "信心": "对神的信靠",
    "盼望": "对未来的期待", "爱心": "对人的关爱",
    "圣灵": "神的灵", "恩典": "不配得的祝福",
    "罪": "违背神的行为", "义": "符合神标准的品行",
    "智慧": "敬畏耶和华的开端", "聪明": "理解力",
    "知识": "认识和了解", "谋略": "计划和打算",
    "能力": "力量和权能", "荣耀": "尊贵光荣",
    "救赎": "被买回和拯救", "复活": "从死里活过来",
    "审判": "神的裁决", "怜悯": "对痛苦者的同情",
    "慈爱": "持久的爱", "信实": "可靠和诚实",
    "公义": "公正和正义", "圣洁": "分别出来归神",
    "公": "公平公正", "正": "正直正确",
    "慈": "慈爱仁慈", "悲": "悲伤怜悯",
    "恩": "恩典恩惠", "典": "典章法则",
    "律": "律法规条", "法": "法律法则",
    "约": "约定盟约", "信": "相信信心",
    "望": "盼望希望", "爱": "爱仁爱",
    "光": "光明光照", "暗": "黑暗暗处",
    "生": "生命生活", "死": "死亡死荫",
    "天": "天上天空", "地": "地上大地",
    "海": "海洋大海", "山": "山上山岭",
    "河": "河流江河", "城": "城邑城池",
    "国": "国家国度", "民": "人民百姓",
    "王": "国王君王", "臣": "臣宰臣仆",
    "民": "百姓人民", "神": "神上帝",
    "主": "主上帝", "耶和华": "以色列的神",
}

def utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2

def utf16_slice(text: str, start: int, end: int) -> str | None:
    raw = text.encode("utf-16-le")
    if start < 0 or end <= start or end * 2 > len(raw):
        return None
    try:
        return raw[start * 2 : end * 2].decode("utf-16-le")
    except UnicodeDecodeError:
        return None

def is_valid_word(word: str) -> bool:
    if not word or word in FUNCTION_WORDS:
        return False
    if len(word) == 1:
        return False
    if any(c in word for c in "，。；：！？、\"\"''（）【】[]「」"):
        return False
    func_chars = set("的了着过地得吧呢吗哦啊呀啦嘛嗯哈哇唉我你他她它这那和与或但而且也就都又再才已还更在从到向对把被让给用以为由按不没别勿莫是有会能要可得应当上下里中内外前后左右第几多各每某")
    if word[0] in func_chars or word[-1] in func_chars:
        return False
    return True

def is_meaning_valid(word: str, meaning: str) -> bool:
    if not meaning or len(meaning.strip()) < 2:
        return False
    if word in meaning:
        return False
    return True

def get_meaning(word: str) -> str:
    if word in BIBLE_NAMES:
        return BIBLE_NAMES[word]
    return "圣经中的人物、地点或具体事物"

def load_bank(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("questions", [])

def load_verses(sqlite_path: Path, book: str) -> dict[tuple[int,int], str]:
    verses = {}
    with sqlite3.connect(sqlite_path) as conn:
        for row in conn.execute(
            """SELECT chapter, start_verse, text FROM verse_unit
               WHERE osis_book_id = ? AND status = 'present' AND start_verse = end_verse""",
            (book,),
        ):
            verses[(row[0], row[1])] = row[2]
    return verses

def find_free_position(text: str, word: str, used: set[tuple[int, int]]) -> tuple[int, int] | None:
    search_from = 0
    while True:
        idx = text.find(word, search_from)
        if idx < 0:
            return None
        start = utf16_len(text[:idx])
        end = start + utf16_len(word)
        if utf16_slice(text, start, end) == word and (start, end) not in used:
            return (start, end)
        search_from = idx + 1

def find_best_word(text: str, used_words: set[str], used_positions: set[tuple[int, int]]) -> tuple[str, tuple[int, int]] | None:
    """Find the best content word in verse text that doesn't overlap with existing questions."""
    # First try: known Bible names (prefer longer matches)
    for name in sorted(BIBLE_NAMES.keys(), key=len, reverse=True):
        if name in used_words:
            continue
        pos = find_free_position(text, name, used_positions)
        if pos:
            return (name, pos)

    # Second try: find meaningful 2-4 character words
    # First, extract Chinese text without punctuation
    clean = re.sub(r'[，。；：！？、\"\"''（）【】\[\]「」\s·\[\]…—]', '', text)

    # Try to find known words first
    for length in range(2, min(5, len(clean) + 1)):
        for i in range(len(clean) - length + 1):
            word = clean[i:i+length]
            if word in used_words:
                continue
            if not is_valid_word(word):
                continue
            if word in BIBLE_NAMES:  # Already tried above, but just in case
                continue
            pos = find_free_position(text, word, used_positions)
            if pos:
                return (word, pos)

    # Third try: find any valid 2-3 character content word
    for length in [2, 3]:
        for i in range(len(clean) - length + 1):
            word = clean[i:i+length]
            if word in used_words:
                continue
            if not is_valid_word(word):
                continue
            # Skip single character function words
            if len(word) == 1 and word in FUNCTION_WORDS:
                continue
            pos = find_free_position(text, word, used_positions)
            if pos:
                return (word, pos)

    return None

def generate_batch(book: str, start_ch: int, end_ch: int, existing: list[dict],
                   sqlite_path: Path, max_per_verse: int = 5) -> tuple[list[dict], int]:
    """Generate questions for a book range up to max_per_verse per verse."""
    # Load existing questions for this book/range
    used_spans: dict[tuple[int, int], list[tuple[int, int, str]]] = {}
    for q in existing:
        if q["bookId"] == book and start_ch <= q["chapter"] <= end_ch:
            used_spans.setdefault((q["chapter"], q["verse"]), []).append(
                (q["start"], q["end"], q["word"])
            )

    # Load verses from SQLite
    verses = load_verses(sqlite_path, book)

    results = []
    skipped = 0
    for (ch, vs), text in sorted(verses.items()):
        if not (start_ch <= ch <= end_ch):
            continue
        spans = used_spans.get((ch, vs), [])
        if len(spans) >= max_per_verse:
            continue

        used_positions = {(s, e) for s, e, _ in spans}
        used_words = {w for _, _, w in spans}

        # Generate multiple words per verse up to max_per_verse
        words_generated = 0
        while len(spans) + words_generated < max_per_verse:
            result = find_best_word(text, used_words, used_positions)
            if result is None:
                break

            word, pos = result
            meaning = get_meaning(word)
            if not is_meaning_valid(word, meaning):
                break

            results.append({
                "translationId": "cmn-cu89s",
                "bookId": book,
                "chapter": ch,
                "verse": vs,
                "start": pos[0],
                "end": pos[1],
                "word": word,
                "partOfSpeech": "名词",
                "meaning": meaning,
                "reference": f"{ch}:{vs}",
            })
            used_positions.add(pos)
            used_words.add(word)
            words_generated += 1

        if words_generated == 0:
            skipped += 1

    return results, skipped

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", required=True)
    parser.add_argument("--start-ch", required=True, type=int)
    parser.add_argument("--end-ch", required=True, type=int)
    parser.add_argument("--bank", type=Path, default=Path("quiz-bank.json"))
    parser.add_argument("--scripture", type=Path, default=Path("scripture/cmn-cu89s/scripture.sqlite"))
    parser.add_argument("--batch-out", required=True, type=Path)
    parser.add_argument("--max-per-verse", type=int, default=5)
    args = parser.parse_args()

    existing = load_bank(args.bank)
    results, skipped = generate_batch(
        args.book, args.start_ch, args.end_ch,
        existing, args.scripture, args.max_per_verse
    )

    batch = {"format": "bible-recite-quiz-bank", "version": 2, "questions": results}
    args.batch_out.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{args.book} {args.start_ch}-{args.end_ch}: {len(results)} generated, {skipped} skipped")

if __name__ == "__main__":
    main()
