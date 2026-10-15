#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""试验：跑团文本里出现多少花絮站标签（评估跨站互链成本）。

只做「能不能直接对上」这一件事：把花絮站已有的受控标签（人物/组织/地理/设施/剧情线）
拿到跑团场次卡与季志正文里做**最长匹配、不重叠**扫描，统计：
* 有多少个标签真的出现在跑团文本里
* 出现了多少次（总命中）
* 命中量最高的那些是哪些
* 抽几处上下文人工看是否"对得上"（会不会误链）

只读，不改任何数据。用法：python tools/probe_crosslinks.py
"""
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import tag_entries as TE  # noqa: E402

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRPG = os.path.join(W, "trpg-data")
ENT = {"人物", "组织", "地理", "设施", "剧情线"}


def main():
    tags = json.load(open(os.path.join(W, "data", "tags.json"), encoding="utf-8"))
    meta = tags["tags"]
    labels, matchers, entities, ov, contained = TE.load_vocab()

    # 只要实体类标签
    keep = {t for t, m in meta.items() if set(m.get("dimensions") or []) & ENT}
    ent_matchers = [m for m in matchers if m[0] in keep]
    print("花絮站实体类标签：%d 个 ｜ 参与匹配的写法（含别名）：%d 条"
          % (len(keep), len(ent_matchers)))

    sess = json.load(open(os.path.join(TRPG, "sessions.json"), encoding="utf-8"))
    seas = json.load(open(os.path.join(TRPG, "seasons.json"), encoding="utf-8"))

    hits = Counter()
    per_tag_entries = defaultdict(set)
    samples = defaultdict(list)
    total_chars = 0

    def scan(body, where, is_session):
        """对一段文本做最长匹配，累加命中与上下文。"""
        nonlocal total_chars
        total_chars += len(body)
        for (canon, dim), cnt in TE.longest_matches(body, ent_matchers).items():
            if canon not in keep:
                continue
            hits[canon] += cnt
            per_tag_entries[canon].add(where)
            if len(samples[canon]) < 2:
                # 用标签名本身回找一处上下文
                i = body.find(canon)
                if i < 0:
                    i = 0
                samples[canon].append(
                    (where, re.sub(r"\s+", " ", body[max(0, i - 34):i + 44])))

    # 场次卡
    for s in sess:
        body = "\n".join(str(v) for v in s.get("fields", {}).values())
        scan(body, "%s 第%d场" % (s["season"], s["no"]), True)
    # 季志
    for s in seas:
        body = "\n".join(str(v) for v in (s.get("sections") or {}).values())
        scan(body, "%s（季志）" % s["name"], False)

    print("跑团文本合计：%s 字符" % format(total_chars, ","))
    print("命中标签种类：%d / %d（%.0f%% 的花絮标签能在跑团里找到）"
          % (len(hits), len(keep), 100 * len(hits) / max(1, len(keep))))
    print("总命中次数：%s" % format(sum(hits.values()), ","))
    print()
    print("=== 命中最多（前 30）===")
    for t, c in hits.most_common(30):
        dims = "、".join(meta[t].get("dimensions") or [])
        print("   %-12s %5d 次  [%s]  %d 篇/场" % (t, c, dims, len(per_tag_entries[t])))
    print()
    print("=== 只命中 1–2 次的标签数（低置信，建议不链）===")
    low = [t for t, c in hits.items() if c <= 2]
    print("   %d 个标签，占总命中标签的 %.0f%%" % (len(low), 100 * len(low) / max(1, len(hits))))
    print("   例：", "、".join(sorted(low)[:24]))
    print()
    print("=== 上下文抽查（命中量 3–40 的中间地带，最容易误链）===")
    mid = [t for t, c in hits.items() if 3 <= c <= 40]
    for t in sorted(mid)[:14]:
        dims = "、".join(meta[t].get("dimensions") or [])
        print("   【%s】[%s] 命中 %d 次" % (t, dims, hits[t]))
        for where, ctx in samples[t][:1]:
            print("        %s：…%s…" % (where, ctx))
    return


if __name__ == "__main__":
    main()
