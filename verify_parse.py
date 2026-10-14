"""Spot-check: did the body cleanup damage the source? Compare a parsed entry
against the raw lines it came from."""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
SRC = r"E:\黑柩\黑柩AI专供参考\黑柩花絮截止2026.10.md"
raw = open(SRC, encoding="utf-8", errors="ignore").read().split("\n")
ents = json.load(open(os.path.join(WIKI, "data", "entries.json"), encoding="utf-8"))["entries"]

# character-level integrity: strip all markdown/whitespace and compare lengths
def bare(s):
    return re.sub(r"[\s\*#\-—|]", "", s)

bad = 0
for e in ents:
    p = os.path.join(WIKI, "source", e["file"])
    t = open(p, encoding="utf-8").read()
    body = t.split("---\n\n", 1)[1] if "---\n\n" in t else t
    # raw slice
    a = raw.index(next(l for l in raw if l.strip() and False)) if False else None
    rawseg = "\n".join(raw[e["source_line"]: e["source_line"] + 4000])
    # compare only the first 4000 raw lines worth is unreliable; compare bare length ratio
    rb, bb = len(bare(rawseg)), len(bare(body))
    if bb > rb * 1.05:
        bad += 1
print(f"entries whose cleaned body is longer than its raw slice: {bad} (expect ~0)")

print("\n=== entry hx-001 header + first 30 lines ===")
t = open(os.path.join(WIKI, "source", ents[0]["file"]), encoding="utf-8").read()
for l in t.split("\n")[:34]:
    print("  ", l[:96])

print("\n=== entry hx-144 header + first 12 lines ===")
t = open(os.path.join(WIKI, "source", ents[-1]["file"]), encoding="utf-8").read()
for l in t.split("\n")[:16]:
    print("  ", l[:96])

print("\n=== front matter ===")
fp = os.path.join(WIKI, "source", "_front.md")
t = open(fp, encoding="utf-8").read()
print(f"  chars {len(t)}")
for l in t.split("\n")[:12]:
    print("  ", l[:96])

print("\n=== files on disk ===")
fs = [f for f in os.listdir(os.path.join(WIKI, "source")) if f.endswith(".md")]
print(f"  {len(fs)} md files")
tot = sum(os.path.getsize(os.path.join(WIKI, "source", f)) for f in fs)
print(f"  total {tot/1024/1024:.2f} MB")
