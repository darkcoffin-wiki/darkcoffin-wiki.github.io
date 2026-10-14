#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""试验：为「标签↔文章相关性」设计确定性公式（乙方案）。

只针对**实体类**标签（人物/组织/地理/设施/剧情线）。

候选因子
--------
* freq    该标签在本篇出现的次数
* ratio   freq / 本篇正文字数（每千字出现次数）——消除篇幅差异
* cover   若该标签是「说话人」（名字后紧跟冒号）计一次，反映戏份

公式族
------
f1 = log2(1+freq)
f2 = 2*log2(1+freq) + 8*ratio
f3 = 2*log2(1+freq) + 8*ratio + 1.5*log2(1+speaker_hits)
各公式下用分位数定档（红/橙/蓝），比较分布与抽样是否合理。

用法：python tools/grading_experiment.py
"""
import collections
import io
import json
import math
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

W = common.W
DATA = common.DATA
ENT = {"人物", "组织", "地理", "设施", "剧情线"}
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def speaker_hits(body, tag):
    """该标签作为发言人的次数（`名字：` 或 `名字：` 在行首）。"""
    pat = re.compile(r"(?:^|\n)\s*(?:\*\*)?%s(?:\*\*)?\s*[：:]" % re.escape(tag))
    return len(pat.findall(body))


def main():
    tags = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    docs = {e["id"]: e for e in common.load_entries()}
    rows = []
    for e in tags["entries"]:
        body = docs[e["id"]]["body"]
        n = max(1, len(body))
        for t in e["tags"]:
            if not (set(e["dims"].get(t) or []) & ENT):
                continue
            w = e["weights"].get(t, 1)
            ratio = w / n * 1000.0
            sp = speaker_hits(body, t) if "人物" in (e["dims"].get(t) or []) else 0
            rows.append({
                "eid": e["id"], "tag": t, "freq": w, "ratio": ratio, "sp": sp,
                "chars": n,
                "f1": math.log2(1 + w),
                "f2": 2 * math.log2(1 + w) + 8 * ratio,
                "f3": 2 * math.log2(1 + w) + 8 * ratio + 1.5 * math.log2(1 + sp),
            })
    print("实体类配对：%d（涉及 %d 篇）" % (len(rows),
          len({r["eid"] for r in rows})))
    print("ratio（每千字出现次数）分位：",
          {p: round(statistics.quantiles([r["ratio"] for r in rows], n=100)[p - 1], 2)
           for p in (50, 75, 90, 95, 99)})
    print()
    for key in ("f1", "f2", "f3"):
        vals = sorted(r[key] for r in rows)
        q = statistics.quantiles(vals, n=100)
        cut_red, cut_orange = q[79], q[39]      # 20% 红 / 40% 橙 / 40% 蓝
        dist = collections.Counter()
        for r in rows:
            r[key + "_g"] = ("红" if r[key] >= cut_red else
                             "橙" if r[key] >= cut_orange else "蓝")
            dist[r[key + "_g"]] += 1
        print("%s：红阈值 %.2f / 橙阈值 %.2f → 分布 %s"
              % (key, cut_red, cut_orange, dict(dist)))
    print()
    # 抽样看点：同一篇里等级是否合理
    for eid in ("hx-001", "hx-104", "hx-162"):
        print("=== %s（%d 字）===" % (eid, docs[eid] and len(docs[eid]["body"])))
        rs = sorted((r for r in rows if r["eid"] == eid),
                    key=lambda r: -r["f3"])
        for r in rs[:12]:
            print("   %-6s %s freq=%-4d ratio=%-6.2f 发言=%-3d f3=%.2f"
                  % (r["f3_g"], r["tag"], r["freq"], r["ratio"], r["sp"], r["f3"]))
        print()


if __name__ == "__main__":
    main()
