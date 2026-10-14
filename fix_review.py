"""Correct the boundary scan in the review files: cleaned bodies use '---' for
the original '——' dividers."""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
SRC_DIR = os.path.join(WIKI, "source")
REV = os.path.join(WIKI, "_review_long")

ents = json.load(open(os.path.join(WIKI, "data", "entries.json"), encoding="utf-8"))["entries"]
big = sorted([e for e in ents if e["chars"] > 15000], key=lambda e: -e["chars"])

DIV = re.compile(r"^\s*-{3,}\s*$")          # cleaned divider
HASHKIND = re.compile(r"^\s*#\s*黑柩\s*(剧情花絮|花絮|楔子|画外音|特别环节|四格漫画|玩家之声)\s*#?")
HEAD = re.compile(r"^\s*#{1,6}\s")
DIALOG = re.compile(r"^\*\*[^*]+\*\*：")

print(f"{'#':>2} {'字数':>7} {'分隔':>5} {'标题行':>5} {'表格行':>5} {'对白行':>6}  {'场景数':>5}  标题")
rows = []
for n, e in enumerate(big, 1):
    txt = open(os.path.join(SRC_DIR, e["file"]), encoding="utf-8").read()
    body = txt.split("---\n\n", 1)[1] if "---\n\n" in txt else txt
    L = body.split("\n")
    divs = [i + 1 for i, l in enumerate(L) if DIV.match(l)]
    hashes = [i + 1 for i, l in enumerate(L) if HASHKIND.match(l)]
    heads = [i + 1 for i, l in enumerate(L) if HEAD.match(l)]
    tables = [i + 1 for i, l in enumerate(L) if l.strip().startswith("|")]
    dial = sum(1 for l in L if DIALOG.match(l))
    scenes = len(divs) + 1
    print(f"{n:>2} {e['chars']:>7} {len(divs):>5} {len(heads):>5} {len(tables):>5} "
          f"{dial:>6}  {scenes:>5}  {e['title'][:40]}")
    rows.append({"n": n, "id": e["id"], "title": e["title"], "chars": e["chars"],
                 "divs": divs, "heads": heads, "tables": len(tables),
                 "dial": dial, "scenes": scenes, "file": e["file"]})

with open(os.path.join(REV, "_索引.md"), "w", encoding="utf-8") as f:
    f.write("# 超长条目检查单（>15000 字）\n\n")
    f.write(f"最终切分 **{len(ents)} 篇**，其中超过 1.5 万字的 **{len(big)} 篇**。\n\n")
    f.write("| # | 字数 | 文类 | 场景分隔 | 对白行 | 标题 |\n|---:|---:|---|---:|---:|---|\n")
    for r, e in zip(rows, big):
        f.write(f"| {r['n']} | {r['chars']} | {e['kind']} | {r['scenes']} 段 | "
                f"{r['dial']} | {r['title'][:40]} |\n")
    f.write("\n## 怎么用\n\n")
    f.write("1. 逐个打开 `long-NN-*.md`\n")
    f.write("2. 若要拆：在应断开处**单独一行**插入 `<!-- SPLIT -->`（可多处）\n")
    f.write("3. 若要保留一篇：不动它\n")
    f.write("4. 回我「检查完了」，我按标记切分，未标记的保持原样\n\n")
    f.write("## 各篇的场景分隔位置（行号，便于定位）\n\n")
    for r in rows:
        f.write(f"### {r['n']}. {r['title']}（{r['chars']} 字，{r['scenes']} 段）\n\n")
        f.write(f"- 文件：`{r['file']}`\n")
        f.write(f"- 分隔行号：{r['divs'][:60]}\n")
        if r["heads"]:
            f.write(f"- 其他标题行号：{r['heads'][:20]}\n")
        f.write("\n")

# also rewrite each review file's header with correct counts
for r, e in zip(rows, big):
    safe = re.sub(r'[\\/:*?"<>|]', "-", e["title"])[:46]
    fname = f"long-{r['n']:02d}-{e['chars']}字-{safe}.md"
    p = os.path.join(REV, fname)
    txt = open(os.path.join(SRC_DIR, e["file"]), encoding="utf-8").read()
    body = txt.split("---\n\n", 1)[1] if "---\n\n" in txt else txt
    hdr = ["<!-- ===== 待检查的超长条目 ===== ",
           f"  id         : {e['id']}",
           f"  标题       : {e['title']}",
           f"  文类       : {e['kind']}",
           f"  字数       : {e['chars']}",
           f"  场景段数   : {r['scenes']}",
           f"  对白行数   : {r['dial']}",
           f"  分隔行号   : {r['divs'][:40]}",
           f"  标题行号   : {r['heads'][:20]}",
           "  ----------------------------------------",
           "  若要拆：在分割处插入 <!-- SPLIT --> 单独一行",
           "  若要保留：不用改，回我「保留」即可",
           "======================================= -->", ""]
    open(p, "w", encoding="utf-8").write("\n".join(hdr) + body + "\n")

print("\nwrote", REV)
print("files:")
for f in sorted(os.listdir(REV)):
    print("  ", f, f"{os.path.getsize(os.path.join(REV, f))/1024:.1f} KB")
