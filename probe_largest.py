"""Deep probe of the largest remaining entry (L23348, 64226 chars).
Also test whether '#黑柩花絮' style markers exist corpus-wide."""
import io
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SRC = r"E:\黑柩\黑柩AI专供参考\黑柩花絮截止2026.10.md"
lines = open(SRC, encoding="utf-8", errors="ignore").read().split("\n")

# ---------- A. corpus-wide: hash-prefixed markers ----------
print("=== corpus-wide marker census ===")
for pat, label in [
    (r"#黑柩\s*(花絮|楔子|画外音|前言|注意)", "#黑柩X（无空格）"),
    (r"#\s*黑柩\s*(花絮|楔子|画外音)", "# 黑柩X"),
    (r"^\s*#\s*[^#\s]", "行首单井号"),
    (r"\*{4}", "四个星号"),
]:
    print(f"  {label}: {len(re.findall(pat, '\n'.join(lines)))}")

print("\n=== lines starting with '#黑柩' (first 20) ===")
hits = [(i + 1, l.strip()) for i, l in enumerate(lines) if l.strip().startswith("#黑柩")]
print(f"  total: {len(hits)}")
for ln, t in hits[:20]:
    print(f"    L{ln:<7} {t[:84]}")

# ---------- B. the 64226-char entry ----------
A, B = 23348 - 1, 27261 - 1
seg = lines[A:B]
print(f"\n=== largest entry L{A+1}-{B}  ({sum(len(x) for x in seg)} chars) ===")

# any line that is short and standalone (possible hidden title)
print("\n--- short standalone lines (<40 chars, non-empty, not dialogue) ---")
n = 0
for j, l in enumerate(seg):
    s = l.strip().strip("*").strip()
    if 0 < len(s) < 40 and not re.match(r"^\*\*[^*]+\*\*\s*[:：]", l):
        print(f"  L{A+j+1:<7} [{len(s):>2}] {s[:60]}")
        n += 1
        if n >= 40:
            break
print(f"  ... {n} shown")

print("\n--- heading-ish lines (start with # or 4+ asterisks) ---")
n = 0
for j, l in enumerate(seg):
    if re.match(r"^\s*#{1,6}", l) or re.search(r"\*{4}", l):
        print(f"  L{A+j+1:<7} {l.strip()[:80]}")
        n += 1
        if n >= 30:
            break
print(f"  ... {n} shown")

print("\n--- first 25 lines of the entry ---")
for l in seg[:25]:
    print("   ", l.strip()[:92])

print("\n--- scene dividers in the entry ---")
div = [j for j, l in enumerate(seg) if re.match(r"^\s*\**——\**\s*$", l)]
print(f"  分隔符 '——' 独占行: {len(div)}")
print(f"  平均间隔: {len(seg) // max(1, len(div))} 行")
for j in div[:15]:
    print(f"    L{A+j+1}")
