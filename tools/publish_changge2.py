# -*- coding: utf-8 -*-
"""《长歌总集篇二》已发布：合集名去掉「(未发布) 」前缀。

改三处：source/*.md 的 frontmatter、data/entries.json、source/_INDEX.md。
用 tag_entries.py 同款归一化（去掉「(未发布)」后名字不变），所以标签不受影响。
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

W = r"E:\DSHwork\heijiu\wiki"
SRC = os.path.join(W, "source")
ENT = os.path.join(W, "data", "entries.json")
IDX = os.path.join(SRC, "_INDEX.md")
OLD = "(未发布) 长歌总集篇二"
NEW = "长歌总集篇二"

d = json.load(io.open(ENT, encoding="utf-8"))
hits = [e for e in d["entries"] if e.get("collection") == OLD]
print("要改的条目：%d 篇" % len(hits))

n_fm = 0
for e in hits:
    p = os.path.join(SRC, e["file"])
    t = io.open(p, encoding="utf-8").read()
    if ("collection: " + OLD) in t:
        t = t.replace("collection: " + OLD, "collection: " + NEW)
        io.open(p, "w", encoding="utf-8", newline="\n").write(t)
        n_fm += 1
    e["collection"] = NEW
io.open(ENT, "w", encoding="utf-8", newline="\n").write(
    json.dumps(d, ensure_ascii=False, indent=1) + "\n")
print("frontmatter 改 %d 个文件" % n_fm)

t = io.open(IDX, encoding="utf-8").read()
if OLD in t:
    t = t.replace(OLD, NEW)
    io.open(IDX, "w", encoding="utf-8", newline="\n").write(t)
    print("_INDEX.md 已改")
left = [e["id"] for e in d["entries"] if "未发布" in (e.get("collection") or "")]
print("仍带「未发布」的条目：%s" % (left or "无"))
