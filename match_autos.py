"""For entries whose md title was auto-generated, find the real title by keyword
search against the official title list (and, if needed, the full article text)."""
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
ents = json.load(open(os.path.join(WIKI, "data", "entries.json"), encoding="utf-8"))["entries"]
official = json.load(open(os.path.join(WIKI, "data", "site_titles.json"), encoding="utf-8"))["titles"]
ART = json.load(open(os.path.join(WIKI, "data", "site_titles.json"), encoding="utf-8"))["per_article"]

autos = [e for e in ents if e["title_source"] == "auto"]
print(f"auto-titled entries: {len(autos)}\n")

UA = {"User-Agent": "Mozilla/5.0"}
IDS = {"总集篇一": 264, "总集篇二": 277, "总集篇三": 289, "总集篇四": 476,
       "总集篇五": 484, "总集篇六": 494, "总集篇七": 535, "总集篇八": 592,
       "北沙篇花絮总集篇": 737, "北沙篇花絮总集篇二": 1015, "长歌总集篇一": 850}

# cache full article text
cache = {}
for name, aid in IDS.items():
    try:
        raw = urllib.request.urlopen(
            urllib.request.Request(f"https://darkcoffin.hubingsf.cn/archives/{aid}", headers=UA),
            timeout=45).read().decode("utf-8", "ignore")
        cache[name] = re.sub(r"<[^>]+>", " ", raw)
    except Exception as e:
        print(f"  !! {name}: {e}")
print(f"cached article texts: {len(cache)}\n")

for e in autos:
    frag = re.sub(r"^(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)\s*[:：]\s*", "", e["title"])
    frag = frag.rstrip("…").strip()
    print("=" * 70)
    print(f"{e['id']}  {e['chars']}字  片段: {frag[:60]}")

    # A. exact-ish match against official titles
    hits = [t for t in official if frag[:12] and frag[:12] in t.replace("*", "")]
    if hits:
        print(f"   >> 站上标题匹配: {hits}")
        continue

    # B. search the article bodies
    found = []
    for name, body in cache.items():
        flat = re.sub(r"\s+", "", body)
        if frag[:14] and re.sub(r"\s+", "", frag)[:14] in flat:
            found.append(name)
    print(f"   >> 出现在文章: {found if found else '（未找到）'}")
