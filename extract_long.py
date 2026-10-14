"""Extract all entries > 15000 chars into a review folder for manual inspection.

Each file gets a header with stats, plus a marker list of potential internal
boundaries (#黑柩X lines and scene dividers) so the author can decide splits.
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SRC = r"E:\黑柩\黑柩AI专供参考\黑柩花絮截止2026.10.md"
WIKI = r"E:\DSHwork\heijiu\wiki"
REV = os.path.join(WIKI, "_review_long")
os.makedirs(REV, exist_ok=True)

lines = open(SRC, encoding="utf-8", errors="ignore").read().split("\n")

KINDS = r"(剧情花絮|花絮|楔子|画外音|特别环节|四格漫画|玩家之声)"
# fixed rule: allow runs of up to 6 asterisks
ENTRY = re.compile(
    r"^\s*(?:#{1,6}\s*)?\*{0,6}\s*"
    r"(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?"
    r"\*{0,6}\s*" + KINDS + r"\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")
# the missing class: '#黑柩<kind>' with no colon, content may follow on the same line
HASHKIND = re.compile(r"^\s*#\s*黑柩\s*(剧情花絮|花絮|楔子|画外音|特别环节|四格漫画|玩家之声)\s*#?")

starts = []
for i, l in enumerate(lines):
    at_b = (i == 0) or (not lines[i - 1].strip())
    if not at_b:
        continue
    m = ENTRY.match(l)
    k = None
    if m:
        k = m.group(1)
    else:
        m2 = HASHKIND.match(l)
        if m2:
            k = m2.group(1)
    if k and not LEGEND.search(l):
        starts.append((i, k))

segments = []
for j, (a, k) in enumerate(starts):
    b = starts[j + 1][0] if j + 1 < len(starts) else len(lines)
    segments.append({"start": a, "end": b, "kind": k})

print(f"entries with BOTH rules: {len(segments)}")


def clean_title(raw):
    t = re.sub(r"^#{1,6}\s*", "", raw).strip()
    t = re.sub(r"^\*+", "", t)
    t = re.sub(r"\*+$", "", t).strip()
    t = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", t)
    t = re.sub(r"^\d+[、.．]\s*", "", t)
    t = re.sub(r"^\*+", "", t).strip()
    return t.strip()


BIG = [s for s in segments if sum(len(x) for x in lines[s["start"]:s["end"]]) > 15000]
print(f"entries > 15000 chars: {len(BIG)}\n")

DIV = re.compile(r"^\s*\**——\**\s*$")
index = []

for n, s in enumerate(sorted(BIG, key=lambda x: -sum(len(y) for y in lines[x["start"]:x["end"]])), 1):
    a, b = s["start"], s["end"]
    seg = lines[a:b]
    size = sum(len(x) for x in seg)
    title = clean_title(seg[0])
    # internal boundary candidates
    divs = [a + j + 1 for j, l in enumerate(seg) if DIV.match(l)]
    hashs = [a + j + 1 for j, l in enumerate(seg) if HASHKIND.match(l) and j > 0]
    heads = [a + j + 1 for j, l in enumerate(seg) if re.match(r"^\s*#{1,6}\s", l) and j > 0]

    fname = f"long-{n:02d}-{size}字-{re.sub(r'[\\\\/:*?\"<>|]', '-', title)[:44]}.md"
    with open(os.path.join(REV, fname), "w", encoding="utf-8") as f:
        f.write(f"<!-- 待检查：{size} 字\n")
        f.write(f"     源文件行号：L{a+1} - L{b}\n")
        f.write(f"     文类：{s['kind']}\n")
        f.write(f"     内部 '#黑柩X' 行：{len(hashs)} 处 {hashs[:40]}\n")
        f.write(f"     内部 '——' 分隔行：{len(divs)} 处\n")
        f.write(f"     内部其他标题行：{len(heads)} 处 {heads[:40]}\n")
        f.write(f"     → 若判定应拆，请在此文件里插入 <!-- SPLIT --> 标记行\n-->\n\n")
        f.write("\n".join(seg) + "\n")

    index.append({"n": n, "file": fname, "title": title, "kind": s["kind"],
                  "chars": size, "from": a + 1, "to": b,
                  "hash_markers": len(hashs), "dividers": len(divs),
                  "other_heads": len(heads)})

with open(os.path.join(REV, "_索引.md"), "w", encoding="utf-8") as f:
    f.write("# 超长条目检查单（> 15000 字）\n\n")
    f.write("| # | 字数 | 文类 | 标题 | 内部 `#黑柩X` | 内部 `——` | 其他标题 | 源行 |\n")
    f.write("|---:|---:|---|---|---:|---:|---:|---|\n")
    for r in index:
        f.write(f"| {r['n']} | {r['chars']} | {r['kind']} | {r['title'][:38]} | "
                f"{r['hash_markers']} | {r['dividers']} | {r['other_heads']} | "
                f"L{r['from']}-{r['to']} |\n")
    f.write("\n**怎么用**：逐个打开文件，若认定应拆成多篇，在文中相应位置插入 "
            "`<!-- SPLIT -->` 一行（可多个），然后告诉我；我按标记切分。\n")

# also refresh source/ + entries.json with the two fixed rules
print("=== refreshing source/ and entries.json (both rules applied) ===")
SRC_DIR = os.path.join(WIKI, "source")
DATA = os.path.join(WIKI, "data")
for old in os.listdir(SRC_DIR):
    if old.endswith(".md") and not old.startswith("_"):
        os.remove(os.path.join(SRC_DIR, old))


def slug_of(title, maxlen=40):
    s = re.sub(r"^(剧情花絮|花絮|楔子|画外音|特别环节|四格漫画|玩家之声)\s*[:：]\s*", "", title)
    s = re.sub(r"[\s\u3000]+", "-", s)
    s = re.sub(r"[\\/:*?\"<>|,，。；;！!？?（）()\[\]【】“”\"'‘’—…·]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:maxlen].strip("-") or "untitled"


def clean_body(seg_lines):
    out = []
    for l in seg_lines:
        s = l.strip()
        if not s:
            out.append("")
            continue
        if DIV.match(s):
            out += ["", "---", ""]
            continue
        m = re.match(r"^\*\*([^*：:\n]{1,16})\*\*\s*[:：]\s*(.*)$", s)
        if m:
            out.append(f"**{m.group(1)}**：{m.group(2)}")
            continue
        m2 = re.match(r"^\*\*([^*]+)\*\*\s*$", s)
        if m2:
            out.append(m2.group(1))
            continue
        out.append(re.sub(r"\*\*([^*]+)\*\*", r"\1", s))
    txt = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", txt).strip()


entries = []
for k, s in enumerate(segments):
    a, b = s["start"], s["end"]
    title = clean_title(lines[a])
    body = clean_body(lines[a + 1:b])
    eid = f"hx-{k+1:03d}"
    fname = f"{eid}-{slug_of(title)}.md"
    if len(fname) > 120:
        fname = f"{eid}-{slug_of(title)[:80]}.md"
    open(os.path.join(SRC_DIR, fname), "w", encoding="utf-8").write(
        f"---\nid: {eid}\ntitle: \"{title}\"\nkind: {s['kind']}\n"
        f"source_line: {a+1}\nchars: {len(body)}\n---\n\n{body}\n")
    entries.append({"id": eid, "title": title, "kind": s["kind"], "file": fname,
                    "chars": len(body), "source_line": a + 1,
                    "source_hash": __import__("hashlib").sha1(body.encode()).hexdigest()[:16]})

json.dump({"source": os.path.basename(SRC), "entry_count": len(entries), "entries": entries},
          open(os.path.join(DATA, "entries.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print(f"source/: {len(entries)} files")
from collections import Counter
print("by kind:", Counter(e['kind'] for e in entries).most_common())
sizes = sorted(e["chars"] for e in entries)
print(f"median {sizes[len(sizes)//2]}  >15000: {sum(1 for x in sizes if x > 15000)}")
print("\nwrote review folder:", REV)
