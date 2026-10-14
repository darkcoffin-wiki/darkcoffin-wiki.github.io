"""Decisive method: rewrite the site articles to markdown, run THE SAME parser
on them, and diff the resulting title lists against our local split.

The site HTML drops the '#'/'**' decorations, so the site's own split is the
cleanest expression of the author's intent.
"""
import html as htmlmod
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

UA = {"User-Agent": "Mozilla/5.0"}
WIKI = r"E:\DSHwork\heijiu\wiki"
OUTDIR = os.path.join(WIKI, "_site_text")
os.makedirs(OUTDIR, exist_ok=True)

ARTICLES = {
    "总集篇一": 264, "总集篇二": 277, "总集篇三": 289, "总集篇四": 476,
    "总集篇五": 484, "总集篇六": 494, "总集篇七": 535, "总集篇八": 592,
    "北沙篇花絮总集篇": 737, "北沙篇花絮总集篇二": 1015, "长歌总集篇一": 850,
}

VOCAB8 = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"
TITLE = re.compile(r"^\s*" + VOCAB8 + r"\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")


def fetch_text(aid):
    raw = urllib.request.urlopen(
        urllib.request.Request(f"https://darkcoffin.hubingsf.cn/archives/{aid}", headers=UA),
        timeout=45).read().decode("utf-8", "ignore")
    # isolate the article body: from the first <p> after entry-content to </article>
    m = re.search(r'(?s)<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>(.*?)(?:<footer|</article>)', raw)
    body = m.group(1) if m else raw
    body = re.sub(r"(?s)<(script|style|nav|aside)[^>]*>.*?</\1>", "", body)
    body = re.sub(r"(?s)<div[^>]*id=\"ez-toc-container\".*?</div>\s*</div>", "", body)
    # paragraph-level conversion
    body = re.sub(r"(?i)</p\s*>", "\n\n", body)
    body = re.sub(r"(?i)<br\s*/?>", "\n", body)
    body = re.sub(r"(?i)</h[1-6]\s*>", "\n\n", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = htmlmod.unescape(body)
    body = re.sub(r"[ \t\u00a0]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


for name, aid in ARTICLES.items():
    try:
        txt = fetch_text(aid)
    except Exception as e:
        print(f"!! {name}: {e}")
        continue
    open(os.path.join(OUTDIR, f"{name}.md"), "w", encoding="utf-8").write(txt)

    # run the same title rule on blank-line-separated paragraphs
    paras = [p.strip() for p in txt.split("\n\n")]
    titles = []
    for p in paras:
        first = p.split("\n")[0].strip()
        if TITLE.match(first) and not LEGEND.search(first):
            titles.append(first)
    print(f"{name:<22} paras {len(paras):>5}  titles {len(titles):>3}")

print("\nwrote site texts to", OUTDIR)
