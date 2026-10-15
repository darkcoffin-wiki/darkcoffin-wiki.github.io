#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《黑柩报告》11 份 docx → report-data/*.md（**可审阅的中间产物**）。

保真的东西：标题层级（Heading1-4）、表格（w:tbl）、粗体/斜体（run 级 rPr）、
列表（List Bullet / List Number）。报告里**没有**图片、高亮、底色、彩色字、
脚注、批注、超链接——所以不需要处理它们。

用法：
    python tools/parse_report.py [--src "E:\\黑柩\\黑柩报告"] [--out report-data]
"""
import argparse
import io
import json
import os
import re
import sys
import zipfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SRC = r"E:\黑柩\黑柩报告"
DEFAULT_OUT = "report-data"

RE_HANZI = re.compile(r"[\u4e00-\u9fff]")


# ══════════════════════════════════════════════════════════════
# 1) 读 docx 的样式表：styleId → (名字, 层级)
# ══════════════════════════════════════════════════════════════
def style_map(z):
    smap, defb, defi = {}, False, False
    if "word/styles.xml" not in z.namelist():
        return smap, defb, defi
    sx = z.read("word/styles.xml").decode("utf-8", "replace")
    for m in re.finditer(r'<w:style [^>]*w:styleId="([^"]+)"[^>]*>(.*?)</w:style>',
                         sx, re.S):
        sid, body = m.group(1), m.group(2)
        nm = re.search(r'<w:name w:val="([^"]+)"', body)
        ol = re.search(r"<w:outlineLvl w:val=\"(\d+)\"", body)
        smap[sid] = (nm.group(1) if nm else sid,
                     int(ol.group(1)) + 1 if ol else None)
    d = re.search(r"<w:docDefaults>.*?</w:docDefaults>", sx, re.S)
    if d:
        defb = bool(re.search(r"<w:b\s*/>", d.group(0)))
        defi = bool(re.search(r"<w:i\s*/>", d.group(0)))
    return smap, defb, defi


# ══════════════════════════════════════════════════════════════
# 2) run 级富文本：把 <w:r> 序列转成带 **粗** / *斜* 的文本
# ══════════════════════════════════════════════════════════════
def runs_to_md(frag, defb=False, defi=False):
    """frag：一段 XML（一个 w:p 或一个 w:tc 的内容）。"""
    out = []
    for rm in re.finditer(r"<w:r[ >](.*?)</w:r>", frag, re.S):
        r = rm.group(1)
        parts = re.findall(r"<w:t[^>]*>([^<]*)</w:t>", r)
        if not parts:
            # 制表符/换行
            if "<w:tab/>" in r:
                out.append(("\t", False, False))
            if "<w:br/>" in r:
                out.append(("\n", False, False))
            continue
        txt = "".join(parts)
        rpr = re.search(r"<w:rPr>(.*?)</w:rPr>", r, re.S)
        pr = rpr.group(1) if rpr else ""
        mb = re.search(r'<w:b(?:\s+w:val="([^"]*)")?\s*/>', pr)
        mi = re.search(r'<w:i(?:\s+w:val="([^"]*)")?\s*/>', pr)
        isb = (mb.group(1) not in ("0", "false")) if mb else defb
        isi = (mi.group(1) not in ("0", "false")) if mi else defi
        out.append((txt, isb, isi))

    # 相邻同格式 run 合并，再包裹标记
    merged = []
    for txt, b, i in out:
        if merged and merged[-1][1] == b and merged[-1][2] == i:
            merged[-1][0] += txt
        else:
            merged.append([txt, b, i])

    res = []
    for txt, b, i in merged:
        if not txt:
            continue
        if txt == "\n":
            res.append("\n")
            continue
        seg = txt
        # 标记符号本身要转义，避免破坏结构
        seg = seg.replace("\\", "\\\\").replace("*", "\\*")
        if b:
            seg = "**%s**" % seg
        if i:
            seg = "*%s*" % seg
        res.append(seg)
    return "".join(res)


# 少数报告（如《齐藤优子传》）没有用 Word 标题样式，层级靠「粗体 + 编号」表达。
# 规则从严，只认两种形态，避免把行内强调误判成标题：
BOLD_H2 = re.compile(r"^\*\*([一二三四五六七八九十]+、[^*]{1,40})\*\*$")
BOLD_H3 = re.compile(r"^\*\*((?:\d{1,2})\.\s?[^*]{1,40})\*\*$")


def bold_heading_level(txt):
    """整行加粗且形如「一、xx」/「1. xx」→ 判为标题，返回层级；否则 None。"""
    if len(txt) > 64:
        return None
    if BOLD_H2.match(txt):
        return 2
    if BOLD_H3.match(txt):
        return 3
    return None


def para_style(p, smap):
    st = re.search(r'<w:pStyle w:val="([^"]+)"', p)
    sid = st.group(1) if st else ""
    nm, lv = smap.get(sid, ("", None))
    isnum = "<w:numPr>" in p
    return sid, nm, lv, isnum


# ══════════════════════════════════════════════════════════════
# 3) 表格 → Markdown 表格
# ══════════════════════════════════════════════════════════════
def cell_text(tc, defb, defi):
    """单元格：把内部各段用 <br> 连接。"""
    paras = re.findall(r"<w:p[ >].*?</w:p>", tc, re.S)
    lines = []
    for p in paras:
        t = runs_to_md(p, defb, defi).strip()
        t = t.replace("|", "\\|")
        if t:
            lines.append(t)
    return "<br>".join(lines)


def table_to_md(tbl, defb, defi):
    rows = []
    for tr in re.findall(r"<w:tr[ >].*?</w:tr>", tbl, re.S):
        cells = [cell_text(tc, defb, defi)
                 for tc in re.findall(r"<w:tc>.*?</w:tc>", tr, re.S)]
        rows.append(cells)
    if not rows:
        return [], 0
    ncol = max(len(r) for r in rows)
    # 补齐列数不齐的行（合并单元格会造成不齐）
    for r in rows:
        while len(r) < ncol:
            r.append("")
    out = ["| " + " | ".join(rows[0]) + " |",
           "|" + "|".join([" --- "] * ncol) + "|"]
    for r in rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    ragged = sum(1 for r in rows if len(r) != ncol)
    return out, ragged


# ══════════════════════════════════════════════════════════════
# 4) 主解析
# ══════════════════════════════════════════════════════════════
def parse_docx(path):
    z = zipfile.ZipFile(path)
    smap, defb, defi = style_map(z)
    xml = z.read("word/document.xml").decode("utf-8", "replace")

    body = re.search(r"<w:body>(.*)</w:body>", xml, re.S)
    body = body.group(1) if body else xml

    md, issues = [], []
    inferred = [0]        # 用粗体推断出的标题数
    levels = {}
    n_table = n_ragged = n_bold = n_italic = n_list = 0
    in_code = False

    # 逐个顶层块（段落或表格）
    for m in re.finditer(r"<w:p[ >].*?</w:p>|<w:tbl>.*?</w:tbl>", body, re.S):
        blk = m.group(0)
        if blk.startswith("<w:tbl>"):
            rows, ragged = table_to_md(blk, defb, defi)
            if rows:
                md += ["", *rows, ""]
                n_table += 1
                n_ragged += ragged
            continue

        sid, nm, lv, isnum = para_style(blk, smap)
        raw = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", blk))
        txt = runs_to_md(blk, defb, defi).strip()
        if not txt:
            md.append("")
            continue

        n_bold += txt.count("**") // 2
        n_italic += max(0, txt.count("*") - txt.count("**") * 2) // 2

        if not lv:
            # 没有标题样式时，用「整行加粗 + 编号」推断层级
            gl = bold_heading_level(txt)
            if gl:
                lv = gl
                txt = re.sub(r"^\*\*|\*\*$", "", txt)
                inferred[0] += 1
        if lv:
            levels[lv] = levels.get(lv, 0) + 1
            md += ["", "#" * min(lv, 6) + " " + txt, ""]
            continue
        if isnum or "List" in sid:
            n_list += 1
            md.append(("- " if "Number" not in sid else "1. ") + txt)
            continue
        md += ["", txt, ""]

    # 压掉连续空行
    out, blank = [], 0
    for line in md:
        if line.strip() == "":
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        out.append(line)

    text = "\n".join(out)
    return {
        "md": text,
        "hanzi": len(RE_HANZI.findall(text)),
        "levels": levels,
        "tables": n_table,
        "ragged_rows": n_ragged,
        "bold": n_bold,
        "italic": n_italic,
        "list_items": n_list,
        "inferred_headings": inferred[0],
        "issues": issues,
        # 供建站用的元信息
        "headings": re.findall(r"^(#{1,6}) (.+)$", text, re.M),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    if not os.path.isdir(args.src):
        sys.exit("找不到源目录：%s" % args.src)
    out_dir = args.out if os.path.isabs(args.out) else os.path.join(W, args.out)
    os.makedirs(out_dir, exist_ok=True)

    files = sorted(f for f in os.listdir(args.src)
                   if f.lower().endswith(".docx") and not f.startswith("~$"))
    catalog, issues = [], []
    print("解析 %d 份报告 → %s" % (len(files), out_dir))
    for fn in files:
        p = os.path.join(args.src, fn)
        r = parse_docx(p)
        slug = fn.replace("黑柩报告-", "").replace(".docx", "")
        rec = {"file": fn, "slug": slug, **{k: v for k, v in r.items() if k != "md"}}
        catalog.append(rec)
        io.open(os.path.join(out_dir, slug + ".md"), "w",
                encoding="utf-8", newline="\n").write(r["md"] + "\n")
        print("  %-40s %7s 字 ｜ 表 %2d ｜ 标题 %s"
              % (slug[:40], format(r["hanzi"], ","), r["tables"],
                 "／".join("H%d×%d" % (k, v) for k, v in sorted(r["levels"].items())) or "无"))

    io.open(os.path.join(out_dir, "catalog.json"), "w", encoding="utf-8",
            newline="\n").write(json.dumps(catalog, ensure_ascii=False, indent=1) + "\n")
    tot_h = sum(c["hanzi"] for c in catalog)
    print()
    print("合计：%d 份 ｜ %s 汉字 ｜ 表格 %d（列数不齐的行 %d）｜ 列表项 %d"
          % (len(catalog), format(tot_h, ","), sum(c["tables"] for c in catalog),
             sum(c["ragged_rows"] for c in catalog),
             sum(c["list_items"] for c in catalog)))
    print("已写出 catalog.json")


if __name__ == "__main__":
    main()
