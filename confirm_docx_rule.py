"""Confirm the title marker: paragraph style. Report, per file, which styles
carry kind-word titles, and count titles under two rules:
  rule-A: style is a 'heading' style AND text starts with a kind word
  rule-B: text starts with a kind word (any style)
"""
import html as htmlmod
import io
import json
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

VOCAB = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"
KIND = re.compile(r"^\s*(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?\s*" + VOCAB + r"\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")
HASHK = re.compile(r"^\s*#\s*黑柩?\s*" + VOCAB)

FILES = [
    r"E:\黑柩\黑柩小说花絮\黑柩TRPG-花絮总集篇一.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩TRPG-花絮总集篇二.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮3.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮4.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮5.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮6.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮7.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮8.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-花絮9.docx",
    r"E:\黑柩\黑柩小说花絮\黑柩-长歌1.docx",
    r"C:\Users\fly12138\AppData\Local\Kingsoft\WPS Cloud Files\userdata\qing\filecache\WPSDrive\240050742\WPS云盘\黑柩-长歌总集篇二.docx",
    r"C:\Users\fly12138\AppData\Local\Kingsoft\WPS Cloud Files\userdata\qing\filecache\WPSDrive\240050742\WPS云盘\黑柩-北沙篇花絮总集篇二.docx",
]


def paras(path):
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


total = 0
report = []
for f in FILES:
    if not os.path.exists(f):
        print(f"{os.path.basename(f):<32} 未找到")
        continue
    ps = paras(f)
    bystyle = defaultdict(list)
    for st, t in ps:
        if t and KIND.match(t) and not LEGEND.search(t):
            bystyle[st].append(t)
    hashlines = [t for st, t in ps if t and HASHK.match(t)]
    nonempty_styles = Counter(st for st, t in ps if t)
    print("=" * 84)
    print(f"{os.path.basename(f)}")
    print(f"  段落样式分布: {nonempty_styles.most_common(6)}")
    print(f"  含类型词的标题行按样式: " +
          " | ".join(f"style={k or '(空)'}×{len(v)}" for k, v in bystyle.items()))
    n = sum(len(v) for v in bystyle.values())
    print(f"  规则B（不看样式）命中: {n}")
    if hashlines:
        print(f"  '#黑柩X' 行: {len(hashlines)}")
    total += n
    report.append({"file": f, "titles_by_style": {k or "": v for k, v in bystyle.items()}})

print("\n" + "=" * 84)
print(f"规则B 合计标题: {total}")

# unique titles and dup check across docx
allt = Counter()
for r in report:
    for k, v in r["titles_by_style"].items():
        for t in v:
            allt[re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", t)] += 1
print(f"唯一标题（去编号）: {len(allt)}")
dups = {t: n for t, n in allt.items() if n > 1}
print(f"跨文件重复: {len(dups)}")
for t, n in list(dups.items())[:20]:
    print(f"   x{n}  {t}")

json.dump(report, open(r"E:\DSHwork\heijiu\wiki\data\docx_sources.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
