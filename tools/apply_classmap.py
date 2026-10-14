#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 data/classmap.txt 的归类结果写回 data/subcategories.json，并校验。

classmap.txt 格式（tools/classmap.py 生成）：
    # ══ 人物 ══
    # 类目表：1=希共阵营 ｜ 2=民主党与高家 ｜ ...
    3 叶心
    0 某个还没归类的标签
    #NEW 新类目名          ← 可选：在下一个维度段落前声明新类目（自动追加编号）

规则：
* 行首数字 = 类目编号；0 = 未分类（会从子分类里移除，留在「未分类」里）
* `#NEW 名字` 会新建一个类目（编号自动接在该维度现有最大编号之后）
* 同一维度内一个标签只能有一个编号；重复出现时以**最后一行**为准并给出警告
* 不认识的标签名会报错并终止（避免把名字打错后静默丢标签）

用法：
    python tools/apply_classmap.py --dry-run   # 只报告改动，不写文件
    python tools/apply_classmap.py             # 写回并校验
"""
import argparse
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

DATA = common.DATA
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def parse(path):
    """→ {dim: {"groups": [name...], "assign": {tag: idx}}}"""
    out = {}
    dim = None
    for raw in io.open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^#\s*══\s*(.+?)\s*══", s)
        if m:
            dim = m.group(1)
            out.setdefault(dim, {"groups": [], "assign": {}, "unknown": []})
            continue
        if s.startswith("#NEW"):
            name = s[4:].strip()
            if dim and name:
                out[dim]["groups"].append(name)
            continue
        if s.startswith("#"):
            continue
        # 行尾允许带 `# 注释`（classmap.py 会写「# 当前类目名」便于核对）
        s = s.split("#", 1)[0].strip()
        if not s:
            continue
        m = re.match(r"^(\d+)\s+(\S+)$", s)
        if not m:
            if dim:
                out[dim]["unknown"].append(s)
            continue
        n, tag = int(m.group(1)), m.group(2)
        if dim:
            if tag in out[dim]["assign"]:
                out[dim]["unknown"].append("重复：%s" % tag)
            out[dim]["assign"][tag] = n
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--file", default=os.path.join(DATA, "classmap.txt"))
    ap.add_argument("--reset", action="store_true",
                    help="不带基线：没提到的标签一律变未分类（默认是**保留原归属**）")
    args = ap.parse_args()

    tags = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    sc = json.load(open(os.path.join(DATA, "subcategories.json"), encoding="utf-8"))
    parsed = parse(args.file)

    problems, report = [], []
    for dim, data in parsed.items():
        real = {t for t, m in tags["tags"].items() if dim in (m.get("dimensions") or [])}
        groups_def = (sc.get("dimensions") or {}).get(dim)
        if groups_def is None:
            problems.append("%s：subcategories.json 里没有这个维度" % dim)
            continue
        # 现有编号表
        idx = {}
        for i, g in enumerate(groups_def, 1):
            idx[i] = g["name"]
        nxt = max(idx) + 1 if idx else 1
        # 追加新类目（#NEW 或直接用 > 现有最大值的编号）
        for name in data["groups"]:
            idx[nxt] = name
            nxt += 1
        # 基线 = 现有归属（除非 --reset）。这样你**只写要动的行**也不会把别的标签弄丢。
        # 注意：一个标签**可以**属于多个子分类（作者裁定）。基线取「第一个」所属：
        # 若你在 classmap 里改了某行，就以你写的那个为准（该标签从原属组移除）。
        assign = {}
        if not args.reset:
            for n in range(1, len(groups_def) + 1):
                for t in (groups_def[n - 1].get("tags") or []):
                    assign.setdefault(t, n)
        assign.update(data["assign"])          # 你写的行覆盖基线
        # 你**主动改写**的标签：从其它组里移除（避免既在旧组又在新组，造成意外多分类）
        moved = set(data["assign"])
        bad = [t for t in data["assign"] if t not in real]
        badnum = sorted({n for n in data["assign"].values() if n != 0 and n not in idx})
        if bad:
            problems.append("%s：%d 个标签不存在于本维度 → %s"
                            % (dim, len(bad), "、".join(bad[:10])))
        if badnum:
            problems.append("%s：%d 个编号没有对应类目 → %s"
                            % (dim, len(badnum), badnum))
        if data["unknown"]:
            problems.append("%s：%d 行无法解析 → %s"
                            % (dim, len(data["unknown"]), data["unknown"][:5]))
        if problems:
            continue
        # 组装：编号 → 标签（被改写的标签只落在新编号下）
        src_of = {g["name"]: g.get("source", "") for g in groups_def}
        buckets = collections.defaultdict(list)
        for t, n in assign.items():
            if n and t in real:
                buckets[n].append(t)
        new_groups = []
        for n in sorted(idx):
            members = [t for t in buckets.get(n, [])]
            members.sort(key=lambda t: -len(tags["tag_index"][t]))
            g = {"name": idx[n], "tags": members}
            if src_of.get(idx[n]):
                g["source"] = src_of[idx[n]]      # 保留分组依据（分类页会显示）
            new_groups.append(g)
        report.append("%s：%d 个标签 → %d 个类目（原 %d 个；本次改动 %d 个）"
                      % (dim, sum(len(g["tags"]) for g in new_groups),
                         len([g for g in new_groups if g["tags"]]), len(groups_def),
                         len(moved)))
        sc["dimensions"][dim] = new_groups

    print("\n".join(report) or "（没有可应用的改动）")
    if problems:
        print("\n发现问题，未写入：")
        for p in problems:
            print("  ✗ " + p)
        sys.exit(1)
    if args.dry_run:
        print("\n--dry-run：未写入。")
        return
    with io.open(os.path.join(DATA, "subcategories.json"), "w",
                 encoding="utf-8", newline="\n") as fh:
        json.dump(sc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("\n已写回 data/subcategories.json。请接着跑：")
    print("  python tools/check_subcategories.py && python tools/build_site.py")


if __name__ == "__main__":
    main()
