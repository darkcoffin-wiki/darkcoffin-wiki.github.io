#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计《黑柩报告》10 份 docx 的结构与富文本构成。

目的：判断要保真到什么程度（标题层级 / 表格 / 图片 / 列表 / 粗斜体 / 高亮 / 引用 / 脚注…）
用法：python tools/audit_reports.py
"""
import io
import os
import re
import sys
import zipfile
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = r"E:\黑柩\黑柩报告"

W_T = re.compile(r"<w:t[^>]*>([^<]*)</w:t>")
RE_HANZI = re.compile(r"[\u4e00-\u9fff]")


def audit(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    xml = z.read("word/document.xml").decode("utf-8", "replace")
    # 样式表
    smap = {}
    if "word/styles.xml" in names:
        sx = z.read("word/styles.xml").decode("utf-8", "replace")
        for m in re.finditer(r'<w:style [^>]*w:styleId="([^"]+)"[^>]*>(.*?)</w:style>', sx, re.S):
            sid, body = m.group(1), m.group(2)
            nm = re.search(r'<w:name w:val="([^"]+)"', body)
            ol = re.search(r'<w:outlineLvl w:val="(\d+)"', body)
            smap[sid] = (nm.group(1) if nm else sid,
                         int(ol.group(1)) if ol else None)
    paras = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)
    styles = Counter()
    lv = Counter()
    for p in paras:
        st = re.search(r'<w:pStyle w:val="([^"]+)"', p)
        sid = st.group(1) if st else ""
        nm, ol = smap.get(sid, ("", None))
        styles["%s(%s)" % (nm or "(正文)", sid or "-")] += 1
        if ol is not None:
            lv[ol + 1] += 1
    text = "".join(W_T.findall(xml))
    return {
        "file": os.path.basename(path),
        "kb": os.path.getsize(path) / 1024,
        "paras": len(paras),
        "hanzi": len(RE_HANZI.findall(text)),
        "tables": xml.count("<w:tbl>"),
        "images": sum(1 for n in names if n.startswith("word/media/")),
        "bold": xml.count("<w:b/>") + xml.count("<w:b "),
        "italic": xml.count("<w:i/>") + xml.count("<w:i "),
        "highlight": xml.count("<w:highlight"),
        "color": xml.count("<w:color "),
        "lists": xml.count("<w:numPr>"),
        "quotes": (xml.count("ListQuote") + xml.count('w:val="Quote"')),
        "shading": xml.count("<w:shd "),
        "levels": dict(sorted(lv.items())),
        "styles": styles.most_common(9),
        "headings": [],
    }


def main():
    if not os.path.isdir(SRC):
        sys.exit("找不到目录：%s" % SRC)
    files = sorted(f for f in os.listdir(SRC) if f.lower().endswith(".docx") and not f.startswith("~$"))
    rows = [audit(os.path.join(SRC, f)) for f in files]

    print("=== 10 份报告的富文本构成 ===")
    print("%-42s %6s %7s %5s %4s %5s %5s %5s %5s %5s" %
          ("文件", "KB", "汉字", "表格", "图", "粗体", "列表", "高亮", "底色", "色字"))
    for r in rows:
        print("%-42s %6.0f %7s %5d %4d %5d %5d %5d %5d %5d" %
              (r["file"][:42], r["kb"], format(r["hanzi"], ","), r["tables"],
               r["images"], r["bold"], r["lists"], r["highlight"],
               r["shading"], r["color"]))
    print()
    tot = Counter()
    for r in rows:
        for k in ("tables", "images", "bold", "italic", "highlight", "color",
                  "lists", "quotes", "shading", "hanzi"):
            tot[k] += r[k]
    print("合计：汉字 %s ｜ 表格 %d ｜ 图片 %d ｜ 粗体 %d ｜ 斜体 %d ｜ 列表 %d ｜ 高亮 %d ｜ 底色 %d ｜ 彩色字 %d"
          % (format(tot["hanzi"], ","), tot["tables"], tot["images"], tot["bold"],
             tot["italic"], tot["lists"], tot["highlight"], tot["shading"], tot["color"]))
    print()
    print("=== 每份的标题层级分布（可用作目录）===")
    for r in rows:
        print("  %-42s 层级 %s" % (r["file"][:42], r["levels"]))
    print()
    print("=== 样式使用（第 1 份）===")
    for k, v in rows[0]["styles"]:
        print("   %-28s %d" % (k, v))


if __name__ == "__main__":
    main()
