# -*- coding: utf-8 -*-
"""查已发布花絮里的重复：
1) 完全重复（正文归一后相等）
2) 包含关系（一篇的正文几乎整个出现在另一篇里）
用 30 字滑窗 shingle + 倒排索引算包含度，避免 251×251 全量比对。
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

W = r"E:\DSHwork\heijiu\wiki"
SRC = os.path.join(W, "source")
N = 30          # shingle 长度
STEP = 4        # 步长，压一下内存

ents = json.load(io.open(os.path.join(W, "data", "entries.json"), encoding="utf-8"))
ent = ents["entries"]
print("条目 %d 篇" % len(ent))


def norm(s):
    """只留汉字/字母/数字，去掉空白与标点——重复判断不该被标点差异干扰。"""
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s)


docs = {}
for e in ent:
    p = os.path.join(SRC, e["file"])
    t = io.open(p, encoding="utf-8").read()
    body = re.sub(r"^---\n.*?\n---\n", "", t, flags=re.S)
    docs[e["id"]] = {"title": e["title"], "collection": e["collection"],
                     "chars": e["chars"], "n": norm(body)}

print("归一后总字数：%s" % format(sum(len(d["n"]) for d in docs.values()), ","))

# 完全重复
by_text = {}
for eid, d in docs.items():
    by_text.setdefault(d["n"], []).append(eid)
exact = [v for v in by_text.values() if len(v) > 1]
print("\n完全重复（归一后逐字相同）：%d 组" % len(exact))
for g in exact:
    print("   " + " = ".join("%s《%s》" % (x, docs[x]["title"]) for x in g))

# 包含关系
ids = sorted(docs)
sets = {}
for eid in ids:
    t = docs[eid]["n"]
    sets[eid] = {t[i:i + N] for i in range(0, max(0, len(t) - N + 1), STEP)}
    if len(t) >= N:
        sets[eid].add(t[-N:])

inv = {}
for eid in ids:
    for sh in sets[eid]:
        inv.setdefault(sh, []).append(eid)

pairs = {}
for sh, lst in inv.items():
    if len(lst) < 2:
        continue
    for i in range(len(lst)):
        for j in range(i + 1, len(lst)):
            k = (lst[i], lst[j])
            pairs[k] = pairs.get(k, 0) + 1

rows = []
for (a, b), shared in pairs.items():
    ca, cb = len(sets[a]) or 1, len(sets[b]) or 1
    cov_ab = shared / ca      # a 的内容有多少出现在 b 里
    cov_ba = shared / cb
    best = max(cov_ab, cov_ba)
    if best < 0.10:
        continue
    small, big = (a, b) if ca <= cb else (b, a)
    rows.append((best, small, big, min(cov_ab, cov_ba)))
rows.sort(reverse=True)

print("\n包含度 ≥10%% 的条目对：%d 组" % len(rows))
for best, small, big, other in rows[:25]:
    print("  %5.1f%%  %s《%s》(%d 字)  ⊂  %s《%s》(%d 字)"
          % (best * 100, small, docs[small]["title"], docs[small]["chars"],
             big, docs[big]["title"], docs[big]["chars"]))
    print("        小篇在大篇里的占比 %.1f%% ｜ 大篇被覆盖 %.1f%%"
          % (best * 100, other * 100))

# 同标题
bt = {}
for eid, d in docs.items():
    bt.setdefault(d["title"], []).append(eid)
dup_t = {k: v for k, v in bt.items() if len(v) > 1}
print("\n标题完全相同的：%d 组" % len(dup_t))
for k, v in dup_t.items():
    print("   %s → %s" % (k, v))
