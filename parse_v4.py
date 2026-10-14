"""FINAL splitter, v4 — implements the author's stated rule exactly.

Rule (author-specified):
  A line is a TITLE iff it contains one of the 8 vocabulary words followed by a
  colon: 花絮 楔子 画外音 长歌 剧情花絮 特别内容 四格 特别环节
  ...unless it is a legend line.

Two boundary cases, both required:
  * the kind word may be preceded by decoration ('#', '**', '****', numbering)
  * the kind word may sit mid-line inside prose  (e.g. '本花絮是TRPG北沙篇…')
    -> to stay safe, a title must START the line (after stripping decoration);
       the '#黑柩<kind>' family has no colon and is handled separately.
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

# ---- THE vocabulary, per the author ----
VOCAB8 = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")

# title = optional '#'s, optional asterisk runs, optional numbering, optional
# asterisk runs, then a vocabulary word immediately followed by ':' or '：'
TITLE = re.compile(
    r"^\s*(?:#{1,6}\s*)?\*{0,8}\s*"
    r"(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?"
    r"\*{0,8}\s*" + VOCAB8 + r"\s*[:：]")
# '#黑柩<kind>' family: no colon
HASH = re.compile(r"^\s*#\s*黑柩\s*(?:#\s*)?" + VOCAB8 + r"\s*#?\s*")

lines = open(SRC, encoding="utf-8", errors="ignore").read().split("\n")

starts = []
for i, l in enumerate(lines):
    prev_blank = (i == 0) or (not lines[i - 1].strip())
    if not prev_blank:
        continue                     # boundary guard
    if LEGEND.search(l):
        continue                     # legend lines are not titles
    m = TITLE.match(l)
    if m:
        starts.append({"line": i, "kind": m.group(1), "style": "colon", "inline": ""})
        continue
    h = HASH.match(l)
    if h:
        starts.append({"line": i, "kind": h.group(1), "style": "hash",
                       "inline": l[h.end():].strip()})

for j, s in enumerate(starts):
    s["end"] = starts[j + 1]["line"] if j + 1 < len(starts) else len(lines)

print(f"entries: {len(starts)}")
print("styles :", dict(Counter(s["style"] for s in starts)))
print("kinds  :", Counter(s["kind"] for s in starts).most_common())


def strip_deco(raw):
    t = re.sub(r"^#{1,6}\s*", "", raw).strip()
    t = re.sub(r"^\*+", "", t).strip()
    t = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", t)
    t = re.sub(r"^\d+[、.．]\s*", "", t)
    t = re.sub(r"^\*+", "", t).strip()
    t = re.sub(r"\*+$", "", t).strip()
    return t


def auto_title(s):
    t = re.sub(r"^[#\s*]+", "", s).strip()
    t = re.sub(r"^(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)\s*[:：#]*\s*", "", t)
    t = re.split(r"[。！？\n]", t)[0].strip("“”\"'　 ")
    return (t[:26] + "…") if len(t) > 26 else (t or "（无题）")


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
    s = re.sub(r"^(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)\s*[:：]?\s*", "", title)
    s = re.sub(r"[\s\u3000]+", "-", s)
    s = re.sub(r"[\\/:*?\"<>|,，。；;！!？?（）()\[\]【】“”\"'‘’—…·]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:maxlen].strip("-") or "untitled"


for f in os.listdir(SRC_DIR):
    if f.endswith(".md") and not f.startswith("_"):
        os.remove(os.path.join(SRC_DIR, f))

entries = []
for k, s in enumerate(starts, 1):
    a, b = s["line"], s["end"]
    if s["style"] == "colon":
        title, tsrc = strip_deco(lines[a]), "source"
        body_src = lines[a + 1:b]
    else:
        body_src = ([s["inline"]] if s["inline"] else []) + lines[a + 1:b]
        first = s["inline"] or (lines[a + 1] if a + 1 < len(lines) else "")
        title, tsrc = f"{s['kind']}：{auto_title(first)}", "auto"

    body = clean_body(body_src)
    eid = f"hx-{k:03d}"
    fname = f"{eid}-{slug_of(title)}.md"
    if len(fname) > 120:
        fname = f"{eid}-{slug_of(title)[:78]}.md"
    open(os.path.join(SRC_DIR, fname), "w", encoding="utf-8").write(
        f"---\nid: {eid}\ntitle: \"{title}\"\ntitle_source: {tsrc}\n"
        f"kind: {s['kind']}\nsource_line: {a+1}\nchars: {len(body)}\n---\n\n{body}\n")
    entries.append({"id": eid, "title": title, "title_source": tsrc, "kind": s["kind"],
                    "file": fname, "chars": len(body), "source_line": a + 1,
                    "source_hash": hashlib.sha1(body.encode()).hexdigest()[:16]})

json.dump({"source": os.path.basename(SRC), "entry_count": len(entries), "entries": entries},
          open(os.path.join(DATA, "entries.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

sizes = sorted(e["chars"] for e in entries)
n = len(sizes)
print(f"\nsource/: {len(entries)} files")
print(f"chars: min {sizes[0]}  p25 {sizes[n//4]}  median {sizes[n//2]}  "
      f"p75 {sizes[3*n//4]}  p90 {sizes[int(n*.9)]}  max {sizes[-1]}")
print(f"zero-length: {sum(1 for x in sizes if x == 0)}")
print(f">15000: {sum(1 for x in sizes if x > 15000)}")
print(f"auto-titled: {sum(1 for e in entries if e['title_source'] == 'auto')}")
print("\nkind breakdown:")
for kk, v in Counter(e["kind"] for e in entries).most_common():
    tot = sum(e["chars"] for e in entries if e["kind"] == kk)
    print(f"  {kk:<6} {v:>4} 篇  {tot:>8} 字")
print("\nentries > 15000:")
for e in sorted(entries, key=lambda x: -x["chars"])[:8]:
    if e["chars"] > 15000:
        print(f"  {e['id']} {e['chars']:>7}  {e['title'][:56]}")
