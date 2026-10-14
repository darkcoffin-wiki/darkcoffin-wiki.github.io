"""Report what the two fixed rules produced vs the old 144-entry parse."""
import io
import json
import os
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
ents = json.load(open(os.path.join(WIKI, "data", "entries.json"), encoding="utf-8"))["entries"]
print(f"entries now: {len(ents)}")
print("by kind:", Counter(e["kind"] for e in ents).most_common())

sizes = sorted(e["chars"] for e in ents)
n = len(sizes)
print(f"\nsize: min {sizes[0]}  p25 {sizes[n//4]}  median {sizes[n//2]}  "
      f"p75 {sizes[3*n//4]}  p90 {sizes[int(n*.9)]}  max {sizes[-1]}")

# entries created by the '#黑柩X' rule: titles that are not normal titles
print("\n=== entries whose title looks like a fragment (starts mid-sentence) ===")
frag = 0
for e in ents:
    t = re.sub(r"^(剧情花絮|花絮|楔子|画外音|特别环节|四格漫画|玩家之声)\s*[:：]?\s*", "", e["title"])
    if len(t) > 18 or t.endswith(("。", "，")) or "↓" in t or "…" in t:
        print(f"  {e['id']} {e['chars']:>6}  {e['title'][:66]}")
        frag += 1
print(f"  total: {frag}")

# small entries (<1000) are suspicious too
print("\n=== small entries (<1000 chars) ===")
for e in sorted(ents, key=lambda x: x["chars"])[:15]:
    print(f"  {e['id']} {e['chars']:>5}  {e['title'][:66]}")
