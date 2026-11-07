#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《黑柩》独立小说 docx → novel-data/*.md（**可审阅的中间产物**）。

与 parse_report.py 的分工
------------------------
报告是论文：要保留标题层级、表格、粗斜体。
小说是正文：**不保留任何 Markdown 行内标记**。原因不是偷懒——

    《来世乐土》docx 里 853 段中有 700 段**整段是斜体**（连叙述句都是，
    "说着说着，叶心就将视线转向了录影机。" 也是斜体）。那是排版残留，
    不是语义。照原样转成 *…* 会让整本书变斜体，页面必然难看。
    《人鱼小队》的粗体则是**分节标记**（日期行），但本工具改用日期正则
    识别分节，粗体同样不必进 Markdown。

    另一个后果是好的：正文里永远不会出现裸 `*`，页面上也就不会有
    Markdown 标记泄漏。

分节规则（data/report_site.json 的 works[].split）
------------------------------------------------
    heading —— docx 标题样式（outlineLvl）就是章；
               level 1 视为书名丢弃，level ≥ 2 为章。
    date    —— 没有标题样式，靠「复兴纪元/战争纪元/进盟历 + 年」的日期行分节；
               没有日期行之前的那一段当作「前言」。
    parts   —— 一个作品含多篇小说，每篇各自从「1」编章（《黑柩校园》）；
               文件名与篇名的对应写在 works[].parts。

输出格式（本文件自定的极简子集，供 build_report.py 读）
------------------------------------------------------
    @part 篇名      ← 仅 split=parts 时出现，一个作品可有多段
    ## 章名         ← 章
    正文段落        ← 一段一行，段间空行

用法：
    python tools/parse_novel.py
"""
import datetime
import html
import io
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
from parse_report import style_map  # noqa: E402  复用同一套 styleId → (名字, 层级)

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = r"E:\黑柩\黑柩小说"
OUT = os.path.join(W, "novel-data")
CFG = os.path.join(W, "data", "report_site.json")

HANZI = re.compile(r"[\u4e00-\u9fff]")
T_RE = re.compile(r"<w:t[^>]*>([^<]*)</w:t>")
BR_RE = re.compile(r"<w:br\s*/?>|<w:cr\s*/?>")
TAB_RE = re.compile(r"<w:tab\s*/?>")
# 人鱼小队的日期行：复兴纪元4年 11月11日 / 战争纪元4年 12月18日 ——来自某芯片
DATE_RE = re.compile(r"^(?:复兴纪元|战争纪元|进盟历)\s*\d+\s*年")
# 「前言」「前言：…」——两种写法都要认
PREFACE_RE = re.compile(r"^前言\s*(?:[:：]\s*(.*))?$", re.S)


# ══════════════════════════════════════════════════════════════
# docx → 段落块
# ══════════════════════════════════════════════════════════════
def block_lines(blk):
    """一个 <w:p> → 若干行文本（`<w:br/>` 软换行拆成独立行）。"""
    txt = TAB_RE.sub("", blk)
    out = []
    for seg in BR_RE.split(txt):
        s = "".join(T_RE.findall(seg))
        s = html.unescape(s).replace("\u3000", " ").strip()
        if s:
            out.append(s)
    return out


def docx_hanzi(path):
    """docx 全文汉字数（含章标题与前言）。

    与报告正文里声明的字数**对齐**：三篇报告写的是「44,636 汉字」「17,162 汉字」
    「28,206 汉字」，前两个正好等于 docx 全文汉字数，故这里按同一口径数，
    免得原著页与报告正文对不上。（《黑柩校园》报告把两句「前言」排除了，
    合计 28,206；本站按全文计为 28,270，差 64 字。）
    """
    z = zipfile.ZipFile(path)
    xml = z.read("word/document.xml").decode("utf-8", "replace")
    m = re.search(r"<w:body>(.*)</w:body>", xml, re.S)
    body = m.group(1) if m else xml
    return len(HANZI.findall("".join(T_RE.findall(body))))


def read_blocks(path):
    """docx → [{"text": 行文本, "level": 标题层级或 None}]，按文档顺序。"""
    z = zipfile.ZipFile(path)
    smap, _, _ = style_map(z)
    xml = z.read("word/document.xml").decode("utf-8", "replace")
    m = re.search(r"<w:body>(.*)</w:body>", xml, re.S)
    body = m.group(1) if m else xml

    blocks = []
    for bm in re.finditer(r"<w:p[ >].*?</w:p>", body, re.S):
        blk = bm.group(0)
        st = re.search(r'<w:pStyle w:val="([^"]+)"', blk)
        sid = st.group(1) if st else ""
        lv = smap.get(sid, ("", None))[1]
        for line in block_lines(blk):
            blocks.append({"text": line, "level": lv})
    return blocks


# ══════════════════════════════════════════════════════════════
# 分节
# ══════════════════════════════════════════════════════════════
def build_sections(blocks, split):
    """→ [{"title": 章名, "paras": [段]}]"""
    secs = []
    cur = [None]     # 用列表当可变容器

    def start(title):
        cur[0] = {"title": title, "paras": []}
        secs.append(cur[0])

    for b in blocks:
        t = b["text"]
        lv = b["level"]

        if split == "heading" and lv:
            if lv == 1:
                continue                      # 书名，页面 <h1> 已有
            if lv >= 2:
                start(t)
                continue

        if split == "parts" and lv and lv >= 1:
            start(t)
            continue

        if split == "date":
            pm = PREFACE_RE.match(t)
            if pm:
                start("前言")
                if pm.group(1) and pm.group(1).strip():
                    cur[0]["paras"].append(pm.group(1).strip())
                continue
            if DATE_RE.match(t):
                start(t)
                continue

        if cur[0] is None:
            # 正文之前、还没有任何章的零散文字：归入「前言」
            pm = PREFACE_RE.match(t)
            if pm:
                start("前言")
                if pm.group(1) and pm.group(1).strip():
                    cur[0]["paras"].append(pm.group(1).strip())
                continue
            start("前言")
        cur[0]["paras"].append(t)
    return secs


# ══════════════════════════════════════════════════════════════
# 一个作品 → md
# ══════════════════════════════════════════════════════════════
def parse_work(work):
    split = work.get("split", "heading")
    files = work["files"]
    md = []
    parts_meta = []
    n_sec = 0
    n_front = 0

    if split == "parts":
        pmap = {p["file"]: p["title"] for p in work.get("parts") or []}
        for fn in files:
            path = os.path.join(SRC, fn)
            if not os.path.exists(path):
                raise SystemExit("找不到源文件：%s" % path)
            title = pmap.get(fn) or os.path.splitext(fn)[0]
            secs = build_sections(read_blocks(path), "parts")
            md.append("@part " + title)
            md.append("")
            for s in secs:
                md.append("## " + s["title"])
                md.append("")
                for p in s["paras"]:
                    md.append(p)
                    md.append("")
            _front = sum(1 for s in secs if s["title"] == "前言")
            parts_meta.append({"title": title,
                               "chapters": len(secs) - _front,
                               "front": _front})
            n_sec += len(secs)
            n_front += _front
    else:
        for fn in files:
            path = os.path.join(SRC, fn)
            if not os.path.exists(path):
                raise SystemExit("找不到源文件：%s" % path)
            secs = build_sections(read_blocks(path), split)
            for s in secs:
                md.append("## " + s["title"])
                md.append("")
                for p in s["paras"]:
                    md.append(p)
                    md.append("")
            _front = sum(1 for s in secs if s["title"] == "前言")
            n_sec += len(secs)
            n_front += _front
            parts_meta.append({"title": work.get("title") or work["key"],
                               "chapters": len(secs) - _front,
                               "front": _front})

    # 正文汉字数（口径见 docx_hanzi：全文，含章标题与前言）
    body_hanzi = sum(docx_hanzi(os.path.join(SRC, fn)) for fn in files)
    text = "\n".join(md).strip() + "\n"
    return {"md": text, "sections": n_sec, "front": n_front,
            "hanzi": body_hanzi, "parts": parts_meta}


def main():
    cfg = json.load(io.open(CFG, encoding="utf-8"))
    works = cfg.get("works") or []
    if not works:
        sys.exit("data/report_site.json 里没有 works 配置")
    os.makedirs(OUT, exist_ok=True)

    catalog = []
    print("解析 %d 部独立作品 → %s" % (len(works), OUT))
    for w in works:
        r = parse_work(w)
        item = {
            "key": w["key"],
            "slug": w["slug"],
            "title": w.get("title") or w["key"],
            "split": w.get("split", "heading"),
            "files": w["files"],
            "report": w.get("report") or w["key"],
            "column_no": w.get("column_no", ""),
            "sections": r["sections"],
            "front": r["front"],
            "parts": r["parts"],
            "hanzi": r["hanzi"],
            # 版本：取源文件的最新修改日期（docx 一改稿，这个日期就变）
            "source_date": max(
                datetime.datetime.fromtimestamp(
                    os.path.getmtime(os.path.join(SRC, f))).strftime("%Y-%m-%d")
                for f in w["files"]),
            "work_notes": w.get("work_notes") or [],
            "report_notes": w.get("report_notes") or [],
            "toc_strip": w.get("toc_strip") or "",
        }
        io.open(os.path.join(OUT, w["slug"] + ".md"), "w",
                encoding="utf-8", newline="\n").write(r["md"])
        catalog.append(item)
        shape = ("%d 篇 / %d 节" % (len(r["parts"]), r["sections"])
                 if w.get("split") == "parts" else "%d 节" % r["sections"])
        print("  %-22s %8s 字 ｜ %-12s ｜ 稿 %s"
              % (item["title"], format(item["hanzi"], ","), shape,
                 item["source_date"]))

    io.open(os.path.join(OUT, "catalog.json"), "w", encoding="utf-8",
            newline="\n").write(
        json.dumps(catalog, ensure_ascii=False, indent=1) + "\n")
    print()
    print("合计：%d 部 ｜ %s 字 ｜ %d 节"
          % (len(catalog), format(sum(c["hanzi"] for c in catalog), ","),
             sum(c["sections"] for c in catalog)))


if __name__ == "__main__":
    main()
