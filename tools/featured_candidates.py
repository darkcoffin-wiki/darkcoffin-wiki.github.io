#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按数据生成首页栏目候选（6–10 个）+ 介绍语草稿骨架。

产出：
    data/featured_candidates.json   候选栏目（含每栏精选条目，按篇内权重排序）
    data/featured_candidates.md     给作者圈定用的可读版（介绍语待作者定稿）

精选逻辑：在该标签下的所有条目里，按「该标签在篇内的权重 + 篇幅」排序取前 6；
这样选出的通常是「围绕着这个标签展开」的篇目，而不是只顺带提一句的。

用法：python tools/featured_candidates.py
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

W = common.W
DATA = common.DATA

# 候选栏目：按数据挑（人物线 / 势力线 / 地域线 / 主题线混合），介绍语由人工起草
CANDIDATES = [
    ("叶心", "人物", "从青都市政府办公室到星都街头。叶心的场合多与党内协调、公开信和访问有关，"
                     "也包括她尚未成为「叶主席」的时候。"),
    ("北沙", "地理", "北沙是事件最密集的城市：警局、广场、电影院、起义与白色恐怖都发生在这里。"),
    ("希共", "组织", "希望联邦共产党的对外宣言、内部争论与党内生活——包括论坛、公开信与党代会现场。"),
    ("陆柩", "人物", "守夜人、警钟与深夜独行。这条线收拢陆柩与路絮的通信、他与李伊的对峙，"
                     "以及更早以前的经历。"),
    ("原星", "人物", "原星对过往的申辩，以及他重回故里的那一段。"),
    ("帝国", "地理", "帝国一侧的宫廷与政务：首相的登场与失势、天皇、以及北沙起义中的帝国机变。"),
    ("宪兵队", "组织", "宪兵队与纠察队：城内秩序的执行者，也是许多冲突的直接对手。"),
    ("高冒", "人物", "民主党与高家一侧：高冒的场合多与党内斗争、经济改革和最后的结局有关。"),
    ("进盟", "组织", "进化者同盟：特务、天使与那场未完成的进攻。"),
    ("中分山", "地理", "中分山的建设计划与山中势力，以及由此在四方引起的回响。"),
    ("日本街", "地理", "日本街的家族、帮派与阴影：时崎家、川崎罗、春叶屋与家主们的会议。"),
    ("蚀血教", "组织", "蚀血教、完人的影子与圣女一脉，以及它与教皇、北沙的交集。"),
    ("月见家", "组织", "月见家的宴席、操盘与旧账。"),
    ("富贵集团", "组织", "富贵集团与光胜集团：城内的资本势力，以及围绕它们的劫案与调查。"),
]

# 介绍语草稿（仅依据本站正文可核实的表述；最终由作者定稿）
BLURBS = {}


def main():
    data = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    meta, idx = data["tags"], data["tag_index"]
    by_id = {e["id"]: e for e in data["entries"]}

    cols = []
    for tag, dim, blurb in CANDIDATES:
        if tag not in idx:
            continue
        ids = idx[tag]
        ranked = sorted(ids, key=lambda i: (-by_id[i]["weights"].get(tag, 0),
                                            -by_id[i]["chars"]))
        cols.append({
            "tag": tag,
            "title": tag,
            "dimension": meta[tag]["dimension"],
            "doc_freq": len(ids),
            "blurb_draft": BLURBS.get(tag, blurb),
            "picks": ranked[:6],
            "picks_titles": ["%s %s" % (i, by_id[i]["title"]) for i in ranked[:6]],
        })
    cols.sort(key=lambda c: -c["doc_freq"])

    out = {"note": "首页栏目候选；picks 为脚本按篇内权重挑出的精选条目，"
                   "blurb_draft 待作者定稿。确定后请写 data/featured.json",
           "candidates": cols,
           "how_to_finalize": {
               "file": "data/featured.json",
               "schema": {"columns": [{"tag": "标签名", "title": "栏目显示名",
                                       "blurb": "介绍语", "picks": ["hx-001"],
                                       "limit": 6}]},
               "note": "picks 省略则按标签下全部条目自动排序；limit 默认 6。"}}
    common.write_json(os.path.join(DATA, "featured_candidates.json"), out)

    md = ["# 首页栏目候选（请圈定）\n",
          "下表由 `tools/featured_candidates.py` 按数据生成。**介绍语是我起草的草稿**，"
          "你可以直接改；确定后我写进 `data/featured.json`。\n",
          "| 选 | 栏目 | 维度 | 篇数 | 介绍语草稿 | 精选示例 |",
          "|---|---|---|---:|---|---|"]
    for c in cols:
        md.append("| ☐ | **%s** | %s | %d | %s | %s |"
                  % (c["tag"], c["dimension"], c["doc_freq"], c["blurb_draft"],
                     "；".join(c["picks_titles"][:3])))
    md.append("\n## 也可以换别的标签\n")
    pool = sorted(((len(v), t) for t, v in idx.items()
                   if meta[t]["dimension"] in ("人物", "组织", "地理", "剧情线", "主题")),
                  reverse=True)[:60]
    md.append("按篇数排的前 60 个可做栏目的标签：\n")
    md.append("　".join("%s(%d)" % (t, n) for n, t in pool))
    with open(os.path.join(DATA, "featured_candidates.md"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(md) + "\n")
    print(json.dumps({"columns": len(cols)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
