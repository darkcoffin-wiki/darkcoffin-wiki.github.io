#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析《黑柩跑团剧情志》的 25 个 markdown → 结构化 JSON。

输入（只读，不改动源文件）：
    E:\\黑柩\\黑柩跑团剧情志\\
        00-目录与说明.md
        NPC总表.md
        场次志\\<季>.md      （12 个，一季一份，一场一张卡）
        季志\\<季>.md        （12 个，固定十节）
        参考资料\\*.md

输出（写到 heijiu/trpg-data/）：
    corpus.json      总览：季列表、统计、缺口
    seasons.json     12 个季志的结构化内容
    sessions.json    113 张场次卡
    npcs.json        379 人
    parse_report.md  解析报告（异常、字段缺失、结构偏差）

用法：
    python tools/parse_trpg.py
    python tools/parse_trpg.py --src "E:\\黑柩\\黑柩跑团剧情志" --out trpg-data
"""
import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numbering as NB  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_SRC = r"E:\黑柩\黑柩跑团剧情志"

# 场次卡的 12 个固定字段（顺序即渲染顺序）
SESSION_FIELDS = [
    ("现实时间", "realtime"),
    ("游戏内时间", "ingame_time"),
    ("世界层", "world_layer"),
    ("地点", "places"),
    ("在场", "present"),
    ("剧情摘要", "summary"),
    ("关键决策点", "decisions"),
    ("骰点", "dice"),
    ("伤亡／退场", "casualties"),
    ("收场状态", "end_state"),
    ("伏笔／钩子", "hooks"),
    ("出处", "sources"),
]
FIELD_BY_CN = {cn: key for cn, key in SESSION_FIELDS}

# 季志的固定十节
# 短团：文件名以「短团·」开头，与 12 个主季**分开归类**
SHORT_PREFIX = "短团·"


def is_short(name):
    return (name or "").startswith(SHORT_PREFIX)


# 短团沿用同一套十节结构，但两节的措辞是「本团」而非「本季」
# （《00-目录与说明》称之为「本团概览」；这里归一到「本季…」以便下游统一处理）
SECTION_ALIAS = {"本团概览": "本季概览", "本团新增设定": "本季新增设定"}


def norm_section(title):
    """小节名归一化：去分层序号 + 把「本团」别名折回「本季」。"""
    t = strip_number(title)
    return SECTION_ALIAS.get(t, t)


SEASON_SECTIONS = [
    "本季概览", "场次索引", "季摘要", "登场人物", "势力与组织动态",
    "主要冲突与结局", "骰点统计", "本季新增设定", "未收伏笔汇总", "完整度与存疑",
]

SEASON_RE = re.compile(r"^##\s+第\s*(\d+)\s*场\s*$", re.M)
SUBHEAD_RE = re.compile(r"^#{2,4}\s+(.+)$", re.M)


def read(path):
    return io.open(path, encoding="utf-8").read()


def norm_name(fn):
    """从文件名得到季名：`第七季·太阳照常升起.md` → `第七季·太阳照常升起`"""
    return fn[:-3] if fn.endswith(".md") else fn


# ══════════════════════════════════════════════════════════════
# 通用小工具
# ══════════════════════════════════════════════════════════════
def split_sections(text):
    """按 ## 切分为 [(标题, 正文)]（不含 ### 层）。"""
    out, cur, buf = [], None, []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if cur is not None:
                out.append((cur, "\n".join(buf).strip()))
            cur, buf = m.group(1), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out.append((cur, "\n".join(buf).strip()))
    return out


CN_NUM = "一二三四五六七八九十"


def strip_number(title):
    """`一、本季概览` → `本季概览`；`七、骰点统计` → `骰点统计`。"""
    m = re.match(r"^[%s]+[、.．]\s*(.+)$" % CN_NUM, title.strip())
    return m.group(1).strip() if m else title.strip()


def find_section(sections, want):
    """按去序号后的名字找小节，返回 (原标题, 正文)。"""
    for title, body in sections:
        if strip_number(title) == want:
            return title, body
    return None, None


def split_h3(body):
    """把一段正文按 ### 切分为 [(小标题, 正文)]；没有小标题则返回 [('', 全文)]。"""
    parts, cur, buf = [], None, []
    for line in body.splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            if cur is not None:
                parts.append((cur, "\n".join(buf).strip()))
            cur, buf = m.group(1), []
        elif cur is not None:
            buf.append(line)
        elif line.strip():
            buf.append(line)
    if cur is not None:
        parts.append((cur, "\n".join(buf).strip()))
    return parts or [("", body.strip())]


def bullets(body, numbered_only=False, stop_at_heading=True):
    """提取条目。

    numbered_only=True  → 只要 `1. ` 这类有序项（决策点就是这个格式）
    stop_at_heading    → 遇到 `### ` 小标题就停（避免把「剧情摘要」里的列表项算进来）
    """
    out, stop = [], False
    for line in body.splitlines():
        if stop_at_heading and re.match(r"^#{2,6}\s", line):
            stop = True
            continue
        if stop:
            continue
        m = re.match(r"^(\s*)(?:[-*]\s+|\d+\.\s+)(.*)$", line)
        if not m:
            continue
        if numbered_only and not re.match(r"^\s*\d+\.\s+", line):
            continue
        out.append((len(m.group(1)), m.group(2).strip()))
    return out


def md_tables(body):
    """解析所有 markdown 表格 → [(表头, 数据行)]（NPC 总表里有两张）。"""
    tables, rows = [], []

    def flush():
        if len(rows) >= 2:
            def cells(l):
                return [c.strip() for c in l.strip().strip("|").split("|")]
            head = cells(rows[0])
            data = [cells(r) for r in rows[2:]
                    if not re.match(r"^\|[\s:\-|]+\|$", r.strip())]
            tables.append((head, data))

    for line in body.splitlines():
        if line.strip().startswith("|"):
            rows.append(line)
        else:
            flush()
            rows = []
    flush()
    return tables


def md_table(body):
    """兼容旧调用：返回第一张表。"""
    ts = md_tables(body)
    return ts[0] if ts else ([], [])


# ══════════════════════════════════════════════════════════════
# 1) 季志
# ══════════════════════════════════════════════════════════════
def parse_season(name, text, issues):
    rec = {"name": name, "sections": {}, "overview": {}, "index": [],
           "summary": [], "cast": "", "factions": "", "conflicts": "",
           "dice_stats": "", "new_settings": "", "hooks": "", "completeness": ""}
    secs = split_sections(text)
    found = [s for s, _ in secs]
    rec["section_order"] = found
    # 用归一化名比对（短团写「本团概览」，主季写「本季概览」，语义相同）
    missing = [s for s in SEASON_SECTIONS
               if not any(norm_section(f) == s for f in found)]
    if missing:
        issues.append(("季志·缺小节", name, "、".join(missing)))
    extra = [s for s in found
             if norm_section(s) not in SEASON_SECTIONS and s != name]
    if extra:
        rec["extra_sections"] = extra

    for title, body in secs:
        key = norm_section(title)
        rec["sections"][key] = body
        if key == "本季概览":
            for line in body.splitlines():
                m = re.match(r"^-\s*\*\*(.+?)\*\*[：:]\s*(.*)$", line.strip())
                if m:
                    rec["overview"][m.group(1).strip()] = m.group(2).strip()
        elif key == "场次索引":
            head, rows = md_table(body)
            rec["index_head"] = head
            for r in rows:
                if len(r) >= 4:
                    rec["index"].append({"id": r[0], "realtime": r[1],
                                         "place": r[2], "gist": r[3]})
        elif key == "季摘要":
            rec["summary"] = [{"title": t, "text": b} for t, b in split_h3(body)]
        elif key == "登场人物":
            rec["cast"] = body
            rec["cast_parts"] = [{"title": t, "text": b} for t, b in split_h3(body)]
        elif key == "势力与组织动态":
            rec["factions"] = body
        elif key == "主要冲突与结局":
            rec["conflicts"] = body
        elif key == "骰点统计":
            rec["dice_stats"] = body
        elif key == "本季新增设定":
            rec["new_settings"] = body
        elif key == "未收伏笔汇总":
            rec["hooks"] = body
        elif key == "完整度与存疑":
            rec["completeness"] = body

    if not rec["index"]:
        issues.append(("季志·场次索引表为空", name, ""))

    # ── 分层序号（作者要求：所有标题都要有层级编号）──
    # 第 1 层：一、本季概览 … 十、完整度与存疑
    rec["sections_numbered"] = [
        {"no": no, "pure": pure, "title": titled, "text": body}
        for no, pure, titled, body in NB.number_sections(rec["sections"], level=1)
    ]
    # 第 2 层：季摘要下的（一）（二）…
    rec["summary"] = NB.number_items(rec["summary"], key="title", level=2)
    if rec.get("cast_parts"):
        rec["cast_parts"] = NB.number_items(rec["cast_parts"], key="title", level=2)
    # 目录（渲染时直接用）
    rec["toc"] = ([{"level": 1, "no": s["no"], "title": s["title"], "text": ""}
                   for s in rec["sections_numbered"]]
                  + [{"level": 2, "no": p["no"], "title": p["numbered"],
                      "text": ""} for p in rec["summary"] if p["pure"]])
    return rec


# ══════════════════════════════════════════════════════════════
# 2) 场次志
# ══════════════════════════════════════════════════════════════
def parse_sessions(season_name, text, issues):
    """取 `### 第 N 场` 之间的内容，按 12 个固定字段切分。"""
    marks = list(SEASON_RE.finditer(text))
    out = []
    for i, m in enumerate(marks):
        num = int(m.group(1))
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[start:end].strip()
        rec = {"season": season_name, "no": num, "fields": {}, "extra": {},
               "summary_parts": [], "dice": [], "decisions": [], "hooks": []}

        # 按 `- **字段**：` 切块（顶层）
        blocks, cur, buf = [], None, []
        for line in body.splitlines():
            fm = re.match(r"^-\s*\*\*(.+?)\*\*\s*[：:]\s*(.*)$", line)
            if fm:
                if cur:
                    blocks.append((cur, "\n".join(buf).strip()))
                cur, buf = fm.group(1).strip(), [fm.group(2)]
            elif cur is not None:
                buf.append(line)
        if cur:
            blocks.append((cur, "\n".join(buf).strip()))

        for cn, content in blocks:
            key = FIELD_BY_CN.get(cn)
            if key:
                rec["fields"][key] = content
                rec["fields_cn"] = rec.get("fields_cn", {})
                rec["fields_cn"][key] = cn
            else:
                # 自定义加粗条目（如第七季的游乐设施清单）
                rec["extra"][cn] = content

        # 结构化的子项
        if "summary" in rec["fields"]:
            rec["summary_parts"] = [{"title": t, "text": b}
                                    for t, b in split_h3(rec["fields"]["summary"])]
        if "decisions" in rec["fields"]:
            rec["decisions"] = [t for _i, t in
                                bullets(rec["fields"]["decisions"],
                                        numbered_only=True)]
        if "hooks" in rec["fields"]:
            rec["hooks"] = [t for _i, t in bullets(rec["fields"]["hooks"])]
        if "dice" in rec["fields"]:
            for _i, t in bullets(rec["fields"]["dice"]):
                parts = [p.strip() for p in t.split("·")]
                rec["dice"].append({"raw": t, "parts": parts})

        miss = [cn for cn, key in SESSION_FIELDS if key not in rec["fields"]]
        if miss:
            issues.append(("场次·缺字段", "%s 第%d场" % (season_name, num),
                           "、".join(miss)))
        rec["missing_fields"] = miss
        rec["n_dice"] = len(rec["dice"])
        rec["n_decisions"] = len(rec["decisions"])
        rec["n_summary_parts"] = len(rec["summary_parts"])
        rec["chars"] = len(body)
        rec["hanzi"] = len(re.findall(r"[\u4e00-\u9fff]", body))

        # ── 分层序号（作者要求）──
        # 第 1 层：一、现实时间 … 十二、出处（12 个固定字段，按定义顺序）
        rec["fields_numbered"] = [
            {"key": key, "cn": cn, "no": NB.level1(i), "title": NB.level1(i) + cn,
             "text": rec["fields"].get(key, "")}
            for i, (cn, key) in enumerate(SESSION_FIELDS, 1)
        ]
        # 第 2 层：剧情摘要下的（一）（二）…
        rec["summary_parts"] = NB.number_items(rec["summary_parts"],
                                               key="title", level=2)
        rec["toc"] = ([{"level": 1, "no": f["no"], "title": f["title"]}
                       for f in rec["fields_numbered"] if f["text"]]
                      + [{"level": 2, "no": p["no"], "title": p["numbered"]}
                         for p in rec["summary_parts"] if p["pure"]])
        out.append(rec)

    decl = 0
    m = re.search(r"共\s*(\d+)\s*场", text)
    if m:
        decl = int(m.group(1))
    if decl and decl != len(out):
        issues.append(("场次·数量与声明不符", season_name,
                       "声明 %d 场，解析到 %d 场" % (decl, len(out))))
    return out, decl


# ══════════════════════════════════════════════════════════════
# 3) NPC 总表
# ══════════════════════════════════════════════════════════════
def parse_npcs(text, issues):
    """NPC 总表含两张表：主表（379 人，9 列）+ 附录（11 人，3 列）。"""
    tables = md_tables(text)
    main, appendix = [], []
    out = []
    for head, rows in tables:
        ncol = len(head)
        if ncol >= 8:
            for r in rows:
                if len(r) < 8:
                    issues.append(("NPC·主表行列数不足", r[0] if r else "?", str(len(r))))
                    continue
                out.append({
                    "no": r[0], "name": r[1], "aliases": r[2], "role": r[3],
                    "faction": r[4], "first_seen": r[5],
                    "appearances": int(r[6]) if r[6].isdigit() else r[6],
                    "desc": r[7],
                })
        elif ncol == 3:
            for r in rows:
                if len(r) >= 3:
                    appendix.append({"no": r[0], "name": r[1], "note": r[2]})
        else:
            issues.append(("NPC·未知表格", "列数 %d" % ncol, "表头 " + "|".join(head)))
    out.sort(key=lambda x: -(x["appearances"] if isinstance(x["appearances"], int) else 0))
    return {"head": tables[0][0] if tables else [],
            "npcs": out, "appendix": appendix}


# ══════════════════════════════════════════════════════════════
# 4) 目录说明（提取季清单与体量）
# ══════════════════════════════════════════════════════════════
def parse_index(text, issues):
    info = {"seasons": [], "raw_sections": [s for s, _ in split_sections(text)]}
    for title, body in split_sections(text):
        if title == "收录范围":
            head, rows = md_table(body)
            for r in rows:
                if len(r) >= 4 and r[0] != "季":
                    info["seasons"].append({
                        "name": r[0], "sessions": r[1], "realtime": r[2],
                        "completeness": r[3]})
        elif title == "体量":
            for line in body.splitlines():
                m = re.match(r"^-\s*(.+?)[：:]\s*\*?\*?([\d,]+)\s*汉字", line.strip())
                if m:
                    info[m.group(1).strip()] = int(m.group(2).replace(",", ""))
        elif title == "已知缺口":
            info["gaps_md"] = body
        elif title == "时间轴怎么理解":
            info["timeline_note"] = body
    return info


# ══════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=os.path.join(W, "trpg-data"))
    args = ap.parse_args()

    if not os.path.isdir(args.src):
        sys.exit("找不到源目录：%s" % args.src)
    out_dir = args.out if os.path.isabs(args.out) else os.path.join(W, args.out)
    os.makedirs(out_dir, exist_ok=True)

    issues = []

    # 目录说明
    idx_path = os.path.join(args.src, "00-目录与说明.md")
    info = parse_index(read(idx_path), issues) if os.path.exists(idx_path) else {}

    # 季志
    seasons = []
    sdir = os.path.join(args.src, "季志")
    for fn in sorted(os.listdir(sdir)):
        if fn.endswith(".md"):
            nm = norm_name(fn)
            rec = parse_season(nm, read(os.path.join(sdir, fn)), issues)
            rec["kind"] = "short" if is_short(nm) else "main"
            seasons.append(rec)

    # 场次志
    sessions, declared = [], {}
    xdir = os.path.join(args.src, "场次志")
    for fn in sorted(os.listdir(xdir)):
        if fn.endswith(".md"):
            nm = norm_name(fn)
            ss, decl = parse_sessions(nm, read(os.path.join(xdir, fn)), issues)
            declared[nm] = decl
            sessions.extend(ss)

    # 短团与主季分开统计
    n_short = sum(1 for x in seasons if x.get("kind") == "short")
    print("  季志：主季 %d ｜ 短团 %d" % (len(seasons) - n_short, n_short))

    # 季志与场次志配对检查
    snames = {s["name"] for s in seasons}
    xnames = set(declared)
    if snames - xnames:
        issues.append(("配对·季志多于场次志", "、".join(sorted(snames - xnames)), ""))
    if xnames - snames:
        issues.append(("配对·场次志多于季志", "、".join(sorted(xnames - snames)), ""))

    # NPC
    npc_path = os.path.join(args.src, "NPC总表.md")
    npcs = parse_npcs(read(npc_path), issues) if os.path.exists(npc_path) else {"npcs": []}

    # 参考资料
    refs = []
    rdir = os.path.join(args.src, "参考资料")
    if os.path.isdir(rdir):
        for fn in sorted(os.listdir(rdir)):
            if fn.endswith(".md"):
                t = read(os.path.join(rdir, fn))
                refs.append({"name": norm_name(fn), "chars": len(t),
                             "preview": t.strip().splitlines()[0] if t.strip() else ""})

    # ── 写文件 ──
    def dump(name, obj):
        with io.open(os.path.join(out_dir, name), "w",
                     encoding="utf-8", newline="\n") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1)
        return os.path.getsize(os.path.join(out_dir, name))

    sess_out = []
    for s in sessions:
        s2 = dict(s)
        s2.pop("fields", None)
        s2["fields"] = s["fields"]
        sess_out.append(s2)

    sizes = {
        "corpus.json": dump("corpus.json", {
            "source": args.src, "index": info, "counts": {
                "seasons": len(seasons), "sessions": len(sessions),
                "npcs": len(npcs["npcs"]),
                "sessions_declared": declared,
            }, "refs": refs}),
        "seasons.json": dump("seasons.json", seasons),
        "sessions.json": dump("sessions.json", sess_out),
        "npcs.json": dump("npcs.json", npcs),
    }

    # ── 解析报告 ──
    tot_chars = sum(s["chars"] for s in sessions)
    tot_hanzi = sum(s["hanzi"] for s in sessions)
    lines = ["# 跑团剧情志 · 解析报告", "",
             "来源：`%s`" % args.src, ""]
    lines += ["## 一、总量", "",
              "| 项 | 数量 |", "|---|---:|",
              "| 季 | %d |" % len(seasons),
              "| 场次卡 | %d |" % len(sessions),
              "| 场次正文（纯汉字） | %s 字 |" % format(tot_hanzi, ","),
              "| 场次正文（含 markdown 的字符数） | %s |" % format(tot_chars, ","),
              "| NPC | %d 人（＋附录 %d 个待查名） |" % (len(npcs["npcs"]),
                                                     len(npcs.get("appendix") or [])),
              "| 参考资料 | %d 份 |" % len(refs), "",
              "> 作者说明里标注「场次志 526,838 汉字」；本报告按纯汉字统计得 %s，"
              "差异来自统计口径（是否计入 markdown 语法与英数字）。" % format(tot_hanzi, ","),
              ""]

    lines += ["## 二、每季解析结果", "",
              "| 季 | 场次 | 声明 | 正文(汉字) | 季摘要小节 | 场次索引 | 骰点 | 决策点 | 自定义字段 | 缺字段场次 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in seasons:
        ss = [x for x in sessions if x["season"] == s["name"]]
        lines.append("| %s | %d | %s | %s | %d | %d | %d | %d | %d | %d |" % (
            s["name"], len(ss), declared.get(s["name"], "?"),
            format(sum(x["hanzi"] for x in ss), ","),
            len(s["summary"]), len(s["index"]),
            sum(x["n_dice"] for x in ss), sum(x["n_decisions"] for x in ss),
            len({k for x in ss for k in x["extra"]}),
            sum(1 for x in ss if x["missing_fields"])))
    lines.append("")

    missing_sec = [s for s in seasons if len(s["section_order"]) != 10]
    lines += ["## 三、结构偏差", ""]
    if missing_sec:
        for s in missing_sec:
            lines.append("- **%s**：小节 %d 个（应为 10）→ %s"
                         % (s["name"], len(s["section_order"]),
                            "、".join(s["section_order"])))
    else:
        lines.append("- 12 份季志的十节结构**全部齐全**，无缺失、无多余。")
    lines.append("")
    bykind = {}
    for kind, where, detail in issues:
        bykind.setdefault(kind, []).append((where, detail))
    if bykind:
        lines += ["## 四、发现的问题", ""]
        for kind, items in sorted(bykind.items()):
            lines.append("### %s（%d 处）" % (kind, len(items)))
            for where, detail in items[:40]:
                lines.append("- %s%s" % (where, ("：" + detail) if detail else ""))
            if len(items) > 40:
                lines.append("- …（其余 %d 处略）" % (len(items) - 40))
            lines.append("")
    else:
        lines += ["## 四、发现的问题", "", "无。", ""]

    lines += ["## 五、每季摘要小节", ""]
    for s in seasons:
        lines.append("- **%s**：%s" % (s["name"],
                     "、".join(x["title"] for x in s["summary"]) or "（无）"))
    lines.append("")
    lines += ["## 六、季志「本季概览」的字段（判断能否自动出首页）", ""]
    keys = {}
    for s in seasons:
        for k in s["overview"]:
            keys.setdefault(k, 0)
            keys[k] += 1
    for k, v in sorted(keys.items(), key=lambda kv: -kv[1]):
        lines.append("- `%s`（%d/12 季有）" % (k, v))
    lines.append("")
    lines += ["## 七、产出文件", ""]
    for k, v in sizes.items():
        lines.append("- `%s`：%.1f KB" % (k, v / 1024))

    rep_path = os.path.join(out_dir, "parse_report.md")
    with io.open(rep_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")

    print("解析完成 →", out_dir)
    print(json.dumps({"seasons": len(seasons), "sessions": len(sessions),
                      "npcs": len(npcs["npcs"]), "refs": len(refs),
                      "issues": len(issues), "session_chars": tot_chars},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
