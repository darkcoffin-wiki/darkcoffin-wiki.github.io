#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为四个短团生成「输入包」→ trpg-src/_raw/输入包/<短团>.md

对应主季当年的「输入包\包XX-N·季·第X~Y场.txt」这一层：
把净版正文按「第 N 场」切好，并**显式标注年份与起止时间**（当年提示词特别警告过不许瞎猜年份）。

输入
----
    E:\\黑柩\\黑柩跑团记录-整理\\净版\\A-剧情主干\\短团·*.txt
    E:\\黑柩\\黑柩跑团记录-整理\\净版\\A-剧情主干\\重置版·星都陨落.txt
    E:\\黑柩\\黑柩跑团记录-整理\\净版\\骰点记录\\同名文件

输出
----
    trpg-src/_raw/输入包/<短团名>.md   —— 每场含：正文 + 该场骰点记录

用法：python tools/prep_short.py
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = r"E:\黑柩\黑柩跑团记录-整理\净版"
OUT = os.path.join(W, "trpg-src", "_raw", "输入包")

# 短团定义：输出名 → (A-剧情主干文件名, 骰点文件名, 现实时间范围, 年份, 一句说明)
SHORTS = [
    dict(name="重置版·星都陨落", a="重置版·星都陨落.txt", dice="重置版·星都陨落.txt",
         span="2023-04-19 ~ 2023-05-07", year=2023,
         note="重置版；与主线第二季同名不同团"),
    dict(name="西沙", a="短团·勇者小队与炮灰小队.txt", dice="短团·勇者小队与炮灰小队.txt",
         span="2026-04-24 ~ 2026-05-05", year=2026,
         note="短团「勇者小队与炮灰小队」，西沙事件"),
    dict(name="食龙则肥", a="短团·食龙则肥.txt", dice="短团·食龙则肥.txt",
         span="2026-08-04 ~ 2026-08-19", year=2026,
         note="北沙散居区锅底"),
    dict(name="竖棺", a="短团·竖棺.txt", dice="短团·竖棺.txt",
         span="2026-08-21 ~ 2026-09-01", year=2026,
         note="富贵集团主场；另有战报 docx 可作脚手架"),
]

SESS = re.compile(r"^第\s*(\d+)\s*场\s*[｜|]")


def split_sessions(text):
    """按「第 N 场 ｜ 源：…」切分 → [(场号, 正文行列表)]"""
    out, cur, buf = [], None, []
    for line in text.split("\n"):
        m = SESS.match(line)
        if m:
            if cur is not None:
                out.append((cur, buf))
            cur, buf = int(m.group(1)), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out.append((cur, buf))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    summary = []
    for s in SHORTS:
        apath = os.path.join(BASE, "A-剧情主干", s["a"])
        dpath = os.path.join(BASE, "骰点记录", s["dice"])
        if not os.path.exists(apath):
            print("!! 缺正文：%s" % apath)
            continue
        body = io.open(apath, encoding="utf-8").read()
        dice = io.open(dpath, encoding="utf-8").read() if os.path.exists(dpath) else ""
        sess = split_sessions(body)
        dice_sess = dict(split_sessions(dice)) if dice else {}

        L = ["# 输入包 ｜ 短团·%s ｜ 共 %d 场" % (s["name"], len(sess)),
             "",
             "★本短团现实时间：%s（**年份已确认，不要自行假定**）" % s["span"],
             "★说明：%s" % s["note"],
             "★本团为**短团**，与 12 个主季分开归类。",
             "",
             "───── 旁白体例 ─────",
             "  `[月-日 时:分] 发言人：正文`；正文里 `【名字：台词】` 的 `名字` 是 NPC。",
             "  KP 账号昵称含「海燕与雷电」「空调」。",
             "",
             "══════════════════════════════════════════════════════════════════"]
        for no, buf in sess:
            lines = [x.rstrip() for x in buf]
            while lines and not lines[0].strip():
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()
            L += ["第 %d 场 ｜ 源：%s" % (no, s["a"]),
                  "══════════════════════════════════════════════════════════════════"]
            L += lines
            dl = dice_sess.get(no)
            if dl:
                dl = [x.rstrip() for x in dl if x.strip()]
                L += ["", "───── 第 %d 场 · 骰点记录（%d 行）─────" % (no, len(dl))]
                L += dl
            else:
                L += ["", "───── 第 %d 场 · 骰点记录（无）─────" % no]
            L += [""]
        out = os.path.join(OUT, "%s.md" % s["name"])
        io.open(out, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
        hanzi = len(re.findall(r"[\u4e00-\u9fff]", "\n".join(L)))
        summary.append((s["name"], len(sess), hanzi, os.path.getsize(out)))
        print("  %-16s %2d 场 ｜ %s 汉字 ｜ %.0f KB"
              % (s["name"], len(sess), format(hanzi, ","), os.path.getsize(out) / 1024))
    print()
    print("合计 %d 场 ｜ %s 汉字" % (sum(x[1] for x in summary),
                                 format(sum(x[2] for x in summary), ",")))
    print("输出目录：%s" % OUT)


if __name__ == "__main__":
    main()
