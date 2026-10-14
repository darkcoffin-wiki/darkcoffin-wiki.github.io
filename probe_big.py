"""Find suspicious title-like lines INSIDE the oversized entries.

Hypothesis: some oversized entries actually contain un-split sub-sections whose
headings were not matched by the parser rule.
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SRC = r"E:\黑柩\黑柩AI专供参考\黑柩花絮截止2026.10.md"
WIKI = r"E:\DSHwork\heijiu\wiki"
raw = open(SRC, encoding="utf-8", errors="ignore").read().split("\n")
ents = json.load(open(os.path.join(WIKI, "data", "entries.json"), encoding="utf-8"))["entries"]

BIG = [e for e in ents if e["chars"] > 15000]
BIG.sort(key=lambda e: -e["chars"])
print(f"entries > 15000 chars: {len(BIG)}\n")

KINDS = "剧情花絮|花絮|楔子|画外音|特别环节|四格漫画|玩家之声"

# any heading-ish line
HEADISH = re.compile(r"^\s*(#{1,6}\s+)")
# any line containing a kind word, whatever the decoration
KINDISH = re.compile(KINDS)

for e in BIG:
    a = e["source_line"] - 1
    # end = next entry start (or EOF)
    idx = ents.index(e)
    b = ents[idx + 1]["source_line"] - 1 if idx + 1 < len(ents) else len(raw)
    seg = raw[a:b]
    print("=" * 78)
    print(f"{e['id']}  {e['chars']} chars  L{a+1}-{b}  {e['title']}")

    # 1) heading lines beyond the first
    hs = [(a + j + 1, l.strip()) for j, l in enumerate(seg) if HEADISH.match(l)]
    print(f"  heading lines inside: {len(hs)}")
    for ln, t in hs[:12]:
        print(f"    L{ln:<7} {t[:74]}")

    # 2) lines containing a kind word but NOT at the start (would be missed)
    ks = []
    for j, l in enumerate(seg):
        s = l.strip()
        if j == 0:
            continue
        if KINDISH.search(s):
            # is it a paragraph start? blank line before?
            blank_before = (j == 0) or (not seg[j - 1].strip())
            ks.append((a + j + 1, blank_before, s))
    blankified = [x for x in ks if x[1]]
    print(f"  kind-word lines: {len(ks)}  of which blank-line-preceded: {len(blankified)}")
    for ln, bb, t in blankified[:20]:
        print(f"    L{ln:<7} {'*' if bb else ' '} {t[:72]}")
    print()
