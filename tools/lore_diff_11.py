#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1.0 vs 1.1 结构比对（**移动感知**）。

只看三件事：
  A. 卷的变化（改名 / 拆分 / 消失）
  B. 节的变化（新增 / 删除 / 改名）
  C. 词条的变化（真正的新增 / 删除，以及跨节跨卷的移动）

usage: python tools/lore_diff_11.py
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import parse_lore as PL  # noqa: E402

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D10 = r"E:\黑柩\黑柩小说花絮\黑柩设定集·第一版·DSH版.docx"
D11 = r"E:\黑柩\黑柩小说花絮\黑柩设定集·1.1版·DSH版.docx"


def outline(path):
    smap = PL.style_map(path)
    paras = PL.docx_paragraphs(path, smap)
    vols = []
    for p in paras:
        lv, txt = p["level"], p["text"]
        if not txt:
            continue
        if lv == 1:
            vols.append({"title": txt, "sections": []})
        elif lv == 2 and vols:
            vols[-1]["sections"].append({"title": txt, "entries": []})
        elif lv == 3 and vols and vols[-1]["sections"]:
            vols[-1]["sections"][-1]["entries"].append(txt)
    return vols


def flat(vs):
    """→ {(卷, 节): [词条]}、{词条: (卷,节)}、{卷: [节]}"""
    sec, loc, volsec = {}, {}, {}
    for v in vs:
        volsec.setdefault(v["title"], [])
        for s in v["sections"]:
            sec[(v["title"], s["title"])] = s["entries"]
            volsec[v["title"]].append(s["title"])
            for e in s["entries"]:
                loc.setdefault(e, []).append((v["title"], s["title"]))
    return sec, loc, volsec


def main():
    o10, o11 = outline(D10), outline(D11)
    s10, l10, v10 = flat(o10)
    s11, l11, v11 = flat(o11)

    L = ["# 设定集 1.0 → 1.1 结构差异（移动感知）", "",
         "| 项 | 1.0 | 1.1 |", "|---|---:|---:|",
         "| 卷 | %d | %d |" % (len(v10), len(v11)),
         "| 节 | %d | %d |" % (sum(len(x) for x in v10.values()),
                              sum(len(x) for x in v11.values())),
         "| 词条（去重） | %d | %d |" % (len(l10), len(l11)),
         ""]
    print(L[3]); print(L[4]); print(L[5])
    print()

    # ── A. 卷 ──
    print("=== A. 卷 ===")
    only10, only11 = [v for v in v10 if v not in v11], [v for v in v11 if v not in v10]
    print("  1.0 有 / 1.1 无:", only10 or "无")
    print("  1.1 有 / 1.0 无:", only11 or "无")
    L += ["## A. 卷", "",
          "- 1.0 有而 1.1 无：%s" % ("、".join(only10) or "无"),
          "- 1.1 有而 1.0 无：%s" % ("、".join(only11) or "无"), ""]

    # ── B. 节 ──
    print()
    print("=== B. 节 ===")
    L += ["## B. 节", "", "| 卷 | 1.0 | 1.1 | 删节 | 增节 |", "|---|---:|---:|---|---|"]
    for v in v11:
        a, b = set(v10.get(v, [])), set(v11[v])
        rm, add = sorted(a - b), sorted(b - a)
        if rm or add or len(a) != len(b):
            print("  %-22s 1.0 %d 节 → 1.1 %d 节 ｜ 删 %s ｜ 增 %s"
                  % (v[:22], len(a), len(b), rm or "—", add or "—"))
        L.append("| %s | %d | %d | %s | %s |"
                 % (v, len(a), len(b), "、".join(rm) or "—", "、".join(add) or "—"))
    L.append("")

    # ── C. 词条 ──
    print()
    print("=== C. 词条 ===")
    gone = sorted(set(l10) - set(l11))
    fresh = sorted(set(l11) - set(l10))
    moved = []
    for e in set(l10) & set(l11):
        # 多处的取集合比
        if set(l10[e]) != set(l11[e]):
            moved.append((e, l10[e], l11[e]))
    print("  真删除（1.1 完全没有）: %d 条" % len(gone))
    for e in gone:
        print("     - %s   （原在 %s）" % (e[:46], l10[e][0][1][:18]))
    print("  真新增（1.0 完全没有）: %d 条" % len(fresh))
    for e in fresh[:10]:
        print("     + %s   （现于 %s）" % (e[:46], l11[e][0][1][:18]))
    print("  跨节/跨卷移动: %d 条" % len(moved))
    from collections import Counter
    c = Counter()
    for e, a, b in moved:
        c[(a[0][1], b[0][1])] += 1
    for (fa, tb), n in c.most_common(20):
        print("     %-24s → %-24s %d 条" % (fa[:24], tb[:24], n))

    L += ["## C. 词条", "",
          "### 真删除（1.1 完全没有）%d 条" % len(gone), ""]
    L += ["- `%s`（原在 %s）" % (e, l10[e][0][1]) for e in gone]
    L += ["", "### 真新增（1.0 完全没有）%d 条" % len(fresh), ""]
    L += ["- `%s`（现于 %s）" % (e, l11[e][0][1]) for e in fresh]
    L += ["", "### 跨节/跨卷移动 %d 条" % len(moved), "",
          "| 从 | 到 | 条数 |", "|---|---|---:|"]
    for (fa, tb), n in c.most_common():
        L.append("| %s | %s | %d |" % (fa, tb, n))
    L.append("")
    L += ["### 移动明细", ""]
    for e, a, b in sorted(moved):
        L.append("- `%s`：%s → %s" % (e, a[0][1], b[0][1]))

    p = os.path.join(W, "lore-data", "versions", "diff-1.0-1.1.md")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print()
    print("已写出 %s" % p)


if __name__ == "__main__":
    main()
