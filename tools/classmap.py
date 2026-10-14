#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「快速归类」工具包：让你用最少的手工动作重排标签归属。

设计目标
--------
* 你不必碰 JSON——改一个**编号**就行（一个标签 = 一行 = 一个数字）
* 格式可回读：tools/apply_classmap.py 会把它写回 data/subcategories.json 并校验
* 三种载体，按你顺手选一个用：
    data/classmap.txt   ← 最快：一行一个标签，改数字即可（推荐）
    data/classmap.md    ← 问答卡式：带分组说明与表格，适合看着读
    data/classmap.csv   ← Excel 友好（带 BOM，可用数据验证做下拉）

用法：python tools/classmap.py [--dim 人物]
产出：上述三个文件 + data/classmap_groups.md（分组编号表）
"""
import argparse
import collections
import csv
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

DATA = common.DATA


def load():
    tags = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    sc = json.load(open(os.path.join(DATA, "subcategories.json"), encoding="utf-8"))
    return tags, sc


def build_index(sc, dim):
    """返回 (编号→组名, 标签→编号, 顺序)  。编号按 JSON 里的顺序，全局在维度内唯一。"""
    groups = (sc.get("dimensions") or {}).get(dim) or []
    idx = {}          # 组名 -> 编号（从 1 开始）
    slot = {}         # 标签 -> 编号
    for i, g in enumerate(groups, 1):
        idx[g["name"]] = i
        for t in g.get("tags") or []:
            if t not in slot:
                slot[t] = i
    return idx, slot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dim", default=None, help="只处理某个维度（默认全部已定义的维度）")
    args = ap.parse_args()

    tags, sc = load()
    dims = list((sc.get("dimensions") or {}).keys())
    if args.dim:
        dims = [args.dim]

    txt, md, rows, group_md = [], [], [], []
    group_md.append("# 分组编号表（改类目时用编号）\n")

    for dim in dims:
        real = sorted([t for t, m in tags["tags"].items()
                       if dim in (m.get("dimensions") or [])],
                      key=lambda t: -len(tags["tag_index"][t]))
        gidx, slot = build_index(sc, dim)
        unassigned = [t for t in real if t not in slot]

        group_md.append("\n## %s（%d 个标签）\n" % (dim, len(real)))
        for name, n in sorted(gidx.items(), key=lambda kv: kv[1]):
            cnt = sum(1 for t in real if slot.get(t) == n)
            group_md.append("- **%d** = %s（现有 %d 个）" % (n, name, cnt))
        if unassigned:
            group_md.append("- **0** = 未分类（%d 个）" % len(unassigned))

        txt.append("# ══ %s ══  行首数字＝类目编号（0＝未分类），改数字即可" % dim)
        txt.append("# 类目表：" + " ｜ ".join(
            "%d=%s" % (n, name) for name, n in sorted(gidx.items(), key=lambda kv: kv[1])))
        txt.append("#")
        for t in real:
            n = slot.get(t, 0)
            name = next((k for k, v in gidx.items() if v == n), "未分类")
            txt.append("%d %s  # %s" % (n, t, name))
        txt.append("")

        md.append("\n## %s\n" % dim)
        md.append("当前归属（改最后一列即可，也可整行重排）：\n")
        md.append("| 编号 | 类目 | 标签 | 篇数 |")
        md.append("|---:|---|---|---:|")
        by_group = collections.defaultdict(list)
        for t in real:
            by_group[slot.get(t, 0)].append(t)
        for n in sorted(by_group):
            name = next((k for k, v in gidx.items() if v == n), "未分类")
            for t in by_group[n]:
                md.append("| %d | %s | %s | %d |" % (n, name, t, len(tags["tag_index"][t])))

        for t in real:
            rows.append({"维度": dim, "类目编号": slot.get(t, 0),
                         "类目名": next((k for k, v in gidx.items()
                                         if v == slot.get(t)), "未分类"),
                         "标签": t, "篇数": len(tags["tag_index"][t])})

    header = ("# 快速归类表\n#\n"
              "# 怎么用：改每行开头的**数字**即可（0＝未分类）。编号含义见 data/classmap_groups.md\n"
              "# 行尾的 `# 类目名` 只是给你核对用的注释，改不改都不影响。\n"
              "#\n"
              "# 想**新增类目**：先看 data/classmap_groups.md 里该维度的最大编号 N，\n"
              "# 然后在文件末尾（或该维度段落之后）另起一段写：\n"
              "#\n"
              "# ══ 人物 ══\n"
              "# 类目表：11=其他与客串 ｜ 12=新类目名\n"
              "#\n"
              "# 12 某个标签\n"
              "# 12 另一个标签\n"
              "#\n"
              "# （只写你**要动**的行也可以，其余行保持原样即可）\n"
              "#\n"
              "# 完成后告诉我，或自己跑：python tools/apply_classmap.py\n\n")
    with io.open(os.path.join(DATA, "classmap.txt"), "w",
                 encoding="utf-8", newline="\n") as fh:
        fh.write(header + "\n".join(txt) + "\n")
    with io.open(os.path.join(DATA, "classmap.md"), "w",
                 encoding="utf-8", newline="\n") as fh:
        fh.write("# 子分类校对卡\n\n"
                 "> 改「编号」列即可；编号相同的标签会归到同一类目。\n"
                 "> 类目编号表见 `data/classmap_groups.md`。改完告诉我，或跑 "
                 "`python tools/apply_classmap.py`。\n" + "\n".join(md) + "\n")
    with io.open(os.path.join(DATA, "classmap_groups.md"), "w",
                 encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(group_md) + "\n")
    with io.open(os.path.join(DATA, "classmap.csv"), "w",
                 encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["维度", "类目编号", "类目名", "标签", "篇数"])
        w.writeheader()
        w.writerows(rows)

    print(json.dumps({"dims": dims, "rows": len(rows),
                      "files": ["data/classmap.txt", "data/classmap.md",
                                "data/classmap.csv", "data/classmap_groups.md"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
