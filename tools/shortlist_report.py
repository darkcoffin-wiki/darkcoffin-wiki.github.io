#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 entity_candidates.json 压成可读短名单（md + json），供审核。

用法：python tools/shortlist_report.py
产出：
    data/shortlist_people.md
    data/shortlist_proper.md
"""
import json
import os

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(W, "data")
cand = json.load(open(os.path.join(DATA, "entity_candidates.json"), encoding="utf-8"))


def table(rows, cols=4):
    out = []
    for i in range(0, len(rows), cols):
        chunk = rows[i:i + cols]
        out.append(" | ".join(chunk))
    return "\n".join(out)


people = [r for r in cand["people_candidates"] if r["count"] >= 6 and r["entropy"] >= 1.2]
proper = [r for r in cand["proper_candidates"] if r["count"] >= 12 and r["entropy"] >= 1.5]

with open(os.path.join(DATA, "shortlist_people.md"), "w", encoding="utf-8") as fh:
    fh.write("# 人名/称谓候选（count>=6, entropy>=1.2）共 %d\n\n" % len(people))
    for r in people:
        fh.write("- %s  (%d, H=%.2f)%s\n" % (r["tag"], r["count"], r["entropy"],
                                             "  [职务]" if r["is_role"] else ""))

with open(os.path.join(DATA, "shortlist_proper.md"), "w", encoding="utf-8") as fh:
    fh.write("# 专名候选（count>=12, entropy>=1.5）共 %d\n\n" % len(proper))
    for r in proper:
        fh.write("- %s  (%d, H=%.2f)\n" % (r["tag"], r["count"], r["entropy"]))

print("people shortlist:", len(people), "proper shortlist:", len(proper))
