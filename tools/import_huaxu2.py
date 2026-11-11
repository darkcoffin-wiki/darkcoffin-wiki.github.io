# -*- coding: utf-8 -*-
"""把 hx-250 / hx-251 两篇楔子写进 wiki（source + entries.json + _INDEX.md）。

文本来自 `_xx\\花絮时间\\楔子-*.txt`：头部三行是元信息，`-----` 之后才是正文。
用法：python import_huaxu2.py [--dry]
"""
import hashlib
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

W = r"E:\DSHwork\heijiu\wiki"
SRC = os.path.join(W, "source")
ENT = os.path.join(W, "data", "entries.json")
IDX = os.path.join(SRC, "_INDEX.md")
D = r"E:\DSHwork\heijiu\_xx\花絮时间"
DRY = "--dry" in sys.argv

JOBS = [
    ("hx-250", "楔子-白夜瞳的疾速追杀.txt"),
    ("hx-251", "楔子-齐藤的奥德赛时期.txt"),
]
COLLECTION = "未收录补录"
ORIGIN = "群聊"


def parse(path):
    lines = io.open(path, encoding="utf-8").read().split("\n")
    title = lines[0].strip()
    m = None
    for ln in lines[:4]:
        if ln.startswith("编号"):
            m = re.search(r"(hx-\d{3}).*?发布[：:]\s*(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)", ln)
    if not m:
        raise SystemExit("头部解析失败：%s" % path)
    eid, when = m.group(1), m.group(2).replace("T", " ")
    if len(when) == 16:
        when += ":00"
    cut = next(i for i, ln in enumerate(lines) if ln.startswith("-----"))
    body = [ln.rstrip() for ln in lines[cut + 1:]]
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    return {"id": eid, "title": title, "date": when,
            "kind": title.split("：", 1)[0], "body": "\n".join(body)}


def slug_file(title):
    return re.sub(r"[^\w\u4e00-\u9fff]+", "-", title.split("：", 1)[-1]).strip("-")


ents = json.load(io.open(ENT, encoding="utf-8"))
have = {e["id"] for e in ents["entries"]}
new = []
for eid, fn in JOBS:
    r = parse(os.path.join(D, fn))
    if r["id"] != eid:
        raise SystemExit("编号不符：%s ≠ %s" % (r["id"], eid))
    if eid in have:
        raise SystemExit("entries.json 里已有 %s" % eid)
    fname = "%s-%s.md" % (eid, slug_file(r["title"]))
    text = ("---\nid: %s\ntitle: \"%s\"\nkind: %s\ncollection: %s\n"
            "origin: %s\nchars: %d\ndate: %s\n---\n\n%s\n"
            % (eid, r["title"], r["kind"], COLLECTION, ORIGIN,
               len(r["body"]), r["date"], r["body"]))
    new.append((r, fname, text))
    print("%s ｜ %s ｜ %s ｜ %d 字 ｜ %s"
          % (eid, r["title"], r["date"], len(r["body"]), fname))

if DRY:
    print("\n--- 预览 %s ---" % new[0][1])
    print(new[0][2][:420])
    sys.exit(0)

for r, fname, text in new:
    p = os.path.join(SRC, fname)
    if os.path.exists(p):
        raise SystemExit("已存在：" + p)
    io.open(p, "w", encoding="utf-8", newline="\n").write(text)
    ents["entries"].append({
        "id": r["id"], "title": r["title"], "kind": r["kind"],
        "collection": COLLECTION, "origin": ORIGIN, "file": fname,
        "chars": len(r["body"]), "date": r["date"],
        "date_level": "A",
        "source_hash": hashlib.md5(text.encode("utf-8")).hexdigest()[:16]})
ents["entry_count"] = len(ents["entries"])
ents["entries"].sort(key=lambda e: e["id"])
io.open(ENT, "w", encoding="utf-8", newline="\n").write(
    json.dumps(ents, ensure_ascii=False, indent=1) + "\n")

idx = io.open(IDX, encoding="utf-8").read().rstrip("\n").split("\n")
for r, fname, text in new:
    idx.append("| %s | %s | %s | %s | %d | %s |"
               % (r["id"], r["kind"], COLLECTION, ORIGIN, len(r["body"]), r["title"]))
io.open(IDX, "w", encoding="utf-8", newline="\n").write("\n".join(idx) + "\n")
print("\n已写 %d 篇；entries.json 现 %d 条" % (len(new), ents["entry_count"]))
