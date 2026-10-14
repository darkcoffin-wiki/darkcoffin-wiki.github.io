#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一哈希口径（一次性维护脚本）。

**哈希契约**（所有脚本必须一致，否则增量更新每次都误判为「全变了」）：
    source_hash = sha256(正文字节).hexdigest()[:16]
    其中「正文」= md 文件去掉 YAML frontmatter 之后的部分，UTF-8 编码，**不做任何其他处理**
    （不 strip、不折叠空白、不改行尾——这样任何内容改动都会改变哈希）。

历史原因：entries.json 里原有的 source_hash 是切分阶段用「整文件」算的，
而 tools/update.py 按「正文」算，导致 --check 时 210 篇全部被判定为变更。
本脚本按上面的契约重算全部哈希，使两者一致。

用法：
    python tools/fix_hashes.py --check     # 只报告不一致
    python tools/fix_hashes.py             # 重算并写回 entries.json
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

DATA = common.DATA
SRC = common.SRC


def body_hash(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    path = os.path.join(DATA, "entries.json")
    idx = json.load(open(path, encoding="utf-8"))
    changed = []
    for e in idx["entries"]:
        p = os.path.join(SRC, e["file"])
        _, body = common.read_entry(p)
        h = body_hash(body)
        if e.get("source_hash") != h:
            changed.append((e["id"], e.get("source_hash"), h))
        e["source_hash"] = h
        # chars 与哈希同一口径：**正文字符数**（含空白），与 tools/update.py 一致
        e["chars"] = len(body)
    if args.check:
        print(json.dumps({"mismatch": len(changed),
                          "sample": changed[:5]}, ensure_ascii=False))
        return
    common.write_json(path, idx)
    print(json.dumps({"updated": len(idx["entries"]),
                      "was_mismatched": len(changed)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
