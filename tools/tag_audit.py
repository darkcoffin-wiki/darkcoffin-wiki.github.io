#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打标自检：把「可能漏标」的篇目自动挑出来。

思路：用**正文自身的信号**去质疑打标结果，而不是靠人抽查。
命中任一规则就列出该篇，供人工复核。

规则
----
R1 有对白但无人物标签：出现多处 `名字：` 形式的发言位，却没有任何人物标签
R2 家庭成员词很多但无「亲族」：正文出现 ≥4 次父亲/母亲/哥哥/姐姐… 却没打亲族
R3 出现明确组织名但无该组织标签
R4 人物标签只有 1 个却篇幅 ≥2500 字（长文通常不止一个人）
R5 出现 `我叫X`/`名叫X`/`叫作X` 且该名字不在词表内（候选新角色）

用法：python tools/tag_audit.py
产出：data/tag_audit.md
"""
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

FAMILY = ["父亲", "母亲", "哥哥", "姐姐", "弟弟", "妹妹", "儿子", "女儿",
          "爷爷", "奶奶", "叔叔", "舅舅", "姨妈", "爸妈", "父母", "妈妈", "爸爸"]
SPEAKER = re.compile(r"(?:^|\n)\s*(?:\*\*)?([\u4e00-\u9fffA-Za-z0-9·]{2,8})(?:\*\*)?\s*[：:]")
NAMED = re.compile(r"(?:我叫|名叫|叫作|叫做|名字是|绰号|被称为|人称)[“\"']?([\u4e00-\u9fff·]{2,6})")


def main():
    tags = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    meta, idx = tags["tags"], tags["tag_index"]
    people = {t for t, m in meta.items() if "人物" in (m.get("dimensions") or [])}
    orgs = {t for t, m in meta.items() if "组织" in (m.get("dimensions") or [])}
    flags = collections.defaultdict(list)
    detail = {}

    for e in tags["entries"]:
        eid = e["id"]
        rec = next(x for x in common.load_entries() if x["id"] == eid)
        body = rec["body"]
        p_tags = [t for t in e["tags"] if t in people]
        o_tags = [t for t in e["tags"] if t in orgs]
        msgs = []

        # R1
        speakers = {m.group(1) for m in SPEAKER.finditer(body)}
        speakers = {s for s in speakers if not re.fullmatch(r"[A-Za-z0-9]+", s)}
        if len(speakers) >= 3 and not p_tags:
            msgs.append("R1 有 %d 个发言位（%s）但无人物标签"
                        % (len(speakers), "、".join(sorted(speakers)[:6])))

        # R2
        fam = sum(body.count(k) for k in FAMILY)
        if fam >= 4 and not any("亲族" == t for t in e["tags"]):
            msgs.append("R2 亲属词 %d 次但未打「亲族」" % fam)

        # R3 正文出现组织名但未打标签——只在「没有更长写法吸收了它」时报
        # （避免 希共 被 希共中央 吸收后误报）
        miss_org = []
        for o in orgs:
            if o in e["tags"] or o not in body:
                continue
            absorbed = any(o != t and o in t and t in e["tags"] for t in orgs)
            if not absorbed:
                miss_org.append(o)
        if miss_org:
            msgs.append("R3 正文出现组织但未打标签：%s" % "、".join(sorted(miss_org)[:5]))

        # R4
        if len(p_tags) == 1 and e["chars"] >= 2500:
            msgs.append("R4 长篇（%d 字）却只有 1 个人物标签（%s）" % (e["chars"], p_tags[0]))

        # R5 疑似新名字——从严：2~4 个汉字、**正文出现 ≥2 次**、
        # 且不是常见词/代词/机构词尾（早期版本把「资本主义」「希望联邦人民」也抓进来了）
        NOISE = re.compile(r"^(?:什么|他们|你们|我们|她们|这个|那个|一个|没有|就是|什么|"
                           r"可以|不能|不知道|这样|那样|现在|以后|时候)")
        BADTAIL = re.compile(r"(主义|联邦|人民|政府|公司|集团|组织|社会|世界|城市|"
                             r"装置|者|们|的|了|是|有|不|在|和|与|就|都)$")
        news = set()
        for m in NAMED.finditer(body):
            n = m.group(1)
            if (2 <= len(n) <= 4 and body.count(n) >= 2 and n not in people
                    and not any(n == x or n in x for x in people)
                    and not NOISE.match(n) and not BADTAIL.search(n)):
                news.add(n)
        if news:
            msgs.append("R5 疑似新名字（出现≥2次）：%s" % "、".join(sorted(news)[:5]))

        if msgs:
            detail[eid] = {"title": e["title"], "chars": e["chars"], "msgs": msgs}
            for m in msgs:
                flags[m.split()[0]].append(eid)

    L = ["# 打标自检\n",
         "共 %d 篇被挑出（%d 篇总计）。这些**不一定是错的**——是值得人工看一眼的。\n"
         % (len(detail), len(tags["entries"])),
         "| 规则 | 命中篇数 | 含义 |", "|---|---:|---|",
         "| R1 | %d | 有多个对白发言位却无人物标签 |" % len(flags["R1"]),
         "| R2 | %d | 亲属词多但未打「亲族」 |" % len(flags["R2"]),
         "| R3 | %d | 正文出现组织名但未打该组织标签 |" % len(flags["R3"]),
         "| R4 | %d | 长篇却只有 1 个人物标签 |" % len(flags["R4"]),
         "| R5 | %d | 出现疑似新名字（不在词表） |" % len(flags["R5"]),
         ""]
    for eid, d in sorted(detail.items()):
        L.append("## %s %s（%d 字）" % (eid, d["title"], d["chars"]))
        for m in d["msgs"]:
            L.append("- %s" % m)
        L.append("")
    with io.open(os.path.join(DATA, "tag_audit.md"), "w",
                 encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")
    print(json.dumps({"entries_flagged": len(detail),
                      "R1": len(flags["R1"]), "R2": len(flags["R2"]),
                      "R3": len(flags["R3"]), "R4": len(flags["R4"]),
                      "R5": len(flags["R5"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
