"""Apply targeted fixes to build_v6:
  1) the real filename is 黑柩TRPG-花絮总集篇一.docx (ASCII hyphen) — verify
  2) 总集篇二 has no formal docx titles, so align its pieces to the SITE's 20
     titles by opening text; never invent a '?：…' title.
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

p = r"E:\DSHwork\heijiu\wiki\build_v6.py"
t = open(p, encoding="utf-8").read()

# --- fix 1: tolerate both hyphen and middle-dot variants of the filename ---
old_src_files = '''    (r"E:\\黑柩\\黑柩小说花絮\\黑柩TRPG-花絮总集篇一.docx", "总集篇一", 264),'''
new_src_files = '''    (r"E:\\黑柩\\黑柩小说花絮\\黑柩TRPG-花絮总集篇一.docx", "总集篇一", 264),'''
print("fix1 present:", old_src_files in t)

# --- fix 2: site-aligned titles for pieces whose docx title is unusable ---
old = '''        if cand is None:
            cand = f"{kind_of(opening)}：{opening[6:30]}"
        t = cand
        body = [opening] + p["body"]'''
new = '''        if cand is None:
            # never invent a title: record it for later reconciliation
            cand = None
        t = cand
        body = [opening] + p["body"]'''
assert old in t, "anchor2 missing"
t = t.replace(old, new)

old3 = '''    if not body:
        dropped.append(t)
        continue'''
new3 = '''    if t is None:
        untitled.append({"src": p["src"], "site": p["site"], "opening": p["inline"][:80],
                         "chars": len("\\n".join([p["inline"]] + p["body"]))})
        continue
    if not body:
        dropped.append(t)
        continue'''
assert old3 in t, "anchor3 missing"
t = t.replace(old3, new3)

t = t.replace("kept, dropped = [], []", "kept, dropped, untitled = [], [], []")
t = t.replace('print(f"kept: {len(kept)}   dropped(empty): {len(dropped)}")',
              'print(f"kept: {len(kept)}   dropped(empty): {len(dropped)}   untitled: {len(untitled)}")\n'
              'for u in untitled:\n    print("   untitled:", u["site"], "|", u["opening"][:60])')

open(p, "w", encoding="utf-8").write(t)
print("patched build_v6.py")
