#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设定集结构校验：样式层级 vs 文档自带目录，产出报告。

用法：python tools/lore_report.py
输出：lore-data/report.md
"""
import io
import json
import os
import re
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numbering  # noqa: E402

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LORE = os.path.join(W, "lore-data")
HANZI = re.compile(r"[\u4e00-\u9fff]")


def norm(t):
    """标题归一化：与 numbering.strip_number 保持一致（去序号、去尾随页码、去空白）。

    两侧必须用**同一套**归一化，否则「仅样式有 / 仅目录有」会全是假阳性。
    """
    t = numbering.strip_number(t or "")
    t = re.sub(r"[\s\u3000]+", "", t)
    return t


def main():
    d = json.load(io.open(os.path.join(LORE, "doc.json"), encoding="utf-8"))
    vols = d["vols"]
    toc = d["toc"]["items"]

    L = ["# 设定集结构校验报告", "",
         "来源：`%s`" % d["source"], "",
         "## 一、总量", "",
         "| 项 | 数值 |", "|---|---:|",
         "| 段落 | %s |" % format(d["counts"]["paragraphs"], ","),
         "| 卷 | **%d** |" % d["counts"]["vols"],
         "| 节 | **%d** |" % d["counts"]["sections"],
         "| 词条 | **%d** |" % d["counts"]["entries"],
         "| 汉字 | %s |" % format(d["counts"]["hanzi"], ","),
         "| 目录行（toc 样式） | %d |" % len(toc),
         ""]

    # ── 二、目录 vs 样式：逐级比对 ──
    toc_txt = [norm(t["text"]) for t in toc]
    toc_h1 = [norm(t["text"]) for t in toc if (t["style"] or "").startswith("toc 1")]
    toc_h2 = [norm(t["text"]) for t in toc if (t["style"] or "").startswith("toc 2")]
    toc_h3 = [norm(t["text"]) for t in toc if (t["style"] or "").startswith("toc 3")]
    s_h1 = [norm(v["title"]) for v in vols]
    s_h2 = [norm(s["title"]) for v in vols for s in v["sections"]]
    s_h3 = [norm(e["title"]) for v in vols for s in v["sections"] for e in s["entries"]]

    def cmp(name, a, b):
        sa, sb = set(a), set(b)
        return ("| %s | %d | %d | %d | %d | %d |"
                % (name, len(a), len(b), len(sa - sb), len(sb - sa),
                   len(sa & sb)))

    L += ["## 二、目录 vs 样式层级（核心校验）", "",
          "「样式」＝按 Word 标题样式反推；「目录」＝文档自带的 TOC 域。",
          "两者**应当一致**；不一致处就是需要人工确认的地方。", "",
          "| 层级 | 样式条数 | 目录条数 | 仅样式有 | 仅目录有 | 两边都有 |",
          "|---|---:|---:|---:|---:|---:|",
          cmp("卷 / toc 1", s_h1, toc_h1),
          cmp("节 / toc 2", s_h2, toc_h2),
          cmp("词条 / toc 3", s_h3, toc_h3),
          ""]

    only_style_h2 = sorted(set(s_h2) - set(toc_h2))
    only_toc_h2 = sorted(set(toc_h2) - set(s_h2))
    only_style_h3 = sorted(set(s_h3) - set(toc_h3))
    only_toc_h3 = sorted(set(toc_h3) - set(s_h3))
    if only_style_h2 or only_toc_h2:
        L += ["### 节层面不一致", ""]
        if only_style_h2:
            L.append("**只在样式里（目录没有）**：")
            L += ["- `%s`" % x for x in only_style_h2[:30]]
            L.append("")
        if only_toc_h2:
            L.append("**只在目录里（样式没标）**：")
            L += ["- `%s`" % x for x in only_toc_h2[:30]]
            L.append("")
    if only_style_h3 or only_toc_h3:
        L += ["### 词条层面不一致（前 20 条各列）", ""]
        if only_style_h3:
            L.append("**只在样式里**：%s" % "、".join("`%s`" % x for x in only_style_h3[:20]))
            L.append("")
        if only_toc_h3:
            L.append("**只在目录里**：%s" % "、".join("`%s`" % x for x in only_toc_h3[:20]))
            L.append("")

    # ── 三、坑 1：没有 H3 的节 ──
    noent = [(v["title"], s) for v in vols for s in v["sections"]
             if s["n_entries"] == 0]
    L += ["## 三、⚠️ 没有子词条的节（内容直接挂在节上）", "",
          "这些节**不能按 H3 切词条**，否则内容会全部丢失。", "",
          "共 **%d** 个节，合计 **%s** 字：" % (
              len(noent), format(sum(s["chars"] for _v, s in noent), ",")), "",
          "| 卷 | 节 | 字数 | 段落数 |", "|---|---|---:|---:|"]
    for vt, s in noent:
        L.append("| %s | %s | %s | %d |"
                 % (vt[:16], s["title"][:34], format(s["chars"], ","),
                    s["text"].count("\n") + 1))
    L.append("")

    # ── 四、各卷结构 ──
    L += ["## 四、各卷结构", "",
          "| 卷 | 节 | 词条 | 字数 | 无词条的节 |", "|---|---:|---:|---:|---:|"]
    for v in vols:
        n0 = sum(1 for s in v["sections"] if s["n_entries"] == 0)
        L.append("| %s | %d | %d | %s | %d |"
                 % (v["title"][:24], v["n_sections"], v["n_entries"],
                    format(v["chars"], ","), n0))
    L.append("")

    # ── 五、词条长度 ──
    ents = [(e["title"], e["chars"], e["hanzi"]) for v in vols
            for s in v["sections"] for e in s["entries"]]
    lens = sorted(x[1] for x in ents)
    L += ["## 五、词条长度分布", "",
          "| 项 | 值 |", "|---|---:|",
          "| 词条数 | %d |" % len(ents),
          "| 中位 | %d 字 |" % statistics.median(lens),
          "| 平均 | %d 字 |" % (sum(lens) // len(lens)),
          "| 最短 | %d 字 |" % lens[0],
          "| 最长 | %d 字 |" % lens[-1],
          "| >3000 字 | %d 个 |" % sum(1 for x in lens if x > 3000),
          "| >5000 字 | %d 个 |" % sum(1 for x in lens if x > 5000),
          "| <300 字 | %d 个 |" % sum(1 for x in lens if x < 300),
          "", "**最长的 8 条**：", ""]
    for t, c, _h in sorted(ents, key=lambda x: -x[1])[:8]:
        L.append("- %s 字 —— `%s`" % (format(c, ","), t))
    L.append("")

    # ── 六、编纂备注 ──
    notes = [(v["title"], s["title"], s["chars"]) for v in vols for s in v["sections"]
             if "编纂备注" in s["title"]]
    L += ["## 六、编纂备注的位置与分量", "",
          "共 **%d** 处，合计 %s 字。" % (len(notes), format(sum(n[2] for n in notes), ",")),
          "", "| 卷 | 备注字数 |", "|---|---:|"]
    for vt, st, c in notes:
        L.append("| %s | %s |" % (vt[:24], format(c, ",")))
    L.append("")

    # ── 七、目录条目样例 ──
    L += ["## 七、目录提取样例（用于确认层级正确）", ""]
    for i, t in enumerate(toc[:24], 1):
        L.append("- [%s] %s" % (t["style"], t["text"]))
    L.append("")
    L.append("（目录共 %d 行，此处只列前 24）" % len(toc))

    p = os.path.join(LORE, "report.md")
    io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print("已写出 %s" % p)
    print("无子词条的节：%d 个，合计 %s 字"
          % (len(noent), format(sum(s["chars"] for _v, s in noent), ",")))
    print("仅样式有的节：%d ｜ 仅目录有的节：%d"
          % (len(only_style_h2), len(only_toc_h2)))
    print("仅样式有的词条：%d ｜ 仅目录有的词条：%d"
          % (len(only_style_h3), len(only_toc_h3)))


if __name__ == "__main__":
    main()
