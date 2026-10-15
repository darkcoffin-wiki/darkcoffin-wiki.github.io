#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从《黑柩战报-竖棺》docx 提取结构化素材 → trpg-src/_raw/竖棺-战报素材.md

**只做提取，不做改写**：把 8 章正文按「一、二、三…」小节切好，
附录（逐日大事记/人物名录/地点志/未决之事/骰点）原样保留，
并抽取元信息（规模表、参与者表、权限表、特殊规则、体例说明、时间坐标）。

用途：作为生成《竖棺》季志与场次卡的**中间读本**，避免反复解压 docx。
"""
import io
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = r"E:\黑柩\黑柩小说花絮\黑柩战报-竖棺.docx"
OUT = os.path.join(W, "trpg-src", "_raw", "竖棺-战报素材.md")

W_T = re.compile(r"<w:t[^>]*>([^<]*)</w:t>")


def parse(path):
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "replace")
    out = []
    for m in re.finditer(r"<w:p[ >].*?</w:p>|<w:tbl>.*?</w:tbl>", xml, re.S):
        blk = m.group(0)
        if blk.startswith("<w:tbl>"):
            rows = []
            for tr in re.findall(r"<w:tr[ >].*?</w:tr>", blk, re.S):
                cells = ["".join(W_T.findall(tc)).strip()
                         for tc in re.findall(r"<w:tc>.*?</w:tc>", tr, re.S)]
                rows.append("| " + " | ".join(cells) + " |")
            out.append(("TABLE", "\n".join(rows)))
            continue
        t = "".join(W_T.findall(blk)).strip()
        if not t:
            continue
        isnum = "<w:numPr>" in blk
        isbul = 'w:val="ListBullet"' in blk
        out.append(("BULLET" if (isnum or isbul) else "PARA", t))
    return out


def main():
    rows = parse(SRC)
    lines = ["# 竖棺战报 · 原始素材（自动提取，未改写）", "",
             "来源：`%s`" % SRC, ""]
    for kind, t in rows:
        if kind == "TABLE":
            lines += ["", t, ""]
        elif kind == "BULLET":
            lines.append("- " + t)
        else:
            lines += ["", t]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    n = len(re.findall(r"[\u4e00-\u9fff]", "\n".join(lines)))
    print("已写出 %s" % OUT)
    print("段落/表格块 %d ｜ 汉字 %s ｜ 文件 %.1f MB"
          % (len(rows), format(n, ","), os.path.getsize(OUT) / 1048576))


if __name__ == "__main__":
    main()
