#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为词表重建生成「证据报表」：候选 × 篇覆盖数 × 上下文片段。

用法：python tools/vocab_evidence.py
产出：
    data/evidence_people.md    旧词表 289 名 + n-gram 人名候选
    data/evidence_orgs.md      机构/地名/设施候选（n-gram，高边界熵）
每个候选给出：
    n_entries  出现在多少篇里
    n_total    总出现次数
    ctx        最多 3 条上下文片段（各 24 字窗口）
"""
import glob
import json
import os
import re
import collections

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(W, "source")
DATA = os.path.join(W, "data")
CTX_WIN = 22


def body_of(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    return text


def load_entries():
    out = []
    for f in sorted(glob.glob(os.path.join(SRC, "hx-*.md"))):
        raw = open(f, encoding="utf-8").read()
        eid = os.path.basename(f).split("-")[1] + "-" + os.path.basename(f).split("-")[2]
        out.append((eid, os.path.basename(f), body_of(raw)))
    return out


def main():
    entries = load_entries()
    old = json.load(open(os.path.join(DATA, "vocabulary.json"), encoding="utf-8"))
    cand = json.load(open(os.path.join(DATA, "entity_candidates.json"), encoding="utf-8"))

    old_tags = [p["tag"] for p in old["people"] if p["tag"] != "薇薇安"]
    ng_people = [r["tag"] for r in cand["people_candidates"]
                 if r["count"] >= 8 and r["entropy"] >= 1.3 and len(r["tag"]) <= 5]
    ng_orgs = [r["tag"] for r in cand["proper_candidates"]
               if r["count"] >= 10 and r["entropy"] >= 2.2]

    def measure(tag):
        hitting, total, ctxs = [], 0, []
        for eid, fn, text in entries:
            c = text.count(tag)
            if c:
                hitting.append(eid)
                total += c
                if len(ctxs) < 3:
                    i = text.find(tag)
                    a = max(0, i - CTX_WIN)
                    b = min(len(text), i + len(tag) + CTX_WIN)
                    ctxs.append(text[a:b].replace("\n", " "))
        return hitting, total, ctxs

    def report(tags, path, title):
        rows = []
        for t in dict.fromkeys(tags):
            hitting, total, ctxs = measure(t)
            rows.append({"tag": t, "n_entries": len(hitting), "n_total": total,
                         "entries": hitting, "ctx": ctxs})
        rows.sort(key=lambda r: (-r["n_entries"], -r["n_total"], r["tag"]))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# %s\n\n共 %d 个候选\n\n" % (title, len(rows)))
            for r in rows:
                fh.write("## %s  [篇=%d 次=%d]\n" % (r["tag"], r["n_entries"], r["n_total"]))
                if r["ctx"]:
                    fh.write("   ctx: " + " ⏐ ".join(r["ctx"]) + "\n")
                fh.write("   ids: " + (",".join(r["entries"][:12]) +
                                       ("…" if len(r["entries"]) > 12 else "")) + "\n\n")
        return rows

    r1 = report(old_tags + ng_people, os.path.join(DATA, "evidence_people.md"),
                "人名候选证据（旧词表 289 + n-gram，去重后）")
    r2 = report(ng_orgs, os.path.join(DATA, "evidence_orgs.md"),
                "机构/地名/设施候选证据（n-gram 高边界熵）")

    # 旧词表里在 210 篇中「完全没出现」的名
    missing = [r["tag"] for r in r1 if r["n_entries"] == 0]
    with open(os.path.join(DATA, "evidence_missing.md"), "w", encoding="utf-8") as fh:
        fh.write("# 旧词表中在新语料 210 篇里**零命中**的名（%d 个）\n\n" % len(missing))
        for t in missing:
            fh.write("- %s\n" % t)

    print(json.dumps({
        "people_candidates": len(r1),
        "org_candidates": len(r2),
        "old_zero_hit": len(missing),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
