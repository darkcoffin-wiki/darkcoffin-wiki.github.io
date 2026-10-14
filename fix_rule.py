"""Fix the parser rule: allow any run of '*' (2 or 4) as decoration.
Re-measure entries and coverage, and list the newly recovered ones."""
import io
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SRC = r"E:\黑柩\黑柩AI专供参考\黑柩花絮截止2026.10.md"
lines = open(SRC, encoding="utf-8", errors="ignore").read().split("\n")
TOT = sum(len(l) for l in lines)

KINDS = r"(剧情花絮|花絮|楔子|画外音|特别环节|四格漫画|玩家之声)"
OLD = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*"
    r"(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?"
    r"(?:\*\*)?\s*" + KINDS + r"\s*[:：]")
NEW = re.compile(
    r"^\s*(?:#{1,6}\s*)?\*{0,6}\s*"
    r"(?:[一二三四五六七八九十百]+[、.．]\s*|\d+[、.．]\s*)?"
    r"\*{0,6}\s*" + KINDS + r"\s*[:：]")
LEGEND = re.compile(r"(表示在|代表在未来|代表在平行|已经发生或很可能|未来的黑柩TRPG|平行世界线中可能发生)")


def scan(pat):
    out = []
    for i, l in enumerate(lines):
        m = pat.match(l)
        if not m:
            continue
        at_b = (i == 0) or (not lines[i - 1].strip())
        if at_b and not LEGEND.search(l):
            out.append((i, m.group(1)))
    return out


old = scan(OLD)
new = scan(NEW)
print(f"OLD rule: {len(old)} entries")
print(f"NEW rule: {len(new)} entries   (+{len(new) - len(old)})")

oldset = {i for i, _ in old}
extra = [(i, k) for i, k in new if i not in oldset]
print(f"\n=== {len(extra)} newly recovered entries ===")
for i, k in extra:
    print(f"  L{i+1:<7} {k:<5} {lines[i].strip()[:72]}")

# sizes
starts = [i for i, _ in new] + [len(lines)]
sizes = [sum(len(x) for x in lines[a:b]) for a, b in zip(starts, starts[1:])]
covered = sum(sizes)
print(f"\ncoverage: {covered} / {TOT} = {covered / TOT * 100:.1f}%")
ss = sorted(sizes)
n = len(ss)
print("size distribution:")
for p in (0, 10, 25, 50, 75, 90, 95, 99, 100):
    print(f"  p{p:<3} {ss[min(n - 1, int(n * p / 100))]}")
print(f"\n>15000 chars: {sum(1 for s in sizes if s > 15000)}")
print(f">20000 chars: {sum(1 for s in sizes if s > 20000)}")
print("\n=== entries still > 15000 chars ===")
for a, b, c in zip(starts, starts[1:], sizes):
    if c > 15000:
        print(f"  L{a+1:<7} {c:>7}  {lines[a].strip()[:66]}")

print("\nby kind:", Counter(k for _, k in new).most_common())
