#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""玩家名册：活跃表 + 名册 → data/players.json

源（都在仓库外，和跑团/报告的源在一起）：
    E:\\黑柩\\黑柩跑团记录-整理\\黑柩团玩家活跃表-2026.10.md   ← 逐季发言数
    E:\\黑柩\\黑柩跑团记录-整理\\黑柩团玩家名册.md             ← 首末次、主要用名

两份表都是「一人一行」，按 # 号对齐。输出只保留能核对的字段，
不做任何推断（不猜谁演了谁）。
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = r"E:\黑柩\黑柩跑团记录-整理"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "data", "players.json")
ACT = os.path.join(SRC, "黑柩团玩家活跃表-2026.10.md")
ROS = os.path.join(SRC, "黑柩团玩家名册.md")

NUM = re.compile(r"^[\d,]+$")


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def table_rows(path):
    for line in io.open(path, encoding="utf-8").read().split("\n"):
        if not line.startswith("|"):
            continue
        c = cells(line)
        if c and c[0].isdigit():
            yield c


# ── 活跃表：编号 / 玩家 / QQ / 总计 / 实场 / 各季… ──
act = {}
seasons = []
for c in table_rows(ACT):
    if not seasons:
        # 头一次解析到的数字行无法回看表头，单独取一次
        pass
    act[int(c[0])] = c
# 表头（取列名）
for line in io.open(ACT, encoding="utf-8").read().split("\n"):
    if line.startswith("|") and "第一季" in line:
        seasons = cells(line)[5:]
        break

# ── 名册：编号 / 玩家 / QQ / 总计 / 实场 / 首次 / 末次 / 主要用名 ──
ros = {int(c[0]): c for c in table_rows(ROS)}

players = []
for no in sorted(act):
    a = act[no]
    r = ros.get(no, [])
    vals = [x.replace(",", "") for x in a[5:] if NUM.match(x.replace(",", ""))]
    per = {}
    for i, name in enumerate(seasons):
        if i < len(a) - 5:
            v = a[5 + i].replace(",", "")
            if NUM.match(v):
                per[name] = int(v)
    aliases = [x.strip() for x in (r[7] if len(r) > 7 else "").split("／")
               if x.strip()]
    players.append({
        "no": no,
        "name": a[1],
        "qq": "" if a[2] in ("—", "-") else a[2].strip("`"),
        "total": int(a[3].replace(",", "")),
        "scenes": int(a[4].replace(",", "")),
        "first": r[5] if len(r) > 5 else "",
        "last": r[6] if len(r) > 6 else "",
        "aliases": aliases,
        "seasons": per,
    })

data = {"note": "玩家名册：由 tools/parse_players.py 从「玩家活跃表-2026.10」与"
                "「玩家名册」生成。活跃数＝该 QQ（无 QQ 者为该名字）在原始层＋口述层的"
                "发言条数（已去噪声/舞台）。第二、三季记录不全。",
        "count": len(players),
        "seasons": seasons,
        "players": players}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
io.open(OUT, "w", encoding="utf-8", newline="\n").write(
    json.dumps(data, ensure_ascii=False, indent=1) + "\n")
print("写出 %d 人 → %s" % (len(players), OUT))
print("赛季列：%s" % "、".join(seasons))
print("有 QQ 的 %d 人；有主要用名的 %d 人"
      % (sum(1 for p in players if p["qq"]), sum(1 for p in players if p["aliases"])))
