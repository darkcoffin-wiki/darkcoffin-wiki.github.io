#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""紧凑表：旧词表覆盖度 + n-gram 候选，方便人工/模型快速筛选。"""
import glob
import json
import os
import re

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(W, "source")
DATA = os.path.join(W, "data")


def body_of(t):
    if t.startswith("---"):
        e = t.find("\n---", 3)
        if e != -1:
            return t[e + 4:]
    return t


entries = []
for f in sorted(glob.glob(os.path.join(SRC, "hx-*.md"))):
    entries.append(body_of(open(f, encoding="utf-8").read()))

old = json.load(open(os.path.join(DATA, "vocabulary.json"), encoding="utf-8"))
cand = json.load(open(os.path.join(DATA, "entity_candidates.json"), encoding="utf-8"))


def cover(tag):
    return sum(1 for t in entries if tag in t)


def line(tags, path, title, limit=None):
    rows = sorted(((cover(t), t) for t in dict.fromkeys(tags)), key=lambda r: (-r[0], r[1]))
    if limit:
        rows = rows[:limit]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# %s（%d 条，格式：名:篇数）\n\n" % (title, len(rows)))
        fh.write("　".join("%s:%d" % (t, c) for c, t in rows))
    return len(rows)


old_tags = [p["tag"] for p in old["people"]]
n1 = line(old_tags, os.path.join(DATA, "tab_old_people.txt"), "旧词表 289 名 · 新语料覆盖篇数")
ng_people = [r["tag"] for r in cand["people_candidates"]
             if r["count"] >= 8 and r["entropy"] >= 1.3 and len(r["tag"]) <= 5]
n2 = line(ng_people, os.path.join(DATA, "tab_ng_people.txt"), "n-gram 人名候选 · 覆盖篇数", 420)
ng_orgs = [r["tag"] for r in cand["proper_candidates"]
           if r["count"] >= 12 and r["entropy"] >= 2.4]
n3 = line(ng_orgs, os.path.join(DATA, "tab_ng_orgs.txt"), "n-gram 专名候选 · 覆盖篇数", 500)
print(json.dumps({"old": n1, "ng_people": n2, "ng_orgs": n3}, ensure_ascii=False))
