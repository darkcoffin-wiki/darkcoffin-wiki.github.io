#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""试验二：把「红＝全篇围绕它展开、蓝＝顺带一提」写成可判定的规则。

设计思路（三条判据并行，任一满足即得该档；逐档从高到低判）：
* 红：① 篇内该维度标签中按频次排第 1 且 freq≥8；或 ② freq≥15；或 ③ ratio≥8（每千字 ≥8 次，短文里的主角）
* 橙：① 篇内排名前 3 且 freq≥4；或 ② freq≥6；或 ③ ratio≥3
* 蓝：其余
在真实数据上跑出分布，并逐篇抽样核对。
"""
import collections
import io
import json
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
    pat = re.compile(r"(?:^|\n)\s*(?:\*\*)?%s(?:\*\*)?\s*[：:]" % re.escape(tag))
    return len(pat.findall(body))


def main():
    tags = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    docs = {e["id"]: e for e in common.load_entries()}
    rows = []
    for e in tags["entries"]:
        body = docs[e["id"]]["body"]
        n = max(1, len(body))
        # 篇内按频次排名（只对实体类）
        ents = [(t, e["weights"].get(t, 1)) for t in e["tags"]
                if set(e["dims"].get(t) or []) & ENT]
        ents.sort(key=lambda x: -x[1])
        rank = {t: i + 1 for i, (t, _w) in enumerate(ents)}
        for t, w in ents:
            ratio = w / n * 1000.0
            rows.append({
                "eid": e["id"], "tag": t, "freq": w, "ratio": ratio,
                "rank": rank[t], "sp": speaker_hits(body, t)
                if "人物" in (e["dims"].get(t) or []) else 0,
                "chars": n,
                "dims": e["dims"].get(t) or [],
            })

    def grade(r):
        if (r["rank"] == 1 and r["freq"] >= 8) or r["freq"] >= 15 or r["ratio"] >= 8:
            return "红"
        if (r["rank"] <= 3 and r["freq"] >= 4) or r["freq"] >= 6 or r["ratio"] >= 3:
            return "橙"
        return "蓝"

    for r in rows:
        r["g"] = grade(r)
    dist = collections.Counter(r["g"] for r in rows)
    total = len(rows)
    print("实体类配对 %d ｜ 分布：红 %d (%.0f%%)、橙 %d (%.0f%%)、蓝 %d (%.0f%%)"
          % (total, dist["红"], 100*dist["红"]/total, dist["橙"],
             100*dist["橙"]/total, dist["蓝"], 100*dist["蓝"]/total))
    print()
    # 各篇等级数分布
    per = collections.Counter()
    for r in rows:
        per[(r["eid"], r["g"])] += 1
    reds = [v for (e, g), v in per.items() if g == "红"]
    print("每篇红级数：中位 %d，均值 %.1f，最大 %d；有 %d 篇无红级"
          % (statistics.median(reds), statistics.mean(reds), max(reds),
             len({r['eid'] for r in rows}) - len({e for (e, g) in per if g == '红'})))
    print()
    for eid in ("hx-001", "hx-104", "hx-162", "hx-009", "hx-191"):
        if eid not in docs:
            continue
        print("=== %s（%d 字）===" % (eid, len(docs[eid]["body"])))
        for r in sorted((x for x in rows if x["eid"] == eid),
                        key=lambda x: ({"红": 0, "橙": 1, "蓝": 2}[x["g"]], -x["freq"])):
            print("   %s %-8s freq=%-4d ratio=%-6.2f 排名=%-3d 发言=%-3d %s"
                  % (r["g"], r["tag"], r["freq"], r["ratio"], r["rank"], r["sp"],
                     "、".join(r["dims"])))
        print()


if __name__ == "__main__":
    main()
