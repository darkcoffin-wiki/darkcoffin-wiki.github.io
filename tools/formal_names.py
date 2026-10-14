#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「正式名称」核实表（A2）。

作者裁定：标签一律用正式名称；简称/全名并存时用全名。
本脚本不猜——只在**候选全名确实出现在正文**时才建议改，并给出两边的篇数供核实。

用法：python tools/formal_names.py
产出：data/formal_name_candidates.md
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

DATA = common.DATA
SRC = common.SRC
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 候选表：现用简称 → 建议正式全名。
# 来源：站点「人物介绍」目录 + 设定集卷八「人物志」的「全名（别名…）」结构。
# 只列**简称确实是正文常用写法**的；已用全名的不动。
SUGGEST = {
    # —— 由站点目录 / 卷八条目直接给出 ——
    "信子": "时崎信子",
    "双叶": "海老名双叶",
    "惠子": "海老名惠子",
    "雄介": "海老名雄介",
    "纯一": "柳生纯一",
    "镰川": "渡边镰川",
    "宗魁": "宗魁",
    "夜瞳": "白夜瞳",
    "保罗": "大主教（保罗）",
    # —— 编号身份（蚀血教／蛛眼小队）——
    "杜丁": "“0号”（杜丁）",
    "薇薇安": "“3号”（薇薇安）",
    "鲜红超人": "“4号”（鲜红超人）",
    "1号": "“1号”（曼陀罗）",
    "2号": "“2号”（礼先生）",
    "5号": "“5号”（怪物）",
}


def main():
    tags = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    idx = tags["tag_index"]
    meta = tags["tags"]
    people = {t for t, m in meta.items() if "人物" in (m.get("dimensions") or [])}

    docs = []
    for f in sorted(os.listdir(SRC)):
        if f.startswith("hx-") and f.endswith(".md"):
            _, body = common.read_entry(os.path.join(SRC, f))
            docs.append(body)

    def freq(name):
        return sum(1 for b in docs if name in b)

    L = ["# 正式名称核实表（A2）\n",
         "作者裁定：标签一律用**正式名称**，简称/全名并存时用全名。",
         "下表左边是现在用的名字，右边是我查证后建议的正式名（含正文篇数）。",
         "**请圈定要改的**；没列的说明本来就是正式名。\n",
         "| 现用 | 篇数 | 建议正式名 | 该写法正文篇数 | 依据 |",
         "|---|---:|---|---:|---|"]
    for short, full in SUGGEST.items():
        if short not in people:
            continue
        n_new = freq(full)
        basis = ("设定集卷八/站点目录给出" if n_new else "**正文未出现该写法，需你确认**")
        L.append("| %s | %d | %s | %d | %s |"
                 % (short, len(idx[short]), full, n_new, basis))

    # 顺带列出「已是全名」的高频人物，供对照
    L.append("\n## 参考：篇数最高的 25 个人物标签（多为正式名）\n")
    top = sorted(((len(idx[t]), t) for t in people), reverse=True)[:25]
    L.append("　".join("%s(%d)" % (t, n) for n, t in top))
    with io.open(os.path.join(DATA, "formal_name_candidates.md"), "w",
                 encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")
    print(json.dumps({"suggestions": sum(1 for s in SUGGEST if s in people)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
