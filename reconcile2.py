"""Reconcile v2: normalise BOTH sides identically (strip numbering & all
decoration), then order-preserving greedy match."""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SRC = r"E:\黑柩\黑柩AI专供参考\黑柩花絮截止2026.10.md"
WIKI = r"E:\DSHwork\heijiu\wiki"
official = json.load(open(os.path.join(WIKI, "data", "site_titles.json"),
                          encoding="utf-8"))["titles"]
text = open(SRC, encoding="utf-8", errors="ignore").read()

NUM = re.compile(r"^(?:#{1,6}\s*)?(?:\*{0,6})?\s*(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?(?:\*{0,6})?\s*")


def strip_num(s):
    s = re.sub(r"^#{1,6}\s*", "", s)
    s = re.sub(r"^\*+", "", s).strip()
    s = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", s)
    s = re.sub(r"^\d+[、.．]\s*", "", s)
    s = re.sub(r"^\*+", "", s).strip()
    return s


def norm(s):
    s = strip_num(s)
    s = re.sub(r"[\s\u3000]", "", s)
    s = re.sub(r"[（）()【】\[\]「」『』“”\"'‘’、，,。.！!？?：:]", "", s)
    s = s.replace("——", "").replace("—", "").replace("-", "")
    s = s.replace("*", "")
    return s


# locate every md title-like line
KIND = re.compile(r"^(?:#{1,6}\s*)?\*{0,6}\s*(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?"
                  r"\*{0,6}\s*(剧情花絮|花絮|楔子|画外音|长歌|特别内容|四格|特别环节|四格漫画)\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")

md = []
off = 0
for line in text.split("\n"):
    if KIND.match(line) and not LEGEND.search(line):
        md.append({"line": text[:off].count("\n") + 1, "off": off,
                   "raw": line.strip(), "norm": norm(line)})
    off += len(line) + 1

print(f"md title-like lines: {len(md)}")
norm_to_md = {}
for m in md:
    norm_to_md.setdefault(m["norm"], []).append(m)

matched, missing = [], []
for t in official:
    key = norm(t)
    cands = norm_to_md.get(key, [])
    if cands:
        matched.append((t, cands[0]))
    else:
        # fuzzy: official title is a prefix of an md title (or vice versa)
        fz = [m for m in md if m["norm"].startswith(key) or key.startswith(m["norm"])]
        if fz:
            matched.append((t, fz[0]))
        else:
            missing.append(t)

claimed = {m["line"] for _, m in matched}
unclaimed = [m for m in md if m["line"] not in claimed]

print(f"official titles    : {len(official)}")
print(f"matched            : {len(matched)}")
print(f"missing (not in md): {len(missing)}")
for t in missing:
    print(f"   MISS  {t}")

print(f"\nmd titles total    : {len(md)}")
print(f"claimed            : {len(claimed)}")
print(f"unclaimed          : {len(unclaimed)}  (候选：未发布 / 站点无对应标题)")
for m in unclaimed:
    print(f"   L{m['line']:<7} {strip_num(m['raw'])[:80]}")

json.dump({"matched": [{"official": t, "md_line": m["line"]} for t, m in matched],
           "missing_official": missing,
           "unclaimed_md": [{"line": m["line"], "title": strip_num(m["raw"])} for m in unclaimed]},
          open(os.path.join(WIKI, "data", "reconcile.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\nwrote data/reconcile.json")
