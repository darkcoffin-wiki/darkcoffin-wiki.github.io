"""Feasibility probe for the author's proposal: build the wiki from the SITE,
using h1/h2 as piece boundaries.

Checks per 总集篇 article:
  * how many <h1>/<h2> pieces exist
  * how many inline <strong>kind：</strong> title markers exist (old style)
  * whether every piece has a usable boundary
Also inspects the unpublished docx.
"""
import html as htmlmod
import io
import os
import re
import sys
import urllib.request
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

UA = {"User-Agent": "Mozilla/5.0"}
SNAP = r"E:\DSHwork\heijiu\wiki\_site_raw"
os.makedirs(SNAP, exist_ok=True)

ARTICLES = {
    "总集篇一": 264, "总集篇二": 277, "总集篇三": 289, "总集篇四": 476,
    "总集篇五": 484, "总集篇六": 494, "总集篇七": 535, "总集篇八": 592,
    "北沙篇花絮总集篇": 737, "北沙篇花絮总集篇二": 1015, "长歌总集篇一": 850,
}
VOCAB = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"


def body_of(raw):
    m = re.search(r'(?s)<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>(.*?)(?:<footer|</article>|</main>)', raw)
    return m.group(1) if m else raw


print(f"{'文章':<20}{'h1':>4}{'h2':>4}{'h3':>4}{'strong标题':>10}{'p标题':>7}  判定")
print("-" * 74)
rows = []
for name, aid in ARTICLES.items():
    p = os.path.join(SNAP, f"{aid}.html")
    if os.path.exists(p):
        raw = open(p, encoding="utf-8", errors="ignore").read()
    else:
        raw = urllib.request.urlopen(
            urllib.request.Request(f"https://darkcoffin.hubingsf.cn/archives/{aid}", headers=UA),
            timeout=45).read().decode("utf-8", "ignore")
        open(p, "w", encoding="utf-8").write(raw)
    body = body_of(raw)

    h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    h2 = re.findall(r"<h2[^>]*>(.*?)</h2>", body, re.S)
    h3 = re.findall(r"<h3[^>]*>(.*?)</h3>", body, re.S)

    def cl(x):
        return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", "", x))).strip()

    h1c = [cl(x) for x in h1 if VOCAB in cl(x)]
    h2c = [cl(x) for x in h2 if VOCAB in cl(x)]

    # inline <strong>花絮：</strong> style
    st = re.findall(r"<strong>\s*" + VOCAB + r"\s*[:：]\s*</strong>", body)
    # <p>花絮：</p> style
    pt = re.findall(r"<p[^>]*>\s*" + VOCAB + r"\s*[:：]", body)

    verdict = []
    if h1c:
        verdict.append(f"h1×{len(h1c)}")
    if h2c:
        verdict.append(f"h2×{len(h2c)}")
    if st:
        verdict.append(f"strong×{len(st)}")
    if pt:
        verdict.append(f"p×{len(pt)}")
    rows.append((name, len(h1c), len(h2c), len(h3), len(st), len(pt)))
    print(f"{name:<20}{len(h1c):>4}{len(h2c):>4}{len(h3):>4}{len(st):>10}{len(pt):>7}  {' + '.join(verdict) or '无标题标记!'}")

# ---- the unpublished docx ----
print("\n" + "=" * 74)
DOCX = r"C:\Users\fly12138\AppData\Local\Kingsoft\WPS Cloud Files\userdata\qing\filecache\WPSDrive\240050742\WPS云盘\黑柩-长歌总集篇二.docx"
print("unpublished docx:")
if os.path.exists(DOCX):
    print("  exists:", os.path.getsize(DOCX), "bytes")
    with zipfile.ZipFile(DOCX) as z:
        names = z.namelist()
        print("  zip entries:", len(names))
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    paras = re.findall(r"<w:p[^>]*>(.*?)</w:p>", xml, re.S)
    texts = []
    for p in paras:
        t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
        t = htmlmod.unescape(re.sub(r"<[^>]+>", "", t)).strip()
        if t:
            texts.append(t)
    print(f"  paragraphs with text: {len(texts)}")
    kinds = [t for t in texts if re.match(r"^\s*" + VOCAB + r"\s*[:：]", t)]
    print(f"  lines starting with a kind: {len(kinds)}")
    for k in kinds[:40]:
        print("    ", k[:80])
else:
    print("  NOT FOUND at that path")
