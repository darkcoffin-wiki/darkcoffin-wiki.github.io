"""If the docx piece order matches the site title order (minus titles whose body
lives elsewhere), the mapping is positional and needs no guessing.

Print both sequences side by side.
"""
import html as htmlmod
import io
import json
import os
import re
import sys
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
DOCX2 = r"E:\黑柩\黑柩小说花絮\黑柩TRPG-花絮总集篇二.docx"
VOCAB = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"
HASHK = re.compile(r"^\s*#\s*黑柩?\s*(?:#\s*)?" + VOCAB + r"\s*#?\s*")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")


def read_docx(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    return [htmlmod.unescape(re.sub(r"<[^>]+>", "", "".join(
        re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S)))).strip()
        for p in re.findall(r"<w:p[^>]*>(.*?)</w:p>", xml, re.S)]


lines = read_docx(DOCX2)
print("=== docx 原始行（前 60 行，看清标题行结构）===")
n = 0
for i, l in enumerate(lines):
    if not l:
        continue
    mark = "T" if HASHK.match(l) else " "
    print(f"  {mark} L{i:<4} {l[:88]}")
    n += 1
    if n >= 60:
        break

# pieces
pieces, cur = [], None
for l in lines:
    if not l or LEGEND.search(l):
        continue
    m = HASHK.match(l)
    if m:
        if cur:
            pieces.append(cur)
        cur = {"kind": m.group(1), "opening": l[m.end():].strip()}
    elif cur is not None:
        pass
if cur:
    pieces.append(cur)

site = json.load(open(os.path.join(WIKI, "data", "site_vs_docx.json"), encoding="utf-8"))
titles = site["site_titles"]["总集篇二"]

print(f"\n=== docx 篇目（{len(pieces)}）  vs  站点标题（{len(titles)}） ===")
for i in range(max(len(pieces), len(titles))):
    a = f"P{i+1:02d} [{pieces[i]['kind']}] {pieces[i]['opening'][:34]}" if i < len(pieces) else ""
    b = f"T{i+1:02d} {titles[i]}" if i < len(titles) else ""
    print(f"  {a:<58} | {b}")
