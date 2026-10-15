#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读《设定集-修改建议》文件，产出 lore-data/overrides.json。

**这是可审阅的中间产物**：把「人工写作的建议」转成解析器可执行的结构。
生成后请打开 overrides.json 核对，确认无误再建站。

提取三类东西
------------
1. `sections`  —— 卷五/卷六 的节归属（13 个节，取自原作者的分组标签）
2. `entries`   —— 需要**替换正文**的词条（卷七「斯卡雷特帝国」用合并稿）
3. `seealso`   —— 需要加「另见」交叉引用的词条

用法：python tools/lore_overrides.py
"""
import io
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = r"E:\DSHwork\heijiu\设定集-修改建议-卷五卷六分节与斯卡雷特整合.md"
OUT = os.path.join(W, "lore-data", "overrides.json")


def find_block(lines, start_pat, stop_pats):
    """从匹配 start_pat 的行之后开始，直到命中任一 stop_pats，返回行列表。"""
    s = None
    for i, l in enumerate(lines):
        if re.match(start_pat, l):
            s = i + 1
            break
    if s is None:
        return []
    out = []
    for l in lines[s:]:
        if any(re.match(p, l) for p in stop_pats):
            break
        out.append(l)
    return out


def main():
    if not os.path.exists(SRC):
        sys.exit("找不到建议文件：%s" % SRC)
    text = io.open(SRC, encoding="utf-8").read()
    lines = text.split("\n")

    # ── 1) 卷五/卷六 的节归属 ──
    i2 = next((i for i, l in enumerate(lines) if l.startswith("# 第二部分")), None)
    i3 = next((i for i, l in enumerate(lines) if l.startswith("# 第三部分")), None)
    body = lines[i2:i3]
    sections, cur_vol, cur_sec = {}, None, None
    for ln in body:
        m = re.match(r"^## (第五卷|第六卷)[　\s]*(.+)$", ln.strip())
        if m:
            cur_vol = ("卷五 " if m.group(1) == "第五卷" else "卷六 ") + m.group(2).strip()
            sections.setdefault(cur_vol, [])
            cur_sec = None
            continue
        m = re.match(r"^### (.+)$", ln)
        if m and cur_vol:
            cur_sec = m.group(1).strip()
            sections[cur_vol].append({"name": cur_sec, "entries": []})
            continue
        m = re.match(r"^#### (.+)$", ln)
        if m and cur_vol and cur_sec:
            sections[cur_vol][-1]["entries"].append(m.group(1).strip())

    # ── 2) 卷七「斯卡雷特帝国」合并稿 ──
    merged = find_block(
        lines, r"^## 3\.1　建议的新「斯卡雷特帝国」词条",
        [r"^## 3\.2"])
    merged_txt = "\n".join(merged).strip()
    # 去掉引用块形式的「标记说明」注记（换行会打断单行匹配，故按行过滤）
    merged_txt = "\n".join(
        l for l in merged_txt.split("\n")
        if not re.match(r"^>\s*(标记说明|\*\*合并稿中未出现)", l.strip())
        and "标记说明" not in l and "合并稿中未出现的内容" not in l).strip()
    # 去掉编纂过程标记：【并】＝取自卷五版（合并已完成，读者不需要看到）
    merged_txt = re.sub(r"\*\*【并】\*\*\s*", "", merged_txt)
    merged_txt = re.sub(r"【并】\s*", "", merged_txt)

    # ── 3) 「另见」交叉引用（建议 5 第 5 条）──
    seealso = [
        {"title": "斯卡雷特帝国（血族国家政权）", "vol": "卷五 神圣希望帝国",
         "note": "本词条为卷五版；**内容更完整的合并稿见「卷七 · 斯卡雷特帝国」**。",
         "href": ""},
        {"title": "帝国号角", "vol": "卷五 神圣希望帝国",
         "note": "卷七另有一处侧重不同的同名词条。",
         "href": ""},
        {"title": "天使", "vol": "卷六 进化者同盟",
         "note": "卷七另有一处侧重不同的同名词条。", "href": ""},
        {"title": "星都战争", "vol": "卷六 进化者同盟",
         "note": "卷七另有一处侧重不同的同名词条。", "href": ""},
    ]

    # ── 4) 待删除词条 ──
    # 作者 2026-10-14 决定：**不删**卷五的「斯卡雷特帝国」，保留并在其上标「另见卷七合并稿」，
    # 这样卷五「斯卡雷特帝国」节不会变空，读者也能找到更完整的版本。
    drop = []

    out = {
        "source": SRC,
        "note": "由 tools/lore_overrides.py 从《修改建议》提取；请人工核对后建站。",
        "sections": sections,
        "replace_entries": [
            {"title": "斯卡雷特帝国", "vol": "卷七 走廊区与中立势力",
             "text": merged_txt, "from": "建议 3.1 合并稿"}
        ],
        "drop_entries": drop,
        "seealso": seealso,
    }
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(
        json.dumps(out, ensure_ascii=False, indent=1) + "\n")

    print("已写出 %s" % OUT)
    for v, secs in sections.items():
        print("  %s：%d 节" % (v, len(secs)))
        for s in secs:
            print("     %-22s %d 条" % (s["name"], len(s["entries"])))
    print("  合并稿字数：%s 字符（%d 行）"
          % (format(len(merged_txt), ","), merged_txt.count("\n") + 1))
    print("  待删除词条：%d ｜ 另见标记：%d" % (len(drop), len(seealso)))


if __name__ == "__main__":
    main()
