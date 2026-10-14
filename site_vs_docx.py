"""1) Get 总集篇二's piece titles from the site (strong/ez-toc, eight-word method).
2) Map each DOCX source to a site article by title overlap.
3) List docx titles that are NOT on the site (= unpublished).
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
RAW = os.path.join(WIKI, "_site_raw")
os.makedirs(RAW, exist_ok=True)

VOCAB = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"
TITLEISH = re.compile(VOCAB + r"\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")

ARTICLES = {
    "总集篇一": 264, "总集篇二": 277, "总集篇三": 289, "总集篇四": 476,
    "总集篇五": 484, "总集篇六": 494, "总集篇七": 535, "总集篇八": 592,
    "北沙篇花絮总集篇": 737, "北沙篇花絮总集篇二": 1015, "长歌总集篇一": 850,
}


def raw_of(name, aid):
    p = os.path.join(RAW, f"{aid}.html")
    if os.path.exists(p):
        return open(p, encoding="utf-8", errors="ignore").read()
    r = urllib.request.urlopen(
        urllib.request.Request(f"https://darkcoffin.hubingsf.cn/archives/{aid}", headers=UA),
        timeout=45).read().decode("utf-8", "ignore")
    open(p, "w", encoding="utf-8").write(r)
    return r


def clean(s):
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", "", s))).strip()


# ---------- 1) per-article titles: ez-toc + headings + strong + p ----------
site_titles = {}
for name, aid in ARTICLES.items():
    raw = raw_of(name, aid)
    found = []

    for m in re.finditer(r'<a[^>]*class="[^"]*ez-toc-link[^"]*"[^>]*>(.*?)</a>', raw, re.S):
        found.append(clean(m.group(1)))
    for tag in ("h1", "h2", "h3"):
        for m in re.finditer(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), raw, re.S):
            found.append(clean(m.group(1)))
    # inline <strong>花絮：</strong>标题   (the WordPress-classic pattern)
    for m in re.finditer(r"<strong>\s*(" + VOCAB + r"\s*[:：])\s*</strong>\s*([^<]{0,60})", raw):
        found.append((m.group(1) + m.group(2)).strip())
    for m in re.finditer(r"<p[^>]*>\s*(" + VOCAB + r"\s*[:：][^<]{0,60})", raw):
        found.append(clean(m.group(1)))

    keep = []
    for t in found:
        t = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", t).strip()
        t = re.sub(r"\*+", "", t).strip()
        if not t or LEGEND.search(t) or not TITLEISH.match(t):
            continue
        if t not in keep:
            keep.append(t)
    site_titles[name] = keep
    print(f"{name:<20} {len(keep):>3} 标题")

# ---------- 2) 总集篇二 detail ----------
print("\n=== 总集篇二 的标题（站点） ===")
for i, t in enumerate(site_titles.get("总集篇二", []), 1):
    print(f"  T{i:02d}  {t}")

# ---------- 3) docx vs site ----------
docx = json.load(open(os.path.join(WIKI, "data", "docx_sources.json"), encoding="utf-8"))


def norm(t):
    t = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", t)
    t = re.sub(r"^" + VOCAB + r"\s*[:：]\s*", "", t)
    t = t.replace("*", "")
    t = re.sub(r"[\s\u3000]", "", t)
    t = re.sub(r"[（）()【】\[\]「」『』“”\"'‘’、，,。.！!？?：:]", "", t)
    return t.replace("——", "").replace("—", "").replace("-", "")


site_all = {}
for name, ts in site_titles.items():
    for t in ts:
        site_all.setdefault(norm(t), []).append((name, t))

print("\n=== docx → 站点文章 对表 ===")
report = {}
for entry in docx:
    name = os.path.basename(entry["file"])
    titles = []
    for st, vs in entry.get("titles_by_style", {}).items():
        titles += vs
    if not titles:
        continue
    hit = {}
    for t in titles:
        for art, tt in site_all.get(norm(t), []):
            hit[art] = hit.get(art, 0) + 1
    best = sorted(hit.items(), key=lambda kv: -kv[1])[:3]
    report[name] = {"count": len(titles), "site_match": best}
    print(f"  {name:<34} {len(titles):>3} 篇 → " +
          (" | ".join(f"{a}:{c}" for a, c in best) or "站点无对应"))

print("\n=== docx 有、站点没有（= 未发布）===")
unpub = []
for entry in docx:
    name = os.path.basename(entry["file"])
    for st, vs in entry.get("titles_by_style", {}).items():
        for t in vs:
            if norm(t) not in site_all:
                unpub.append((name, t))
for name, t in unpub:
    print(f"  [{name[:22]:<22}] {t}")
print(f"\n未发布合计: {len(unpub)}")

docx_all = {}
for entry in docx:
    for st, vs in entry.get("titles_by_style", {}).items():
        for t in vs:
            docx_all.setdefault(norm(t), t)
print(f"\ndocx 唯一标题: {len(docx_all)}   站点唯一标题: {len(site_all)}")
print("站点有、docx 没有:")
for k, v in site_all.items():
    if k not in docx_all:
        print(f"   {v[0][1]}   [{v[0][0]}]")

json.dump({"site_titles": site_titles, "unpublished": unpub,
           "docx_to_site": report},
          open(os.path.join(WIKI, "data", "site_vs_docx.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\nwrote data/site_vs_docx.json")
