"""Verify the 总集篇二 mapping by keyword hits between each piece's text and
each site title. Prints a score matrix so the mapping is evidenced, not guessed."""
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
    out = []
    for p in re.findall(r"<w:p[^>]*>(.*?)</w:p>", xml, re.S):
        t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
        out.append(htmlmod.unescape(re.sub(r"<[^>]+>", "", t)).strip())
    return out


lines = read_docx(DOCX2)
pieces, cur = [], None
for text in lines:
    if not text or LEGEND.search(text):
        continue
    m = HASHK.match(text)
    if m:
        if cur:
            pieces.append(cur)
        cur = {"kind": m.group(1), "opening": text[m.end():].strip(), "body": []}
    elif cur is not None:
        cur["body"].append(text)
if cur:
    pieces.append(cur)

site = json.load(open(os.path.join(WIKI, "data", "site_vs_docx.json"), encoding="utf-8"))
titles = site["site_titles"]["总集篇二"]

# keywords of each site title: CJK runs of 2+ after the kind prefix
def keys(t):
    s = re.sub(r"^" + VOCAB + r"\s*[:：]\s*", "", t)
    s = re.sub(r"[—\-–·、，。！？（）()【】「」“”]", " ", s)
    return [w for w in re.split(r"\s+", s) if len(w) >= 2]

print(f"pieces {len(pieces)}   site titles {len(titles)}\n")
print("每个片段的文本对每个标题的关键词命中（只列 ≥1 的）\n")
for i, p in enumerate(pieces, 1):
    blob = " ".join([p["opening"]] + p["body"])
    scores = []
    for j, t in enumerate(titles, 1):
        hit = [k for k in keys(t) if k in blob]
        if hit:
            scores.append((len(hit), j, t, hit))
    scores.sort(reverse=True)
    print(f"P{i:02d} [{p['kind']}] 字数{len(blob):>6}  「{p['opening'][:44]}」")
    for sc, j, t, hit in scores[:3]:
        print(f"      T{j:02d} 命中{sc}  {t}   ← {hit}")
    if not scores:
        print("      （无关键词命中）")
    print()
