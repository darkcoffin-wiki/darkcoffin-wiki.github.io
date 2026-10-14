"""Regenerate review folder from v3 parse + verify total coverage."""
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
REV = os.path.join(WIKI, "_review_long")
THRESH = 15000

for f in os.listdir(REV):
    if f.endswith(".md"):
        os.remove(os.path.join(REV, f))

ents = json.load(open(os.path.join(WIKI, "data", "entries.json"), encoding="utf-8"))["entries"]

# ---- coverage check: sum of entry chars vs source ----
raw = open(SRC, encoding="utf-8", errors="ignore").read()
tot_src = len(raw)
tot_ent = sum(e["chars"] for e in ents)
print(f"source chars : {tot_src}")
print(f"entries chars: {tot_ent}  ({tot_ent/tot_src*100:.1f}%)")
print(f"entries      : {len(ents)}")
print("kinds        :", Counter(e['kind'] for e in ents).most_common())

DIV = re.compile(r"^\s*-{3,}\s*$")
DIALOG = re.compile(r"^\*\*[^*]+\*\*：")

big = sorted([e for e in ents if e["chars"] > THRESH], key=lambda e: -e["chars"])
print(f"\nentries > {THRESH}: {len(big)}")

rows = []
for n, e in enumerate(big, 1):
    txt = open(os.path.join(SRC_DIR, e["file"]), encoding="utf-8").read()
    body = txt.split("---\n\n", 1)[1] if "---\n\n" in txt else txt
    L = body.split("\n")
    divs = [i + 1 for i, l in enumerate(L) if DIV.match(l)]
    dial = sum(1 for l in L if DIALOG.match(l))
    heads = [i + 1 for i, l in enumerate(L) if re.match(r"^#{1,6}\s", l)]
    safe = re.sub(r'[\\/:*?"<>|]', "-", e["title"])[:44]
    fname = f"long-{n:02d}-{e['chars']}字-{safe}.md"
    hdr = ["<!-- ===== 待检查的超长条目 ===== ",
           f"  id        : {e['id']}",
           f"  标题      : {e['title']}",
           f"  文类      : {e['kind']}",
           f"  字数      : {e['chars']}",
           f"  场景段数  : {len(divs)+1}",
           f"  对白行    : {dial}",
           f"  分隔行号  : {divs[:40]}",
           f"  标题行号  : {heads[:20]}",
           "  ----------------------------------------",
           "  要拆：在断开处插入 <!-- SPLIT --> 单独一行（可多处）",
           "  保留：不用改，回我「保留」",
           "======================================= -->", ""]
    open(os.path.join(REV, fname), "w", encoding="utf-8").write("\n".join(hdr) + body + "\n")
    rows.append({"n": n, "e": e, "scenes": len(divs) + 1, "dial": dial, "file": fname})

with open(os.path.join(REV, "_索引.md"), "w", encoding="utf-8") as f:
    f.write("# 超长条目检查单（>15000 字）\n\n")
    f.write(f"最终切分：**{len(ents)} 篇**，超过 1.5 万字的 **{len(big)} 篇**。\n\n")
    f.write("| # | 字数 | 文类 | 场景段 | 对白行 | 标题 |\n|---:|---:|---|---:|---:|---|\n")
    for r in rows:
        f.write(f"| {r['n']} | {r['e']['chars']} | {r['e']['kind']} | {r['scenes']} | "
                f"{r['dial']} | {r['e']['title'][:40]} |\n")
    f.write("\n## 怎么用\n\n")
    f.write("1. 逐个打开 `long-NN-*.md`\n")
    f.write("2. 该拆的：在断开处**单独一行**插入 `<!-- SPLIT -->`\n")
    f.write("3. 保留的：不动\n")
    f.write("4. 回我「检查完了」\n")

print("\n| # | 字数 | 文类 | 场景段 | 对白行 | 标题 |")
for r in rows:
    print(f"| {r['n']} | {r['e']['chars']} | {r['e']['kind']} | {r['scenes']} | "
          f"{r['dial']} | {r['e']['title'][:38]} |")

print("\n无题条目（需你命名）:")
for e in ents:
    if "（无题）" in e["title"]:
        print(f"  {e['id']}  {e['chars']:>6} 字  {e['title']}")

print("\nreview files:")
for f in sorted(os.listdir(REV)):
    print(f"  {f}  ({os.path.getsize(os.path.join(REV, f))/1024:.1f} KB)")
