#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析《黑柩设定集·第一版·DSH版.docx》→ 结构化 JSON。

**只读源文件，不改动任何东西。**

为什么要单独写解析器（而不是直接渲染）
--------------------------------------
这份文档有两处「层级不可靠」：

1. 有些 H2 节下**没有 H3**（内容直接挂在 H2 上）；
2. 文档自带一个「目　录」卷，它的层级是**作者认可的权威层级**。

所以本脚本同时抽取两条线索：
  * `by_style`  —— 按 word 样式（Heading1/2/3）反推的层级
  * `by_toc`    —— 文档自带的目录域（若为纯文本则可读）
并把两者**交叉校验**，输出差异清单。

产出（默认写到 lore-data/）：
    doc.json       {vols, sections, entries, notes}  完整结构
    report.md      结构校验报告（层级差异、无 H3 的节、字数分布）
    toc.json       目录域提取结果（若可读）

用法：
    python tools/parse_lore.py
    python tools/parse_lore.py --src "路径.docx" --out lore-data
"""
import argparse
import io
import json
import os
import re
import sys
import zipfile
from collections import Counter, OrderedDict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numbering  # noqa: E402  分层序号 / 标题清洗（去掉尾随页码）

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 作者 2026-10-14：结构源改为 **1.1 版**（1.1 已含全部结构改动与 7 条合并稿，
# 由设定集侧的对话直接生成 docx；本站不再用 overrides 做结构改写）
DEFAULT_SRC = r"E:\黑柩\黑柩小说花絮\黑柩设定集·1.1版·DSH版.docx"
SOURCE_VERSION = "1.1"

# 段落 → 纯文本
W_T = re.compile(r"<w:t[^>]*>([^<]*)</w:t>")
P_STYLE = re.compile(r'<w:pStyle w:val="([^"]+)"')


def style_map(path):
    """读 styles.xml：styleId → (样式名, 大纲层级)。

    这份 DSH 版的 pStyle 用的是**数字 ID**（3/4/5…），不是 "Heading1"，
    所以必须查表。返回 {"3": ("heading 1", 0), ...}
    """
    z = zipfile.ZipFile(path)
    xml = z.read("word/styles.xml").decode("utf-8", "replace")
    out = {}
    for m in re.finditer(r'<w:style\b[^>]*w:styleId="([^"]+)"[^>]*>(.*?)</w:style>',
                         xml, re.S):
        sid, body, whole = m.group(1), m.group(2), m.group(0)
        if 'w:type="paragraph"' not in whole:
            continue
        nm = re.search(r'<w:name w:val="([^"]*)"', body)
        name = nm.group(1) if nm else ""
        ol = re.search(r'<w:outlineLvl w:val="(\d+)"', body)
        out[sid] = (name, int(ol.group(1)) if ol else None)
    return out


# 依据样式名/大纲层级判断这是第几级标题（None 表示不是标题）
def heading_level(style_name, outline):
    n = (style_name or "").lower()
    m = re.match(r"heading\s*(\d)", n)
    if m:
        return int(m.group(1))
    if outline is not None and 0 <= outline <= 5:
        return outline + 1
    return None
# 目录项的常见特征：段落里有超链接锚点 _Toc 或样式名含 toc
TOC_HINT = re.compile(r'_Toc\d+|toc\s*\d+', re.I)

HANZI = re.compile(r"[\u4e00-\u9fff]")


TAIL_PAGE = re.compile(r"\s{0,3}(\d{1,3})\s*$")   # 标题尾随的页码


def strip_page_no(text, max_page):
    """去掉标题尾随的页码（如「黑柩世界（世界结构）28」→「黑柩世界（世界结构）」）。

    只在**最后一个数字 ≤ max_page** 时才剥，避免误伤
    「0计划」「十三圣人」这类名字里本来带数字的标题。
    """
    m = TAIL_PAGE.search(text)
    if not m:
        return text
    n = int(m.group(1))
    if n > max_page:
        return text
    # 只有数字紧跟在汉字或右括号之后才剥（避免误伤「0083号计划」这类名字）
    head = text[:m.start()]
    if head and (head[-1] in "）)》」』" or "\u4e00" <= head[-1] <= "\u9fff"):
        return head.strip()
    return text


def docx_paragraphs(path, smap):
    z = zipfile.ZipFile(path)
    xml = z.read("word/document.xml").decode("utf-8", "replace")
    raw = []
    for m in re.finditer(r"<w:p[ >].*?</w:p>", xml, re.S):
        p = m.group(0)
        st = P_STYLE.search(p)
        sid = st.group(1) if st else ""
        name, outline = smap.get(sid, ("", None))
        raw.append({"style_id": sid, "style": name,
                    "text": "".join(W_T.findall(p)).strip(),
                    "toc_anchor": bool(TOC_HINT.search(p)),
                    "level": heading_level(name, outline)})
    # 剥离标题尾随页码。
    # **不设页码上限**：真正的判据是 numbering._ok_tail —— 只有紧跟在
    # 汉字 / 右括号 / 引号之后的数字才算页码；紧跟字母或数字的（如「0083号计划」）保留。
    for p in raw:
        if p["level"] is not None:
            p["text"] = numbering.strip_number(p["text"])
    return raw


def extract_toc(paras):
    """文档自带的「目　录」卷：找出它到下一个 Heading1 之间的段落。

    目录在 DSH 版里可能是**域代码**（文本为空）或**纯文本行**。
    本函数两种都处理：返回 (条目列表, 判定方式)。
    """
    def is_toc_style(p):
        return (p.get("style") or "").lower().startswith("toc")

    start = end = None
    for i, p in enumerate(paras):
        if p["level"] == 1 and re.sub(r"\s|\u3000", "", p["text"]) == "目录":
            start = i
            continue
        # 结束条件：遇到**下一个真正的卷标题**。
        # 注意目录条目本身也用 heading 样式（toc 1/2/3，styleId 27/30/24），
        # 必须用样式名区分，否则会在目录的第一行就停下（1.1 版就是这种情况）。
        if start is not None and p["level"] == 1 and i > start and not is_toc_style(p):
            end = i
            break
    if start is None:
        return [], "未找到「目录」标题"
    block = paras[start + 1: end if end else len(paras)]
    items = [p for p in block if p["text"]]
    toc_items = [p for p in items if (p["style"] or "").lower().startswith("toc")]
    for t in toc_items:
        t["text"] = strip_page_no(t["text"], 9999)
    if toc_items:
        return toc_items, "纯文本目录（%d 行，toc 样式）" % len(toc_items)
    if items:
        return items, "纯文本目录（%d 行，无 toc 样式）" % len(items)
    return [], "目录为空（可能是域代码，需在 Word 里展开才可见）"


def build_structure(paras, issues):
    """按样式层级建树：卷(H1) → 节(H2) → 词条(H3)。

    返回 (vols, orphan_paras)，orphan 指 H3 之前、不属于任何词条的段落。
    """
    vols, cur_vol, cur_sec, cur_ent = [], None, None, None
    preface = []                     # H1 之前的内容
    for p in paras:
        lv, txt = p["level"], p["text"]
        if not txt and lv == 0:
            continue
        # 标题统一剥掉尾随页码（docx 里每个标题后面都跟着页码）
        if lv:
            txt = numbering.strip_number(txt)
        if lv == 1:
            cur_vol = {"title": txt, "sections": [], "body": [], "level": 1}
            vols.append(cur_vol)
            cur_sec = cur_ent = None
        elif lv == 2:
            if cur_vol is None:
                preface.append(txt)
                continue
            cur_sec = {"title": txt, "entries": [], "body": [],
                       "vol": cur_vol["title"]}
            cur_vol["sections"].append(cur_sec)
            cur_ent = None
        elif lv == 3:
            if cur_sec is None:
                prose = cur_vol["body"] if cur_vol else preface
                prose.append(txt)
                continue
            cur_ent = {"title": txt, "body": [], "vol": cur_vol["title"],
                       "section": cur_sec["title"]}
            cur_sec["entries"].append(cur_ent)
        else:
            if cur_ent is not None:
                cur_ent["body"].append(txt)
            elif cur_sec is not None:
                cur_sec["body"].append(txt)
            elif cur_vol is not None:
                cur_vol["body"].append(txt)
            else:
                preface.append(txt)

    # overrides 路径（全程可用）
    ov_path = os.path.join(W, "lore-data", "overrides.json")
    applied = {"sections": 0, "replaced": 0, "dropped": 0, "seealso": 0}

    # ── 拆分合并卷：「卷五、卷六」→「卷五 神圣希望帝国」+「卷六 进化者同盟」──
    # 原文把两卷并成一个 H1，两个 H2 分别是「第五卷 神圣希望帝国」「第六卷 进化者同盟」，
    # 末尾还有一个共用的「编纂备注」。作者 2026-10-14 要求拆开。
    SPLIT_SRC = "卷五、卷六 神圣希望帝国 · 进化者同盟"
    new_vols = []
    for v in vols:
        if v["title"] != SPLIT_SRC:
            new_vols.append(v)
            continue
        keep, notes = [], []
        for sec in v["sections"]:
            (notes if "编纂备注" in sec["title"] else keep).append(sec)
        for sec in keep:
            t = sec["title"]
            # 拆分后节名与卷名重复（卷五/第五卷 神圣希望帝国），改成语义化的节名
            if t.startswith("第五卷"):
                vname, sname = "卷五 神圣希望帝国", "帝国概览"
            elif t.startswith("第六卷"):
                vname, sname = "卷六 进化者同盟", "进盟概览"
            else:
                vname, sname = t, t
            sec["title"] = sname
            # 词条里也存了 section 名（面包屑/返回链接要用），必须一起改
            for e in sec["entries"]:
                e["section"] = sname
            # 作者 2026-10-14：卷五/卷六 的节**取自原作者的分组标签**（见《修改建议》），
            # 不是拆卷时临时加的「帝国概览」→ 丢掉临时层，让 overrides 重新分节
            if sname in ("帝国概览", "进盟概览"):
                holder = {"title": vname, "sections": [], "body": [], "level": 1,
                          "pre_text": "", "pending_entries": sec["entries"],
                          "split_from": SPLIT_SRC}
                for e in sec["entries"]:
                    e["vol"] = vname
                new_vols.append(holder)
                continue
            nv = {"title": vname, "sections": [sec], "body": [],
                  "level": 1, "pre_text": "", "split_from": SPLIT_SRC}
            for e in sec["entries"]:
                e["vol"] = vname
            new_vols.append(nv)
        # 共用的编纂备注：两卷各放一份（内容相同，读者在哪一卷都能看到）
        for nv in (new_vols[-2], new_vols[-1]):
            for nt in notes:
                cp = json.loads(json.dumps(nt))
                cp["vol"] = nv["title"]
                for e in cp["entries"]:
                    e["vol"] = nv["title"]
                nv["sections"].append(cp)
    vols = new_vols

    # ── 先给所有词条补 text/chars/hanzi（合并与统计都要用）──
    def normalize(entry):
        if "text" not in entry:
            entry["text"] = "\n".join(x for x in entry.get("body", []) if x)
            entry["chars"] = len(entry["text"])
            entry["hanzi"] = len(HANZI.findall(entry["text"]))
        return entry

    for v0 in vols:
        for e0 in (v0.get("direct_entries") or []):
            normalize(e0)
        for s0 in v0["sections"]:
            for e0 in s0["entries"]:
                normalize(e0)

    # ── 作者 2026-10-14（乙方案）：把「编纂备注」下被误标为词的编号小节并回备注正文 ──
    # Word 里这些小结用了 Heading3 样式，于是被当成独立词条；其实它们是备注的内部小节。
    # 1.0 的备注里混进了 4 个被误标为词条的编号小节；1.1 已由设定集侧修正
    NOTE_SUBS = ({"条目数", "覆盖轮次号清单", "未收录轮次及原因", "发现的矛盾与存疑点"}
                 if SOURCE_VERSION.startswith("1.0") or SOURCE_VERSION == "第一版"
                 else set())
    SUB_RE = re.compile(r"^[一二三四五六七八九十]+[、.]?\s*\S")
    merged = 0
    for v in vols:
        for sec in v["sections"]:
            if "编纂备注" not in sec["title"]:
                continue
            keep, subs = [], []
            for e in sec["entries"]:
                # 命中名单，或形如「一、xxx」的编号小节，都视为备注内部小节
                if e["title"] in NOTE_SUBS or SUB_RE.match(e["title"]):
                    subs.append(e)
                else:
                    keep.append(e)
            if not subs:
                continue
            pieces = [x for x in (sec.get("body") or []) if x]
            for e in subs:
                pieces.append("### %s" % e["title"])
                pieces.append(e["text"])
            sec["body"] = pieces
            sec["entries"] = keep
            merged += len(subs)

    # ── 应用 overrides 的 ① 分节（由 tools/lore_overrides.py 从《修改建议》提取）──
    if os.path.exists(ov_path):
        ov = json.load(io.open(ov_path, encoding="utf-8"))

        # ① 卷五/卷六 分节
        for v in vols:
            pend = v.pop("pending_entries", None)
            if not pend:
                continue
            want = (ov.get("sections") or {}).get(v["title"]) or []
            by_title = {e["title"]: e for e in pend}
            for sec_def in want:
                sec = {"title": sec_def["name"], "entries": [], "body": [],
                       "vol": v["title"]}
                for t in sec_def["entries"]:
                    e = by_title.get(t)
                    if not e:
                        issues.append(("分节·词条未找到", v["title"], t))
                        continue
                    e["section"] = sec["title"]
                    e["direct"] = False
                    sec["entries"].append(e)
                v["sections"].append(sec)
                applied["sections"] += 1
            rest = [e for e in pend if e.get("direct") is None
                    and not any(e in x["entries"] for x in v["sections"])]
            for e in rest:
                issues.append(("分节·未被任何节收录", v["title"], e["title"]))

        # ② 替换词条正文（对所有卷生效，不限卷五/六）
        for rep in ov.get("replace_entries") or []:
            for v in vols:
                if v["title"] != rep["vol"]:
                    continue
                for sec in v["sections"]:
                    for e in sec["entries"]:
                        if e["title"] == rep["title"]:
                            e["text"] = rep["text"]
                            e["body"] = rep["text"].split("\n")
                            e["chars"] = len(e["text"])
                            e["hanzi"] = len(HANZI.findall(e["text"]))
                            e["replaced_by"] = rep.get("from", "")
                            applied["replaced"] += 1

        # ③ 删除词条（内容已并入他卷）
        drop = {(x["vol"], x["title"]) for x in (ov.get("drop_entries") or [])}
        for v in vols:
            for sec in v["sections"]:
                sec["entries"] = [e for e in sec["entries"]
                                  if (v["title"], e["title"]) not in drop]

        # ④ 另见交叉引用（跨卷同名主题；标注而非删除）
        for sa in ov.get("seealso") or []:
            for v in vols:
                if v["title"] != sa["vol"]:
                    continue
                for sec in v["sections"]:
                    for e in sec["entries"]:
                        if e["title"] == sa["title"]:
                            e["seealso"] = sa
                            applied["seealso"] += 1

    # ── ④b 自动标注全部跨卷同名主题（作者 2026-10-14：13 组，保留两处、加「另见」）──
    # 不依赖手工清单：凡是同一词条名出现在**多个卷**，每处都加指向其余卷的标注。
    from collections import defaultdict as _dd
    _loc = _dd(list)
    for v in vols:
        if v["title"].startswith(("目", "前言")):
            continue
        for sec in v["sections"]:
            for e in sec["entries"]:
                _loc[e["title"]].append((v["title"], e))
    for title, places in _loc.items():
        if len({p[0] for p in places}) < 2:
            continue
        for volname, e in places:
            others = [p[0] for p in places if p[0] != volname]
            if not others:
                continue
            lst = list(dict.fromkeys(others))
            note = ("%s另有一处侧重不同的同名条目，两处保留、不合并。"
                    % "、".join("「%s」" % o for o in lst))
            e["seealso"] = {"note": note, "href": "", "auto": True,
                            "others": lst}
            applied["seealso"] += 1

    # ── 「编纂备注」永远排在每卷最后（作者要求：单列在卷末）──
    # 必须在 ① 分节之后执行，否则新建的节会把备注顶回前面
    for v in vols:
        v["sections"].sort(key=lambda s: 1 if "编纂备注" in s["title"] else 0)

    # ── slug：跨卷唯一（19 组词条同名，必须去重）──
    import common as _common
    seen = {}
    for v in vols:
        # 先给**所有**词条补 text/chars/hanzi（后面的合并、统计都要用）
        all_entries = list(v.get("direct_entries") or [])
        for sec0 in v["sections"]:
            all_entries += sec0["entries"]
        for e in all_entries:
            if "text" not in e:
                e["text"] = "\n".join(x for x in e.get("body", []) if x)
                e["chars"] = len(e["text"])
                e["hanzi"] = len(HANZI.findall(e["text"]))
        # 直属词条与节内词条共用同一套 slug 去重
        for e in (v.get("direct_entries") or []) + [
                x for s in v["sections"] for x in s["entries"]]:
            base = _common.slugify(e["title"], maxlen=48) or "entry"
            n = seen.get(base, 0) + 1
            seen[base] = n
            e["slug"] = base if n == 1 else "%s-%d" % (base, n)
    # 汇总统计（拆分后重算）
    for v in vols:
        for s in v["sections"]:
            for e in s["entries"]:
                e["text"] = "\n".join(x for x in e["body"] if x)
                e["chars"] = len(e["text"])
                e["hanzi"] = len(HANZI.findall(e["text"]))
            body_text = "\n".join(x for x in s["body"] if x)
            ent_text = "\n".join(e["text"] for e in s["entries"])
            s["text"] = (body_text + "\n" + ent_text).strip()
            s["body_chars"] = len(body_text)
            s["entry_chars"] = len(ent_text)
            # 节的字数 = 直接正文 + 全部词条
            s["chars"] = len(s["text"])
            s["hanzi"] = len(HANZI.findall(s["text"]))
            s["n_entries"] = len(s["entries"])
        v.setdefault("direct_entries", [])
        # 直属词条（卷五/卷六）也要补 text/chars/hanzi
        for e in v["direct_entries"]:
            if "text" not in e:
                e["text"] = "\n".join(x for x in e.get("body", []) if x)
                e["chars"] = len(e["text"])
                e["hanzi"] = len(HANZI.findall(e["text"]))
        v["pre_text"] = "\n".join(x for x in v["body"] if x)
        # 卷的字数 = 自述正文 + 各节（含词条）
        v["chars"] = (len(v["pre_text"])
                      + sum(len(e["text"]) for e in v["direct_entries"])
                      + sum(s["chars"] for s in v["sections"]))
        v["hanzi"] = len(HANZI.findall(v["pre_text"])) + sum(
            s.get("hanzi", 0) for s in v["sections"])
        v["n_sections"] = len(v["sections"])
        v["n_entries"] = (len(v["direct_entries"])
                          + sum(s["n_entries"] for s in v["sections"]))
    return vols, preface


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=os.path.join(W, "lore-data"))
    args = ap.parse_args()
    if not os.path.exists(args.src):
        sys.exit("找不到源文件：%s" % args.src)
    out_dir = args.out if os.path.isabs(args.out) else os.path.join(W, args.out)
    os.makedirs(out_dir, exist_ok=True)

    smap = style_map(args.src)
    paras = docx_paragraphs(args.src, smap)
    toc_items, toc_how = extract_toc(paras)
    issues = []
    vols, preface = build_structure(paras, issues)

    # 统计字数时**排除目录卷**（那是 TOC 域，1.1 起含完整三级目录与页码，不是设定内容）
    toc_para_ids = set()
    _in_toc = False
    for i, p in enumerate(paras):
        pm = p["level"] == 1 and re.sub(r"\s|\u3000", "", p["text"]) == "目录"
        if pm:
            _in_toc = True
            toc_para_ids.add(i)
            continue
        if _in_toc:
            toc_para_ids.add(i)
            if p["level"] == 1 and not (p.get("style") or "").lower().startswith("toc"):
                _in_toc = False
    all_text = "\n".join(p["text"] for i, p in enumerate(paras)
                          if i not in toc_para_ids)
    todo = {
        "source": args.src,
        "source_version": SOURCE_VERSION,
        "counts": {
            "paragraphs": len(paras),
            "vols": len(vols),
            "sections": sum(v["n_sections"] for v in vols),
            "entries": sum(v["n_entries"] for v in vols),
            "chars": len(all_text),
            "hanzi": len(HANZI.findall(all_text)),
        },
        "styles": dict(Counter(p["style"] or "(默认)" for p in paras)),
        "toc": {"how": toc_how, "items": [{"text": t["text"],
                                           "style": t["style"],
                                           "level": t["level"]}
                                          for t in toc_items]},
        "preface": preface,
        "vols": vols,
    }
    p = os.path.join(out_dir, "doc.json")
    io.open(p, "w", encoding="utf-8", newline="\n").write(
        json.dumps(todo, ensure_ascii=False, indent=1))
    print("样式映射 %d 条" % len(smap))
    print("已写出 %s（%.1f MB）" % (p, os.path.getsize(p) / 1048576))
    print("卷 %d ｜ 节 %d ｜ 词条 %d ｜ 汉字 %s"
          % (todo["counts"]["vols"], todo["counts"]["sections"],
             todo["counts"]["entries"], format(todo["counts"]["hanzi"], ",")))
    print("目录：%s" % toc_how)


if __name__ == "__main__":
    main()
