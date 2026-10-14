#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""增量更新：加入新花絮时只重建受影响的页面。

流程（对应《项目说明书》3.4）
----------------------------
1. `--scan`   扫描 source/ 里**尚未登记**的 md（按文件名与内容哈希判断），
              为它们分配**延续的** id（不重排既有编号），登记进 data/entries.json
2. 只对新增/变更条目重新打标（tag_entries.py --only-new 的逻辑内联在这里）
3. 只重写「受影响的」页面：新条目页 + 其标签页 + 首页 + search.json

用法
----
    python tools/update.py --check      # 只报告有哪些新文件，不改动
    python tools/update.py              # 登记 + 打标 + 重建受影响页面
    python tools/update.py --rebuild-all  # 忽略增量，全量重建

新文件命名约定：`hx-NNN-标题.md`（NNN 由脚本自动分配，也可先自己命名，
脚本会尊重已存在的编号并只在冲突时重新分配）。
"""
import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

W = common.W
SRC = common.SRC
DATA = common.DATA


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def slug_from_title(title):
    """文件名用的短 slug：去掉标点，保留中文（与既有文件风格一致）。"""
    t = re.sub(r"^[^：:]{1,8}[：:]\s*", "", title)
    t = re.sub(r"[？?！!。，,、；;：:\"'“”‘’《》()（）\[\]【】\s]+", "-", t)
    return t.strip("-")[:40] or "untitled"


def scan_new():
    """返回 source/ 下未登记（或内容已变）的 md 列表。"""
    idx_path = os.path.join(DATA, "entries.json")
    idx = json.load(open(idx_path, encoding="utf-8"))
    known = {e["file"]: e for e in idx["entries"]}
    new, changed = [], []
    for p in sorted(glob.glob(os.path.join(SRC, "hx-*.md"))):
        fn = os.path.basename(p)
        if fn.startswith("_"):
            continue
        fm, body = common.read_entry(p)
        h = content_hash(body)
        if fn not in known:
            new.append((p, fn, fm, body, h))
        elif known[fn].get("source_hash") != h:
            changed.append((p, fn, fm, body, h))
    return idx, new, changed


def next_ids(idx, n):
    used = {e["id"] for e in idx["entries"]}
    nums = [int(e["id"].split("-")[1]) for e in idx["entries"] if e["id"].startswith("hx-")]
    nxt = max(nums) + 1 if nums else 1
    out = []
    for _ in range(n):
        while "hx-%03d" % nxt in used:
            nxt += 1
        out.append("hx-%03d" % nxt)
        used.add("hx-%03d" % nxt)
        nxt += 1
    return out


def register(idx, new, changed):
    """把新文件登记进 entries.json（就地更新，不重排既有 id）。"""
    ids = next_ids(idx, len(new))
    added = []
    for (p, fn, fm, body, h), eid in zip(new, ids):
        title = fm.get("title") or os.path.basename(p)[:-3]
        kind = fm.get("kind") or "花絮"
        rec = {
            "id": eid,
            "title": title,
            "kind": kind,
            "collection": fm.get("collection", ""),
            "origin": fm.get("origin", "site"),
            "file": fn,
            "chars": len(body),      # 与 fix_hashes.py 同口径
            "source_hash": h,
        }
        idx["entries"].append(rec)
        added.append(rec)
    # 内容变更：刷新哈希与字数（id、链接不变）
    by_file = {e["file"]: e for e in idx["entries"]}
    for p, fn, fm, body, h in changed:
        e = by_file.get(fn)
        if e:
            e["source_hash"] = h
            e["chars"] = len(body)
    idx["entry_count"] = len(idx["entries"])
    common.write_json(os.path.join(DATA, "entries.json"), idx)
    return added


def run(cmd):
    r = subprocess.run([sys.executable] + cmd, cwd=W, capture_output=True, text=True,
                       encoding="utf-8")
    if r.returncode != 0:
        sys.stderr.write(r.stdout or "")
        sys.stderr.write(r.stderr or "")
        raise SystemExit("failed: %s" % " ".join(cmd))
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--rebuild-all", action="store_true")
    ap.add_argument("--no-build", action="store_true", help="只登记与打标，不生成站点")
    args = ap.parse_args()

    idx, new, changed = scan_new()
    print(json.dumps({"new": [f for _, f, *_ in new],
                      "changed": [f for _, f, *_ in changed]}, ensure_ascii=False))
    if args.check:
        return
    if not new and not changed and not args.rebuild_all:
        print("没有新文件，也没有内容变更。")
        return

    if new:
        added = register(idx, new, changed)
        print("已登记 %d 条：%s" % (len(added), ", ".join(a["id"] for a in added)))
    elif changed:
        register(idx, [], changed)
        print("已刷新 %d 条变更条目的哈希。" % len(changed))

    # 只对新增/变更条目重算标签（其余沿用 tags.json 里的结果）
    print(run(["tools/tag_entries.py", "--only-new", "--report"]))
    if not args.no_build:
        print(run(["tools/build_site.py"]))


if __name__ == "__main__":
    main()
