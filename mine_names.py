"""Mine candidate proper nouns from the huaxu corpus itself, then reconcile
with the setting collection for canonical spelling."""
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

# ---- corpus ----
texts = {}
for f in sorted(os.listdir(SRC_DIR)):
    if f.endswith(".md") and not f.startswith("_"):
        texts[f] = open(os.path.join(SRC_DIR, f), encoding="utf-8").read()

# ---- 1. speaker labels (**Name**：) are almost all character names ----
spk = Counter()
for t in texts.values():
    for m in re.finditer(r"(?m)^\*\*([^*：:\n]{1,16})\*\*\s*[:：]", t):
        spk[m.group(1).strip()] += 1
print(f"speaker labels: {len(spk)} distinct")
print("  top 40:")
for k, v in spk.most_common(40):
    print(f"    {v:>4}  {k}")

# ---- 2. quoted-name pattern: XX：..., also 「」【】bracketed names ----
# ---- 3. frequent CJK n-grams 2-6 that repeat across entries ----
from collections import defaultdict
files_with = defaultdict(set)
for f, t in texts.items():
    for n in (2, 3, 4, 5, 6):
        for m in re.finditer(r"[\u4e00-\u9fff]{%d}" % n, t):
            files_with[m.group(0)].add(f)

# keep n-grams appearing in >=3 entries and not part of a longer one we keep
cand = {k: len(v) for k, v in files_with.items() if len(v) >= 5}
print(f"\nCJK n-grams in >=5 entries: {len(cand)}")

# ---- 4. setting-collection headings for canonical spelling ----
heads = set()
for f in sorted(os.listdir(BOOK)):
    if not f.endswith(".md"):
        continue
    t = open(os.path.join(BOOK, f), encoding="utf-8").read()
    for m in re.finditer(r"(?m)^#{1,4} +(.*)$", t):
        h = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", m.group(1)).strip("*【】 ")
        if 2 <= len(h) <= 24:
            heads.add(h)

# ---- 5. report: names confirmed by the setting collection ----
confirmed = []
for k, n in cand.items():
    for h in heads:
        if k in h:
            confirmed.append((k, n, h))
            break

confirmed.sort(key=lambda x: -x[1])
print(f"\n=== n-grams confirmed by a setting-collection heading (top 70) ===")
for k, n, h in confirmed[:70]:
    print(f"  {n:>4} 篇  {k:<12} ← {h[:34]}")

with open(os.path.join(DATA, "name_candidates.json"), "w", encoding="utf-8") as f:
    json.dump({
        "speaker_labels": spk.most_common(),
        "confirmed_ngrams": [{"term": k, "entries": n, "ref": h} for k, n, h in confirmed],
    }, f, ensure_ascii=False, indent=1)
print("\nwrote", os.path.join(DATA, "name_candidates.json"))
