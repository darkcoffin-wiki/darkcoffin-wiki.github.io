#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「石头扔袋子」的导出结果写回 data/subcategories.json。

支持两种导出格式：
* **v2（推荐）**：{"dim":"人物","bags":[{"name":"主角团队","source":"…","tags":[...]}, …]}
  —— 由新版 sorter.html 导出，**包含袋子名与新建的袋子**，可改名、可增删袋子
* **v1（兼容）**：{"dim":"人物","assign":{"叶心":0, …}}
  —— 只改归属、不动袋子结构

用法：
    python tools/apply_sorter_export.py 人物.json
    python tools/apply_sorter_export.py --json "{\"dim\":\"人物\",\"bags\":[…]}" --dry-run

安全措施：
* v1：标签必须存在于该维度、编号必须有效；未提及的标签保留原归属
* v2：每个标签必须存在于该维度；袋子名不得重复/为空；默认**保留原袋子顺序**，
  新增的袋子追加在后面
"""
import argparse
import collections
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

DATA = common.DATA
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def vocab_file_for(dim):
    """维度 → 需要登记新标签的受控词表文件与字段。"""
    return {
        "人物": (os.path.join(DATA, "vocab_people.json"), "people"),
        "组织": (os.path.join(DATA, "vocab_entities.json"), "orgs"),
        "地理": (os.path.join(DATA, "vocab_entities.json"), "places"),
        "设施": (os.path.join(DATA, "vocab_entities.json"), "facilities"),
        "剧情线": (os.path.join(DATA, "vocab_entities.json"), "series"),
    }.get(dim)


def is_real_tag(dim, tag):
    """该标签是否已经是有词表条目的受控标签（tags.json 里带 in_vocab）。"""
    tags = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    m = tags["tags"].get(tag)
    return bool(m and m.get("in_vocab"))


def add_new_stones(dim, stones, dry_run):
    """把分类器里「新建的石头」登记进对应维度的受控词表（entries=0，待确认）。"""
    stones = [s for s in stones if s]
    if not stones:
        return []
    target = vocab_file_for(dim)
    if not target:
        return ["维度 %s 没有对应的词表文件，无法自动登记新石头：%s"
                % (dim, "、".join(stones))]
    path, key = target
    d = json.load(io.open(path, encoding="utf-8"))
    have = {r.get("tag") for r in d.get(key, [])}
    added = []
    for s in stones:
        if s in have:
            continue
        rec = {"tag": s, "entries": 0, "kind": "person" if dim == "人物" else None,
               "confidence": 0, "variants": [],
               "note": "由分类器新建（%s）：花絮里还没有出现，条目数为 0，待作者确认。"
                       % "2026-10-14"}
        if rec["kind"] is None:
            del rec["kind"]
        d.setdefault(key, []).append(rec)
        added.append(s)
    if added and not dry_run:
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    return ["已登记新石头 %d 个到 %s：%s（entries=0，待确认）"
            % (len(added), os.path.basename(path), "、".join(added))] if added else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", help="导出结果 JSON 文件")
    ap.add_argument("--json", dest="raw")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.raw:
        payload = json.loads(args.raw)
    elif args.src:
        payload = json.load(io.open(args.src, encoding="utf-8"))
    else:
        sys.exit("请给一个导出文件，或用 --json 直接粘贴")

    dim = payload.get("dim")
    if not dim:
        sys.exit("结果里缺少 dim")

    tags = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    meta = tags["tags"]
    idx = tags["tag_index"]
    sc = json.load(open(os.path.join(DATA, "subcategories.json"), encoding="utf-8"))
    old = (sc.get("dimensions") or {}).get(dim)
    if not old:
        sys.exit("subcategories.json 里没有维度：%s" % dim)
    real = {t for t, m in meta.items() if dim in (m.get("dimensions") or [])}

    if payload.get("bags"):
        new_groups, problems, report = from_v2(payload["bags"], old, real, idx,
                                               payload.get("newStones") or [],
                                               dim)
    elif payload.get("assign"):
        new_groups, problems, report = from_v1(payload["assign"], old, real, idx)
    else:
        sys.exit("结果里既没有 bags 也没有 assign")

    for line in report:
        print(line)
    if problems:
        print("\n发现问题，未写入：")
        for p in problems:
            print("  x " + p)
        sys.exit(1)
    if args.dry_run:
        print("\n--dry-run：未写入。")
        return

    sc["dimensions"][dim] = new_groups
    with io.open(os.path.join(DATA, "subcategories.json"), "w",
                 encoding="utf-8", newline="\n") as fh:
        json.dump(sc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    extra = add_new_stones(dim, payload.get("newStones") or [], False)
    for line in extra:
        print(line)
    print("\n已写回 data/subcategories.json。接着跑：")
    print("  python tools/check_subcategories.py")
    print("  python tools/tag_entries.py && python tools/build_site.py")


def from_v2(bags, old, real, idx, new_stones=(), dim=""):
    """v2：直接采用导出里的袋子结构（可改名/新增/删除），并登记新建的石头。"""
    problems, report = [], []
    names = [b.get("name", "").strip() for b in bags]
    if any(not n for n in names):
        problems.append("有袋子没有名字")
    dup = [n for n, c in collections.Counter(names).items() if c > 1 and n]
    if dup:
        problems.append("袋子名重复：%s" % "、".join(dup))

    # 允许出现在袋子里的标签 = 该维度已有的真实标签 + 本次新建的石头
    allowed = set(real) | set(s for s in new_stones if s)
    for b in bags:
        bad = [t for t in (b.get("tags") or []) if t not in allowed]
        if bad:
            problems.append("袋子「%s」里有不存在的标签（也不在 newStones 里）：%s"
                            % (b.get("name"), "、".join(bad[:6])))
    if problems:
        return None, problems, []

    fresh = [s for s in new_stones if s and not is_real_tag(dim, s)]
    if fresh:
        report.append("新建的石头会登记进词表（entries=0，待确认）：%s"
                      % "、".join(fresh))

    old_by_name = {g["name"]: g for g in old}
    new_groups = []
    for b in bags:
        name = b["name"].strip()
        g = {"name": name}
        src = b.get("source") or old_by_name.get(name, {}).get("source", "")
        if src:
            g["source"] = src
        g["tags"] = sorted(set(b.get("tags") or []), key=lambda t: -len(idx.get(t, [])))
        new_groups.append(g)
    dropped = [g["name"] for g in old if g["name"] not in set(names)]
    report.append("袋子 %d → %d 个（以导出内容为准）" % (len(old), len(new_groups)))
    if dropped:
        report.append("  被删掉的袋子：%s" % "、".join(dropped))
    report.append("  标签合计 %d 个" % sum(len(g["tags"]) for g in new_groups))
    for i, g in enumerate(new_groups, 1):
        report.append("  %2d. %-20s %3d 个" % (i, g["name"], len(g["tags"])))
    return new_groups, [], report


def from_v1(assign, old, real, idx):
    """v1：只改归属，袋子结构不动；未提及的标签保留原归属。"""
    problems = []
    bad_tag = sorted(t for t in assign if t not in real)
    bad_bag = sorted({v for v in assign.values()
                      if not isinstance(v, int) or v < 0 or v >= len(old)})
    if bad_tag:
        problems.append("标签不存在于该维度：%s" % "、".join(bad_tag[:8]))
    if bad_bag:
        problems.append("袋子编号越界：%s（本维度只有 %d 个袋子）" % (bad_bag, len(old)))
    if problems:
        return None, problems, []

    current = {}
    for gi, g in enumerate(old):
        for t in g.get("tags") or []:
            current.setdefault(t, gi)
    final = dict(current)
    final.update(assign)
    buckets = collections.defaultdict(list)
    for t, gi in final.items():
        if t in real:
            buckets[gi].append(t)
    new_groups = []
    for gi, g in enumerate(old):
        rec = {"name": g["name"],
               "tags": sorted(buckets.get(gi, []), key=lambda t: -len(idx[t]))}
        if g.get("source"):
            rec["source"] = g["source"]
        new_groups.append(rec)
    moved = sum(1 for t, gi in assign.items() if current.get(t) != gi)
    report = ["%s：%d 个标签 → %d 个袋子；本次移动 %d 个"
              % ("", sum(len(g["tags"]) for g in new_groups),
                 len([g for g in new_groups if g["tags"]]), moved)]
    for i, g in enumerate(new_groups, 1):
        report.append("  %2d. %-20s %3d 个" % (i, g["name"], len(g["tags"])))
    return new_groups, [], report


if __name__ == "__main__":
    main()
