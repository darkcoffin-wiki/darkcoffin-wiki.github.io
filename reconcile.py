"""Reconcile: official title list (from the site) vs the source markdown.

Method:
  * for each official title, find the FIRST occurrence in the md after the
    previous title's position (order-preserving greedy match)
  * report titles not found, and markdown title-lines not claimed by any
    official title (candidates for unpublished pieces)
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SRC = r"E:\黑柩\黑柩AI专供参考\黑柩花絮截止2026.10.md"
WIKI = r"E:\DSHwork\heijiu\wiki"
data = json.load(open(os.path.join(WIKI, "data", "site_titles.json"), encoding="utf-8"))
official = data["titles"]

text = open(SRC, encoding="utf-8", errors="ignore").read()
low = text.lower()


def norm(s):
    s = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", s)
    s = re.sub(r"[\s\u3000]", "", s)
    s = re.sub(r"[（）()【】\[\]「」『』“”\"'‘’]", "", s)
    s = s.replace("——", "-").replace("—", "-")
    return s


# loose index of the md for each official title
found, missing = {}, []
cursor = 0
for t in official:
    key = norm(t)
    hit = None
    # search loose: allow '***' decorations between pieces of the title
    pat = re.compile(r"\*{0,6}\s*".join(re.escape(c) for c in key))
    for m in pat.finditer(text):
        if m.start() >= cursor:
            hit = m
            break
    if not hit:
        m = pat.search(text)
        hit = m
    if hit:
        found[t] = hit.start()
        cursor = hit.start()
    else:
        missing.append(t)

print(f"official titles      : {len(official)}")
print(f"matched in markdown  : {len(found)}")
print(f"NOT matched          : {len(missing)}")
for t in missing:
    print(f"   ?? {t}")

# ---- markdown title-like lines not claimed ----
# any line whose de-decoration starts with a kind + colon
KIND = re.compile(r"^(?:#{1,6}\s*)?\*{0,6}\s*(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?"
                  r"\*{0,6}\s*(剧情花絮|花絮|楔子|画外音|长歌|特别内容|四格|特别环节|四格漫画)\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")

md_lines = []
pos = 0
for l in text.split("\n"):
    if KIND.match(l) and not LEGEND.search(l):
        md_lines.append((pos, l.strip()))
    pos += len(l) + 1

claimed = set()
for t, p in found.items():
    # find the md line nearest to p
    best, bd = None, 10 ** 9
    for lp, lt in md_lines:
        d = abs(lp - p)
        if d < bd:
            best, bd = (lp, lt), d
    if bd < 400:
        claimed.add(best[0])

unclaimed = [(p, l) for p, l in md_lines if p not in claimed]
print(f"\nmd title-like lines        : {len(md_lines)}")
print(f"claimed by official titles : {len(claimed)}")
print(f"UNCLAIMED (unpublished?)   : {len(unclaimed)}")
for p, l in unclaimed:
    print(f"   L{text[:p].count(chr(10)) + 1:<7} {l[:84]}")

json.dump({"missing_official": missing,
           "unclaimed_md": [{"line": text[:p].count("\n") + 1, "text": l} for p, l in unclaimed],
           "matched": len(found), "official": len(official)},
          open(os.path.join(WIKI, "data", "reconcile.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\nwrote data/reconcile.json")
