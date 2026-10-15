#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「跨站互链 · 待过目标签」复核清单。

用途：跑团站要把人名/组织/地名链到花絮站的标签页。为把误链降到最低，
**只链「结构化名单字段」里的名字**（场次卡的【在场】，季志的【登场人物】），
不碰剧情摘要正文。

本脚本把这批标签连同样例列出来给作者过目，作者只需勾掉不该链的。

输出：trpg-data/review_tags.md
用法：python tools/review_tags.py
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
    keep = {t for t, m in meta.items() if set(m.get("dimensions") or []) & ENT}
    em = [m for m in matchers if m[0] in keep]

    sess = json.load(io.open(os.path.join(TRPG, "sessions.json"), encoding="utf-8"))
    seas = json.load(io.open(os.path.join(TRPG, "seasons.json"), encoding="utf-8"))

    hits = Counter()
    where = defaultdict(list)      # tag -> [样例文本]
    contexts = defaultdict(list)   # tag -> [上下文]

    def scan(body, label):
        for (canon, dim), cnt in TE.longest_matches(body, em).items():
            if canon not in keep:
                continue
            hits[canon] += cnt
            if len(where[canon]) < 6:
                where[canon].append(label)
            if len(contexts[canon]) < 3:
                i = body.find(canon)
                if i >= 0:
                    contexts[canon].append(
                        re.sub(r"\s+", " ", body[max(0, i - 30):i + 40]))

    # ① 场次卡：在场 + 地点
    for s in sess:
        body = "\n".join(str(s["fields"].get(k, "")) for k in ("present", "places"))
        scan(body, "%s 第%d场" % (s["season"], s["no"]))
    # ② 季志：登场人物 + 场次索引
    for s in seas:
        body = "\n".join(str(s["sections"].get(k, ""))
                         for k in ("登场人物", "场次索引"))
        scan(body, "%s（季志）" % s["name"])

    rows = sorted(hits.items(), key=lambda kv: (-kv[1], kv[0]))
    out = ["# 跨站互链 · 待过目标签清单", "",
           "## 怎么用这份清单", "",
           "跑团站会把**结构化名单字段**（场次卡的「在场」「地点」、季志的「登场人物」「场次索引」）",
           "里的人名／组织名／地名，链到花絮站对应的标签页。",
           "**剧情摘要正文不做任何链接。**", "",
           "需要你做的：**看一遍下面的标签，把不该链的划掉**（直接在「链接」列写 `否` 即可）。",
           "判断标准很简单：**这个名字在跑团里指的是不是同一个东西**。", "",
           "重点看这几类（最容易出错）：", "",
           "1. **数字序号型**（`1号`～`5号`）——现在已不在名单字段里出现，但保险起见还是列出来",
           "2. **通用词/职务**（如「泡泡」是 KP 的名字，不是角色）",
           "3. **短名**（2 字）——容易和别的词撞",
           "4. **同名不同身份**——两个站里名字相同但不是同一个实体",
           "",
           "---", "",
           "## 汇总", "",
           "| 项 | 数值 |", "|---|---:|",
           "| 结构化名单里出现的花絮站标签 | **%d** 个 |" % len(rows),
           "| 命中总次数 | %s 次 |" % format(sum(hits.values()), ","),
           "| 其中 2 字标签 | %d 个 |" % sum(1 for t, _ in rows if len(t) == 2),
           "| 其中数字序号型 | %d 个 |" % sum(
               1 for t, _ in rows if re.fullmatch(r"[0-9]+号?", t)),
           "",
           "---", "",
           "## 逐个过目", "",
           "| # | 标签 | 维度 | 命中 | 链接 | 出现在（样例） | 一处上下文 |",
           "|---:|---|---|---:|:--:|---|---|"]

    for i, (t, c) in enumerate(rows, 1):
        dims = "、".join(meta[t].get("dimensions") or [])
        w = "、".join(where[t][:3]) + ("…" if len(where[t]) > 3 else "")
        ctx = contexts[t][0] if contexts[t] else ""
        flag = ""
        if re.fullmatch(r"[0-9]+号?", t):
            flag = " ⚠️数字序号"
        elif len(t) == 2:
            flag = " ⚠️短名"
        out.append("| %d | `%s`%s | %s | %d | 是 | %s | …%s… |"
                   % (i, t, flag, dims, c, w, ctx))

    out += ["", "---", "",
            "## 我先替你标出来的可疑项（请重点确认）", ""]
    suspects = [t for t, _ in rows
                if re.fullmatch(r"[0-9]+号?", t) or len(t) == 2]
    out.append("这些是我按规则筛出的**高风险**标签（数字序号型 + 2 字短名）：")
    out.append("")
    out.append("　".join("`%s`" % t for t in suspects))
    out.append("")

    p = os.path.join(TRPG, "review_tags.md")
    io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    print("已生成：%s" % p)
    print("待过目标签 %d 个；其中可疑（数字型+2字短名）%d 个"
          % (len(rows), len(suspects)))
    print("命中总次数 %s" % format(sum(hits.values()), ","))


if __name__ == "__main__":
    main()
