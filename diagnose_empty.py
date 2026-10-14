"""Diagnose the 16 empty-body pieces: they are almost certainly definition lines."""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
inv = json.load(open(os.path.join(WIKI, "data", "v5_inventory.json"), encoding="utf-8"))

# re-run the docx parse and report pieces with no following body paragraph
import html as htmlmod, re, zipfile
VOCAB = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"
KIND_AT_START = re.compile(r"^\s*(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?" + VOCAB + r"\s*[:：]")
TITLEISH = re.compile(VOCAB + r"\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")
HASHK = re.compile(r"^\s*#\s*黑柩?\s*(?:#\s*)?" + VOCAB)

# definition-line detector: text after the colon explains the category
DEF = re.compile(r"^\s*" + VOCAB + r"\s*[:：]\s*(表示|代表|指|是|类|用于|见|说明)")

DOCX = json.load(open(os.path.join(WIKI, "data", "docx_sources.json"), encoding="utf-8"))
paths = [d["file"] for d in DOCX]


def read_docx(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    out = []
    for p in re.findall(r"<w:p[^>]*>(.*?)</w:p>", xml, re.S):
        m = re.search(r'<w:pStyle w:val="([^"]+)"', p)
        style = m.group(1) if m else ""
        t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
        t = htmlmod.unescape(re.sub(r"<[^>]+>", "", t)).strip()
        out.append((style, t))
    return out


def is_title(style, text):
    if not text or LEGEND.search(text) or DEF.match(text):
        return False
    if style == "2" and KIND_AT_START.match(text):
        return True
    if style == "2" and TITLEISH.search(text) and len(text) < 60:
        return True
    if HASHK.match(text):
        return True
    if not style and KIND_AT_START.match(text) and len(text) < 60:
        return True
    return False


for path in paths:
    if not os.path.exists(path):
        continue
    paras = read_docx(path)
    pieces, cur = [], None
    for style, text in paras:
        if is_title(style, text):
            if cur:
                pieces.append(cur)
            cur = {"style": style, "title": text, "body": 0}
        elif cur is not None and text:
            cur["body"] += 1
    if cur:
        pieces.append(cur)
    empt = [p for p in pieces if p["body"] == 0]
    if empt:
        print("=" * 70)
        print(os.path.basename(path))
        for p in empt:
            print(f"   [style={p['style'] or '-'}] {p['title'][:84]}")
