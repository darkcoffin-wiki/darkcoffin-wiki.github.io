#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建原始记录的倒排索引，给「不依赖季志」的检索入口。

两个索引，解决两类问题
  ① terms     词 → 场次:次数        「李伊出现在哪些场」「四季常村在哪」
               —— 正文里**提到**某词
  ② speakers  发言人 → 场次:行数     「余烬说过什么」「镜缘的台词」
               —— 某人**说的话**（规范名列），和「正文提到」是两回事

为什么以前错了
  · 初版只索引正文里出现 2 次以上的片段，结果「余烬」只命中 3 场——
    因为 9,986 行台词都记在**规范名**列，正文是他讲的内容，不会自称。
  · 初版还按「每场 top N」截断，长尾实体（李伊）被高频组合挤掉，
    必须改成**先按全局词频选词，再回填场次分布**。

用法
    python tools/build_invert.py [--force]
"""
import argparse
import collections
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RD = os.path.join(W, "docs", "records", "session")
OUT = os.path.join(W, "docs", "records", "invert.json")

# 注意：数字**不能**放进「含该字就否决」的黑名单。
# 「四季常村」的「四」会因此被误杀（实测该词正文出现 155 次却进不了索引）。
# 数字只在「整词全是数字」时才排除，见 valid_term。
STOP_CHARS = set(
    "的了是我你他她它们这那有和与就都也不没很太更最个上下来到去把被让给对从为以于而但可"
    "能要会什怎谁哪吗呢吧啊呀哦嗯请您"
)
NUMERIC_RE = re.compile(r"^[\d一二三四五六七八九十百千万亿两]+$")
MIN_GLOBAL_FREQ = 12   # 全局至少出现这么多次才入选
MIN_SESSIONS = 2       # 至少出现在 2 个场次
MAX_TERMS = 5000
CJK_RUN = re.compile(r"[\u4e00-\u9fff]{2,}")


def valid_term(t):
    if not (2 <= len(t) <= 4):
        return False
    if NUMERIC_RE.match(t):        # 整词是数字才排除
        return False
    if any(ch in STOP_CHARS for ch in t):
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(RD) if f.endswith(".tsv"))
    print("第一遍：统计全局词频（%d 个场次）…" % len(files))

    freq = collections.Counter()
    speakers = collections.defaultdict(collections.Counter)   # 发言人 -> {场次: 行数}
    total_rows = 0

    for f in files:
        sess = f[:-4]
        with io.open(os.path.join(RD, f), encoding="utf-8") as fh:
            head = next(fh).rstrip("\n").split("\t")
            iName = head.index("规范名")
            iBody = head.index("正文")
            for ln in fh:
                c = ln.rstrip("\n").split("\t")
                if len(c) < len(head):
                    continue
                total_rows += 1
                name = c[iName].strip()
                if name and name != "匿名玩家":
                    speakers[name][sess] += 1
                for seg in CJK_RUN.findall(c[iBody]):
                    n = len(seg)
                    for size in (2, 3, 4):
                        for i in range(n - size + 1):
                            t = seg[i:i + size]
                            if valid_term(t):
                                freq[t] += 1

    print("   %d 行，候选词 %d 个，发言人 %d 个"
          % (total_rows, len(freq), len(speakers)))

    selected = [t for t, c in freq.items() if c >= MIN_GLOBAL_FREQ]
    selected.sort(key=lambda t: -freq[t])
    selected = selected[:MAX_TERMS]
    sel_set = set(selected)
    print("   入选 %d 个词（全局频次 >= %d）" % (len(selected), MIN_GLOBAL_FREQ))

    # ── 第二遍：回填每个词的场次分布 ──
    print("第二遍：回填场次分布…")
    term_sessions = collections.defaultdict(lambda: collections.Counter())
    for f in files:
        sess = f[:-4]
        with io.open(os.path.join(RD, f), encoding="utf-8") as fh:
            head = next(fh).rstrip("\n").split("\t")
            iBody = head.index("正文")
            local = collections.Counter()
            for ln in fh:
                c = ln.rstrip("\n").split("\t")
                if len(c) < len(head):
                    continue
                for seg in CJK_RUN.findall(c[iBody]):
                    n = len(seg)
                    for size in (2, 3, 4):
                        for i in range(n - size + 1):
                            t = seg[i:i + size]
                            if t in sel_set:
                                local[t] += 1
            for t, cnt in local.items():
                if cnt >= 2:
                    term_sessions[t][sess] = cnt

    terms = {}
    for t, cnts in term_sessions.items():
        if len(cnts) < MIN_SESSIONS:
            continue
        terms[t] = ["%s:%d" % (k, v) for k, v in cnts.most_common(40)]

    spk = {}
    for name, cnts in speakers.items():
        if sum(cnts.values()) < 20:
            continue
        spk[name] = ["%s:%d" % (k, v) for k, v in cnts.most_common(40)]

    data = {
        "note": "原始记录倒排索引。terms = 正文提到的词 → 场次:次数；"
                "speakers = 发言人的规范名 → 场次:行数（用于「某人说过什么」）。",
        "sessions": len(files),
        "rows": total_rows,
        "count": len(terms),
        "terms": terms,
        "speakers": spk,
    }
    raw = (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    old = open(OUT, "rb").read() if os.path.exists(OUT) else None
    if old != raw or args.force:
        open(OUT, "wb").write(raw)
    print("   写出 invert.json：%d 词 + %d 发言人，%.0f KB"
          % (len(terms), len(spk), len(raw) / 1024))

    print()
    for probe in ("李伊", "四季常村", "希共", "北沙", "镜缘", "余烬", "高冒"):
        v = terms.get(probe)
        if v:
            print("   [词] %-8s %3d 场  %s" % (probe, len(v), v[:2]))
        else:
            print("   [词] %-8s 不在索引" % probe)
    for probe in ("余烬", "镜缘", "海燕与雷电"):
        v = spk.get(probe)
        if v:
            print("   [人] %-8s %3d 场  %s" % (probe, len(v), v[:2]))
        else:
            print("   [人] %-8s 不在索引" % probe)


if __name__ == "__main__":
    main()
