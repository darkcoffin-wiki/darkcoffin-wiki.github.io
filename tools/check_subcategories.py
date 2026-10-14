#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 data/subcategories.json 的完整性。

查四类问题：
1. **重复归类**：同一标签在同一维度下被列进多个子分类 → **允许**（作者裁定：
   标签可以属于多个子分类，如主角团队的蛛眼也在蛛眼小队），只作为提示
2. **不存在的标签**：列了名字但该维度里没有这个标签（拼错或已被降级）→ 错误
3. **漏归类**：该维度有标签但没进任何子分类（会落进「未分类」）→ 提示
4. **跨维度错放**：把别维度的标签写进了本维度 → 错误

用法：
    python tools/check_subcategories.py            # 全维度检查
    python tools/check_subcategories.py --dim 人物  # 只看一个维度
退出码非 0 表示有**错误**（重复归类不算错误）。
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

DATA = common.DATA

# Windows 控制台可能是 GBK，检查结果里有中文/符号，统一按 UTF-8 输出
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dim")
    args = ap.parse_args()

    tags = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    sc = json.load(open(os.path.join(DATA, "subcategories.json"), encoding="utf-8"))

    problems, notes, summary = [], [], []
    dims = sc.get("dimensions") or {}
    names = list(dims) if not args.dim else [args.dim]

    for dim in names:
        groups = dims.get(dim) or []
        real = {t for t, m in tags["tags"].items() if dim in (m.get("dimensions") or [])}
        seen = collections.Counter()
        for g in groups:
            for t in (g.get("tags") or []):
                seen[t] += 1
        dupes = sorted(t for t, c in seen.items() if c > 1)
        unknown = sorted(t for t in seen if t not in real)
        missing = sorted(real - set(seen))
        if dupes:
            notes.append("%s：%d 个标签属于多个子分类（允许）→ %s"
                         % (dim, len(dupes), "、".join(dupes)))
        if unknown:
            problems.append("%s：%d 个标签不存在于本维度（拼错或已降级）→ %s"
                            % (dim, len(unknown), "、".join(unknown)))
        if missing:
            notes.append("%s：%d 个标签未归类（会落进「未分类」）→ %s"
                         % (dim, len(missing), "、".join(missing)))
        summary.append("%s：本维度 %d 个标签，已归类 %d，子分类 %d 个（含多分类 %d 个）"
                       % (dim, len(real), len(set(seen) & real), len(groups), len(dupes)))

    print("\n".join(summary))
    if notes:
        print("\n提示（不是错误）：")
        for p in notes:
            print("  · " + p)
    if problems:
        print("\n错误：")
        for p in problems:
            print("  ✗ " + p)
        sys.exit(1)
    print("\n✓ 子分类映射无错名、无跨维度错放；漏项与多分类仅作提示。")


if __name__ == "__main__":
    main()
