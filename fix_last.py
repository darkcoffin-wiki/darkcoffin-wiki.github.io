"""Fix the last stale figure in the project spec."""
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

P = r"E:\DSHwork\heijiu\wiki\项目说明书.md"
t = open(P, encoding="utf-8").read()

# replace whatever line still quotes the old count
lines = t.split("\n")
out = []
for l in lines:
    if "144" in l and "entries.json" in l:
        out.append("2. 核对 `data/entries.json`（**210 条**）与 `source/`（210 个 md + `_INDEX.md`）是否一致")
    else:
        out.append(l)
t = "\n".join(out)

open(P, "w", encoding="utf-8").write(t)
print("144 remaining:", t.count("144"))
print("210 occurrences:", t.count("210"))
for l in t.split("\n"):
    if "entries.json" in l:
        print("  ", l)
