"""Parse the huaxu compilation into per-entry markdown files.

Rules (validated: 144 entries, 100% coverage, no duplicates):
  * entry start = line matching optional '#', optional '**', optional numbering,
    then one of 花絮|楔子|画外音|剧情花絮|特别环节|四格漫画|玩家之声 followed by ':'
  * the previous line must be blank (boundary guard)
  * legend lines (definitions of 花絮/楔子/画外音) are excluded
  * front matter before the first entry is kept separately as _front.md

Output:
  E:\\DSHwork\\heijiu\\wiki\\source\\entry-XXX-<slug>.md
  E:\\DSHwork\\heijiu\\wiki\\source\\_front.md
  E:\\DSHwork\\heijiu\\wiki\\data\\entries.json
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
DATA_DIR = os.path.join(WIKI, "data")
os.makedirs(SRC_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

KINDS = r"(剧情花絮|花絮|楔子|画外音|特别环节|四格漫画|玩家之声)"
ENTRY = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*"
    r"(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?"
    r"(?:\*\*)?\s*" + KINDS + r"\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")

lines = open(SRC, encoding="utf-8", errors="ignore").read().split("\n")
TOT = sum(len(l) for l in lines)

# ---------------------------------------------------------------- 1. split
starts = []
for i, l in enumerate(lines):
    m = ENTRY.match(l)
    if not m:
        continue
    at_b = (i == 0) or (not lines[i - 1].strip())
    if at_b and not LEGEND.search(l):
        starts.append((i, m.group(1)))

segments = []
for k, (a, kind) in enumerate(starts):
    b = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
    segments.append({"start": a, "end": b, "kind": kind})

# front matter
front = lines[:starts[0][0]]
front_txt = "\n".join(front).strip()
if front_txt:
    open(os.path.join(SRC_DIR, "_front.md"), "w", encoding="utf-8").write(
        "# 前言与体例\n\n" + front_txt + "\n")

print(f"segments: {len(segments)}")


# ---------------------------------------------------------------- 2. naming
def clean_title(raw):
    t = re.sub(r"^#{1,6}\s*", "", raw).strip()
    t = re.sub(r"^\*+\s*", "", t)
    t = re.sub(r"\s*\*+$", "", t).strip()
    t = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", t)
    t = re.sub(r"^\d+[、.．]\s*", "", t)
    t = re.sub(r"^\*+\s*", "", t).strip()
    return t.strip()


def slug_of(title, maxlen=40):
    # strip the kind prefix, keep CJK + ascii, replace runs of punctuation
    s = re.sub(r"^(剧情花絮|花絮|楔子|画外音|特别环节|四格漫画|玩家之声)\s*[:：]\s*", "", title)
    s = re.sub(r"[\s\u3000]+", "-", s)
    s = re.sub(r"[\\/:*?\"<>|,，。；;！!？?（）()\[\]【】“”\"'‘’—…·]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:maxlen].strip("-") or "untitled"


# ---------------------------------------------------------------- 3. body cleanup
DIALOG = re.compile(r"^\*\*(?P<who>[^*：:]{1,20})\s*[:：]\*\*\s*(?P<say>.*)$")
BOLD_ONLY = re.compile(r"^\*\*(?P<txt>[^*]+)\*\*\s*$")
RULE = re.compile(r"^\s*(?:\*\*)?——(?:\*\*)?\s*$")


def clean_body(seg_lines):
    """Source is bold-everything; normalise to light markdown."""
    out = []
    for l in seg_lines:
        s = l.strip()
        if not s:
            out.append("")
            continue
        if RULE.match(s):
            out.append("")
            out.append("---")
            out.append("")
            continue
        m = DIALOG.match(s)
        if m:
            out.append(f"**{m.group('who')}**：{m.group('say')}")
            continue
        m = BOLD_ONLY.match(s)
        if m:
            out.append(m.group("txt"))
            continue
        # mixed bold: unwrap **…** inside a line
        out.append(re.sub(r"\*\*([^*]+)\*\*", r"\1", s))
    # collapse 3+ blank lines
    txt = "\n".join(out)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


# ---------------------------------------------------------------- 4. write entries
entries = []
kind_count = Counter()
for k, seg in enumerate(segments):
    raw_title_line = lines[seg["start"]]
    title = clean_title(raw_title_line)
    body_lines = lines[seg["start"] + 1: seg["end"]]
    body = clean_body(body_lines)
    kind = seg["kind"]
    kind_count[kind] += 1

    eid = f"hx-{k + 1:03d}"
    slug = slug_of(title)
    fname = f"{eid}-{slug}.md"
    # guard against absurdly long filenames on Windows
    if len(fname) > 120:
        fname = f"{eid}-{slug[:80]}.md"

    header = (f"---\n"
              f"id: {eid}\n"
              f"title: \"{title}\"\n"
              f"kind: {kind}\n"
              f"source_line: {seg['start'] + 1}\n"
              f"chars: {len(body)}\n"
              f"---\n\n")
    open(os.path.join(SRC_DIR, fname), "w", encoding="utf-8").write(header + body + "\n")

    entries.append({
        "id": eid,
        "title": title,
        "kind": kind,
        "file": fname,
        "chars": len(body),
        "source_line": seg["start"] + 1,
        "source_hash": hashlib.sha1(body.encode("utf-8")).hexdigest()[:16],
    })

# ---------------------------------------------------------------- 5. data files
with open(os.path.join(DATA_DIR, "entries.json"), "w", encoding="utf-8") as f:
    json.dump({"source": os.path.basename(SRC),
               "source_chars": TOT,
               "entry_count": len(entries),
               "entries": entries}, f, ensure_ascii=False, indent=1)

sizes = sorted(e["chars"] for e in entries)
n = len(sizes)
print(f"written {len(entries)} entries to {SRC_DIR}")
print("by kind:", dict(kind_count))
print(f"chars covered: {sum(e['chars'] for e in entries)} / {TOT}")
print(f"median {sizes[n // 2]}  max {sizes[-1]}  min {sizes[0]}")
print(f">20000: {sum(1 for e in entries if e['chars'] > 20000)}")
print("\nsample filenames:")
for e in entries[:5]:
    print("  ", e["file"])
print("  ...")
for e in entries[-3:]:
    print("  ", e["file"])
