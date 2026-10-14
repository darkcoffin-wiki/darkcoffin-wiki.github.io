"""Compare the md-only fragments' openings against the official TOC titles of
总集篇二 / 总集篇三 by looking for the title's tail (the part after ': ') inside
the md regions."""
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
text = open(SRC, encoding="utf-8", errors="ignore").read()

autos = [e for e in ents if e["title_source"] == "auto"]
print(f"auto-titled: {len(autos)}\n")

# build the md region for each auto entry
lines = text.split("\n")
for e in autos:
    a = e["source_line"] - 1
    idx = ents.index(e)
    b = ents[idx + 1]["source_line"] - 1 if idx + 1 < len(ents) else len(lines)
    region = re.sub(r"[\s*#]", "", "\n".join(lines[a:b]))[:900]

    print("=" * 72)
    print(f"{e['id']}  {e['chars']}字")
    print(f"   片段: {re.sub(chr(10), '', region)[:70]}")

    # find which official titles' TAIL appears in this region
    for art in ("总集篇二", "总集篇三", "总集篇一", "总集篇四"):
        for t in per.get(art, []):
            tail = t.split("：", 1)[-1].split(":", 1)[-1]
            tail_k = re.sub(r"[\s*#（）()【】\-—、，。！？]", "", tail)
            if len(tail_k) >= 4 and tail_k[:10] in region:
                print(f"   >> 命中标题: [{art}] {t}")
