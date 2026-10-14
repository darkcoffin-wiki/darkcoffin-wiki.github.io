#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出「n-gram 候选 但 不在旧词表」的疑似人名，供补漏。"""
import json
import os

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(W, "data")
old = json.load(open(os.path.join(DATA, "vocabulary.json"), encoding="utf-8"))
rows = open(os.path.join(DATA, "tab_ng_people.txt"), encoding="utf-8").read() \
    .splitlines()[2].replace("\u3000", " ").split()
oldset = {p["tag"] for p in old["people"]}
pairs = []
for tok in rows:
    if ":" not in tok:
        continue
    name, n = tok.rsplit(":", 1)
    if name not in oldset:
        pairs.append((int(n), name))
pairs.sort(key=lambda r: (-r[0], r[1]))
with open(os.path.join(DATA, "tab_new_people.txt"), "w", encoding="utf-8") as fh:
    fh.write("# 不在旧词表的 n-gram 人名候选（%d 条，格式：名:篇数）\n\n" % len(pairs))
    fh.write("　".join("%s:%d" % (n, c) for c, n in pairs))
print("new candidates:", len(pairs))
