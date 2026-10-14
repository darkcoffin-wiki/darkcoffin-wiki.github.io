#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子分类原型：按「篇目重合度」把标签自动聚成子分类。

用途：让你**看见**聚类效果，再决定子分类的口径。
本脚本只产出建议，不改站点；人工确认后写 data/subcategories.json。

方法
----
对某维度的标签集合，两两算篇目集合的 Jaccard 相似度，
再用简单凝聚聚类（阈值可调）分组；小的散落组归入「其他」。
对人物标签，另给一个更好用的信号：**同一篇里的共现强度**
（两个人物在同一篇出现 → 视为同场，自然形成圈子）。

用法：
    python tools/subcategory_prototype.py --dim 组织 --threshold 0.12
    python tools/subcategory_prototype.py --dim 人物 --threshold 0.06
产出：
    data/subcat_<维度>.md
"""
import argparse
import collections
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

W = common.W
DATA = common.DATA


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster(sets, threshold, min_size):
    """凝聚聚类：每轮把最相似的一对并起来，直到相似度低于阈值。"""
    groups = [[t] for t in sets]
    while True:
        best = (0.0, -1, -1)
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                ua = set().union(*[sets[t] for t in groups[i]])
                ub = set().union(*[sets[t] for t in groups[j]])
                s = jaccard(ua, ub)
                if s > best[0]:
                    best = (s, i, j)
        score, i, j = best
        if score < threshold or i < 0:
            break
        groups[i] = groups[i] + groups[j]
        groups.pop(j)
    big = [sorted(g, key=lambda t: -len(sets[t])) for g in groups if len(g) >= min_size]
    small = [t for g in groups if len(g) < min_size for t in g]
    big.sort(key=lambda g: -sum(len(sets[t]) for t in g))
    return big, sorted(small, key=lambda t: -len(sets[t]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dim", required=True)
    ap.add_argument("--threshold", type=float, default=0.12)
    ap.add_argument("--min-size", type=int, default=3)
    args = ap.parse_args()

    tags = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    idx = tags["tag_index"]
    members = [t for t, m in tags["tags"].items() if args.dim in (m.get("dimensions") or [])]
    sets = {t: set(idx[t]) for t in members}
    big, small = cluster(sets, args.threshold, args.min_size)

    L = ["# %s 维度的自动聚类建议（阈值 %.2f）\n" % (args.dim, args.threshold),
         "共 %d 个标签；聚成 %d 个较大的组，另有 %d 个标签未归类。\n"
         % (len(members), len(big), len(small))]
    for n, g in enumerate(big, 1):
        n_entries = len(set().union(*[sets[t] for t in g]))
        L.append("\n## 组 %d（%d 个标签，覆盖 %d 篇）\n" % (n, len(g), n_entries))
        L.append("　".join("%s(%d)" % (t, len(sets[t])) for t in g))
    if small:
        L.append("\n\n## 未归类（%d 个）\n\n" % len(small))
        L.append("　".join(small))
    out = os.path.join(DATA, "subcat_%s.md" % args.dim)
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")
    print(json.dumps({"dim": args.dim, "tags": len(members), "groups": len(big),
                      "unclassified": len(small)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
