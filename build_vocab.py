"""Build the controlled vocabulary from the setting collection's entry headings,
then count how often each term actually occurs in the parsed huaxu entries.

Setting collection is used ONLY as a spelling reference (option A).
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

# ---------------------------------------------------------------- headings
heads = []
for f in sorted(os.listdir(BOOK)):
    if not f.endswith(".md"):
        continue
    t = open(os.path.join(BOOK, f), encoding="utf-8").read()
    for m in re.finditer(r"(?m)^#{1,4} +(.*)$", t):
        heads.append(re.sub(r"\s+", " ", m.group(1)).strip())

# also bold entry labels like **【概述】**
print(f"raw headings: {len(heads)}")

STOP = {"概述", "详述", "源", "异说", "存疑", "索引", "条目数", "未定之论",
        "编纂过程中发现的矛盾与未定之论", "发现的矛盾与存疑点", "矛盾与存疑点",
        "卷八 人物志", "卷一 世界观与神秘学", "卷二 启示录教团国",
        "卷三 希望联邦", "卷四 北沙与走廊", "卷五 帝国与进盟",
        "卷六 走廊区", "卷七 制度", "一", "二", "三", "四", "五", "六", "七", "八",
        "九", "十", "十一", "十二", "十三", "十四", "十五", "前言", "注意"}

cands = []
for h in heads:
    h = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", h)
    h = h.strip("*【】 ").strip()
    if not h or h in STOP:
        continue
    if len(h) < 2 or len(h) > 24:
        continue
    # drop obvious section words
    if re.search(r"(卷[一二三四五六七八九十]|编纂|备注|清单|总表|对照|说明|原因)$", h):
        continue
    if h.endswith(("条", "表", "清单", "备注", "说明", "原因", "问题", "点")):
        continue
    cands.append(h)

vocab = sorted(set(cands))
print(f"vocabulary candidates from setting collection: {len(vocab)}")

# ---------------------------------------------------------------- count in huaxu
entry_texts = {}
for f in sorted(os.listdir(SRC_DIR)):
    if f.endswith(".md") and not f.startswith("_"):
        entry_texts[f] = open(os.path.join(SRC_DIR, f), encoding="utf-8").read()
alltext = "\n".join(entry_texts.values())
print(f"huaxu entries scanned: {len(entry_texts)}, chars {len(alltext)}")

rows = []
for v in vocab:
    n = alltext.count(v)
    nfiles = sum(1 for t in entry_texts.values() if v in t)
    if n:
        rows.append({"term": v, "occurrences": n, "entries": nfiles})

rows.sort(key=lambda r: -r["entries"])
print(f"\nterms actually appearing in huaxu: {len(rows)}")

# write vocabulary
with open(os.path.join(DATA, "vocabulary.json"), "w", encoding="utf-8") as f:
    json.dump({
        "note": "Setting collection used ONLY as a spelling reference. "
                "occurrences/entries measured against the parsed huaxu entries.",
        "total_candidates": len(vocab),
        "terms": rows,
        "not_attested": [v for v in vocab if v not in {r["term"] for r in rows}],
    }, f, ensure_ascii=False, indent=1)

print("\n=== top 60 terms by number of entries they appear in ===")
for r in rows[:60]:
    print(f"  {r['entries']:>4} 篇  {r['occurrences']:>5} 次  {r['term']}")
print(f"\n... plus {len(rows) - 60} more")
print("wrote", os.path.join(DATA, "vocabulary.json"))
