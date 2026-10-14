"""Inspect the early DOCX files: what style marks their titles?"""
import html as htmlmod
import io
import os
import re
import sys
import zipfile
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

FILES = [
    r"E:\黑柩\黑柩小说花絮\黑柩TRPG-花絮总集篇一.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩TRPG-花絮总集篇二.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮3.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮5.docx",
]


def paras(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    out = []
    for p in re.findall(r"<w:p[^>]*>(.*?)</w:p>", xml, re.S):
        m = re.search(r'<w:pStyle w:val="([^"]+)"', p)
        style = m.group(1) if m else ""
        bold = bool(re.search(r"<w:b\s*/?>", p))
        t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
        t = htmlmod.unescape(re.sub(r"<[^>]+>", "", t)).strip()
        out.append((style, bold, t))
    return out


for f in FILES:
    if not os.path.exists(f):
        print("missing:", f)
        continue
    ps = paras(f)
    print("=" * 78)
    print(os.path.basename(f), f"  paras={len(ps)}")
    print("  styles:", Counter(s for s, b, t in ps if t).most_common(8))
    print("  bold-paragraph count:", sum(1 for s, b, t in ps if b and t))
    print("  first 30 non-empty paragraphs:")
    n = 0
    for s, b, t in ps:
        if not t:
            continue
        print(f"    [{s or '-':<12}]{'B' if b else ' '} {t[:70]}")
        n += 1
        if n >= 30:
            break
