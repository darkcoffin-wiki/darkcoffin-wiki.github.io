# -*- coding: utf-8 -*-
"""两件事：
1) hx-222 换稿：旧《精英区的幽蓝火焰》是 hx-145 的重复，换成《花絮：普通而平凡的一生》
   （作者 2026-11-11 指定，创作时间 2026-09-27）。id 不变，只换标题/正文/日期。
2) 新增 hx-252《楔子：齐藤不死我们都得死》（创作时间 2026-08-14 23:26:41）。

用法：python fix222_add252.py [--dry]
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
ATT = (r"C:\Users\fly12138\.dsh\attachments\v1\files\60"
       r"\60aa91a0d2a6acf38023f23f4f9ea026455ce24eb3b6685b62e7bf5a7b294a60"
       r"\花絮：普通而平凡的一生.txt")
T252 = r"E:\DSHwork\heijiu\_xx\花絮时间\楔子-齐藤不死我们都得死.txt"
DRY = "--dry" in sys.argv

COLLECTION = "未收录补录"
ORIGIN = "群聊"


def slug_file(title):
    return re.sub(r"[^\w\u4e00-\u9fff]+", "-", title.split("：", 1)[-1]).strip("-")


def kind_of(title):
    return title.split("：", 1)[0]


# ── 1. hx-222 新正文（原始群帖：第一行是 #黑柩 花絮# 标签，去掉）──
raw = io.open(ATT, encoding="utf-8-sig").read().replace("\r\n", "\n")
lines = raw.split("\n")
assert lines[0].strip() == "#黑柩 花絮#", "首行不是预期的帖子标签：%r" % lines[0]
body222 = [ln.rstrip() for ln in lines[1:]]
while body222 and not body222[0].strip():
    body222.pop(0)
while body222 and not body222[-1].strip():
    body222.pop()
body222 = "\n".join(body222)
T222 = "花絮：普通而平凡的一生"
DATE222 = "2026-09-27 00:00:00"

# ── 2. hx-252（标准 txt 头：标题 / 编号 / 原标签 / 正文 N 字 / ----- / 正文）──
l252 = io.open(T252, encoding="utf-8").read().replace("\r\n", "\n").split("\n")
title252 = l252[0].strip()
m = re.search(r"(hx-\d{3}).*?发布[：:]\s*(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})", l252[1])
assert m, "252 头部解析失败"
id252, date252 = m.group(1), m.group(2).replace("T", " ")
cut = next(i for i, ln in enumerate(l252) if ln.startswith("-----"))
b252 = [ln.rstrip() for ln in l252[cut + 1:]]
while b252 and not b252[0].strip():
    b252.pop(0)
while b252 and not b252[-1].strip():
    b252.pop()
body252 = "\n".join(b252)

print("hx-222 新稿《%s》%d 字 ｜ date %s" % (T222, len(body222), DATE222))
print("hx-252《%s》%d 字 ｜ date %s（txt 标称 3642 字）"
      % (title252, len(body252), date252))

ents = json.load(io.open(ENT, encoding="utf-8"))
by_id = {e["id"]: e for e in ents["entries"]}
old222 = by_id["hx-222"]
print("\nhx-222 旧稿：《%s》%d 字 ｜ 文件 %s"
      % (old222["title"], old222["chars"], old222["file"]))

if id252 in by_id:
    sys.exit("entries.json 里已有 %s" % id252)

if DRY:
    print("\n--- hx-222 新正文前 300 字 ---")
    print(body222[:300])
    sys.exit(0)

# ── 写 hx-222 ──
newfile222 = "%s-%s.md" % ("hx-222", slug_file(T222))
text222 = ("---\nid: hx-222\ntitle: \"%s\"\nkind: %s\ncollection: %s\n"
           "origin: %s\nchars: %d\ndate: %s\ndate_level: A\n---\n\n%s\n"
           % (T222, kind_of(T222), old222["collection"], old222["origin"],
              len(body222), DATE222, body222))
io.open(os.path.join(SRC, newfile222), "w", encoding="utf-8", newline="\n").write(text222)
old_path = os.path.join(SRC, old222["file"])
if os.path.exists(old_path) and old_path != os.path.join(SRC, newfile222):
    os.remove(old_path)
old222.update({"title": T222, "kind": kind_of(T222), "file": newfile222,
               "chars": len(body222), "date": DATE222, "date_level": "A",
               "date_note": "作者 2026-11-11 指定；旧稿《精英区的幽蓝火焰》与 hx-145 重复，撤下",
               "source_hash": hashlib.md5(text222.encode("utf-8")).hexdigest()[:16]})
old222.pop("date_end", None)

# ── 写 hx-252 ──
newfile252 = "%s-%s.md" % (id252, slug_file(title252))
text252 = ("---\nid: %s\ntitle: \"%s\"\nkind: %s\ncollection: %s\n"
           "origin: %s\nchars: %d\ndate: %s\ndate_level: A\n---\n\n%s\n"
           % (id252, title252, kind_of(title252), COLLECTION, ORIGIN,
              len(body252), date252, body252))
io.open(os.path.join(SRC, newfile252), "w", encoding="utf-8", newline="\n").write(text252)
ents["entries"].append({
    "id": id252, "title": title252, "kind": kind_of(title252),
    "collection": COLLECTION, "origin": ORIGIN, "file": newfile252,
    "chars": len(body252), "date": date252, "date_level": "A",
    "source_hash": hashlib.md5(text252.encode("utf-8")).hexdigest()[:16]})

ents["entry_count"] = len(ents["entries"])
ents["entries"].sort(key=lambda e: e["id"])
io.open(ENT, "w", encoding="utf-8", newline="\n").write(
    json.dumps(ents, ensure_ascii=False, indent=1) + "\n")

# ── _INDEX.md：改 hx-222 行、追加 hx-252 ──
idx = io.open(IDX, encoding="utf-8").read().rstrip("\n").split("\n")
for i, ln in enumerate(idx):
    if ln.startswith("| hx-222 |"):
        idx[i] = "| hx-222 | %s | %s | %s | %d | %s |" % (
            kind_of(T222), old222["collection"], old222["origin"], len(body222), T222)
idx.append("| %s | %s | %s | %s | %d | %s |"
           % (id252, kind_of(title252), COLLECTION, ORIGIN, len(body252), title252))
io.open(IDX, "w", encoding="utf-8", newline="\n").write("\n".join(idx) + "\n")
print("\n已写：hx-222 换稿（%s）、新增 %s；entries.json 现 %d 条"
      % (newfile222, newfile252, ents["entry_count"]))
