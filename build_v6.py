"""build_v6.py — FINAL corpus build.

  * 12 DOCX files are the body sources.
  * Title markers: paragraph style '2'; for 黑柩TRPG-花絮总集篇二 the inline
    '#黑柩<kind>' marker (its body shares the same line).
  * Legend / definition lines dropped.
  * The site's titles are authoritative (adopted over docx wording, incl. the
    narrative-layer prefix). Site-only pieces are adopted too.
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
for d in (SRC_DIR, DATA, RAW):
    os.makedirs(d, exist_ok=True)

VOCAB = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"
KIND_AT_START = re.compile(r"^\s*(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?" + VOCAB + r"\s*[:：]")
TITLEISH = re.compile(VOCAB + r"\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")
DEFLINE = re.compile(r"^\s*" + VOCAB + r"\s*[:：]\s*(表示|代表|指|是|类|用于|见|说明|类似)")
HASHK = re.compile(r"^\s*#\s*黑柩?\s*(?:#\s*)?" + VOCAB + r"\s*#?\s*")

# (docx path, site article name)
SOURCES = [
    (r"E:\黑柩\黑柩小说花絮\黑柩TRPG-花絮总集篇一.docx", "总集篇一", 264),
    (r"E:\黑柩\黑柩小说花絮\黑柩TRPG-花絮总集篇二.docx", "总集篇二", 277),
    (r"E:\黑柩\黑柩小说花絮\黑柩-花絮3.docx", "总集篇三", 289),
    (r"E:\黑柩\黑柩小说花絮\黑柩-花絮4.docx", "总集篇四", 476),
    (r"E:\黑柩\黑柩小说花絮\黑柩-花絮5.docx", "总集篇五", 484),
    (r"E:\黑柩\黑柩小说花絮\黑柩-花絮6.docx", "总集篇六", 494),
    (r"E:\黑柩\黑柩小说花絮\黑柩-花絮7.docx", "总集篇七", 535),
    (r"E:\黑柩\黑柩小说花絮\黑柩-花絮8.docx", "总集篇八", 592),
    (r"E:\黑柩\黑柩小说花絮\黑柩-花絮9.docx", "北沙篇花絮总集篇", 737),
    (r"C:\Users\fly12138\AppData\Local\Kingsoft\WPS Cloud Files\userdata\qing\filecache\WPSDrive\240050742\WPS云盘\黑柩-北沙篇花絮总集篇二.docx", "北沙篇花絮总集篇二", 1015),
    (r"E:\黑柩\黑柩小说花絮\黑柩-长歌1.docx", "长歌总集篇一", 850),
    (r"C:\Users\fly12138\AppData\Local\Kingsoft\WPS Cloud Files\userdata\qing\filecache\WPSDrive\240050742\WPS云盘\黑柩-长歌总集篇二.docx", "(未发布) 长歌总集篇二", None),
]


def strip_deco(t):
    t = re.sub(r"^#{1,6}\s*", "", t).strip()
    t = re.sub(r"^\*+", "", t).strip()
    t = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", t)
    t = re.sub(r"^\d+[、.．]\s*", "", t)
    t = re.sub(r"\*+$", "", t).strip()
    return t.strip()


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
    if not text or LEGEND.search(text) or DEFLINE.match(text):
        return False
    if style == "2" and KIND_AT_START.match(text):
        return True
    if style == "2" and TITLEISH.search(text) and len(text) < 60:
        return True
    if HASHK.match(text):
        return True
    if not style and KIND_AT_START.match(text) and len(text) < 60:
        return True
    return False


# ---------------------------------------------------------------- site titles
def fetch_site(aid, name):
    p = os.path.join(RAW, f"{aid}.html")
    if os.path.exists(p):
        raw = open(p, encoding="utf-8", errors="ignore").read()
    else:
        raw = urllib.request.urlopen(
            urllib.request.Request(f"https://darkcoffin.hubingsf.cn/archives/{aid}",
                                   headers={"User-Agent": "Mozilla/5.0"}),
            timeout=45).read().decode("utf-8", "ignore")
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
        t = strip_deco(t)
        if not t or LEGEND.search(t) or DEFLINE.match(t) or not TITLEISH.match(t):
            continue
        tail = re.sub(r"^" + VOCAB + r"\s*[:：]\s*", "", t).strip()
        if not tail or tail in ("花絮", "楔子", "画外音", "四格", "四格漫画", "长歌"):
            continue
        if t not in seen:
            seen.add(t)
            keep.append(t)
    return keep


def kind_of(t):
    m = re.match(r"^\s*" + VOCAB, t)
    return m.group(1) if m else "?"


def norm_tail(t):
    s = re.sub(r"^" + VOCAB + r"\s*[:：]\s*", "", t)
    s = s.replace("*", "")
    s = re.sub(r"[\s\u3000]", "", s)
    s = re.sub(r"[（）()【】\[\]「」『』“”\"'‘’、，,。.！!？?：:]", "", s)
    return s.replace("——", "").replace("—", "").replace("-", "")


# ---------------------------------------------------------------- build
for f in os.listdir(SRC_DIR):
    if f.endswith(".md") and not f.startswith("_"):
        os.remove(os.path.join(SRC_DIR, f))

pieces = []
for path, site_name, aid in SOURCES:
    if not os.path.exists(path):
        print("!! missing:", os.path.basename(path))
        continue
    src = os.path.basename(path)
    site_titles_list = fetch_site(aid, site_name) if aid else []
    by_tail = {norm_tail(t): t for t in site_titles_list}

    paras = read_docx(path)
    cur = None
    for style, text in paras:
        if is_title(style, text):
            if cur:
                pieces.append(cur)
            inline = ""
            m = HASHK.match(text)
            if m:
                inline = text[m.end():].strip()
            cur = {"src": src, "site": site_name, "raw_title": strip_deco(text),
                   "inline": inline, "body": []}
        elif cur is not None and text:
            cur["body"].append(text)
    if cur:
        pieces.append(cur)

print(f"raw pieces from docx: {len(pieces)}")

# ---- resolve titles: adopt the site's wording when a match exists ----
kept, dropped, untitled = [], [], []
for p in pieces:
    # candidate title text
    t = p["raw_title"]
    if p["inline"]:
        # 总集篇二: the raw title is the whole opening line -> not a title
        t = None
    if t:
        tail = norm_tail(t)
        if tail in by_tail:
            t = by_tail[tail]                     # site wording wins
        body = p["body"]
    else:
        # match by opening text
        opening = p["inline"]
        cand = None
        for st in site_titles_list:
            tl = norm_tail(st)
            if tl and (tl[:12] in re.sub(r"[\s*#]", "", opening) or
                       re.sub(r"[\s*#]", "", opening)[:12] in tl):
                cand = st
                break
        if cand is None:
            # never invent a title: record it for later reconciliation
            cand = None
        t = cand
        body = [opening] + p["body"]
    if t is None:
        untitled.append({"src": p["src"], "site": p["site"], "opening": p["inline"][:80],
                         "chars": len("\n".join([p["inline"]] + p["body"]))})
        continue
    if not body:
        dropped.append(t)
        continue
    kept.append({"src": p["src"], "site": p["site"], "title": t, "body": body})

print(f"kept: {len(kept)}   dropped(empty): {len(dropped)}   untitled: {len(untitled)}")
for u in untitled:
    print("   untitled:", u["site"], "|", u["opening"][:60])
if dropped:
    for d in dropped:
        print("   dropped:", d[:70])

# ---- dedupe across sources by normalised full title ----
seen, uniq = {}, []
for k in kept:
    key = re.sub(r"[\s*#]", "", k["title"])
    if key in seen:
        continue
    seen[key] = True
    uniq.append(k)
print(f"unique after dedupe: {len(uniq)}")


def slug_of(title, maxlen=42):
    s = re.sub(r"^" + VOCAB + r"\s*[:：]?\s*", "", title)
    s = re.sub(r"[\s\u3000]+", "-", s)
    s = re.sub(r'[\\/:*?"<>|,，。；;！!？?（）()\[\]【】“”"\'‘’—…·]+', "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:maxlen].strip("-") or "untitled"


entries = []
for i, k in enumerate(uniq, 1):
    body = "\n\n".join(k["body"])
    eid = f"hx-{i:03d}"
    fname = f"{eid}-{slug_of(k['title'])}.md"
    if len(fname) > 120:
        fname = f"{eid}-{slug_of(k['title'])[:78]}.md"
    open(os.path.join(SRC_DIR, fname), "w", encoding="utf-8").write(
        f"---\nid: {eid}\ntitle: \"{k['title']}\"\nkind: {kind_of(k['title'])}\n"
        f"collection: {k['site']}\nsource_docx: {k['src']}\nchars: {len(body)}\n"
        f"---\n\n{body}\n")
    entries.append({"id": eid, "title": k["title"], "kind": kind_of(k["title"]),
                    "collection": k["site"], "source_docx": k["src"],
                    "file": fname, "chars": len(body),
                    "source_hash": hashlib.sha1(body.encode()).hexdigest()[:16]})

json.dump({"entry_count": len(entries), "entries": entries},
          open(os.path.join(DATA, "entries.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

sizes = sorted(e["chars"] for e in entries)
n = len(sizes)
print(f"\nsource/: {len(entries)} files")
print(f"chars: min {sizes[0]} p25 {sizes[n//4]} median {sizes[n//2]} "
      f"p75 {sizes[3*n//4]} max {sizes[-1]}")
print("by kind  :", Counter(e["kind"] for e in entries).most_common())
print("by source:", Counter(e["collection"] for e in entries).most_common())
print("\nlargest 6:")
for e in sorted(entries, key=lambda x: -x["chars"])[:6]:
    print(f"  {e['id']} {e['chars']:>6}  {e['title'][:60]}")
open(os.path.join(SRC_DIR, "_INDEX.md"), "w", encoding="utf-8").write(
    "# 花絮语料索引\n\n| id | 类型 | 合集 | 字数 | 标题 |\n|---|---|---|---:|---|\n" +
    "\n".join(f"| {e['id']} | {e['kind']} | {e['collection']} | {e['chars']} | {e['title']} |"
              for e in entries) + "\n")
print("\nwrote _INDEX.md and data/entries.json")
