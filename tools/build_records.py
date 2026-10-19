#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把跑团原始记录脱敏切片，供「黑柩问答」检索取证。

输入
  E:\\黑柩\\黑柩跑团记录-整理\\归一数据\\全部消息.tsv    （237,878 行 × 15 列）
  trpg-data/sessions.json                              （152 场的结构化摘要）

输出（提交进仓库，由 GitHub Pages 直接服务）
  docs/records/index.json          152 场索引：季/场/时间/地点/在场/摘要/关键词
  docs/records/session/{s}-{nn}.tsv   每场一个脱敏切片

脱敏规则（按作者《检索取证与写作流程》的读者向要求）
  · 删除 QQ（账号）与 发言名（群名片）两列 —— 账号数字一律不出现
  · **名字兜底**：有些玩家没设群名片，QQ 号被当成了「规范名」（实测 14 行），
    这些行改写成「匿名玩家」；正文里出现的真实 QQ 号替换为「[已隐去]」
  · 删除 来源/日期/回复/字数/身份依据（问答用不到）
  · 只保留 季 场 序号 时间 规范名 类型 正文
  · 只保留 类型 ∈ {台词, 旁白, 舞台}（去掉 噪声/骰/系统/空/损坏）

用法
  python tools/build_records.py            # 增量（已存在且源未更新则跳过）
  python tools/build_records.py --force    # 强制重建
"""
import argparse
import io
import json
import os
import re
import sys
import unicodedata

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_TSV = r"E:\黑柩\黑柩跑团记录-整理\归一数据\全部消息.tsv"
SRC_SESS = os.path.join(W, "trpg-data", "sessions.json")
OUT = os.path.join(W, "docs", "records")

# 原记录里的季简称 → wiki 的正式季名
SEASON_MAP = {
    "一": "第一季·星灯之谜",
    "二": "第二季·星都陨落",
    "三": "第三季·青都疑云",
    "四上": "第四季上·夜都曙光",
    "四下": "第四季下·夜都曙光",
    "四结局": "第四季下·夜都曙光",
    "五": "第五季·青都大选",
    "六": "第六季·血与火",
    "七": "第七季·太阳照常升起",
    "八": "第八季·人民万岁",
    "九上": "第九季上·阳谋",
    "九下": "第九季下·再聚",
    "幕间二": "幕间季二·狂飙",
    "重置版": "短团·重置版·星都陨落",
    "西沙": "短团·西沙",
    "食龙": "短团·食龙则肥",
    "竖棺": "短团·竖棺",
}

KEEP_TYPES = ("台词", "旁白", "舞台")

# QQ 号长度通常 9~11 位。只在「确实出现在原始 QQ 列里」时才替换，
# 避免误伤正文里的游戏数值（如希联币金额、编号）。
QQ_RE = re.compile(r"(?<!\d)(\d{5,12})(?!\d)")
ANON_NAME = "匿名玩家"
MASK = "[已隐去]"


NUMERIC_NAME_RE = re.compile(r"\d{5,12}")


def collect_qq(tsv_path):
    """收集所有「像账号」的号码。

    除了 QQ 列，还要扫规范名/发言名——实测有人 QQ 列为空、名字直接是一串号码
    （如 1659838404 共 7 条），只按 QQ 列收集会漏。
    """
    out = set()
    with io.open(tsv_path, encoding="utf-8") as fh:
        hdr = next(fh).rstrip("\n").split("\t")
        cols = [i for i, h in enumerate(hdr) if h in ("QQ", "规范名", "发言名")]
        if not cols:
            return out
        for ln in fh:
            p = ln.rstrip("\n").split("\t")
            for i in cols:
                if len(p) > i:
                    v = p[i].strip()
                    if v and NUMERIC_NAME_RE.fullmatch(v):
                        out.add(v)
    return out


def make_scrubber(qq_set):
    def scrub(text):
        if not text:
            return text
        return QQ_RE.sub(
            lambda m: MASK if m.group(1) in qq_set else m.group(1), text)
    return scrub
DROP_COLS = ("来源", "日期", "QQ", "发言名", "回复", "字数", "身份依据")
KEEP_COLS = ("季", "场", "序号", "时间", "规范名", "类型", "正文")


def season_slug_map(sess):
    """按 sessions.json 里的季出现顺序编号 s01..s16，避免中文文件名。"""
    order, seen = [], set()
    for s in sess:
        if s["season"] not in seen:
            seen.add(s["season"])
            order.append(s["season"])
    return {name: "s%02d" % (i + 1) for i, name in enumerate(order)}, order


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(SRC_TSV):
        sys.exit("找不到原始记录：%s" % SRC_TSV)
    if not os.path.exists(SRC_SESS):
        sys.exit("找不到 trpg-data/sessions.json，请先跑 parse_trpg.py")

    sess = json.load(io.open(SRC_SESS, encoding="utf-8"))
    slug_of, season_order = season_slug_map(sess)

    # 只保留 sessions.json 里真实存在的 (季, 场)。
    # 实测原始记录里「第一季」有第 3、4 场的零散留言，但整理后的季志只有 2 场，
    # 若不过滤会生成 index 里查不到、也没人用的孤儿切片。
    valid = set()
    for x in sess:
        try:
            valid.add((x["season"], int(str(x["no"]).strip())))
        except (ValueError, KeyError):
            pass

    # ── 读取 TSV，按 (季全名, 场) 分组 ──
    groups = {}          # key -> list of rows
    print("正在收集 QQ 号集合…")
    qq_set = collect_qq(SRC_TSV)
    print("   原始记录里的 QQ 号：%d 个" % len(qq_set))
    scrub = make_scrubber(qq_set)

    idx = None
    kept = dropped = 0
    unknown_season = {}
    name_masked = body_masked = 0

    with io.open(SRC_TSV, encoding="utf-8") as fh:
        header = next(fh).rstrip("\n").split("\t")
        idx = {h: i for i, h in enumerate(header)}
        for ln in fh:
            p = ln.rstrip("\n").split("\t")
            if len(p) < len(header):
                continue
            typ = p[idx["类型"]]
            if typ not in KEEP_TYPES:
                dropped += 1
                continue
            raw_season = p[idx["季"]]
            full = SEASON_MAP.get(raw_season)
            if not full:
                unknown_season[raw_season] = unknown_season.get(raw_season, 0) + 1
                full = raw_season
            no = p[idx["场"]].strip()
            try:
                no_i = int(re.sub(r"\D", "", no) or 0)
            except ValueError:
                no_i = 0
            if no_i <= 0:
                dropped += 1
                continue
            if (full, no_i) not in valid:
                continue          # 不在季志里的零散场次，跳过
            row = [p[idx[c]] for c in KEEP_COLS]
            # 规范名兜底：没设群名片的人，QQ 号会直接变成名字。
            # 名字不应该是纯数字，所以**只要形如号码就匿名**（不依赖是否在 QQ 列里）。
            nm = row[4].strip()
            if nm and NUMERIC_NAME_RE.fullmatch(nm):
                row[4] = ANON_NAME
                name_masked += 1
            # 其它列里的真实 QQ 号一律隐去
            for ci in range(len(row)):
                if ci == 4:
                    continue
                cleaned = scrub(row[ci])
                if cleaned != row[ci]:
                    body_masked += 1
                    row[ci] = cleaned
            # 整条消息就是一串 5~12 位数字的情况（实测 3 条，像是随手发的号/验证码）。
            # 这种条目没有语义，直接换成占位符，零误伤。
            body = row[6].strip()
            if body and NUMERIC_NAME_RE.fullmatch(body):
                row[6] = "[数字]"
                body_masked += 1
            groups.setdefault((full, no_i), []).append(row)
            kept += 1

    print("读入 %d 条，保留 %d 条，丢弃 %d 条（噪声/骰/系统等）"
          % (kept + dropped, kept, dropped))
    print("脱敏：规范名改写 %d 条，其它列替换账号 %d 处" % (name_masked, body_masked))
    if unknown_season:
        print("⚠️ 未映射的季名：%s" % unknown_season)

    # ── 写切片 ──
    sdir = os.path.join(OUT, "session")
    os.makedirs(sdir, exist_ok=True)
    written = 0
    total_bytes = 0
    manifest = []

    for (season, no), rows in sorted(groups.items(),
                                     key=lambda kv: (season_order.index(kv[0][0])
                                                     if kv[0][0] in season_order else 99,
                                                     kv[0][1])):
        slug = slug_of.get(season, "s??")
        fn = "%s-%02d.tsv" % (slug, no)
        path = os.path.join(sdir, fn)
        buf = io.StringIO()
        buf.write("\t".join(KEEP_COLS) + "\n")
        for r in rows:
            buf.write("\t".join(r) + "\n")
        txt = buf.getvalue()
        data = txt.encode("utf-8")
        total_bytes += len(data)
        old = None
        if os.path.exists(path) and not args.force:
            old = open(path, "rb").read()
        if old != data:
            open(path, "wb").write(data)
            written += 1
        manifest.append({
            "season": season, "no": no, "file": "session/" + fn,
            "rows": len(rows), "bytes": len(data),
        })

    print("写出 %d 个场次切片（新建/更新 %d 个），合计 %.1f MB"
          % (len(manifest), written, total_bytes / 1e6))

    # 删掉本次没生成的旧切片。
    # 实测：原始记录里「第一季」有第 3、4 场的零散留言，但 sessions.json 只整理了 2 场，
    # 于是会留下 index 未引用的孤儿文件 —— 清掉，免得 Pages 上挂着一堆没人用的数据。
    used = {os.path.basename(m["file"]) for m in manifest}
    pruned = 0
    for f in os.listdir(sdir):
        if f.endswith(".tsv") and f not in used:
            os.remove(os.path.join(sdir, f))
            pruned += 1
    if pruned:
        print("清理孤儿切片 %d 个" % pruned)

    # ── 写索引（用 sessions.json 的摘要）──
    by_key = {(m["season"], m["no"]): m for m in manifest}
    entries = []
    for s in sess:
        season = s["season"]
        try:
            no = int(str(s["no"]).strip())
        except ValueError:
            continue
        m = by_key.get((season, no))
        if not m:
            continue
        f = s.get("fields") or {}
        summary = (f.get("summary") or "").replace("\n", " ").strip()
        entries.append({
            "season": season,
            "slug": slug_of.get(season, "s??"),
            "no": no,
            "file": m["file"],
            "rows": m["rows"],
            "chars": s.get("chars") or 0,
            "realtime": (f.get("realtime") or "")[:120],
            "places": (f.get("places") or "")[:200],
            "present": (f.get("present") or "")[:200],
            "end_state": (f.get("end_state") or "")[:200],
            "summary": summary[:600],
        })

    index = {
        "note": "黑柩跑团记录索引：152 场。summary 摘自 trpg-data/sessions.json（场次志），"
                "file 指向脱敏后的原始记录切片（TSV：季 场 序号 时间 规范名 类型 正文）。"
                "已删除 QQ 号与群名片两列。",
        "seasons": season_order,
        "count": len(entries),
        "entries": entries,
    }
    ipath = os.path.join(OUT, "index.json")
    data = (json.dumps(index, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    old = open(ipath, "rb").read() if os.path.exists(ipath) else None
    if old != data:
        open(ipath, "wb").write(data)
        print("写出 index.json（%d 场，%.0f KB）" % (len(entries), len(data) / 1024))
    else:
        print("index.json 无变化（%d 场）" % len(entries))

    # 汇总
    miss = len(sess) - len(entries)
    print("\n汇总：sessions.json %d 场 ｜ 切片 %d 场 ｜ 未匹配 %d"
          % (len(sess), len(entries), miss))
    if miss:
        have = {(e["season"], e["no"]) for e in entries}
        for s in sess:
            try:
                no = int(str(s["no"]).strip())
            except ValueError:
                continue
            if (s["season"], no) not in have:
                print("   缺：%s 第 %d 场" % (s["season"], no))


if __name__ == "__main__":
    main()
