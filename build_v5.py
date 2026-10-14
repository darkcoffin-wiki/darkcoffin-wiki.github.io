"""FINAL corpus build, v5 — DOCX sources first, site as authority for naming.

Sources (priority):
  1. 12 DOCX files   -> body text; titles marked by paragraph style '2',
                        or (总集篇二) inline '#黑柩<kind>'
  2. the site        -> authoritative titles/hierarchy; adopted over docx
  3. the merged .md  -> only where docx has no counterpart

Rules locked with the author:
  * 8 vocabulary words, colon required: 花絮 楔子 画外音 长歌 剧情花絮 特别内容 四格 特别环节
  * legend/definition lines are dropped
  * site titles win over docx titles (including the narrative-layer prefix)
  * pieces present only on the site are adopted as well
"""
import html as htmlmod
import hashlib
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
SRC_DIR = os.path.join(WIKI, "source")
DATA = os.path.join(WIKI, "data")
RAW = os.path.join(WIKI, "_site_raw")
os.makedirs(SRC_DIR, exist_ok=True)
os.makedirs(DATA, exist_ok=True)
os.makedirs(RAW, exist_ok=True)

VOCAB = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"
KIND_AT_START = re.compile(r"^\s*(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?" + VOCAB + r"\s*[:：]")
TITLEISH = re.compile(VOCAB + r"\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")
HASHK = re.compile(r"^\s*#\s*黑柩?\s*(?:#\s*)?" + VOCAB)

DOCX = [
    r"E:\黑柩\黑柩小说花絮\黑柩TRPG-花絮总集篇一.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩TRPG-花絮总集篇二.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮3.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮4.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮5.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮6.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮7.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮8.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮9.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-长歌1.docx",
    r"C:\Users\fly12138\AppData\Local\Kingsoft\WPS Cloud Files\userdata\qing\filecache\WPSDrive\240050742\WPS云盘\黑柩-长歌总集篇二.docx",
    r"C:\Users\fly12138\AppData\Local\Kingsoft\WPS Cloud Files\userdata\qing\filecache\WPSDrive\240050742\WPS云盘\黑柩-北沙篇花絮总集篇二.docx",
]
ARTICLES = {
    "总集篇一": 264, "总集篇二": 277, "总集篇三": 289, "总集篇四": 476,
    "总集篇五": 484, "总集篇六": 494, "总集篇七": 535, "总集篇八": 592,
    "北沙篇花絮总集篇": 737, "北沙篇花絮总集篇二": 1015, "长歌总集篇一": 850,
}

# ---------------------------------------------------------------- docx parse
def read_docx(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    out = []
    for p in re.findall(r"<w:p[^>]*>(.*?)</w:p>", xml, re.S):
        m = re.search(r'<w:pStyle w:val="([^"]+)"', p)
        style = m.group(1) if m else ""
        t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
        t = htmlmod.unescape(re.sub(r"<[^>]+>", "", t)).strip()
        out.append((style, t))
    return out


def is_title(style, text):
    if not text or LEGEND.search(text):
        return False
    if style == "2" and KIND_AT_START.match(text):
        return True          # the standard marker
    if style == "2" and TITLEISH.search(text) and len(text) < 60:
        return True          # heading style, allow odd decoration
    m = HASHK.match(text)
    if m:
        return True          # 总集篇二 style
    if not style and KIND_AT_START.match(text) and len(text) < 60:
        return True          # unstyled but clean title line
    return False


def strip_deco(t):
    t = re.sub(r"^#{1,6}\s*", "", t).strip()
    t = re.sub(r"^\*+", "", t).strip()
    t = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", t)
    t = re.sub(r"^\d+[、.．]\s*", "", t)
    return t.strip()


docx_pieces = []          # {source, title, paras:[...]}
for path in DOCX:
    if not os.path.exists(path):
        print("!! missing:", path)
        continue
    paras = read_docx(path)
    base = os.path.basename(path)
    cur = None
    for style, text in paras:
        if is_title(style, text):
            if cur:
                docx_pieces.append(cur)
            cur = {"source": base, "title": strip_deco(text), "paras": []}
        elif cur is not None and text:
            cur["paras"].append(text)
    if cur:
        docx_pieces.append(cur)

print(f"docx pieces: {len(docx_pieces)}")
print("by source:", Counter(p["source"] for p in docx_pieces).most_common())
print("empty-body pieces:", sum(1 for p in docx_pieces if not p["paras"]))

# ---------------------------------------------------------------- site titles
def site_titles(name, aid):
    p = os.path.join(RAW, f"{aid}.html")
    raw = (open(p, encoding="utf-8", errors="ignore").read() if os.path.exists(p)
           else urllib.request.urlopen(
               urllib.request.Request(f"https://darkcoffin.hubingsf.cn/archives/{aid}",
                                      headers={"User-Agent": "Mozilla/5.0"}),
               timeout=45).read().decode("utf-8", "ignore"))
    if not os.path.exists(p):
        open(p, "w", encoding="utf-8").write(raw)

    def clean(s):
        return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", "", s))).strip()

    found = []
    for m in re.finditer(r'<a[^>]*class="[^"]*ez-toc-link[^"]*"[^>]*>(.*?)</a>', raw, re.S):
        found.append(clean(m.group(1)))
    for tag in ("h1", "h2"):
        for m in re.finditer(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), raw, re.S):
            found.append(clean(m.group(1)))
    for m in re.finditer(r"<strong>\s*(" + VOCAB + r"\s*[:：])\s*</strong>\s*([^<]{0,64})", raw):
        found.append(clean(m.group(1) + m.group(2)))
    for m in re.finditer(r"<p[^>]*>\s*(" + VOCAB + r"\s*[:：][^<]{0,64})", raw):
        found.append(clean(m.group(1)))

    keep, seen = [], set()
    for t in found:
        t = strip_deco(t).strip()
        if not t or LEGEND.search(t) or not TITLEISH.match(t):
            continue
        # drop definition noise ("花絮：花絮" etc.)
        tail = re.sub(r"^" + VOCAB + r"\s*[:：]\s*", "", t).strip()
        if not tail or tail in ("花絮", "楔子", "画外音", "四格", "四格漫画", "长歌"):
            continue
        if t not in seen:
            seen.add(t)
            keep.append(t)
    return keep


site = {name: site_titles(name, aid) for name, aid in ARTICLES.items()}
print("\nsite titles:", {k: len(v) for k, v in site.items()})
print("site total:", sum(len(v) for v in site.values()))

json.dump({"docx_pieces": [{"source": p["source"], "title": p["title"]} for p in docx_pieces],
           "site_titles": site},
          open(os.path.join(DATA, "v5_inventory.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\nwrote data/v5_inventory.json")
