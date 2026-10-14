"""Assemble the controlled vocabulary: speaker labels (the real character list)
+ setting-collection headings (canonical spelling) + manual categories.
"""
import io
import json
import os
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BOOK = r"E:\DSHwork\heijiu\book"
WIKI = r"E:\DSHwork\heijiu\wiki"
SRC_DIR = os.path.join(WIKI, "source")
DATA = os.path.join(WIKI, "data")

texts = {}
for f in sorted(os.listdir(SRC_DIR)):
    if f.endswith(".md") and not f.startswith("_"):
        texts[f] = open(os.path.join(SRC_DIR, f), encoding="utf-8").read()

# ---- speaker labels ----
spk = Counter()
for t in texts.values():
    for m in re.finditer(r"(?m)^\*\*([^*：:\n]{1,16})\*\*\s*[:：]", t):
        s = m.group(1).strip()
        if re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9·\-]{1,16}", s):
            spk[s] += 1

# drop obvious non-names
NOISE = {"？", "议员", "总统", "大主教", "将军", "血兄", "游客", "队长", "记者",
         "主持人", "旁白", "众人", "士兵", "警察", "军官", "学生", "工人", "商人",
         "医生", "护士", "老人", "少女", "少年", "男人", "女人", "孩子", "青年",
         "教徒", "教众", "群众", "市民", "观众", "同事", "员工", "老师", "同学"}
names = {k: v for k, v in spk.items() if k not in NOISE and len(k) >= 2}
print(f"speaker labels kept as names: {len(names)}")

# ---- variant merging: 风熏 / 风薰 etc. use setting collection spellings ----
book_text = "\n".join(open(os.path.join(BOOK, f), encoding="utf-8").read()
                      for f in sorted(os.listdir(BOOK)) if f.endswith(".md"))
VARIANTS = {
    "风熏": "风薰", "西娜": "西娜·陈", "齐藤": "齐藤优子", "斯卡雷特": "斯卡雷特家族",
    "鸣": "鸣十二", "安安": "柳生安安", "薇薇安": "薇薇安", "曼陀罗": "1号（曼陀罗）",
}
merged = Counter()
for k, v in names.items():
    merged[VARIANTS.get(k, k)] += v

# ---- setting-collection heads for canonical checks ----
heads = set()
for f in sorted(os.listdir(BOOK)):
    if not f.endswith(".md"):
        continue
    t = open(os.path.join(BOOK, f), encoding="utf-8").read()
    for m in re.finditer(r"(?m)^#{1,4} +(.*)$", t):
        h = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", m.group(1)).strip("*【】 ")
        if 1 <= len(h) <= 30:
            heads.add(h)

def attested(name):
    return any(name in h for h in heads)

people = []
for k, v in merged.most_common():
    people.append({"tag": k, "slug": None, "lines": v, "attested_in_setting": attested(k)})

# ---- taxonomy skeleton (categories for the homepage) ----
taxonomy = {
    "文类": ["花絮", "楔子", "画外音", "剧情花絮", "特别环节", "四格漫画", "玩家之声"],
    "叙事层级": ["已发生", "未来可能", "平行世界线"],
    "主题": ["政治", "思想", "经济", "军事", "神秘学", "法律", "教育", "媒体", "宗教",
             "劳动", "科技", "外交"],
    "事件类型": ["战争", "政变", "屠杀", "暗杀", "公审", "谈判", "起义", "会议", "典礼",
                 "选举", "清洗", "起义失败"],
    "关系": ["师徒", "恋人", "亲族", "政敌", "同盟", "背叛", "上下级"],
    "主题词": ["忠诚", "背叛", "牺牲", "复仇", "宽恕", "救赎", "腐败", "理想", "自由",
               "暴力", "绝望", "希望"],
    "时间": ["战前", "战后3年", "战后5年", "战后6年", "战时"],
    "剧情线": ["北沙篇", "青都篇", "星都篇", "日本街", "中分山", "帝国线", "教团国线",
               "走廊区", "第一特区", "富贵集团", "光胜集团"],
}

vocab = {
    "note": "受控词表。设定集仅用于规范写法（选项A），不引用其内容。",
    "people": people,
    "taxonomy": taxonomy,
    "variant_map": VARIANTS,
    "stats": {"speaker_labels_raw": len(spk), "people_kept": len(people),
              "attested": sum(1 for p in people if p["attested_in_setting"])},
}

with open(os.path.join(DATA, "vocabulary.json"), "w", encoding="utf-8") as f:
    json.dump(vocab, f, ensure_ascii=False, indent=1)

print(f"\n=== top 60 people tags (lines = dialogue lines they speak) ===")
for p in people[:60]:
    mark = "*" if p["attested_in_setting"] else " "
    print(f"  {mark} {p['lines']:>4}  {p['tag']}")
print(f"\n({sum(1 for p in people if p['attested_in_setting'])} of {len(people)} "
      f"confirmed present in the setting collection)")
print("\nwrote", os.path.join(DATA, "vocabulary.json"))
print("\ntaxonomy categories:", list(taxonomy.keys()))
for k, v in taxonomy.items():
    print(f"  {k}: {len(v)} terms")
