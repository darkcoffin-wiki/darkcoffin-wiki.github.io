#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""人名判别器：把「真名」与「同形常用词」分开。

思路（语料自带信号）
--------------------
这套花絮的剧本式段落用 `名字：对白` 标出发言人，散文段落用 `名字说/道/问`。
因此对每个候选名统计两类证据：

* **标签位**：出现于行首或紧跟对话开头的 `名字：`（连续两次出现更可信，如 `叶心：……`）
* **一般位**：其余出现

真名：标签位占比高，或虽无标签位但只出现在叙述性称谓位置。
同形词（如「容易」「望风」「洗尘」）：一般位占绝对多数，且后面常接虚词。

产出：data/name_audit.md（供人工审核）+ data/name_audit.json

用法：python tools/name_audit.py
"""
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

W = common.W
SRC = common.SRC
DATA = common.DATA

LABEL = re.compile(r"(?:^|\n)\s*(?:\*\*)?%s(?:\*\*)?\s*[：:]")
# 常见「非名字」后继字：同形词后面往往接这些
STOP_NEXT = set("的了我你他她它们是在有和与就都也还很太再又只从到对向把被让使给"
                "易于得着过起来去出进上下里外前后中之间时候会能要想说")


def main():
    p = os.path.join(DATA, "vocab_people.json")
    if not os.path.exists(p):
        sys.exit("缺少 data/vocab_people.json")
    v = json.load(open(p, encoding="utf-8"))
    docs = []
    for f in sorted(glob.glob(os.path.join(SRC, "hx-*.md"))):
        docs.append((os.path.basename(f).split("-")[1], common.read_entry(f)[1]))

    rows = []
    for r in v.get("people", []):
        names = [r["tag"]] + list(r.get("variants") or [])
        label_hits = general_hits = 0
        bad_next = collections.Counter()
        ctxs = []
        for name in names:
            pat = re.compile(r"(?:^|\n)\s*(?:\*\*)?%s(?:\*\*)?\s*[：:]" % re.escape(name))
            for eid, body in docs:
                label_hits += len(pat.findall(body))
                for m in re.finditer(re.escape(name), body):
                    i = m.start()
                    pre = body[i - 1] if i > 0 else "\n"
                    is_label = pre in "\n\r" and body[m.end():m.end() + 1] in "：:"
                    if is_label:
                        continue
                    general_hits += 1
                    nxt = body[m.end():m.end() + 1]
                    if nxt in STOP_NEXT:
                        bad_next[nxt] += 1
                    if len(ctxs) < 3:
                        ctxs.append("%s: …%s…" % (eid, body[max(0, i - 24):i + 26]
                                                  .replace("\n", " ")))
        tot = label_hits + general_hits
        ratio = label_hits / tot if tot else 0
        bad = sum(bad_next.values())
        bad_ratio = bad / general_hits if general_hits else 0
        rows.append({"tag": r["tag"], "entries": r.get("entries", 0),
                     "label_hits": label_hits, "general_hits": general_hits,
                     "label_ratio": round(ratio, 3),
                     "bad_next": bad, "bad_ratio": round(bad_ratio, 3),
                     "confidence": r.get("confidence", 1),
                     "suspect": bool(tot and ratio < 0.15 and bad_ratio >= 0.5),
                     "ctx": ctxs})

    rows.sort(key=lambda r: (-r["bad_ratio"], -r["general_hits"]))
    common.write_json(os.path.join(DATA, "name_audit.json"), {"rows": rows})

    suspects = [r for r in rows if r["suspect"]]
    md = ["# 人名判别报告\n",
          "判定依据：`bad_ratio` = 该词后面的字属于常用虚词/动词的比例（同形词高）；",
          "`label_ratio` = 出现在「名字：」发言位（真名高）。\n",
          "## 疑似同形词（建议从词表移除）：%d 个\n" % len(suspects),
          "| 名 | 篇数 | 标签位 | 一般位 | 标签位占比 | 虚词后继占比 | 疑似 |",
          "|---|---:|---:|---:|---:|---:|:-:|"]
    for r in suspects:
        md.append("| %s | %d | %d | %d | %.2f | %.2f | ⚠ |"
                  % (r["tag"], r["entries"], r["label_hits"], r["general_hits"],
                     r["label_ratio"], r["bad_ratio"]))
    md.append("\n## 全部人名（按虚词后继比例降序）\n")
    md.append("| 名 | 篇数 | 标签位占比 | 虚词后继占比 | 上下文 |")
    md.append("|---|---:|---:|---:|---|")
    for r in rows:
        md.append("| %s | %d | %.2f | %.2f | %s |"
                  % (r["tag"], r["entries"], r["label_ratio"], r["bad_ratio"],
                     r["ctx"][0][:70] if r["ctx"] else ""))
    with open(os.path.join(DATA, "name_audit.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(md) + "\n")
    print(json.dumps({"people": len(rows), "suspects": len(suspects),
                      "suspect_names": [r["tag"] for r in suspects][:40]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
