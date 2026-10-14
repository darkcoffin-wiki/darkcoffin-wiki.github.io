"""Rebuild the long-entry review folder from the FINAL parse (entries.json)."""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
SRC_DIR = os.path.join(WIKI, "source")
REV = os.path.join(WIKI, "_review_long")
THRESH = 15000

# clear and rebuild
for f in os.listdir(REV):
    if f.endswith(".md"):
        os.remove(os.path.join(REV, f))

ents = json.load(open(os.path.join(WIKI, "data", "entries.json"), encoding="utf-8"))["entries"]
big = [e for e in ents if e["chars"] > THRESH]
big.sort(key=lambda e: -e["chars"])
print(f"final entries: {len(ents)}")
print(f"entries > {THRESH}: {len(big)}\n")

DIV = re.compile(r"^\s*\**——\**\s*$")
HASHKIND = re.compile(r"^\s*#\s*黑柩\s*(剧情花絮|花絮|楔子|画外音|特别环节|四格漫画|玩家之声)\s*#?")

index = []
for n, e in enumerate(big, 1):
    txt = open(os.path.join(SRC_DIR, e["file"]), encoding="utf-8").read()
    body = txt.split("---\n\n", 1)[1] if "---\n\n" in txt else txt
    body_lines = body.split("\n")
    divs = [i + 1 for i, l in enumerate(body_lines) if DIV.match(l)]
    hashes = [i + 1 for i, l in enumerate(body_lines) if HASHKIND.match(l)]
    heads = [i + 1 for i, l in enumerate(body_lines) if re.match(r"^#{1,6}\s", l)]
    tables = [i + 1 for i, l in enumerate(body_lines) if l.strip().startswith("|")]

    safe = re.sub(r'[\\/:*?"<>|]', "-", e["title"])[:46]
    fname = f"long-{n:02d}-{e['chars']}字-{safe}.md"
    with open(os.path.join(REV, fname), "w", encoding="utf-8") as f:
        f.write("<!-- ===== 待检查的超长条目 =====\n")
        f.write(f"  id            : {e['id']}\n")
        f.write(f"  标题          : {e['title']}\n")
        f.write(f"  文类          : {e['kind']}\n")
        f.write(f"  字数          : {e['chars']}\n")
        f.write(f"  源文件行号    : L{e['source_line']}\n")
        f.write(f"  内部 '#黑柩X' : {len(hashes)} 处  {hashes[:30]}\n")
        f.write(f"  内部 '——' 行  : {len(divs)} 处  {divs[:30]}\n")
        f.write(f"  内部标题行    : {len(heads)} 处  {heads[:30]}\n")
        f.write(f"  内部表格行    : {len(tables)} 处\n")
        f.write("  ----------------------------------------\n")
        f.write("  若认定应拆成多篇：在分割处插入 <!-- SPLIT --> 单独一行\n")
        f.write("  若认定保持单篇：不用改，告诉我「保留」即可\n")
        f.write("======================================= -->\n\n")
        f.write(body + "\n")

    index.append({"n": n, "file": fname, "id": e["id"], "title": e["title"],
                  "kind": e["kind"], "chars": e["chars"],
                  "hash": len(hashes), "div": len(divs), "heads": len(heads)})

with open(os.path.join(REV, "_索引.md"), "w", encoding="utf-8") as f:
    f.write(f"# 超长条目检查单（>{THRESH} 字）\n\n")
    f.write(f"最终切分共 **{len(ents)} 篇**；其中超过 {THRESH} 字的 **{len(big)} 篇**。\n\n")
    f.write("| # | 字数 | 文类 | 标题 | 内部`#黑柩X` | 内部`——` | 内部标题 |\n")
    f.write("|---:|---:|---|---|---:|---:|---:|\n")
    for r in index:
        f.write(f"| {r['n']} | {r['chars']} | {r['kind']} | {r['title'][:40]} | "
                f"{r['hash']} | {r['div']} | {r['heads']} |\n")
    f.write("\n## 怎么用\n\n")
    f.write("1. 逐个打开 `long-NN-*.md`\n")
    f.write("2. 若认为该拆：在文中应断开的位置**单独一行**插入 `<!-- SPLIT -->`（可多处）\n")
    f.write("3. 若认为保持一篇：不动它\n")
    f.write("4. 告诉我「检查完了」，我按标记切分，未标记的保持原样\n")

print("| # | 字数 | 文类 | 标题 | #黑柩X | —— | 标题行 |")
for r in index:
    print(f"| {r['n']} | {r['chars']} | {r['kind']} | {r['title'][:34]} | "
          f"{r['hash']} | {r['div']} | {r['heads']} |")
print("\nwrote", REV)
