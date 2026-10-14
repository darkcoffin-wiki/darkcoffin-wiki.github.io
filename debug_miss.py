"""Debug: why did the parser miss the inner headings of hx-038 (L2645, L2754, ...)?"""
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SRC = r"E:\黑柩\黑柩AI专供参考\黑柩花絮截止2026.10.md"
raw = open(SRC, encoding="utf-8", errors="ignore").read().split("\n")

KINDS = r"(剧情花絮|花絮|楔子|画外音|特别环节|四格漫画|玩家之声)"
ENTRY = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*"
    r"(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?"
    r"(?:\*\*)?\s*" + KINDS + r"\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")

for ln in [2569, 2645, 2754, 2899, 3107, 3234, 4128, 30718]:
    i = ln - 1
    l = raw[i]
    prev = raw[i - 1] if i else ""
    m = ENTRY.match(l)
    print(f"L{ln}")
    print(f"   raw  : {l[:88]!r}")
    print(f"   prev : {prev[:50]!r}  (blank={not prev.strip()})")
    print(f"   match: {m.group(0)[:50]!r}  kind={m.group(1) if m else None}")
    print(f"   legend_hit: {bool(LEGEND.search(l))}")
    print(f"   => accepted: {bool(m and (not prev.strip()) and not LEGEND.search(l))}")
    print()
