"""parse_site_all.py (clean) — extract every piece from the site's 总集篇 articles.

Known-good rules (validated by counts):
  * a piece starts at a paragraph whose first line begins with one of the eight
    vocabulary words followed by ':'
  * legend lines and definition lines are dropped
  * ONE confirmed off-topic line is dropped by an explicit match. Broad
    heuristics were tried and rejected: they deleted real titles such as
    '花絮：苍鬼会为自己的老公做什么？'
"""
import html as htmlmod
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
RAW = os.path.join(WIKI, "_site_raw")
OUT = os.path.join(WIKI, "data")
os.makedirs(RAW, exist_ok=True)

VOCAB = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"
TITLE = re.compile(r"^\s*(?:#{1,6}\s*)?(?:\*{0,6})?\s*"
                   r"(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?\s*" + VOCAB + r"\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")
DEFLINE = re.compile(r"^\s*" + VOCAB + r"\s*[:：]\s*(表示|代表|指|是|类|用于|见|说明|类似)")
DROP_EXACT = ("剧情花絮：专门为黑柩TRPG主线剧情服务的花絮，真正意义上的花絮。",)

ARTICLES = {
    "总集篇一": 264, "总集篇二": 277, "总集篇三": 289, "总集篇四": 476,
    "总集篇五": 484, "总集篇六": 494, "总集篇七": 535, "总集篇八": 592,
    "北沙篇花絮总集篇": 737, "北沙篇花絮总集篇二": 1015, "长歌总集篇一": 850,
}


def clean(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = htmlmod.unescape(s)
    return re.sub(r"[ \t\u00a0]+", " ", s).strip()


def fetch(aid):
    p = os.path.join(RAW, f"{aid}.html")
    if os.path.exists(p):
        return open(p, encoding="utf-8", errors="ignore").read()
    r = urllib.request.urlopen(
        urllib.request.Request(f"https://darkcoffin.hubingsf.cn/archives/{aid}",
                               headers={"User-Agent": "Mozilla/5.0"}),
        timeout=60).read().decode("utf-8", "ignore")
    open(p, "w", encoding="utf-8").write(r)
    return r


def pieces_of(aid):
    raw = fetch(aid)
    m = re.search(r'(?s)<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>(.*?)(?:<footer|</article>|</main>)', raw)
    body = m.group(1) if m else raw
    body = re.sub(r"(?s)<(script|style|nav|aside)[^>]*>.*?</\1>", "", body)
    body = re.sub(r'(?s)<div[^>]*id="ez-toc-container".*?</div>\s*</div>', "", body)
    body = re.sub(r"(?i)</p\s*>", "\n\n", body)
    body = re.sub(r"(?i)</h[1-6]\s*>", "\n\n", body)
    body = re.sub(r"(?i)<br\s*/?>", "\n", body)

    paras = [clean(p) for p in body.split("\n\n")]
    paras = [p for p in paras if p]

    out, cur = [], None
    for p in paras:
        first = p.split("\n")[0]
        is_title = (TITLE.match(first) and not LEGEND.search(first)
                    and not DEFLINE.match(first) and len(first) < 80
                    and first not in DROP_EXACT)
        if is_title:
            if cur:
                out.append(cur)
            title = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", first).strip()
            cur = {"title": title, "body": []}
            rest = "\n".join(p.split("\n")[1:]).strip()
            if rest:
                cur["body"].append(rest)
        elif cur is not None:
            cur["body"].append(p)
    if cur:
        out.append(cur)
    return out


allp = {}
for name, aid in ARTICLES.items():
    ps = pieces_of(aid)
    allp[name] = ps
    print(f"{name:<20} {len(ps):>3} 篇")

tot = sum(len(v) for v in allp.values())
print(f"\n站点合计: {tot} 篇")
json.dump(allp, open(os.path.join(OUT, "site_pieces.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("wrote data/site_pieces.json")

flat = [(len("\n".join(x["body"])), x["title"]) for v in allp.values() for x in v]
print("\n最短 6 篇:")
for c, t in sorted(flat)[:6]:
    print(f"   {c:>5}  {t}")
