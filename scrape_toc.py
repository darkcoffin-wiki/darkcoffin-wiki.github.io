"""Authoritative title extraction: use each 总集篇's ez-toc table of contents
(fallback: h1/h2 title cards). Both list the piece titles verbatim."""
import html as htmlmod
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
OUT = r"E:\DSHwork\heijiu\wiki\data"

ARTICLES = {
    "总集篇一": 264, "总集篇二": 277, "总集篇三": 289, "总集篇四": 476,
    "总集篇五": 484, "总集篇六": 494, "总集篇七": 535, "总集篇八": 592,
    "北沙篇花絮总集篇": 737, "北沙篇花絮总集篇二": 1015, "长歌总集篇一": 850,
}

LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")
KIND = re.compile(r"^(?:[一二三四五六七八九十百]+[、.．]\s*)?"
                  r"(花絮|楔子|画外音|长歌|剧情花絮|特别内容|四格|特别环节|四格漫画)\s*[:：]")


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                  timeout=45).read().decode("utf-8", "ignore")


def clean(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = htmlmod.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


master = {}
per_article = {}

for name, aid in ARTICLES.items():
    try:
        raw = get(f"https://darkcoffin.hubingsf.cn/archives/{aid}")
    except Exception as e:
        print(f"!! {name}: {e}")
        continue

    titles = []

    # --- A. ez-toc entries (old articles) ---
    toc = re.findall(r'<a[^>]*class="[^"]*ez-toc-link[^"]*"[^>]*>(.*?)</a>', raw, re.S)
    titles += [clean(t) for t in toc]

    # --- B. h1/h2/h3 headings (new articles' title cards) ---
    for tag in ("h1", "h2", "h3"):
        for m in re.finditer(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), raw, re.S):
            titles.append(clean(m.group(1)))

    # --- keep only real piece titles ---
    keep = []
    for t in titles:
        t = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", t).strip()
        if not t or LEGEND.search(t):
            continue
        if not KIND.match(t):
            continue
        if t not in keep:
            keep.append(t)

    per_article[name] = keep
    for t in keep:
        master.setdefault(t, []).append(name)

    print(f"{name:<24} {len(keep):>3} titles")

all_titles = sorted(master)
print(f"\n=== DISTINCT TITLES ACROSS ALL 总集篇: {len(all_titles)} ===\n")
for t in all_titles:
    src = ",".join(master[t])
    print(f"  {t}   [{src}]")

json.dump({"per_article": per_article, "titles": all_titles,
           "title_sources": master},
          open(os.path.join(OUT, "site_titles.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\nwrote", os.path.join(OUT, "site_titles.json"))
