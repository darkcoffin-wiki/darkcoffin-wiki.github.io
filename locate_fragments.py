"""Locate each md-only fragment's opening sentence inside the scraped site texts,
and report the nearest preceding official title in that article."""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
SITE = os.path.join(WIKI, "_site_text")
ents = json.load(open(os.path.join(WIKI, "data", "entries.json"), encoding="utf-8"))["entries"]
lines = open(r"E:\黑柩\黑柩AI专供参考\黑柩花絮截止2026.10.md",
             encoding="utf-8", errors="ignore").read().split("\n")

VOCAB8 = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"
TITLE = re.compile(r"^\s*(?:\*{0,4}\s*)?" + VOCAB8 + r"\s*[:：]")


def flat(s):
    s = re.sub(r"[\s*#\\]", "", s)
    return s


site = {}
for f in sorted(os.listdir(SITE)):
    if f.endswith(".md"):
        site[f[:-3]] = open(os.path.join(SITE, f), encoding="utf-8").read()

autos = [e for e in ents if e["title_source"] == "auto"]
print(f"auto-titled: {len(autos)}\n")

for e in autos:
    a = e["source_line"] - 1
    i = ents.index(e)
    b = ents[i + 1]["source_line"] - 1 if i + 1 < len(ents) else len(lines)
    region = flat("\n".join(lines[a:b]))
    probe = region[:26]
    print("=" * 76)
    print(f"{e['id']}  {e['chars']}字   {region[:52]}")
    hit_any = False
    for art, txt in site.items():
        ftxt = flat(txt)
        pos = ftxt.find(probe)
        if pos < 0 and len(probe) > 14:
            pos = ftxt.find(probe[:14])
        if pos < 0:
            continue
        hit_any = True
        # nearest preceding title in that article
        before = ftxt[:pos]
        cands = list(TITLE.finditer(before))
        # TITLE on flattened text: find last line-ish occurrence
        cands2 = [m for m in re.finditer(VOCAB8 + r"[:：]", before)]
        prev = None
        if cands2:
            s = cands2[-1].start()
            prev = before[s:s + 40]
        print(f"   >> 在 [{art}] 内，位置 {pos}；其前最近标题: {prev}")
    if not hit_any:
        print("   >> 未在站点文章中找到（未发布）")
