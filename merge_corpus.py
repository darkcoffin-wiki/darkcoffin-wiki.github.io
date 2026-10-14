"""merge_corpus.py — final corpus.

  site pieces (195, published, authoritative titles+text)
+ docx pieces not on the site (the unpublished 长歌总集篇二 etc.)
= final corpus, one markdown per piece.
"""
import html as htmlmod
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
SRC_DIR = os.path.join(WIKI, "source")
DATA = os.path.join(WIKI, "data")
os.makedirs(SRC_DIR, exist_ok=True)

VOCAB = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"
HASHK = re.compile(r"^\s*#\s*黑柩?\s*(?:#\s*)?" + VOCAB + r"\s*#?\s*")
KIND_AT_START = re.compile(r"^\s*(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?" + VOCAB + r"\s*[:：]")
TITLEISH = re.compile(VOCAB + r"\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")
DEFLINE = re.compile(r"^\s*" + VOCAB + r"\s*[:：]\s*(表示|代表|指|是|类|用于|见|说明|类似)")


def norm(t):
    s = re.sub(r"^" + VOCAB + r"\s*[:：]\s*", "", t)
    s = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", s)
    s = s.replace("*", "")
    s = re.sub(r"[\s\u3000]", "", s)
    s = re.sub(r"[（）()【】\[\]「」『』“”\"'‘’、，,。.！!？?：:]", "", s)
    return s.replace("——", "").replace("—", "").replace("-", "")


def kind_of(t):
    m = re.match(r"^\s*" + VOCAB, t)
    return m.group(1) if m else "?"


# ---------------- site pieces ----------------
site = json.load(open(os.path.join(DATA, "site_pieces.json"), encoding="utf-8"))
corpus, seen = [], {}
for coll, ps in site.items():
    for p in ps:
        key = norm(p["title"])
        if not key or key in seen:
            if key in seen:
                print(f"  dup site title, skipped: {p['title'][:50]}")
            continue
        seen[key] = True
        corpus.append({"title": p["title"], "kind": kind_of(p["title"]),
                       "collection": coll, "origin": "site",
                       "body": "\n\n".join(p["body"])})
print(f"site pieces: {len(corpus)}")

# ---------------- docx pieces (only those NOT on the site) ----------------
DOCX_UNPUB = [
    (r"C:\Users\fly12138\AppData\Local\Kingsoft\WPS Cloud Files\userdata\qing\filecache\WPSDrive\240050742\WPS云盘\黑柩-长歌总集篇二.docx",
     "(未发布) 长歌总集篇二"),
]


def read_docx(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    out = []
    for p in re.findall(r"<w:p[^>]*>(.*?)</w:p>", xml, re.S):
        m = re.search(r'<w:pStyle w:val="([^"]+)"', p)
        t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
        t = htmlmod.unescape(re.sub(r"<[^>]+>", "", t)).strip()
        out.append(((m.group(1) if m else ""), t))
    return out


added = 0
for path, coll in DOCX_UNPUB:
    if not os.path.exists(path):
        print("!! missing:", path)
        continue
    cur = None
    for style, t in read_docx(path):
        if not t or LEGEND.search(t) or DEFLINE.match(t):
            continue
        if style == "2" and KIND_AT_START.match(t):
            if cur:
                corpus.append(cur)
                added += 1
            cur = {"title": re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", t).strip(),
                   "kind": kind_of(t), "collection": coll, "origin": "docx", "body": []}
        elif cur is not None:
            cur["body"].append(t)
    if cur:
        corpus.append(cur)
        added += 1
print(f"docx (unpublished) pieces added: {added}")

# dedupe again (docx titles may coincide with site ones)
final, seen2 = [], set()
for x in corpus:
    k = norm(x["title"])
    if not k or k in seen2:
        continue
    seen2.add(k)
    final.append(x)
print(f"final pieces: {len(final)}")


def slug_of(title, maxlen=44):
    s = re.sub(r"^" + VOCAB + r"\s*[:：]?\s*", "", title)
    s = re.sub(r"[\s\u3000]+", "-", s)
    s = re.sub(r'[\\/:*?"<>|,，。；;！!？?（）()\[\]【】“”"\'‘’—…·]+', "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:maxlen].strip("-") or "untitled"


for f in os.listdir(SRC_DIR):
    if f.endswith(".md") and not f.startswith("_"):
        os.remove(os.path.join(SRC_DIR, f))

entries = []
for i, x in enumerate(final, 1):
    body = x["body"] if isinstance(x["body"], str) else "\n\n".join(x["body"])
    eid = f"hx-{i:03d}"
    name = f"{eid}-{slug_of(x['title'])}.md"
    if len(name) > 120:
        name = f"{eid}-{slug_of(x['title'])[:80]}.md"
    open(os.path.join(SRC_DIR, name), "w", encoding="utf-8").write(
        f"---\nid: {eid}\ntitle: \"{x['title']}\"\nkind: {x['kind']}\n"
        f"collection: {x['collection']}\norigin: {x['origin']}\nchars: {len(body)}\n"
        f"---\n\n{body}\n")
    entries.append({"id": eid, "title": x["title"], "kind": x["kind"],
                    "collection": x["collection"], "origin": x["origin"],
                    "file": name, "chars": len(body),
                    "source_hash": hashlib.sha1(body.encode()).hexdigest()[:16]})

json.dump({"entry_count": len(entries), "entries": entries},
          open(os.path.join(DATA, "entries.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
open(os.path.join(SRC_DIR, "_INDEX.md"), "w", encoding="utf-8").write(
    "# 花絮语料索引\n\n| id | 类型 | 合集 | 来源 | 字数 | 标题 |\n|---|---|---|---|---:|---|\n" +
    "\n".join(f"| {e['id']} | {e['kind']} | {e['collection']} | {e['origin']} | "
              f"{e['chars']} | {e['title']} |" for e in entries) + "\n")

sizes = sorted(e["chars"] for e in entries)
n = len(sizes)
print(f"\nsource/: {len(entries)} files")
print(f"chars: min {sizes[0]}  p25 {sizes[n//4]}  median {sizes[n//2]}  "
      f"p75 {sizes[3*n//4]}  max {sizes[-1]}")
print("by kind :", Counter(e["kind"] for e in entries).most_common())
print("by origin:", Counter(e["origin"] for e in entries).most_common())
print("unknown kind:", [e["title"][:40] for e in entries if e["kind"] == "?"])
