"""Match md-only regions to official TOC titles by character-set overlap.

Report the best candidate per region, so the author can confirm whether a piece
was merely re-titled/re-typed on the site, or genuinely unpublished.
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
SRC = r"E:\黑柩\黑柩AI专供参考\黑柩花絮截止2026.10.md"
ents = json.load(open(os.path.join(WIKI, "data", "entries.json"), encoding="utf-8"))["entries"]
per = json.load(open(os.path.join(WIKI, "data", "site_titles.json"), encoding="utf-8"))["per_article"]

lines = open(SRC, encoding="utf-8", errors="ignore").read().split("\n")


def norm(s):
    s = s.replace("*", "")
    s = re.sub(r"[\s\u3000]", "", s)
    s = re.sub(r"[（）()【】\[\]「」『』“”\"'‘’、，,。.！!？?：:；;\-—－…·]", "", s)
    return s


# every official title as a char set
off = []
for art, ts in per.items():
    for t in ts:
        n = norm(t)
        if n:
            off.append((art, t, set(n)))

print(f"official titles: {len(off)}\n")
for e in [x for x in ents if x["title_source"] == "auto"]:
    a = e["source_line"] - 1
    i = ents.index(e)
    b = ents[i + 1]["source_line"] - 1 if i + 1 < len(ents) else len(lines)
    region = norm("\n".join(lines[a:b]))
    rset = set(region)
    scored = []
    for art, t, oset in off:
        inter = len(oset & rset)
        scored.append((inter / max(1, len(oset)), inter, art, t))
    scored.sort(reverse=True)
    print("=" * 74)
    print(f"{e['id']}  {e['chars']}字   片段: {region[:46]}")
    for sc, inter, art, t in scored[:3]:
        print(f"    {sc*100:5.1f}%  ({inter:>2}/{len(norm(t))})  [{art}] {t}")
