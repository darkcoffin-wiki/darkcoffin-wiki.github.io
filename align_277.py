"""Option B, step 1: align 总集篇二's 17 untitled docx pieces to the site's 20
titles, by opening text. Report every piece and every site title so gaps show."""
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
        m = re.search(r'<w:pStyle w:val="([^"]+)"', p)
        t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
        t = htmlmod.unescape(re.sub(r"<[^>]+>", "", t)).strip()
        out.append(((m.group(1) if m else ""), t))
    return out


paras = read_docx(DOCX2)
pieces, cur = [], None
for style, text in paras:
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

print(f"总集篇二: {len(pieces)} pieces\n")
for i, p in enumerate(pieces, 1):
    print(f"P{i:02d} [{p['kind']}] {p['opening'][:78]}")

site = json.load(open(os.path.join(WIKI, "data", "site_vs_docx.json"), encoding="utf-8"))
st = site["site_titles"]["总集篇二"]
print(f"\n站点 总集篇二 标题: {len(st)}")
for i, t in enumerate(st, 1):
    print(f"T{i:02d} {t}")

print("\n=== 自动配对（按开头文字重合） ===")
def flat(s):
    return re.sub(r"[\s*#\u3000]", "", s)

used = set()
for i, p in enumerate(pieces, 1):
    op = flat(p["opening"])
    best, score = None, 0
    for t in st:
        tl = flat(re.sub(r"^" + VOCAB + r"\s*[:：]\s*", "", t))
        # longest common prefix-ish score
        s = 0
        for a, b in zip(op, tl):
            if a != b:
                break
            s += 1
        if s > score:
            best, score = t, s
    mark = "★" if score >= 4 else " "
    print(f"{mark} P{i:02d} -> [{score:>2}] {best}")
    if score >= 4:
        used.add(best)

print(f"\n已配对站点标题: {len(used)}/{len(st)}")
print("未被配对的站点标题:")
for t in st:
    if t not in used:
        print("   ", t)
