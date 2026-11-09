# -*- coding: utf-8 -*-
"""按作者 2026-11-10 的清单，改 18 篇花絮的标题（含 2 篇的文类变化）。

改三处：source/*.md 的 frontmatter（title / kind）、文件名、entries.json（title/kind/file/source_hash）。
正文一个字不动。文类变了的（234、241 花絮→画外音）跑完要重打标——叙事层级会跟着变。

用法：python rename_huaxu.py --dry   /   去掉 --dry 真改
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
DRY = "--dry" in sys.argv

NEW = {
    "hx-212": "花絮：未能诞生的情敌",
    "hx-224": "长歌：蛛眼小队的玉横山之行",
    "hx-225": "花絮：两台强人工智能的寒暄",
    "hx-228": "画外音：笼中鸟的困兽之斗",
    "hx-229": "花絮：川崎罗的规矩",
    "hx-231": "花絮：川崎罗论川式死仇",
    "hx-234": "画外音：如果镜缘毁了西沙",
    "hx-235": "花絮：西娜和叶心的爱恨情仇",
    "hx-237": "花絮：阿拉莎咨询涌哥餐饮",
    "hx-238": "花絮：蛛眼与美之居的少女",
    "hx-241": "画外音：如果西娜和蛛眼论革命",
    "hx-243": "花絮：南塔镇精彩二打一",
    "hx-244": "花絮：南塔镇精彩一挑三",
    "hx-245": "花絮：良玉村扩张计划",
    "hx-246": "花絮：两位当家的天台对谈（一）",
    "hx-247": "花絮：两位当家的天台对谈（二）",
    "hx-248": "花絮：两位当家的天台对谈（三）",
    "hx-249": "花絮：两位当家的天台对谈（四）",
}

KINDS = ("花絮", "楔子", "画外音", "长歌", "四格", "剧情花絮")


def kind_of(title):
    for k in KINDS:
        if title.startswith(k + "：") or title.startswith(k + ":"):
            return k
    return "花絮"


def file_of(eid, title):
    tail = title.split("：", 1)[-1]
    return "%s-%s.md" % (eid, re.sub(r"[^\w\u4e00-\u9fff]+", "-", tail).strip("-"))


ents = json.load(io.open(ENT, encoding="utf-8"))
by_id = {e["id"]: e for e in ents["entries"]}

moves = []
for eid, new_title in NEW.items():
    e = by_id[eid]
    old_file = os.path.join(SRC, e["file"])
    if not os.path.exists(old_file):
        sys.exit("源文件不存在：%s" % old_file)
    raw = io.open(old_file, encoding="utf-8").read()
    new_kind = kind_of(new_title)
    new_file = file_of(eid, new_title)
    dst = os.path.join(SRC, new_file)
    if dst != old_file and os.path.exists(dst):
        sys.exit("目标文件已存在：%s" % dst)
    # 只改 frontmatter 里的两行
    m = re.match(r"^---\n(.*?)\n---\n", raw, re.S)
    if not m:
        sys.exit("frontmatter 解析失败：%s" % old_file)
    fm = m.group(1)
    fm2 = re.sub(r'(?m)^title: ".*"$', 'title: "%s"' % new_title, fm)
    fm2 = re.sub(r"(?m)^kind: .*$", "kind: %s" % new_kind, fm2)
    raw2 = raw[:m.start(1)] + fm2 + raw[m.end(1):]
    moves.append({"id": eid, "old_title": e["title"], "new_title": new_title,
                  "old_kind": e["kind"], "new_kind": new_kind,
                  "old_file": e["file"], "new_file": new_file,
                  "old_path": old_file, "new_path": dst, "text": raw2})

print("%-8s %-26s → %-28s %s" % ("id", "旧标题", "新标题", "文类"))
for m in moves:
    flag = "" if m["old_kind"] == m["new_kind"] else "  ← %s→%s" % (m["old_kind"], m["new_kind"])
    print("%-8s %-26s → %-28s%s" % (m["id"], m["old_title"][:24], m["new_title"], flag))
print("\n共 %d 篇；文类变化 %d 篇"
      % (len(moves), sum(1 for m in moves if m["old_kind"] != m["new_kind"])))
if DRY:
    for m in moves[:3]:
        print("\n--- %s:\n%s" % (m["new_file"], m["text"][:260]))
    sys.exit(0)

for m in moves:
    io.open(m["new_path"], "w", encoding="utf-8", newline="\n").write(m["text"])
    if m["new_path"] != m["old_path"]:
        os.remove(m["old_path"])
    e = by_id[m["id"]]
    e["title"] = m["new_title"]
    e["kind"] = m["new_kind"]
    e["file"] = m["new_file"]
    e["source_hash"] = hashlib.md5(m["text"].encode("utf-8")).hexdigest()[:16]

io.open(ENT, "w", encoding="utf-8", newline="\n").write(
    json.dumps(ents, ensure_ascii=False, indent=1) + "\n")

# _INDEX.md 同步
idx = io.open(IDX, encoding="utf-8").read()
for m in moves:
    idx = re.sub(r"(?m)^\| %s \| (\S+) \| (\S+) \| (\S+) \| (\d+) \| .*\|$"
                 % re.escape(m["id"]),
                 lambda mo, m=m: "| %s | %s | %s | %s | %s | %s |"
                 % (m["id"], m["new_kind"], mo.group(2), mo.group(3),
                    mo.group(4), m["new_title"]),
                 idx)
io.open(IDX, "w", encoding="utf-8", newline="\n").write(idx)

print("已写盘：%d 个 md、entries.json、_INDEX.md" % len(moves))
