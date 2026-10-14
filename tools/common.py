#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小块工具：pinyin slug、frontmatter、正文读取、极简 Markdown→HTML。

供 tag_entries.py / build_site.py / update.py 共用。
"""
import json
import os
import re

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(W, "data")
SRC = os.path.join(W, "source")

_PY = None
_PY_OVERRIDE = None
_WORD_OVERRIDE = None


def _load_pinyin_overrides():
    global _PY_OVERRIDE, _WORD_OVERRIDE
    if _PY_OVERRIDE is None:
        p = os.path.join(DATA, "pinyin_overrides.json")
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            _PY_OVERRIDE = d.get("override", {}) or {}
            _WORD_OVERRIDE = {k: v for k, v in (d.get("word_override") or {}).items()
                              if k != "note"}
        else:
            _PY_OVERRIDE, _WORD_OVERRIDE = {}, {}
    return _PY_OVERRIDE, _WORD_OVERRIDE


def pinyin_overrides():
    """人工读音覆盖（多音字）。见 data/pinyin_overrides.json。"""
    return _load_pinyin_overrides()[0]


def pinyin_table():
    global _PY
    if _PY is None:
        path = os.path.join(DATA, "pinyin_table.json")
        base = {}
        if os.path.exists(path):
            base = json.load(open(path, encoding="utf-8"))["table"]
        merged = dict(base)
        merged.update(pinyin_overrides())
        _PY = merged
    return _PY


def slugify(text, maxlen=40):
    """中文标签/标题 → 英文 slug（无声调拼音，**每个音节一个连字符词**）。

    规则（与既有站点风格一致，如 `ye-xin-yu-hong-ying-de-tan-hua`）：
    * 每个汉字 → 一个拼音音节，独立成词；
    * 连续的 ASCII 字母/数字（如 THEM、287）→ 一个词；
    * 标点/空白只作分词边界，不额外产生词。
    * 多音字：先查 `data/pinyin_overrides.json` 的**词级**覆盖，再查**字级**覆盖。
    """
    table = pinyin_table()
    _, words = _load_pinyin_overrides()
    text = str(text)
    parts = []
    ascii_run = []
    i = 0
    n = len(text)

    def flush_ascii():
        if ascii_run:
            parts.append("".join(ascii_run))
            ascii_run.clear()

    while i < n:
        hit = None
        for w in sorted(words, key=len, reverse=True):
            if text.startswith(w, i):
                hit = w
                break
        if hit:
            flush_ascii()
            parts.extend(p for p in words[hit].split("-") if p)
            i += len(hit)
            continue
        ch = text[i]
        if re.match(r"[A-Za-z0-9]", ch):
            ascii_run.append(ch.lower())
        else:
            flush_ascii()
            if re.match(r"[\u4e00-\u9fff]", ch):
                syl = table.get(ch)
                parts.append(syl if syl else "%x" % ord(ch))
        i += 1
    flush_ascii()
    s = re.sub(r"-{2,}", "-", "-".join(p for p in parts if p)).strip("-")
    return s[:maxlen].strip("-") or "x"


# ------------------------------------------------------------------ 正文
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)


def read_entry(path):
    """返回 (frontmatter dict, body str)。"""
    raw = open(path, encoding="utf-8").read()
    fm = {}
    m = FM_RE.match(raw)
    body = raw
    if m:
        body = raw[m.end():]
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, body


def load_entries():
    """按 id 排序的 entries.json 记录（附 source 路径与正文）。"""
    idx = json.load(open(os.path.join(DATA, "entries.json"), encoding="utf-8"))
    out = []
    for e in idx["entries"]:
        p = os.path.join(SRC, e["file"])
        fm, body = read_entry(p)
        rec = dict(e)
        rec["path"] = p
        rec["body"] = body
        rec["fm"] = fm
        out.append(rec)
    return out


# ------------------------------------------------------- Markdown → HTML
def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def inline(s):
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def body_to_html(body):
    """极简渲染：空行分段，`#` 开头作小标题，`>` 作引用，`-` 作列表。

    正文以散文与对白为主，不需要完整 Markdown 实现；这里保证
    段落切分与转义正确即可（幂等、无外部依赖）。
    """
    blocks = []
    for chunk in re.split(r"\n\s*\n", body.strip()):
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = [l.rstrip() for l in chunk.split("\n") if l.strip()]
        if not lines:
            continue
        if all(l.lstrip().startswith(("- ", "* ")) for l in lines):
            items = "".join("<li>%s</li>" % inline(l.lstrip()[2:]) for l in lines)
            blocks.append("<ul>%s</ul>" % items)
            continue
        if all(l.lstrip().startswith(">") for l in lines):
            txt = " ".join(l.lstrip().lstrip(">").strip() for l in lines)
            blocks.append("<blockquote>%s</blockquote>" % inline(txt))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", lines[0])
        if m and len(lines) == 1:
            lv = min(6, len(m.group(1)) + 2)
            blocks.append("<h%d>%s</h%d>" % (lv, inline(m.group(2)), lv))
            continue
        txt = "\n".join(lines)
        txt = re.sub(r"\n{2,}", "\n", txt)
        blocks.append("<p>%s</p>" % "<br>".join(inline(x) for x in txt.split("\n")))
    return "\n".join(blocks)


def write_json(path, obj):
    """统一出口：UTF-8 无 BOM、ensure_ascii=False、稳定格式。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


if __name__ == "__main__":
    for t in ["叶心与红樱的谈话", "蚀血教来袭？这是什么", "hx-001"]:
        print(t, "->", slugify(t))
