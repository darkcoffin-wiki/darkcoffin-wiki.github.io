"""Final parser, v3.

Fixes over v2:
  * '#黑柩<kind>' markers have NO colon and the body may start on the SAME line.
    v2 treated the whole line as a title, leaving body = 0 chars. Now the line is
    split into (marker, inline text); inline text becomes the first body line.
  * titles for such pieces are derived from the first sentence of the body (for
    author review), and recorded as 'title_source: auto'.
"""
import hashlib
import io
import json
import os
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SRC = r"E:\黑柩\黑柩AI专供参考\黑柩花絮截止2026.10.md"
WIKI = r"E:\DSHwork\heijiu\wiki"
SRC_DIR = os.path.join(WIKI, "source")
DATA = os.path.join(WIKI, "data")

lines = open(SRC, encoding="utf-8", errors="ignore").read().split("\n")

KIND = r"(剧情花絮|花絮|楔子|画外音|特别环节|四格漫画|玩家之声)"
# style 1: heading/bold + optional numbering + kind + colon, body follows
COLON = re.compile(
    r"^\s*(?:#{1,6}\s*)?\*{0,6}\s*"
    r"(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?"
    r"\*{0,6}\s*" + KIND + r"\s*[:：]")
# style 2: '#黑柩<kind>[#]' with NO colon
HASH = re.compile(r"^\s*#\s*黑柩\s*(?:#\s*)?" + KIND + r"\s*#?\s*")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")

starts = []
for i, l in enumerate(lines):
    if i and lines[i - 1].strip():
        continue                       # boundary guard: previous line must be blank
    if LEGEND.search(l):
        continue
    if COLON.match(l):
        starts.append({"line": i, "kind": COLON.match(l).group(1),
                       "style": "colon", "inline": ""})
    elif HASH.match(l):
        m = HASH.match(l)
        inline = l[m.end():].strip()   # body text that shares the marker line
        starts.append({"line": i, "kind": m.group(1),
                       "style": "hash", "inline": inline})

for j, s in enumerate(starts):
    s["end"] = starts[j + 1]["line"] if j + 1 < len(starts) else len(lines)

print(f"entries (v3): {len(starts)}")
print("styles:", Counter(s["style"] for s in starts))
print("kinds :", Counter(s["kind"] for s in starts).most_common())


def strip_deco(raw):
    t = re.sub(r"^#{1,6}\s*", "", raw).strip()
    t = re.sub(r"^\*+", "", t)
    t = re.sub(r"\*+$", "", t).strip()
    t = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", t)
    t = re.sub(r"^\d+[、.．]\s*", "", t)
    t = re.sub(r"^\*+", "", t).strip()
    return t.strip()


def auto_title(text):
    """Take the first sentence-ish run as a provisional title."""
    t = re.sub(r"^[#\s*]+", "", text).strip()
    t = re.sub(r"^(剧情花絮|花絮|楔子|画外音|特别环节|四格漫画|玩家之声)\s*[:：#]*\s*", "", t)
    t = re.split(r"[。！？\n]", t)[0]
    t = t.strip("“”\"'　 ")
    return (t[:24] + "…") if len(t) > 24 else (t or "（无题）")


DIV = re.compile(r"^\s*\**——\**\s*$")
DIALOG = re.compile(r"^\*\*([^*：:\n]{1,16})\*\*\s*[:：]\s*(.*)$")
BOLD = re.compile(r"^\*\*([^*]+)\*\*\s*$")


def clean_body(seg):
    out = []
    for l in seg:
        s = l.strip()
        if not s:
            out.append("")
            continue
        if DIV.match(s):
            out += ["", "---", ""]
            continue
        m = DIALOG.match(s)
        if m:
            out.append(f"**{m.group(1)}**：{m.group(2)}")
            continue
        m2 = BOLD.match(s)
        if m2:
            out.append(m2.group(1))
            continue
        out.append(re.sub(r"\*\*([^*]+)\*\*", r"\1", s))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def slug_of(title, maxlen=40):
    s = re.sub(r"^(剧情花絮|花絮|楔子|画外音|特别环节|四格漫画|玩家之声)\s*[:：]?\s*", "", title)
    s = re.sub(r"[\s\u3000]+", "-", s)
    s = re.sub(r"[\\/:*?\"<>|,，。；;！!？?（）()\[\]【】“”\"'‘’—…·]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return (s[:maxlen].strip("-") or "untitled")


for f in os.listdir(SRC_DIR):
    if f.endswith(".md") and not f.startswith("_"):
        os.remove(os.path.join(SRC_DIR, f))

entries = []
for k, s in enumerate(starts, 1):
    a, b = s["line"], s["end"]
    head_line = lines[a]
    if s["style"] == "colon":
        title = strip_deco(head_line)
        src_title = "source"
        body_src = lines[a + 1:b]
    else:
        body_src = ([s["inline"]] if s["inline"] else []) + lines[a + 1:b]
        title = f"{s['kind']}：{auto_title(s['inline'] or (lines[a+1] if a+1 < len(lines) else ''))}"
        src_title = "auto"

    body = clean_body(body_src)
    eid = f"hx-{k:03d}"
    fname = f"{eid}-{slug_of(title)}.md"
    if len(fname) > 120:
        fname = f"{eid}-{slug_of(title)[:80]}.md"
    open(os.path.join(SRC_DIR, fname), "w", encoding="utf-8").write(
        f"---\nid: {eid}\ntitle: \"{title}\"\ntitle_source: {src_title}\n"
        f"kind: {s['kind']}\nsource_line: {a+1}\nchars: {len(body)}\n---\n\n{body}\n")
    entries.append({"id": eid, "title": title, "title_source": src_title,
                    "kind": s["kind"], "file": fname, "chars": len(body),
                    "source_line": a + 1,
                    "source_hash": hashlib.sha1(body.encode()).hexdigest()[:16]})

json.dump({"source": os.path.basename(SRC), "entry_count": len(entries), "entries": entries},
          open(os.path.join(DATA, "entries.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

sizes = sorted(e["chars"] for e in entries)
n = len(sizes)
print(f"\nsource/: {len(entries)} files")
print(f"chars: min {sizes[0]}  p25 {sizes[n//4]}  median {sizes[n//2]}  "
      f"p75 {sizes[3*n//4]}  p90 {sizes[int(n*.9)]}  max {sizes[-1]}")
print(f"zero-length entries: {sum(1 for x in sizes if x == 0)}")
print(f">15000: {sum(1 for x in sizes if x > 15000)}")
print(f"auto-titled entries: {sum(1 for e in entries if e['title_source'] == 'auto')}")
print("\nauto-titled samples:")
for e in entries:
    if e["title_source"] == "auto":
        print(f"  {e['id']} {e['chars']:>6}  {e['title'][:64]}")
