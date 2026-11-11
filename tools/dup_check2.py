# -*- coding: utf-8 -*-
"""更细的重复检查：16 字滑窗找候选对，再用 difflib 算最长公共片段。

比 30 字滑窗灵敏度高——短段落被整段搬进另一篇也能抓到；
但只对「共享 ≥3 个 16 字滑窗」的候选对做最长公共串，避免全量两两比对。
"""
import difflib
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

W = r"E:\DSHwork\heijiu\wiki"
SRC = os.path.join(W, "source")
N = 16
MIN_CAND = 3          # 至少共享 3 个 16 字滑窗才进入候选
REPORT = 40           # 最长公共片段 ≥40 字才报

ent = json.load(io.open(os.path.join(W, "data", "entries.json"), encoding="utf-8"))["entries"]


def norm(s):
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s)


docs = {}
for e in ent:
    t = io.open(os.path.join(SRC, e["file"]), encoding="utf-8").read()
    body = re.sub(r"^---\n.*?\n---\n", "", t, flags=re.S)
    docs[e["id"]] = {"title": e["title"], "col": e["collection"],
                     "chars": e["chars"], "n": norm(body)}

sets, inv = {}, {}
for eid, d in docs.items():
    n = d["n"]
    sh = {n[i:i + N] for i in range(len(n) - N + 1)}
    sets[eid] = sh
    for s in sh:
        inv.setdefault(s, []).append(eid)

cand = {}
for s, lst in inv.items():
    if len(lst) < 2:
        continue
    for i in range(len(lst)):
        for j in range(i + 1, len(lst)):
            k = (lst[i], lst[j])
            cand[k] = cand.get(k, 0) + 1

print("候选对（共享 ≥%d 个 %d 字窗）：%d" % (MIN_CAND, N,
      sum(1 for v in cand.values() if v >= MIN_CAND)))

rows = []
for (a, b), c in cand.items():
    if c < MIN_CAND:
        continue
    na, nb = docs[a]["n"], docs[b]["n"]
    sm = difflib.SequenceMatcher(None, na, nb, autojunk=False)
    m = sm.find_longest_match(0, len(na), 0, len(nb))
    if m.size >= REPORT:
        rows.append((m.size, a, b, m.a, m.b))
rows.sort(reverse=True)

print("\n最长公共片段 ≥%d 字的对：%d 组" % (REPORT, len(rows)))
for size, a, b, pa, pb in rows:
    small, big = (a, b) if len(docs[a]["n"]) <= len(docs[b]["n"]) else (b, a)
    print("\n  【%d 字】%s《%s》%d 字  ↔  %s《%s》%d 字"
          % (size, a, docs[a]["title"], docs[a]["chars"],
             b, docs[b]["title"], docs[b]["chars"]))
    print("     短的那篇长度 %d 字，公共片段占它 %.1f%%"
          % (len(docs[small]["n"]),
             100.0 * size / max(1, len(docs[small]["n"]))))
    print("     %s 侧片段：…%s…" % (a, docs[a]["n"][pa:pa + size][:70]))
