"""Scrape the official site's 总集篇 articles and extract their title cards.

Title cards live in <h1> (and occasionally <h2>). This gives the AUTHORITATIVE
list of piece titles, which we then use to verify the markdown split.
"""
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "https://darkcoffin.hubingsf.cn"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
OUT = r"E:\DSHwork\heijiu\wiki\data"
os.makedirs(OUT, exist_ok=True)


def get(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")


# ---- 1. collect article links from archive pages ----
arts = {}
for p in range(1, 6):
    url = f"{BASE}/" if p == 1 else f"{BASE}/page/{p}"
    try:
        html = get(url)
    except Exception as e:
        print(f"  page {p} failed: {e}")
        continue
    found = re.findall(r'href="(https://darkcoffin\.hubingsf\.cn/archives/\d+)"[^>]*>\s*([^<]{2,120}?)\s*<', html)
    for u, t in found:
        t = t.strip()
        if t and u not in arts:
            arts[u] = t
    print(f"page {p}: {len(found)} links, cumulative {len(arts)}")

totals = {u: t for u, t in arts.items() if "总集篇" in t}
print(f"\narticles whose title contains 总集篇: {len(totals)}")
for u, t in sorted(totals.items()):
    print(f"  {t}   {u}")

# ---- 2. fetch each and pull title cards ----
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")
KIND = re.compile(r"^(花絮|楔子|画外音|长歌|剧情花絮|特别内容|四格|特别环节|四格漫画)\s*[:：]")

all_titles = {}
per_article = {}
for u, name in sorted(totals.items(), key=lambda kv: kv[1]):
    try:
        html = get(u)
    except Exception as e:
        print(f"  !! {name}: {e}")
        continue
    body = re.sub(r"(?s)<(script|style).*?</\1>", "", html)
    heads = []
    for tag in ("h1", "h2", "h3"):
        for m in re.finditer(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), body, re.S):
            txt = re.sub(r"<[^>]+>", "", m.group(1))
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt:
                heads.append(txt)
    cards = [h for h in heads if KIND.match(h) and not LEGEND.search(h)]
    per_article[name] = cards
    print(f"\n=== {name}  ({u}) ===")
    print(f"  headings {len(heads)}  title cards {len(cards)}")
    for c in cards:
        print(f"    {c}")
    for c in cards:
        all_titles.setdefault(c, []).append(name)

print(f"\n\n=== TOTAL distinct title cards: {len(all_titles)} ===")
json.dump({"per_article": per_article,
           "all_titles": {k: v for k, v in all_titles.items()}},
          open(os.path.join(OUT, "site_titles.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("wrote", os.path.join(OUT, "site_titles.json"))
