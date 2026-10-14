"""Probe the '#黑柩花絮' lines: are they entry starts without a colon?
And what is the empty-looking block after L889?"""
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SRC = r"E:\黑柩\黑柩AI专供参考\黑柩花絮截止2026.10.md"
lines = open(SRC, encoding="utf-8", errors="ignore").read().split("\n")

hits = [i for i, l in enumerate(lines) if l.strip().startswith("#黑柩")]
print(f"'#黑柩' lines: {len(hits)}\n")

for i in hits:
    prev_blank = (i == 0) or (not lines[i - 1].strip())
    print(f"L{i+1:<7} blank_before={prev_blank}  {lines[i].strip()[:92]}")

print("\n=== context around the first few ===")
for i in hits[:3]:
    print(f"\n--- L{i+1} context (3 before / 5 after) ---")
    for j in range(max(0, i - 3), min(len(lines), i + 6)):
        tag = ">>>" if j == i else "   "
        print(f"  {tag} L{j+1:<7} {lines[j].strip()[:88]}")

print("\n=== the '#黑柩花絮' alone line (L889) and what follows ===")
i = 888
for j in range(i, min(len(lines), i + 12)):
    print(f"  L{j+1:<7} len={len(lines[j]):>4}  {lines[j].strip()[:84]}")
print("  ...")
print("  lines 889..1030 non-blank count:",
      sum(1 for j in range(888, 1030) if lines[j].strip()))
print("  chars 889..1030:", sum(len(lines[j]) for j in range(888, 1030)))

# which entries currently swallow these lines?
import json, os
WIKI = r"E:\DSHwork\heijiu\wiki"
ents = json.load(open(os.path.join(WIKI, "data", "entries.json"), encoding="utf-8"))["entries"]
print("\n=== which entry contains each '#黑柩' line (by old parse) ===")
for i in hits:
    ln = i + 1
    owner = None
    for e in ents:
        if e["source_line"] <= ln:
            owner = e
        else:
            break
    print(f"  L{ln:<7} -> {owner['id']} {owner['title'][:44]}")
