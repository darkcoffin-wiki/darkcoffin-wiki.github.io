#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成跨站互链白名单（作者复核结果）。

数据来源：tools/review_tags.py 产出的候选清单 trpg-data/review_tags.md
本脚本按**正则**读出「链接」列，凡是 `是` 的一律列入批准集合，
人工排除的项目写在 EXCLUDE 里（可随时增删）。

输出：trpg-data/link_whitelist.json
    {"approved": {"叶心": true, ...}, "excluded": {"1号": "易与编号型表述混淆", ...}}

用法：python tools/make_link_whitelist.py
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRPG = os.path.join(W, "trpg-data")

# 作者 2026-10-14 的复核结果：以下两个不链（太容易与其他编号型表述混淆）
EXCLUDE = {
    "1号": "易与「101号犯人」这类编号型表述混淆",
    "5号": "易与「3285号」这类编号型表述混淆",
}


def main():
    src = os.path.join(TRPG, "review_tags.md")
    if not os.path.exists(src):
        sys.exit("找不到 %s，请先跑 tools/review_tags.py" % src)

    text = io.open(src, encoding="utf-8").read()
    rows = re.findall(r"^\|\s*\d+\s*\|\s*`([^`]+)`[^|]*\|[^|]*\|[^|]*\|\s*([^|]*?)\s*\|",
                      text, re.M)
    approved, excluded, skipped = {}, {}, []
    for tag, verdict in rows:
        v = verdict.strip()
        if tag in EXCLUDE:
            excluded[tag] = EXCLUDE[tag]
            continue
        if v in ("是", "✓", "Y", "y", ""):
            approved[tag] = True
        elif v in ("否", "×", "x", "N", "n"):
            excluded[tag] = "作者复核时排除"
        else:
            skipped.append((tag, v))

    out = {"approved": approved, "excluded": excluded,
           "note": "作者 2026-10-14 复核：共 %d 个标签批准链接，%d 个排除。"
                   "本白名单只作用于「结构化名单字段」（在场/地点/登场人物/场次索引），"
                   "剧情摘要正文一律不链。" % (len(approved), len(excluded))}
    p = os.path.join(TRPG, "link_whitelist.json")
    io.open(p, "w", encoding="utf-8", newline="\n").write(
        json.dumps(out, ensure_ascii=False, indent=1) + "\n")

    print("已生成：%s" % p)
    print("批准 %d 个 ｜ 排除 %d 个 %s"
          % (len(approved), len(excluded), list(excluded)))
    if skipped:
        print("无法判定的行（按批准处理）：%s" % skipped[:10])
    # 抽查
    for probe in ("叶心", "北沙", "1号", "5号", "泡泡"):
        state = ("批准" if probe in approved else
                 ("排除：" + excluded.get(probe, "")) if probe in excluded else "不在名单")
        print("   %-6s %s" % (probe, state))


if __name__ == "__main__":
    main()
