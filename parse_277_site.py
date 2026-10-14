"""Parse the SITE version of 总集篇二 directly with the eight-word rule.

The site text is the published, corrected version — so this yields the pieces
with their proper titles and no mapping needed.
"""
import html as htmlmod
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
RAW = os.path.join(WIKI, "_site_raw", "277.html")

VOCAB = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"
TITLE = re.compile(r"^\s*(?:#{1,6}\s*)?(?:\*{0,6})?\s*"
                   r"(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?\s*" + VOCAB + r"\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")


def clean(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = htmlmod.unescape(s)
    return re.sub(r"[ \t\u00a0]+", " ", s).strip()


raw = open(RAW, encoding="utf-8", errors="ignore").read()

# isolate the article body
m = re.search(r'(?s)<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>(.*?)(?:<footer|</article>|</main>)', raw)
body = m.group(1) if m else raw
body = re.sub(r"(?s)<(script|style|nav|aside)[^>]*>.*?</\1>", "", body)
# drop the ez-toc block so its links don't become content
body = re.sub(r'(?s)<div[^>]*id="ez-toc-container".*?</div>\s*</div>', "", body)

# paragraphs: keep block boundaries
body = re.sub(r"(?i)</p\s*>", "\n\n", body)
body = re.sub(r"(?i)</h[1-6]\s*>", "\n\n", body)
body = re.sub(r"(?i)<br\s*/?>", "\n", body)

paras = [clean(p) for p in body.split("\n\n")]
paras = [p for p in paras if p]

print(f"site 总集篇二 paragraphs: {len(paras)}\n")

pieces, cur = [], None
for p in paras:
    first = p.split("\n")[0]
    if TITLE.match(first) and not LEGEND.search(first) and len(first) < 70:
        if cur:
            pieces.append(cur)
        cur = {"title": re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", first).strip(),
               "body": []}
        rest = "\n".join(p.split("\n")[1:]).strip()
        if rest:
            cur["body"].append(rest)
    elif cur is not None:
        cur["body"].append(p)
if cur:
    pieces.append(cur)

print(f"pieces parsed from the site: {len(pieces)}\n")
for i, x in enumerate(pieces, 1):
    blob = "\n".join(x["body"])
    print(f"P{i:02d} {x['title']}")
    print(f"      {len(blob)} 字   「{blob[:72]}」")

json.dump(pieces, open(os.path.join(WIKI, "data", "site_277_pieces.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\nwrote data/site_277_pieces.json")
