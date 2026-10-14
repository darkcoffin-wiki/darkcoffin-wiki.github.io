"""Is 黑柩花絮截止2026.10.docx the consolidated authoritative source?
Check its title markup (styles / inline markers) and count pieces."""
import html as htmlmod
import io
import os
import re
import sys
import zipfile
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DOCX = (r"C:\Users\fly12138\AppData\Local\Kingsoft\WPS Cloud Files\userdata\qing"
        r"\filecache\WPSDrive\240050742\WPS云盘\黑柩花絮截止2026.10.docx")
VOCAB = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"
KIND_AT_START = re.compile(r"^\s*(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?" + VOCAB + r"\s*[:：]")
TITLEISH = re.compile(VOCAB + r"\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")
DEFLINE = re.compile(r"^\s*" + VOCAB + r"\s*[:：]\s*(表示|代表|指|是|类|用于|见|说明|类似)")
HASHK = re.compile(r"^\s*#\s*黑柩?\s*(?:#\s*)?" + VOCAB + r"\s*#?\s*")

print("exists:", os.path.exists(DOCX), os.path.getsize(DOCX) if os.path.exists(DOCX) else "")
with zipfile.ZipFile(DOCX) as z:
    xml = z.read("word/document.xml").decode("utf-8", "ignore")

paras = []
for p in re.findall(r"<w:p[^>]*>(.*?)</w:p>", xml, re.S):
    m = re.search(r'<w:pStyle w:val="([^"]+)"', p)
    style = m.group(1) if m else ""
    t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
    t = htmlmod.unescape(re.sub(r"<[^>]+>", "", t)).strip()
    paras.append((style, t))

print("paragraphs:", len(paras))
print("style distribution:", Counter(s for s, t in paras if t).most_common(8))

styles_with_titles = Counter()
titles = []
for style, t in paras:
    if not t or LEGEND.search(t) or DEFLINE.match(t):
        continue
    if (style and KIND_AT_START.match(t)) or HASHK.match(t) or \
       (style and TITLEISH.search(t) and len(t) < 60):
        styles_with_titles[style or "(空)"] += 1
        titles.append((style, t))

print("\ntitles by style:", styles_with_titles.most_common())
print(f"total candidate titles: {len(titles)}")
print("\nfirst 40 titles:")
for st, t in titles[:40]:
    print(f"   [{st or '-':<4}] {t[:76]}")

# style-2 only count (the reliable marker)
s2 = [t for st, t in titles if st == "2"]
print(f"\nstyle='2' titles: {len(s2)}")
