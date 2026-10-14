#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从生成的 HTML 里抽出「标签 → 精选示例」，把栏目介绍语草稿升级为有据可查的版本。

用法：python tools/featured_draft.py
产出：data/featured_draft.md —— 每个候选栏目下，列出该标签的**首段**片段，
      这样写介绍语时能引用真实情节，而不是凭猜。
"""
import html
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

W = common.W
DATA = common.DATA
DOCS = os.path.join(W, "docs")


def first_para(body, n=120):
    for chunk in re.split(r"\n\s*\n", body.strip()):
        c = chunk.strip()
        if len(c) >= 24 and not c.startswith("#"):
            return re.sub(r"\s+", "", c)[:n]
    return ""


def main():
    data = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    cand_path = os.path.join(DATA, "featured_candidates.json")
    if not os.path.exists(cand_path):
        sys.exit("先运行 tools/featured_candidates.py")
    cand = json.load(open(cand_path, encoding="utf-8"))
    by_id = {e["id"]: e for e in common.load_entries()}

    out = ["# 栏目介绍语素材（每个候选标签下，精选条目的开头片段）\n",
           "> 用途：让介绍语写的是正文里真实发生的事，而不是猜测。\n"]
    for c in cand["candidates"]:
        tag = c["tag"]
        out.append("\n## %s（%s，%d 篇）\n" % (tag, c["dimension"], c["doc_freq"]))
        out.append("**介绍语草稿**：%s\n" % c["blurb_draft"])
        out.append("**按正文首句复核的精选**：\n")
        for eid in c["picks"][:6]:
            e = by_id.get(eid)
            if not e:
                continue
            fp = first_para(e["body"])
            out.append("- `%s` %s\n  - %s" % (eid, e["title"], fp))
        out.append("")
    with open(os.path.join(DATA, "featured_draft.md"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out))
    print(json.dumps({"columns": len(cand["candidates"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
