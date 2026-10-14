"""Scan every DOCX source for its title structure. Titles only, no body reading."""
import html as htmlmod
import io
import os
import re
import sys
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

VOCAB = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"
KINDLINE = re.compile(r"^\s*" + VOCAB + r"\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")

CANDIDATES = [
    (r"E:\黑柩\黑柩小说花絮\黑柩TRPG-花絮总集篇二.docx", None),
    (r"E:\黑柩\黑柩小说花絮\黑柩TRPG-花絮总集篇一.docx", None),
    (r"E:\黑柩\黑柩小说花絮\黑柩-花絮3.docx", None),
    (r"E:\黑柩\黑柩小说花絮\黑柩-花絮4.docx", None),
    (r"E:\黑柩\黑柩小说花絮\黑柩-花絮5.docx", None),
    (r"E:\黑柩\黑柩小说花絮\黑柩-花絮6.docx", None),
    (r"E:\黑柩\黑柩小说花絮\黑柩-花絮7.docx", None),
    (r"E:\黑柩\黑柩小说花絮\黑柩-花絮8.docx", None),
    (r"E:\黑柩\黑柩小说花絮\黑柩-花絮9.docx", None),
    (r"E:\黑柩\黑柩小说花絮\黑柩-长歌1.docx", None),
    (r"C:\Users\fly12138\AppData\Local\Kingsoft\WPS Cloud Files\userdata\qing\filecache\WPSDrive\240050742\WPS云盘\黑柩-长歌总集篇二.docx", None),
    (r"C:\Users\fly12138\AppData\Local\Kingsoft\WPS Cloud Files\userdata\qing\filecache\WPSDrive\240050742\WPS云盘\黑柩-北沙篇花絮总集篇二.docx", None),
]

# resolve any missing paths by name search first
def find_by_name(name):
    for root in (r"E:\黑柩", r"E:\DSHwork\heijiu"):
        for dp, dn, fn in os.walk(root):
            if name in fn:
                return os.path.join(dp, name)
    return None


def docx_texts(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    paras = re.findall(r"<w:p[^>]*>(.*?)</w:p>", xml, re.S)
    out = []
    for p in paras:
        # keep paragraph style to detect Heading1
        style = ""
        m = re.search(r'<w:pStyle w:val="([^"]+)"', p)
        if m:
            style = m.group(1)
        t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
        t = htmlmod.unescape(re.sub(r"<[^>]+>", "", t)).strip()
        out.append((style, t))
    return out


print(f"{'文件':<34}{'段':>6}{'标题行':>7}{'标题样式':>9}  前 6 个标题")
print("-" * 110)
summary = []
for path, _ in CANDIDATES:
    base = os.path.basename(path)
    if not os.path.exists(path):
        # try to locate by filename anywhere
        found = find_by_name(base)
        if found:
            path = found
        else:
            print(f"{base:<34}{'—':>6}{'—':>7}{'—':>9}  未找到")
            continue
    try:
        paras = docx_texts(path)
    except Exception as e:
        print(f"{base:<34}  读取失败: {e}")
        continue

    titled = [(st, t) for st, t in paras if t and KINDLINE.match(t) and not LEGEND.search(t)]
    styled = [st for st, t in paras if t and st.lower().startswith(("heading", "标题"))]
    print(f"{base:<34}{len(paras):>6}{len(titled):>7}{len(styled):>9}  " +
          " | ".join(t[:26] for _, t in titled[:6]))
    summary.append({"file": path, "name": base, "paras": len(paras),
                    "titles": [t for _, t in titled], "styled": len(styled)})

print("\n" + "=" * 110)
tot = sum(len(s["titles"]) for s in summary)
print(f"合计标题行: {tot}  （{len(summary)} 份文件）")

import json
json.dump(summary, open(r"E:\DSHwork\heijiu\wiki\data\docx_sources.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# duplicate titles across docx sources
from collections import Counter
allt = Counter()
for s in summary:
    for t in s["titles"]:
        allt[t] += 1
dups = {t: n for t, n in allt.items() if n > 1}
print(f"\n重复标题（跨文件）: {len(dups)}")
for t, n in list(dups.items())[:25]:
    print(f"   x{n}  {t}")

print(f"\n唯一标题: {len(allt)}")
