#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查「跨维度重合标签」：同一个标签名同时属于多个维度的情况。

背景：原实现为了避免近义重复，用分面优先级把同名标签压成了一个维度。
但作者指出「长歌」既是文类也是剧情线，这种重合是**有意为之**，不该收敛。

本脚本扫描出三类重合：
1. **词表内重合**：词表里同一个规范写法出现在多个维度（如 长歌：文类 + 剧情线）
2. **别名重叠**：A 标签是 B 标签的别名，但 B 在另一个维度（如 中分山=地理，又是剧情线）
3. **倾向重合**：某标签的篇目集合与另一维度的标签高度重合（可作参考）

用法：python tools/cross_dimension_audit.py
产出：data/cross_dimension.md
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


def main():
    ov = json.load(open(os.path.join(DATA, "taxonomy_overrides.json"), encoding="utf-8"))
    alias = {}
    for k in ("实体同义（variant → 受控标签）", "人物同义（variant → 受控人名）"):
        alias.update(ov.get(k) or {})

    tags = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    idx = tags["tag_index"]

    # 建立「规范写法 → 声明的维度集合」
    declared = collections.defaultdict(set)
    people = json.load(open(os.path.join(DATA, "vocab_people.json"), encoding="utf-8"))
    for r in people.get("people", []):
        if r.get("kind", "person") == "person":
            declared[r["tag"]].add("人物")
    ent = json.load(open(os.path.join(DATA, "vocab_entities.json"), encoding="utf-8"))
    for key, dim in (("orgs", "组织"), ("places", "地理"),
                     ("facilities", "设施"), ("series", "剧情线")):
        for r in ent.get(key, []):
            declared[r["tag"]].add(dim)
    dims = json.load(open(os.path.join(DATA, "vocab_dimensions.json"), encoding="utf-8"))
    for dim in ("主题", "事件类型", "关系", "主题词", "时间"):
        for t in (dims.get(dim) or {}):
            declared[t].add(dim)
    # 文类：语料的 kind 值（长歌/花絮/楔子/画外音…）
    for k in ("花絮", "楔子", "画外音", "剧情花絮", "特别环节", "特别内容",
              "四格漫画", "长歌"):
        declared[k].add("文类")
    for k in ("已发生", "未来可能", "平行世界线"):
        declared[k].add("叙事层级")
    for k in ("短篇", "中篇", "长篇"):
        declared[k].add("篇幅")

    # 1) 声明层面的重合
    multi = {t: sorted(d) for t, d in declared.items() if len(d) > 1}

    # 2) 别名指向的目标也在别的维度
    alias_multi = []
    for src, dst in alias.items():
        if len(declared.get(dst, ())) > 1 or (declared.get(src) and declared.get(dst)
                                             and declared[src] != declared[dst]):
            alias_multi.append((src, sorted(declared.get(src, ())), dst,
                                sorted(declared.get(dst, ()))))

    # 3) 倾向重合：标签集合高度包含
    overlap = []
    names = sorted(idx)
    for a in names:
        for b in names:
            if a == b or len(a) >= len(b):
                continue
            sa, sb = set(idx[a]), set(idx[b])
            if not sb or len(sa) < 5:
                continue
            j = len(sa & sb) / len(sa | sb)
            if j >= 0.6 and declared.get(a) != declared.get(b):
                overlap.append((round(j, 2), a, sorted(declared.get(a, ())),
                                b, sorted(declared.get(b, ()))))
    overlap.sort(reverse=True)

    # 4) 剧情线维度现在实际只有 2 个标签；列出被压掉的候选
    series_declared = [r["tag"] for r in ent.get("series", [])]
    series_live = [t for t in idx if tags["tags"][t]["dimension"] == "剧情线"]

    L = ["# 跨维度重合标签检查\n",
         "## 一、声明层面就是多维度（%d 个）\n" % len(multi),
         "| 标签 | 所属维度 | 当前实际维度 | 篇数 |", "|---|---|---|---:|"]
    for t in sorted(multi, key=lambda x: -len(idx.get(x, []))):
        L.append("| %s | %s | %s | %d |"
                 % (t, " + ".join(multi[t]),
                    tags["tags"].get(t, {}).get("dimension", "（未产出）"),
                    len(idx.get(t, []))))
    L.append("\n## 二、别名跨维度（%d 组）\n" % len(alias_multi))
    L.append("| 别名 | 别名维度 | → 目标 | 目标维度 |")
    L.append("|---|---|---|---|")
    for src, sd, dst, dd in alias_multi:
        L.append("| %s | %s | %s | %s |" % (src, ",".join(sd) or "-", dst, ",".join(dd) or "-"))

    L.append("\n## 三、剧情线维度：词表声明 %d 个，实际只产出 %d 个\n"
             % (len(series_declared), len(series_live)))
    L.append("声明：%s\n" % "、".join(series_declared))
    L.append("实际产出：%s\n" % ("、".join(series_live) or "（无）"))
    L.append("被分面优先级压掉的：%s\n"
             % "、".join(t for t in series_declared if t not in series_live))

    L.append("\n## 四、集合高度重合但维度不同（Jaccard ≥ 0.6，前 40 组）\n")
    L.append("| J | 标签A | A维度 | 标签B | B维度 |")
    L.append("|---:|---|---|---|---|")
    for j, a, ad, b, bd in overlap[:40]:
        L.append("| %.2f | %s | %s | %s | %s |" % (j, a, ",".join(ad) or "-", b, ",".join(bd) or "-"))

    with io.open(os.path.join(DATA, "cross_dimension.md"), "w",
                 encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")

    print(json.dumps({"multi_dimension": len(multi),
                      "alias_cross": len(alias_multi),
                      "series_declared": len(series_declared),
                      "series_live": len(series_live)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
