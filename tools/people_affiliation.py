#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为「人物按阵营/圈子分子分类」生成证据表。

对每个（标签, 集合A）算关联强度：在同一篇里共同出现的比例（类似置信度）。
把人物 × 关键组织标签、人物 × 地名标签、人物 × 其他人物 的关联排出来，
用于人工归类——归类是判断，不是算法，这里只把判断所需的证据集中起来。

用法：python tools/people_affiliation.py
产出：data/people_affiliation.md
"""
import collections
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

W = common.W
DATA = common.DATA

# 关联侧写用的标签（阵营/地点线索）
ORG_HINTS = ["希共", "民主党", "进盟", "宪兵队", "纠察队", "戡乱政府", "富贵集团",
             "光胜集团", "蚀血教", "启示录教团国", "圣照会", "通雷帮", "韩帮",
             "铁狼帮", "月见家", "时崎家", "高家", "鸣家", "斯卡雷特家族", "天策",
             "天天集团", "大禾集团", "小父集团", "复国军", "深黑军团", "学生军",
             "巡林队", "异常事务委员会", "希共中央", "国民大会", "帝国号角"]
PLACE_HINTS = ["北沙", "青都", "星都", "日本街", "中分山", "帝国", "希联", "走廊区",
               "夜都", "散居区"]


def conf(a, b):
    """P(b|a)：在含 a 的篇目里，也含 b 的比例。"""
    if not a:
        return 0.0
    return len(a & b) / len(a)


def main():
    tags = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    idx = tags["tag_index"]
    entries = {e["id"]: e for e in tags["entries"]}

    people = sorted([t for t, m in tags["tags"].items()
                     if "人物" in (m.get("dimensions") or [])],
                    key=lambda t: -len(idx[t]))

    L = ["# 人物 × 阵营/地点 关联侧写（用于子分类）\n",
         "读法：`P(阵营|该人物)`——含这个人物的篇目里，也含该阵营的比例。",
         "数字高＝这个人常与该阵营同场。\n"]

    for t in people:
        s = set(idx[t])
        orgs = sorted(((conf(s, set(idx[o])), o) for o in ORG_HINTS if o in idx),
                      reverse=True)[:5]
        places = sorted(((conf(s, set(idx[p])), p) for p in PLACE_HINTS if p in idx),
                        reverse=True)[:3]
        orgs = [(c, o) for c, o in orgs if c >= 0.25]
        places = [(c, p) for c, p in places if c >= 0.25]
        top = sorted(idx[t], key=lambda e: -entries[e]["weights"].get(t, 0))[:4]
        L.append("- **%s**（%d 篇）｜组织：%s｜地点：%s｜代表篇目：%s"
                 % (t, len(idx[t]),
                    "、".join("%s %.0f%%" % (o, c * 100) for c, o in orgs) or "—",
                    "、".join("%s %.0f%%" % (p, c * 100) for c, p in places) or "—",
                    "、".join(top)))

    with io.open(os.path.join(DATA, "people_affiliation.md"), "w",
                 encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")

    # 顺带统计每个「组织线索」下挂了多少人物（帮助确定子分类数量）
    counts = {o: sum(1 for t in people if conf(set(idx[t]), set(idx[o])) >= 0.4)
              for o in ORG_HINTS if o in idx}
    print(json.dumps({"people": len(people),
                      "clusters>=40%": dict(sorted(counts.items(),
                                                  key=lambda kv: -kv[1])[:12])},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
