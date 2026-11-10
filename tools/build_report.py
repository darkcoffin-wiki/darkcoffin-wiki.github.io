#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《黑柩报告》→ 分析站（`docs/report/`）。

输入：`report-data/*.md`（由 tools/parse_report.py 从 docx 生成）
      `data/report_site.json`（报告目录、分组、警告语）
输出：`docs/report/`（1 首页 + N 报告页 + assets/report.css）

**保真目标**：让报告页读起来和 docx 一致——标题层级、表格、粗体/斜体、列表齐全。
报告内没有图片、高亮、底色、彩色字，故无需处理。

用法：python tools/build_report.py
"""
import html
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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

# 注意：**不要**用 common.site_dir —— 它读环境变量 DSH_SITE_PREFIX（默认 huaxu），
# 会把文件写进 docs/huaxu/report/。分析站有自己固定的前缀，直接拼路径。
PREFIX = "report"
OUT = os.path.join(W, "docs", PREFIX)          # docs/report
ASSETS = os.path.join(W, "docs", "assets")     # docs/assets（与三站共享）
DATA = os.path.join(W, "report-data")
NOVEL = os.path.join(W, "novel-data")          # 独立小说的中间产物（parse_novel.py）
CFG = os.path.join(W, "data", "report_site.json")

# 原著 md（parse_novel.py 的产物）里只有两种结构行：`@part 篇名` 与 `## 章名`。
# 用本文件自定的这两个正则、而不是通用 Markdown，是因为小说正文里可能有
# 以 `-` / `|` / `#` 开头的行，走通用解析会被误判成列表/表格/标题。
NOVEL_PART_RE = re.compile(r"^@part\s+(.+)$")
NOVEL_SEC_RE = re.compile(r"^##\s+(.+)$")

SITE = {
    "title": "黑柩分析站",
    "subtitle": "基于《黑柩设定集》的专题研究报告",
    "disclaimer": "本网站由 AI 生成，内容准确性无法完全保证。",
}
HANZI = re.compile(r"[\u4e00-\u9fff]")

# 行内标记：***粗斜*** / **粗** / *斜*
#
# 踩过的坑（2026-10-17）：斜体的正则原本是 `[^*\n]+?`，**不匹配换行**。
# docx 的一个段落里常带软换行，于是「*跨\n行*」这种斜体无法收敛，
# 星号原样漏到页面上——8 份报告共 1176 个裸 `*`，几乎全是这个原因。
# 现在允许斜体跨行（逐段落调用，不会跨段），并限长 2000 字
# （实测报告里最长的一段斜体引文有 760 字，早先设 500 会漏掉它），
# 避免文档里偶发的未配对单星号把后面一大段吞成斜体。
# docx 里「斜体 + 加粗」相邻时，导出会粘连成 4 个星号（如 `*「****正文****」*`）。
# `****` 在任何 Markdown 方言里都无意义。实测这些 4 连星号**总是成对包裹正文**
# （如 `****同时依据两处证据****`、`*「****悖逆者生****」*`），语义就是「加粗 + 斜体」，
# 即应写作 `***X***`——导出时每处多打了一个星号。
# 折叠成 `***`（而不是 `**`）：否则 `***标题****` 这种首 3 尾 4 的组合会留下半个标记，
# 产出 `<strong><em>标题</strong>` 这样的交叉嵌套（实测 3 处）。
MANY_STAR_RE = re.compile(r"\*{4,}")
TRIPLE_RE = re.compile(r"\*\*\*(.+?)\*\*\*", re.S)
BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.S)
ITAL_RE = re.compile(r"(?<!\*)\*(?!\*)([^*]{1,2000}?)\*(?!\*)", re.S)
# 「推断」类标记：报告用它承载第三方判断，做成醒目小块
INFER_RE = re.compile(r"^\s*(【推断[^】]*】|依据[:：])")


def inline(txt):
    """行内标记 → HTML。顺序很重要：三连星号必须先处理，
    否则 ***x*** 会被拆成 <strong><em>x</strong></em>（嵌套错乱的无效 HTML）。"""
    """行内：转义 → 粗体 → 斜体 → `code`。先转义，再用占位符换标记。"""
    t = html.escape(txt, quote=False)
    t = MANY_STAR_RE.sub("***", t)     # 先折叠 ≥4 连星号 → 粗斜体（见上方注释）
    t = TRIPLE_RE.sub(lambda m: "<strong><em>%s</em></strong>" % m.group(1), t)
    t = BOLD_RE.sub(lambda m: "<strong>%s</strong>" % m.group(1), t)
    t = ITAL_RE.sub(lambda m: "<em>%s</em>" % m.group(1), t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    # 兜底：清掉没能配对的残星号。
    # 实测 8 份报告共 1176 个裸 `*` 全部是 docx 导出的格式标记（正文里没有需要
    # 显示星号的场合），个别段落星号数量本身就不配对（如 `*A……****B***`），
    # 上面几轮替换后仍会剩 1 个，这里统一抹掉，保证页面上永远看不到星号。
    t = t.replace("*", "")
    # 去掉空的内联标签（docx 里偶有 `** **` 这种只有空格的加粗）
    t = re.sub(r"<(em|strong)>\s*</\1>", "", t)
    return t


def slugify_anchor(text, seen):
    base = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text).strip("-").lower() or "h"
    base = base[:48]
    n = seen.get(base, 0) + 1
    seen[base] = n
    return base if n == 1 else "%s-%d" % (base, n)


# ══════════════════════════════════════════════════════════════
# Markdown（本项目的子集）→ HTML
# ══════════════════════════════════════════════════════════════
COVER_TOC_RE = re.compile(
    r"^#{1,6}[ \t\u3000]*\*{0,3}目[ \t\u3000]*[录錄]\*{0,3}[ \t\u3000]*$", re.M)
# 2026-11 起的重制版不再放 Word 目录，封面改用一行「— · —」收尾：
#   # 标题 / **——副标题** / **——《黑柩》设定研究之N** / 本稿为重制版… / 全书章目：…
#   — · —
#   ## 一、导论
# 没有这一条的话 strip_cover 找不到锚点，整片封面（含「本稿为重制版」和全书章目）
# 会原样渲染到页面顶部。
COVER_SEP_RE = re.compile(r"^[\u2014\u2013\u2015-][ \t\u3000]*\u00b7"
                          r"[ \t\u3000]*[\u2014\u2013\u2015-][ \t\u3000]*$", re.M)
# docx 里给 Word 用户的操作提示（「按 F9 更新域」「视图→导航窗格」等），网页读者不需要
# 两种实际形态都要覆盖：
#   · （本目录为自动域：在 Word 中全选后按 F9…）
#   · 在 Word 中右键下方区域并选择「更新域」，或按 Ctrl+A 后 F9，即可生成带页码的目录。
#   · （目录占位：更新域后生成）
WORD_HINT_RE = re.compile(
    r"^[（(]?[^\n]{0,260}?(?:自动域|更新域|更新目录|导航窗格|按\s*Ctrl\+A\s*后\s*F9"
    r"|按\s*F9|Word\s*/\s*WPS|目录占位)[^\n]{0,260}?[）)]?\s*$",
    re.M)


def strip_cover(md):
    """剥掉 docx 的封面区（开头到第一个 `## ` 之前）。

    docx 每篇开头都是这样一片「封面」：
        **标题**
        副标题
        依据《黑柩设定集》整理
        # 目　录
        （本目录为自动域：在 Word 中全选后按 F9，或右键"更新域"，…）
        # 标题
        **——副标题**
        **——《黑柩》设定研究之N**
        ## 一、导论        ← 正文从这里开始

    页面的 <header class="rp-head"> 已经用配置渲染了系列号 / 标题 / 副标题，
    所以这片封面留着只会造成：
      · 页面上出现两个标题（h1 重复）
      · 正文里多出一个「目　录」标题（页面顶部本来就有自动目录 rp-toc）
      · 把「按 F9 更新域」这种**给 Word 用户看的操作提示**暴露给网页读者
    作者明确要求删掉这些，故在渲染前整片剥离。

    只在「第一个二级标题之前确实存在目录标题」时才剥，避免误伤没有封面区的文档。
    """
    md = WORD_HINT_RE.sub("", md)
    m = COVER_TOC_RE.search(md)
    if not m:
        # 结构 C（2026-11 重制版）：没有目录，封面以「— · —」收尾，剥到该行之后。
        # 只在这行确实存在时才剥；没有就原样返回，免得误伤没有封面的文档。
        sep = COVER_SEP_RE.search(md)
        if sep:
            return md[sep.end():].lstrip("\n")
        return md
    tail = md[m.end():]

    # 结构 A（多数旧报告）：目录标题之后还有一片「封面装饰」——
    #   # 标题（与 rp-head 重复）
    #   **——副标题**
    #   **——《黑柩》设定研究之N**
    # 用它当锚点，剥到该行之后。
    m2 = re.search(r"^\*\*——《黑柩》设定研究之[^*]*\*\*\s*$", tail, re.M)
    if m2:
        return tail[m2.end():].lstrip("\n")

    # 结构 B（部分新报告）：目录标题之后直接就是正文标题（# 绪言 / # 前言 / # 引言），
    # 没有那片装饰，剥到第一个标题即可。
    m3 = re.search(r"^#{1,6}\s+\S", tail, re.M)
    if m3:
        return tail[m3.start():]
    return tail


def md_to_html(md):
    md = strip_cover(md)
    lines = md.split("\n")
    out, toc = [], []
    seen = {}
    i, n = 0, len(lines)

    # 标题层级归一化：正文里最浅的标题要落到 <h2>。
    # rp-head 已经用了 <h1>（报告标题），所以正文里再出现 h1 就是语义重复。
    # 各报告的写法不统一：有的正文直接从 `## 一、导论` 起（章=h2，本来就对），
    # 有的先用 `# 上篇　总论` 分篇（篇应该也是 h2，章顺延为 h3）。
    # 取正文里最小的层级，整体平移，保证「一篇只有一个 h1」。
    _lvs = [len(x.group(1)) for x in re.finditer(r"^(#{1,6})\s+\S", md, re.M)]
    _shift = max(0, (min(_lvs) if _lvs else 2) - 2)
    while i < n:
        ln = lines[i]
        s = ln.strip()

        if not s:
            i += 1
            continue

        # ── 标题 ──
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            lv = max(2, len(m.group(1)) - _shift)
            txt = m.group(2).strip()
            # docx 里整行加粗的标题会让 parse_report 导出 `# **标题**`。
            # 目录/锚点必须用**去掉强调标记**的纯文本，否则页面上会露出 `**`，
            # 而且与 main() 里生成搜索索引时用的锚点算法对不上（真实踩过的坑）。
            plain = re.sub(r"\*+", "", txt).strip()
            # 兜底：残留的「目录」标题直接跳过（不进 toc、不输出）
            if re.fullmatch(r"目\s*[录錄]", plain.replace("\u3000", "").strip()):
                i += 1
                continue
            aid = slugify_anchor(plain, seen)
            if lv <= 3:
                toc.append((lv, plain, aid))
            out.append('<h%d id="%s">%s</h%d>' % (lv, aid, inline(txt), lv))
            i += 1
            continue

        # ── 表格 ──
        if s.startswith("|") and i + 1 < n and re.match(r"^\|[\s:\-|]+\|$", lines[i + 1].strip()):
            head = [c.strip() for c in s.strip("|").split("|")]
            i += 2
            body = []
            while i < n and lines[i].strip().startswith("|"):
                body.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            th = "".join("<th>%s</th>" % inline(c) for c in head)
            trs = ""
            for row in body:
                while len(row) < len(head):
                    row.append("")
                trs += "<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c)
                                               for c in row[:len(head)])
            out.append('<div class="tw"><table class="rp"><thead><tr>%s</tr></thead>'
                       '<tbody>%s</tbody></table></div>' % (th, trs))
            continue

        # ── 列表 ──
        if re.match(r"^([-*]|\d+\.)\s+", s):
            items, ordered = [], None
            while i < n and re.match(r"^([-*]|\d+\.)\s+", lines[i].strip()):
                cur = lines[i].strip()
                ordered = bool(re.match(r"^\d+\.", cur))
                items.append(re.sub(r"^([-*]|\d+\.)\s+", "", cur))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append("<%s>%s</%s>" % (tag,
                       "".join("<li>%s</li>" % inline(x) for x in items), tag))
            continue

        # ── 段落（连续行合并）──
        buf = [s]
        i += 1
        while i < n:
            nx = lines[i].strip()
            if (not nx or nx.startswith("|") or nx.startswith("#")
                    or re.match(r"^([-*]|\d+\.)\s+", nx)):
                break
            buf.append(nx)
            i += 1
        para = " ".join(buf)
        esc = inline(para)
        # 推断标记写成 `**【推断一】** 依据：…`，故在**原文**上判定（inline 后看不见 **）
        plain = re.sub(r"\*\*", "", para).strip()

        # 整段都被「」包住 → 引文块
        if re.match(r"^「.*」[。！？]?$", plain):
            out.append('<blockquote class="quote">%s</blockquote>' % esc)
        # 【推断N】/ 依据： 开头 → 推断块（报告的论证骨架，做成醒目小块）
        elif INFER_RE.match(plain):
            out.append('<p class="infer">%s</p>' % esc)
        # 独立的「依据：…」段（常见于推断之后）
        elif plain.startswith("依据：") or plain.startswith("依据:"):
            out.append('<p class="infer">%s</p>' % esc)
        else:
            out.append("<p>%s</p>" % esc)
    return "\n".join(out), toc


# ══════════════════════════════════════════════════════════════
# 页面模板
# ══════════════════════════════════════════════════════════════
def friend_links_html():
    cfg = json.load(io.open(os.path.join(W, "data", "site.json"), encoding="utf-8"))
    return "".join(
        '<a href="%s" title="%s" target="_blank" rel="noopener">%s</a>'
        % (html.escape(f["url"]), html.escape(f.get("note", "")), html.escape(f["label"]))
        for f in cfg.get("friend_links", []) or []) or "—"


def station_switch(up, self_rel=""):
    """四站切换菜单。

    self_rel：**回本站根**的前缀（首页 ""、entry/ 页 "../"）。
    up     ：**回 docs 根**的前缀（首页 "../"、entry/ 页 "../../"）。

    两者的区别必须分清楚——「本站首页」要用 self_rel 拼，
    早先用 up 拼会指向联合首页（真实踩过的 bug）。也正因为这个坑，
    当初干脆把「本站首页」整个删掉了；但那样子页面里就没有回本站首页的入口，
    只能靠页眉的品牌名（不够显眼）。现在用 self_rel 正确拼上。
    """
    # 结构对齐另三站：本站链接 → 分隔符 → 他站切换 → 联合首页
    # （原来最前面有个 <span class="nav-cur">分析站</span> 标记「你正在这里」，
    #   但 .nav-cur 在 style.css / report.css 里都没有定义，等于裸文字；
    #   去掉它、补上「本站首页」，和花絮/跑团/设定的菜单保持一致。）
    items = [("huaxu/index.html", "花絮站"), ("trpg/index.html", "跑团站"),
             ("lore/index.html", "设定站")]
    out = [
        '<a href="%sindex.html">本站首页</a>' % self_rel,
        '<span class="nav-sep"></span>',
    ]
    for href, name in items:
        out.append('<a class="nav-other" href="%s%s" title="切换到%s">%s →</a>'
                   % (up, href, name, name))
    out.append('<a class="nav-other" href="%sindex.html" title="四站入口">联合首页</a>' % up)
    return "".join(out)


def page(title, body, self_rel="", up="../", extra_head="", show_search=True,
         foot_note=None):
    """self_rel：本站内资源前缀（首页 ""、entry/ 页 "../"）。

    up：回 docs/ 根的前缀（首页 "../"、entry/ 页 "../../"），用于跨站菜单与品牌链接。
    分析站自带 assets 副本，故本站资源不依赖共享 docs/assets，路径更稳。

    foot_note：页脚那句「本站报告由 AI …撰写」。原著页必须换掉——
    原著是作者原文，页脚还写「由 AI 撰写」就是错的。
    """
    import json as _json
    # SITE_REL = 「回本站根」的前缀。分析站的结果页都在 entry/ 下，
    # app.js 会拼成 SITE_REL + <报告slug>.html → 必须指向 entry/ 所在层的上一层。
    sr_json = _json.dumps(self_rel)
    si_json = _json.dumps("assets/search.json")   # 本站自己的搜索索引（相对本站根）
    if foot_note is None:
        foot_note = "本站报告由 AI 依据《黑柩》设定集整理撰写，属读者分析，非作者设定原文。"
    search = ('<div class="search-wrap">'
              '<input id="q" type="search" placeholder="搜索报告与章节…" '
              'autocomplete="off" aria-label="搜索">'
              '<div id="q-results" class="q-results" hidden></div></div>'
              if show_search else "")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="icon" type="image/png" href="{self_rel}assets/icon.png">
<link rel="apple-touch-icon" href="{self_rel}assets/icon.png">
<link rel="stylesheet" href="{self_rel}assets/style.css">
<link rel="stylesheet" href="{self_rel}assets/report.css">
{extra_head}
</head>
<body class="rp-body">
<header class="site-head">
  <a class="brand" href="{self_rel}index.html">{html.escape(SITE['title'])}</a>
  <nav class="site-nav">{station_switch(up, self_rel)}</nav>
  {search}
</header>
<main class="wrap">
{body}
</main>
<footer class="site-foot">
  <p class="disclaimer">{html.escape(SITE['disclaimer'])}</p>
  <p>{foot_note}</p>
  <p class="muted">静态站 · 由 <code>tools/build_report.py</code> 生成</p>
  <p class="friend-links">友情链接：{friend_links_html()}</p>
</footer>
<a class="to-top" href="#" id="to-top" title="回到顶部" aria-label="回到顶部">↑ 顶部</a>
<script>window.SITE_REL={sr_json};window.SITE_INDEX={si_json};</script>
<script src="{self_rel}assets/app.js" defer></script>
</body>
</html>"""


def write_if_changed(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        old = io.open(path, encoding="utf-8").read()
        if old == content:
            return 0
    io.open(path, "w", encoding="utf-8", newline="\n").write(content)
    return 1


# ══════════════════════════════════════════════════════════════
# 独立作品（原著）—— novel-data/ 的读取与渲染
# ══════════════════════════════════════════════════════════════
def load_works(cfg):
    """→ {报告 key: 作品记录}。

    作品记录来自 novel-data/catalog.json（parse_novel.py 生成）。
    这里只补一个 series（第十六/十七/十八），与报告的系列号同源，
    避免同一个数字在配置里写两遍、改稿时忘了同步。
    """
    p = os.path.join(NOVEL, "catalog.json")
    if not os.path.exists(p):
        return {}
    out = {}
    for c in json.load(io.open(p, encoding="utf-8")):
        c["series"] = cfg["series"].get(c["key"], "")
        out[c["key"]] = c
    return out


def basis_of(w):
    """原著的规模描述（「44,636 字 · 13 章」）。

    章数要扣掉「前言」：黑柩校园两篇各有一个前言节，不扣就会报成 49 章
    （实际 26＋21＝47 章）。
    """
    n = w.get("sections", 0) - w.get("front", 0)
    h = format(w.get("hanzi", 0), ",")
    split = w.get("split")
    if split == "parts":
        return "%s 字 · %d 章（%d 篇）" % (h, n, len(w.get("parts") or []))
    if split == "date":
        return "%s 字 · 无章节 · 按日期分节" % h
    return "%s 字 · %d 章" % (h, n)


def parse_novel_md(md, toc_strip=""):
    """原著 md → [{"title": 篇名或 None, "prefix": '', "secs": [...]}]

    锚点规则：有篇时加一字母前缀（a-1、b-1），因为《黑柩校园》两篇
    **各自从「1」编章**，不加前缀会出现两个 id="1"。
    """
    has_parts = any(NOVEL_PART_RE.match(x) for x in md.split("\n"))
    parts, seen = [], {}
    cur_part = cur_sec = None
    part_i = -1
    for raw in md.split("\n"):
        line = raw.rstrip()
        if not line:
            continue
        m = NOVEL_PART_RE.match(line)
        if m:
            part_i += 1
            cur_part = {"title": m.group(1).strip(),
                        "prefix": chr(ord("a") + part_i) if has_parts else "",
                        "secs": []}
            parts.append(cur_part)
            cur_sec = None
            continue
        m = NOVEL_SEC_RE.match(line)
        if m:
            if cur_part is None:
                cur_part = {"title": None, "prefix": "", "secs": []}
                parts.append(cur_part)
            title = m.group(1).strip()
            pre = cur_part["prefix"]
            aid = slugify_anchor((pre + "-" + title) if pre else title, seen)
            toc = re.sub(toc_strip, "", title).strip() if toc_strip else title
            cur_sec = {"title": title, "toc": toc or title,
                       "anchor": aid, "paras": []}
            cur_part["secs"].append(cur_sec)
            continue
        if cur_sec is not None:
            cur_sec["paras"].append(line)
    return parts, has_parts


def notes_html(notes, kind="basis"):
    """封面区那几行重要说明（面向谁读 / 定位 / 内容提示）。

    这些字原本长在 docx 封面上，而 strip_cover() 会把封面整片剥掉
    （避免 Word 的「按 F9 更新域」漏到页面上），所以必须由配置补回来，
    否则「读之前不需要任何背景」「定位：正史」这些作者原话就丢了。

    每项可以是字符串（默认 .basis），也可以是 {"kind": ..., "text": ...}——
    「内容提示」用 kind="content" 换橙色左边框，视觉上与「定位」区分开。
    """
    out = []
    for n in notes:
        if isinstance(n, dict):
            out.append('<p class="rp-warn %s">%s</p>'
                       % (n.get("kind", kind), inline(n["text"])))
        else:
            out.append('<p class="rp-warn %s">%s</p>' % (kind, inline(n)))
    return "".join(out)


def remake_badge(cfg, key):
    """「重制」标记。日期写死在 data/report_site.json 的 remakes 里——
    重制日期是**作者换源的那一天**，不是本次构建日期，所以不能从文件 mtime 推。"""
    d = (cfg.get("remakes") or {}).get(key)
    if not d:
        return ""
    return ('<span class="rp-remake" title="本报告已重制换源">'
            '重制 · %s</span>' % html.escape(d))


def series_label(key, cfg, works):
    """报告页顶部的系列标签。

    三种写法：
      · 老 15 篇     →「《黑柩》设定研究之十五」（它们确实就是设定研究）
      · 独立作品研究 →「《黑柩》报告系列之十六 · 独立作品研究之一」
        两个号都挂，因为报告正文里已经在引用「第一篇」「第三篇」，只留全站号会失指
      · 其它栏目     →「《黑柩》报告系列之十九 · 跑团集锦」
        这里**不写栏目序号**：《竖棺》封面自报「跑团集锦之三」、「青都事变」自报
        「之四」，而《三大恨》封面还是旧的「设定研究之十七」，三篇凑不齐一套序号，
        硬编一个「之二」就是替作者编数字。栏目名照样能告诉读者这是哪一栏。
    """
    num = cfg.get("series", {}).get(key, "")
    w = works.get(key)
    if num and w and w.get("column_no"):
        return "《黑柩》报告系列之%s · 独立作品研究之%s" % (num, w["column_no"])
    col = (cfg.get("columns") or {}).get(key)
    if num and col:
        return "《黑柩》报告系列之%s · %s" % (num, col["name"])
    return ("《黑柩》设定研究之%s" % num) if num else "专题报告"


def card_series_label(key, cfg, works):
    """首页卡片上的系列标签（比报告页的短一截）。

    卡片只有 17rem 宽，「《黑柩》报告系列之十九 · 跑团集锦」会折成两行、
    行尾孤零零剩一个「锦」字。分析站内部不需要再自称一次「《黑柩》报告」。
    """
    num = cfg.get("series", {}).get(key, "")
    w = works.get(key)
    if num and w and w.get("column_no"):
        return "系列之%s · 独立作品研究之%s" % (num, w["column_no"])
    col = (cfg.get("columns") or {}).get(key)
    if num and col:
        return "系列之%s · %s" % (num, col["name"])
    return ("《黑柩》设定研究之%s" % num) if num else "专题报告"


def work_series_label(w):
    num = w.get("series") or ""
    return ("《黑柩》独立作品 · 系列之%s" % num) if num else "《黑柩》独立作品"


def render_novel_page(w, parts, has_parts):
    """原著页。正文用 nv-body（书）：首行缩进、段间不空行。"""
    title = html.escape(w["title"])
    n_sec = sum(len(p["secs"]) for p in parts)

    # ── 目录 ──
    # 原著是「书」：章动辄 47 个（黑柩校园），用报告页那种竖排 <ol> 会占掉
    # 一整屏，读者得滚过目录才见到正文。改成**一行排开的芯片**，长目录也只是几行。
    def toc_chips(secs):
        return '<p class="nv-chips">%s</p>' % "".join(
            '<a href="#%s">%s</a>' % (s["anchor"], html.escape(s["toc"]))
            for s in secs)

    if has_parts:
        toc_html = "".join(
            '<p class="nv-part-title">%s</p>%s'
            % (html.escape(p["title"]), toc_chips(p["secs"])) for p in parts)
    else:
        toc_html = toc_chips(parts[0]["secs"]) if parts else ""

    # ── 正文 ──
    body = []
    for p in parts:
        if has_parts and p["title"]:
            body.append('<h2 class="nv-part" id="part-%s">%s</h2>'
                        % (p["prefix"], html.escape(p["title"])))
        for s in p["secs"]:
            lv = 3 if has_parts else 2
            body.append('<h%d class="nv-chap" id="%s">%s</h%d>'
                        % (lv, s["anchor"], html.escape(s["title"]), lv))
            for para in s["paras"]:
                body.append("<p>%s</p>" % html.escape(para, quote=False))

    # ── 与研究报告互跳 ──
    rep = w.get("report")
    rep_html = ""
    if rep:
        rep_html = ('<p class="nv-report"><a href="../entry/%s.html">'
                    '阅读本作研究报告 →</a></p>' % w["slug"])

    return f"""<article class="rp-doc nv-doc">
<nav class="crumbs"><a href="../index.html">分析站</a> · <a href="../index.html#works">独立作品研究</a> · {title}</nav>
<header class="rp-head nv-head">
  <p class="rp-series mono">{html.escape(work_series_label(w))}</p>
  <h1>{title}</h1>
  <p class="rp-meta muted">{html.escape(basis_of(w))} · 据 {html.escape(w.get('source_date',''))} 稿</p>
  {rep_html}
  {notes_html(w.get('work_notes') or [])}
</header>
<nav class="toc rp-toc nv-toc"><h2 class="plain">目录</h2>{toc_html}</nav>
<section class="nv-body">
{chr(10).join(body)}
</section>
<p class="back"><a href="../index.html#works">← 返回独立作品研究</a></p>
</article>"""


# ══════════════════════════════════════════════════════════════
# 渲染报告页
# ══════════════════════════════════════════════════════════════
def render_report(key, cfg, md, slug=None, works=None):
    """key：原中文名（**查配置用这个**）；slug：ASCII 文件名（只用于文件名，本函数不用）。

    works：独立作品表。报告若绑定了原著（works[key]），页头会多一条
    「本报告分析的原文 →」和一个注明版本日的依据行；否则保持原样。
    """
    works = works or {}
    meta_t = cfg["titles"].get(key, key)
    meta_s = cfg["subtitles"].get(key, "")
    html_body, toc = md_to_html(md)
    hanzi = len(HANZI.findall(md))
    n_tbl = html_body.count('<table class="rp">')

    toc_items = "".join(
        '<li class="l%d"><a href="#%s">%s</a></li>' % (lv, aid, html.escape(txt))
        for lv, txt, aid in toc if lv >= 2)
    num_txt = series_label(key, cfg, works)

    w = works.get(key)
    if w:
        basis = ("依据《%s》原文（%s）· 原文据 %s 稿"
                 % (html.escape(w["title"]), html.escape(basis_of(w)),
                    html.escape(w.get("source_date", ""))))
        origin = ('<p class="rp-origin">本报告分析的原文 → '
                  '<a href="../works/%s.html">《%s》%s</a></p>'
                  % (w["slug"], html.escape(w["title"]),
                     html.escape(basis_of(w))))
        warn = ('⚠️ 本报告由 <strong>AI 撰写</strong>，属读者分析；'
                '同栏目的<strong>原著是作者原文</strong>，两者页面分开标注。'
                '引用原文处随文标明，推断处标【推断】。')
        notes = notes_html(w.get("report_notes") or [])
    else:
        # 依据行：默认「依据《黑柩设定集》整理」；跑团集锦三篇的依据写在 docx 封面上
        # （那一行会被 strip_cover 剥掉），所以由配置 bases 补回来。
        basis = ((cfg.get("bases") or {}).get(key)
                 or "依据《黑柩设定集》整理")
        origin = ""
        # 保持原来的两行排版（换行 + 5 空格续行），这样老报告的成品一个字节都不变
        warn = ('⚠️ 本报告由 <strong>AI 撰写</strong>，属读者分析，'
                '<strong>非作者设定原文</strong>；\n'
                '     引用原文处随文标明，推断处标【推断】。')
        notes = ""

    # 页头的可选行拼成一块：空着的时候不要留下「只有两个空格」的行，
    # 否则每份报告页的 HTML 里都会多出几行空白，diff 里也难看。
    extra = []
    if origin:
        extra.append(origin)
    extra.append('<p class="rp-ai">%s</p>' % warn)
    if notes:
        extra.append(notes)
    extra_html = "\n".join(extra)

    # 面包屑：有栏目归属的报告多一节「跑团集锦 →」，方便从正文跳回栏目。
    # 老 15 篇没有 columns 配置 → 输出与以前逐字节相同。
    _col = (cfg.get("columns") or {}).get(key)
    crumb_mid = (' · <a href="../index.html#%s">%s</a>'
                 % (html.escape(_col["anchor"]), html.escape(_col["name"]))
                 if _col else "")

    return f"""<article class="rp-doc">
<nav class="crumbs"><a href="../index.html">分析站</a>{crumb_mid} · {html.escape(meta_t)}</nav>
<header class="rp-head">
  <p class="rp-series mono">{html.escape(num_txt)}{remake_badge(cfg, key)}</p>
  <h1>{html.escape(meta_t)}</h1>
  {f'<p class="rp-sub">{html.escape(meta_s)}</p>' if meta_s else ''}
  <p class="rp-meta muted">{hanzi:,} 汉字 · {n_tbl} 张表 · {basis}</p>
  {extra_html}
</header>
<nav class="toc rp-toc"><h2 class="plain">目录</h2><ol>{toc_items}</ol></nav>
<section class="rp-body">
{html_body}
</section>
<p class="back"><a href="../index.html">← 返回分析站首页</a></p>
</article>"""



# ══════════════════════════════════════════════════════════════
# 渲染首页
# ══════════════════════════════════════════════════════════════
def work_card(cfg, w, by, works):
    """独立作品卡：一个作品一张卡，卡上两枚入口（原著 / 报告）。

    与普通报告卡的区别只有一处——整张卡不是 <a>，因为里面要放两个 <a>
    （HTML 不允许嵌套链接）。所以栏目里这一块的网格用 .rp-card--work。
    """
    c = by.get(w["key"])
    t = cfg["titles"].get(w["key"], w["title"])
    sub = cfg["subtitles"].get(w["key"], "")
    rep_btn = ""
    rep_meta = ""
    if c:
        rep_btn = ('<a class="rp-btn rp-btn-ghost" href="entry/%s.html">读研究报告</a>'
                   % c["slug"])
        rep_meta = " ｜ 报告 %s 字 · %d 表" % (format(c["hanzi"], ","), c["tables"])
    return (
        '<div class="rp-card rp-card--work">'
        '<p class="rp-series mono">{n}</p><h3>{t}</h3>'
        '<p class="rp-sub">{sub}</p>'
        '<p class="muted">原著 {basis}{rep}</p>'
        '<p class="rp-work-links">'
        '<a class="rp-btn" href="works/{slug}.html">读原著</a>{rb}'
        '</p></div>').format(
            # 卡片窄，挂全站前缀会折成三行；这里是分析站内部，省掉「《黑柩》报告」
            n=html.escape(card_series_label(w["key"], cfg, works)),
            t=html.escape(t), sub=html.escape(sub),
            basis=html.escape(basis_of(w)), rep=rep_meta,
            slug=w["slug"], rb=rep_btn)


def render_index(cfg, catalog, works=None):
    works = works or {}
    # g["reports"] 里写的是**原中文名**，故按 key 建索引
    by = {(c.get("key") or c["slug"]): c for c in catalog}
    blocks = []
    n_works = 0
    for g in cfg["groups"]:
        if g.get("kind") == "works":
            cards = [work_card(cfg, works[k], by, works)
                     for k in g["reports"] if k in works]
            n_works += len(cards)
        else:
            cards = []
            for slug in g["reports"]:
                c = by.get(slug)
                if not c:
                    continue
                t = cfg["titles"].get(slug, slug)
                sub = cfg["subtitles"].get(slug, "")
                cards.append(
                    '<a class="rp-card" href="entry/{slug}.html">'
                    '<p class="rp-series mono">{n}</p><h3>{t}</h3>'
                    '<p class="rp-sub">{sub}</p>'
                    '<p class="muted">{h} 汉字 · {tb} 张表</p>{rm}</a>'.format(
                        n=html.escape(card_series_label(slug, cfg, works)),
                        # 卡片窄，把重制标记放到最后一行，免得把系列标签挤成两行、
                        # 让同一行里这张卡的标题比邻卡低一截
                        rm=remake_badge(cfg, slug),
                        t=html.escape(t), sub=html.escape(sub),
                        h=format(c["hanzi"], ","), tb=c["tables"],
                        slug=c["slug"]))   # 卡片链接用 ASCII slug
        blocks.append(
            '<section class="rp-group"%s><h2>%s</h2>'
            '<p class="muted">%s</p>'
            '<div class="rp-grid%s">%s</div></section>'
            % (' id="%s"' % html.escape(g["anchor"]) if g.get("anchor") else "",
               html.escape(g["name"]), html.escape(g["desc"]),
               " rp-grid-work" if g.get("kind") == "works" else "",
               "".join(cards)))

    # ── 置顶「最近主打」──
    # 配置见 data/report_site.json 的 featured：{report, label, note}
    # 它是**推荐位**，与该报告在下面栏目里的位置并存（栏目要保持完整）。
    feat_html = ""
    _f = cfg.get("featured") or {}
    _fk = _f.get("report")
    if _fk and _fk in by:
        _c = by[_fk]
        _t = cfg["titles"].get(_fk, _fk)
        _sub = cfg["subtitles"].get(_fk, "")
        feat_html = f"""<section class="rp-feature">
  <a class="rp-feature-card" href="entry/{_c['slug']}.html">
    <p class="rp-feature-tag">{html.escape(_f.get('label', '最近主打'))}</p>
    <p class="rp-series mono">{html.escape(series_label(_fk, cfg, works))}{remake_badge(cfg, _fk)}</p>
    <h2>{html.escape(_t)}</h2>
    {f'<p class="rp-sub">{html.escape(_sub)}</p>' if _sub else ''}
    <p class="muted">{format(_c['hanzi'], ',')} 汉字 · {_c['tables']} 张表</p>
    {f'<p class="rp-feature-note">{html.escape(_f["note"])}</p>' if _f.get('note') else ''}
  </a>
</section>"""

    warns = "".join(
        '<p class="rp-warn %s">%s</p>' % (w.get("kind", ""), inline(w["text"]))
        for w in cfg["warnings"])
    tot_h = sum(c["hanzi"] for c in catalog)
    tot_t = sum(c["tables"] for c in catalog)
    tot_nv = sum(w.get("hanzi", 0) for w in works.values())
    nv_bit = (" · 附 %d 部原著（%s 字）" % (n_works, format(tot_nv, ","))
              if n_works else "")
    return f"""<article class="rp-home">
<header class="hero">
  <h1>{html.escape(cfg['site_title'])}</h1>
  <p class="sub">{html.escape(cfg['subtitle'])}</p>
  <p class="stats">{len(catalog)} 份报告 · {format(tot_h, ',')} 汉字 · {tot_t} 张表{nv_bit}</p>
</header>
<section class="rp-warns">{warns}</section>
<section class="rp-intro"><p>{inline(cfg['intro'])}</p></section>
{feat_html}
{''.join(blocks)}
<section class="rp-howto"><h2>怎么读</h2>
<ol class="howto">
  <li>本站在<strong>设定站</strong>之外，收录基于<strong>设定集与跑团记录</strong>的研究报告——适合已经知道设定、想看制度与人物怎么被分析的读者。</li>
  <li>每份报告一篇，页内目录可跳转；报告里的<b>表格</b>是它的主要论证骨架。</li>
  <li><strong>跑团集锦</strong>是把一段跑团记录整个读成一篇长文：一次事变、一个短团、一场戏。每一处引用都标了季与场，想核对原始记录可以去 <a href="../trpg/index.html">跑团站</a> 按场次查。</li>
  <li><strong>独立作品研究</strong>栏目的每张卡有两个入口：<b>读原著</b>（作者的原文全文，本站附上）与<b>读研究报告</b>（AI 的分析）。报告是<strong>面向第一次读的人</strong>写的，读之前不需要任何背景——<strong>先读哪个都行</strong>；报告里每一处引用都能回原文核对。</li>
  <li>只想确认<strong>设定本身</strong>，请去 <a href="../lore/index.html">设定站</a>；想看跑团实录去 <a href="../trpg/index.html">跑团站</a>；花絮在 <a href="../huaxu/index.html">花絮站</a>。</li>
</ol></section>
</article>"""



# ══════════════════════════════════════════════════════════════
# 报告页专用样式
# ══════════════════════════════════════════════════════════════
CSS = r"""
/* ══ 分析站：报告页专用样式（长文阅读优先）══ */
/* 首页置顶「最近主打」：整块卡片，视觉上要明显高于普通分组卡片 */
.rp-feature{margin:1.4rem 0 .6rem}
.rp-feature-card{
  display:block;padding:1.1rem 1.2rem;border-radius:14px;
  border:1px solid var(--accent);background:var(--card);
  box-shadow:0 2px 14px rgba(0,0,0,.06);
}
.rp-feature-card:hover{text-decoration:none;border-color:var(--accent2)}
.rp-feature-tag{
  display:inline-block;margin:0 0 .5rem;padding:.12rem .6rem;border-radius:99px;
  background:var(--accent);color:#fff;font-size:.78rem;font-weight:700;letter-spacing:.06em;
}
.rp-feature-card h2{font-size:1.28rem;margin:.15rem 0 .3rem;line-height:1.35;color:var(--fg)}
.rp-feature-card .rp-sub{margin:.1rem 0 .35rem}
.rp-feature-note{margin:.5rem 0 0;font-size:.84rem;color:var(--accent2)}
@media (prefers-color-scheme:light){
  .rp-feature-card{box-shadow:0 2px 12px rgba(0,0,0,.08)}
}
/* 顶部菜单的样式：另三站在各自 CSS（lore.css / trpg.css）里定义了这两条，
   分析站此前没有，导致「本站首页」后的分隔符和不换色。补上以保持一致。 */
.nav-sep{width:1px;height:1.1em;background:var(--line);display:inline-block}
.nav-other{color:var(--accent)}
.rp-body{background:var(--bg);color:var(--fg)}
.rp-head{margin:1rem 0 1.4rem}
.rp-series{font-size:.82rem;color:var(--accent2);margin:0 0 .3rem;letter-spacing:.04em}
/* 「重制」标记：换源重写过的报告，卡片与正文页都挂一枚。 */
.rp-remake{display:inline-block;margin-left:.5rem;padding:.02rem .45rem;
border:1px solid var(--accent2);border-radius:99px;color:var(--accent2);
font-size:.72rem;font-weight:700;letter-spacing:.04em;vertical-align:.06em;
white-space:nowrap}
/* 卡片里单独占一行（放在字数之后）：与系列标签同行会把标签挤成两行，
   同一行里这张卡的标题就会比邻卡低一截。 */
.rp-card .rp-remake{display:block;width:max-content;margin:.45rem 0 0}
.rp-head h1{font-size:1.85rem;line-height:1.35;margin:0 0 .4rem}
.rp-sub{color:var(--muted);margin:.2rem 0 .5rem;font-size:.98rem}
.rp-meta{margin:.2rem 0 .7rem}
.rp-ai{background:var(--card);border-left:3px solid #d98b2b;border-radius:0 10px 10px 0;
padding:.55rem .9rem;margin:.6rem 0 0;font-size:.9rem;color:var(--fg)}

/* 目录 */
.rp-toc{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:.7rem 1rem .8rem;margin:1rem 0 1.4rem}
.rp-toc ol{list-style:none;padding:0;margin:.3rem 0 0;columns:2;column-gap:1.6rem}
@media(max-width:760px){.rp-toc ol{columns:1}}
.rp-toc li{margin:.14rem 0;font-size:.9rem;break-inside:avoid}
.rp-toc li.l2{font-weight:600}
.rp-toc li.l3{padding-left:1rem;color:var(--muted)}

/* 正文：行高与段距调大，长文阅读舒适 */
.rp-body{line-height:1.95;font-size:1.02rem}
.rp-body h2{font-size:1.35rem;margin:2.4rem 0 .8rem;padding-bottom:.3rem;
border-bottom:1px solid var(--line);scroll-margin-top:1rem}
.rp-body h3{font-size:1.12rem;margin:1.9rem 0 .6rem;scroll-margin-top:1rem}
/* h4 用 --fg + 透明度做出层级差别。
   注意：style.css 里**没有** --fg2（那是另一个主题体系的变量名），
   用 var(--fg2, #cfd6e4) 会在浅色主题下取到浅灰、几乎看不见。 */
.rp-body h4{font-size:1rem;margin:1.5rem 0 .5rem;
color:var(--fg);opacity:.86;scroll-margin-top:1rem}
.rp-body p{margin:.85rem 0}
.rp-body ul,.rp-body ol{margin:.7rem 0 .9rem;padding-left:1.6rem}
.rp-body li{margin:.35rem 0}
.rp-body strong{color:var(--fg);font-weight:700}
.rp-body em{color:var(--muted);font-style:italic}

/* 引文（「…」整段） */
.rp-body blockquote.quote{margin:.9rem 0;padding:.35rem 0 .35rem 1rem;
border-left:3px solid var(--line);color:var(--fg);background:transparent}

/* 推断 / 依据块 */
.rp-body p.infer{background:var(--card);border-left:3px solid var(--accent2);
border-radius:0 8px 8px 0;padding:.45rem .85rem;margin:.7rem 0;font-size:.97rem}

/* 表格：报告的主要论证骨架。
   宽表优化：横向滚动 + **表头行与首列固定**，拖动时行列标题始终可见。 */
.tw{overflow:auto;max-height:80vh;margin:1.1rem 0;
border:1px solid var(--line);border-radius:10px;position:relative}
.tw.is-wide{border-color:var(--accent2)}
table.rp{border-collapse:separate;border-spacing:0;width:100%;
font-size:.92rem;line-height:1.7;background:var(--card)}
table.rp th,table.rp td{border:0;border-right:1px solid var(--line);
border-bottom:1px solid var(--line);padding:.5rem .7rem;
vertical-align:top;text-align:left;background:var(--card)}

/* 行分隔线略强一点，保证不靠底色也能分清行 */
table.rp tbody tr>td{border-bottom-color:var(--line)}
table.rp tbody tr:hover>td{background:rgba(255,255,255,.035)}
table.rp tbody tr:hover>td:first-child{background:rgba(255,255,255,.05)}
table.rp tr>th:last-child,table.rp tr>td:last-child{border-right:0}
table.rp tbody tr:last-child>td{border-bottom:0}

/* 表头行固定。
   注意：**不要**用 var(--bg2) —— 该变量在 style.css 里并不存在，
   会回退成硬编码的 #1b2130，在浅色主题下变成突兀的深色块。
   改用极淡的白色叠加：暗色主题提亮一点、浅色主题几乎不可见，两主题都不刺眼。 */
table.rp thead th{position:sticky;top:0;z-index:2;font-weight:700;
background:rgba(255,255,255,.05);white-space:normal}
/* 首列固定 */
table.rp th:first-child,table.rp td:first-child{position:sticky;left:0;z-index:1;
background:var(--card);font-weight:600;
box-shadow:1px 0 0 var(--line)}
/* 左上角单元格：两个方向都固定，层级最高 */
table.rp thead th:first-child{z-index:3}
/* 不再用深浅交替：深色行在暗色主题下字看不清。
   改用「清晰分隔线」区分行 —— 所有行同底色，只靠线分隔。 */

/* 宽表提示 */
.tw::after{content:"⇄ 可横向拖动，表头与首列固定";position:absolute;top:.35rem;right:.5rem;
font-size:.72rem;color:var(--muted);pointer-events:none;opacity:0;transition:opacity .2s}
.tw:hover::after{opacity:1}

/* 回到顶部（与设定站/跑团站同一套；app.js 负责 .show 的切换） */
.to-top{position:fixed;right:1.1rem;bottom:1.1rem;z-index:30;
background:var(--card);border:1px solid var(--line);border-radius:99px;
padding:.45rem .9rem;font-size:.85rem;color:var(--fg);
opacity:0;pointer-events:none;transition:opacity .2s,transform .2s;text-decoration:none}
.to-top.show{opacity:.96;pointer-events:auto}
.to-top:hover{border-color:var(--accent2);text-decoration:none;transform:translateY(-2px)}

/* 搜索框：与花絮/跑团/设定三站**同一位置**（页头右侧，margin-left:auto 顶开）。
   .q-results 下拉样式共享 style.css 已有，这里不重复定义。 */
.search-wrap{position:relative;margin-left:auto}
.search-wrap input{width:13.5rem;padding:.38rem .7rem;border-radius:99px;
border:1px solid var(--line);background:var(--bg);color:var(--fg);
font-size:.88rem;transition:width .18s,border-color .18s}
.search-wrap input:focus{outline:none;border-color:var(--accent2);width:17rem}
@media(max-width:760px){.search-wrap input{width:100%}}

/* 浅色主题微调：表头更淡、行 hover 用暗色叠加 */
@media (prefers-color-scheme:light){
  table.rp thead th{background:rgba(0,0,0,.035)}
  table.rp tbody tr:hover>td{background:rgba(0,0,0,.035)}
  table.rp tbody tr:hover>td:first-child{background:rgba(0,0,0,.05)}
}

/* 首页 */
.rp-home .hero{text-align:center;margin:1.6rem 0 1.2rem}
.rp-home .hero h1{font-size:2rem;margin:0 0 .35rem}
.rp-home .stats{color:var(--muted);font-size:.95rem}
.rp-warns{margin:1.2rem 0}
.rp-warn{background:var(--card);border-left:3px solid var(--line);
border-radius:0 10px 10px 0;padding:.6rem .95rem;margin:.55rem 0;font-size:.93rem}
.rp-warn.ai{border-left-color:#d98b2b}
.rp-warn.not_lore{border-left-color:var(--accent)}
.rp-warn.origin{border-left-color:var(--accent2)}
.rp-warn.future{border-left-color:var(--muted)}
.rp-intro{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:.8rem 1rem;margin:1.1rem 0 1.6rem}
.rp-group{margin:1.8rem 0}
.rp-group>h2{font-size:1.2rem;margin:0 0 .25rem}
.rp-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(17rem,1fr));
gap:.7rem;margin:.8rem 0}
.rp-card{display:block;background:var(--card);border:1px solid var(--line);
border-radius:12px;padding:.8rem .95rem;color:var(--fg)}
.rp-card:hover{border-color:var(--accent2);text-decoration:none}
.rp-card h3{margin:.15rem 0 .3rem;font-size:1.05rem;line-height:1.4}
.rp-card .rp-sub{font-size:.88rem;margin:.1rem 0 .4rem}
.rp-card p{margin:.12rem 0}

/* ══ 独立作品研究：作品卡（一张卡两个入口）══ */
/* 与普通报告卡的唯一差别：卡本身不是链接，里面放两个 <a>，
   所以用 div + .rp-card 的同一套外观，只补按钮与排版。 */
.rp-grid-work{grid-template-columns:repeat(auto-fill,minmax(17rem,1fr))}
.rp-card--work{display:flex;flex-direction:column}
.rp-card--work:hover{border-color:var(--line)}   /* 整卡不可点，就别给可点的反馈 */
.rp-work-links{margin:auto 0 0;padding-top:.65rem;display:flex;gap:.5rem;flex-wrap:wrap}
.rp-btn{display:inline-block;padding:.3rem .85rem;border-radius:99px;
border:1px solid var(--accent);background:var(--accent);color:#fff;
font-size:.86rem;font-weight:600;line-height:1.5}
.rp-btn:hover{text-decoration:none;opacity:.88}
.rp-btn-ghost{background:transparent;color:var(--accent)}
.rp-btn-ghost:hover{background:var(--card);opacity:1;border-color:var(--accent2);
color:var(--accent2)}

/* ══ 报告页：原文入口条（只出现在绑定了原著的报告上）══ */
.rp-origin{margin:.75rem 0 0;padding:.5rem .9rem;border-left:3px solid var(--accent);
background:var(--card);border-radius:0 10px 10px 0;font-size:.93rem}
.rp-origin a{color:var(--accent);font-weight:600}
/* 封面区搬过来的说明（面向谁读 / 定位 / 内容提示）：
   沿用 .rp-warn 的外观，只把内边距压小一点，免得页头太长 */
.rp-head .rp-warn{margin:.55rem 0 0;padding:.5rem .9rem;font-size:.92rem}
.rp-head .rp-warn.content{border-left-color:#d98b2b}

/* ══ 原著页：这是「书」，不是「论文」══
   报告页是空行分段、首行不缩进、表格多；原著页反过来——首行缩进 2 字、
   段间不空行、无表格。两套排版明确区分，读者一眼知道自己在读哪种东西。 */
.nv-body{line-height:1.98;font-size:1.03rem;max-width:39rem;margin:0 auto}
.nv-body p{margin:0;text-indent:2em;text-align:justify}
.nv-body p+p{margin-top:.35rem}
.nv-body h2.nv-part{font-size:1.32rem;margin:3rem 0 1.2rem;text-align:center;
padding-bottom:.5rem;border-bottom:1px solid var(--line);scroll-margin-top:1rem}
/* 章标题要把 .rp-body h2 的下划线关掉——章很多，条条带线会碎掉版面 */
.nv-body h2.nv-chap,.nv-body h3.nv-chap{font-size:1.02rem;font-weight:700;
margin:2.4rem 0 1rem;text-align:center;color:var(--accent2);letter-spacing:.02em;
border-bottom:0;padding-bottom:0;scroll-margin-top:1rem}
/* 原著页目录：章多（黑柩校园 47 章），保持两列；篇名单独一行做分组 */
.nv-toc{padding:.55rem 1rem .7rem}
.nv-toc h2.plain{margin:0 0 .4rem;font-size:1.02rem;padding:0 0 .3rem;
border-bottom:1px solid var(--line)}
.nv-toc .nv-part-title{margin:.55rem 0 .25rem;font-weight:700;font-size:.92rem;
color:var(--accent)}
.nv-toc .nv-part-title:first-of-type{margin-top:.1rem}
/* 目录做成芯片而不是竖排 <ol>：47 个章名的竖排目录会占掉一整屏，
   读者得先滚过目录才见到正文。芯片一行排开，长目录也只是几行。 */
.nv-chips{display:flex;flex-wrap:wrap;gap:.35rem .4rem;margin:0 0 .3rem}
.nv-chips a{display:inline-block;padding:.02rem .5rem;border:1px solid var(--line);
border-radius:6px;font-size:.86rem;line-height:1.7;color:var(--fg)}
.nv-chips a:hover{border-color:var(--accent2);color:var(--accent2);
text-decoration:none}
/* 原著页页头：研究报告入口做成按钮，和首页作品卡的按钮同一套 */
.nv-report{margin:.85rem 0 0}
.nv-report a{display:inline-block;padding:.32rem .95rem;border-radius:99px;
border:1px solid var(--accent);background:var(--accent);color:#fff;
font-size:.9rem;font-weight:600}
.nv-report a:hover{text-decoration:none;opacity:.88}
"""


def main():
    if not os.path.isdir(DATA):
        sys.exit("找不到 report-data/，请先跑 tools/parse_report.py")
    cfg = json.load(io.open(CFG, encoding="utf-8"))
    catalog = json.load(io.open(os.path.join(DATA, "catalog.json"), encoding="utf-8"))
    works = load_works(cfg)
    n = 0

    # 本站 assets：report.css 自己生成，style.css / app.js 从共享 docs/assets 复制
    # （分析站自带副本 → 路径不依赖共享目录，跨目录相对路径不会算错）
    OWN = os.path.join(OUT, "assets")
    n += write_if_changed(os.path.join(OWN, "report.css"), CSS.strip() + "\n")
    for src_name in ("style.css", "app.js", "icon.png"):
        src = os.path.join(ASSETS, src_name)
        if not os.path.exists(src):
            continue
        dst = os.path.join(OWN, src_name)
        # 文本与二进制分开读（icon.png 是二进制，用 utf-8 读会炸）
        if src_name.endswith(".png"):
            data = open(src, "rb").read()
            os.makedirs(OWN, exist_ok=True)
            if not os.path.exists(dst) or open(dst, "rb").read() != data:
                open(dst, "wb").write(data)
                n += 1
        else:
            data = io.open(src, encoding="utf-8").read()
            n += write_if_changed(dst, data)

    # 原著页（独立作品研究）。works 为空时整块跳过，不影响原 15 篇。
    NV = {}
    for key, w in works.items():
        p = os.path.join(NOVEL, w["slug"] + ".md")
        if not os.path.exists(p):
            sys.exit("缺 novel-data/%s.md，请先跑 tools/parse_novel.py" % w["slug"])
        md = io.open(p, encoding="utf-8").read()
        parts, has_parts = parse_novel_md(md, w.get("toc_strip") or "")
        NV[key] = (md, parts, has_parts)
        n += write_if_changed(
            os.path.join(OUT, "works", w["slug"] + ".html"),
            page("《%s》原著 · %s" % (w["title"], cfg["site_title"]),
                 render_novel_page(w, parts, has_parts),
                 self_rel="../", up="../../",
                 foot_note="本页是<strong>作者原文全文</strong>（据 %s 稿整理），"
                           "非 AI 生成；分析见同作的<strong>研究报告</strong>。"
                           % html.escape(w.get("source_date", ""))))

    # 报告页
    order = [s for g in cfg["groups"] for s in g["reports"]]
    for c in catalog:
        slug = c["slug"]              # ASCII slug → 文件名
        key = c.get("key") or slug    # 原中文名 → 查 titles/series/subtitles
        md = io.open(os.path.join(DATA, slug + ".md"), encoding="utf-8").read()
        _w = works.get(key)
        _foot = None
        if _w:
            _foot = ("本报告由 <strong>AI</strong> 依据《%s》原著整理撰写，属读者分析；"
                     "原著是<strong>作者原文</strong>，见同栏目的原著页。"
                     % html.escape(_w["title"]))
        n += write_if_changed(
            os.path.join(OUT, "entry", slug + ".html"),
            page(cfg["titles"].get(key, slug) + " · " + cfg["site_title"],
                 render_report(key, cfg, md, slug=slug, works=works),
                 self_rel="../", up="../../", foot_note=_foot))

    # 本站搜索索引：报告标题 + 各节标题（子项带锚点）+ 原著与其各章
    def kind_of(k):
        if k in works and works[k].get("column_no"):
            return "独立作品研究之%s" % works[k]["column_no"]
        # 有栏目归属却凑不齐栏目序号的（跑团集锦三篇），只写栏目名——
        # 写「跑团集锦之二十一」会被读成「这一栏的第 21 篇」，而它其实是全站第 21 篇。
        col = (cfg.get("columns") or {}).get(k)
        if col:
            return col["name"]
        num = cfg["series"].get(k, "")
        return ("设定研究之%s" % num) if num else "专题报告"

    idx = []
    for c in catalog:
        slug = c["slug"]              # ASCII → 搜索结果链接
        key = c.get("key") or slug    # 原中文名 → 查配置
        md = io.open(os.path.join(DATA, slug + ".md"), encoding="utf-8").read()
        title = cfg["titles"].get(key, slug)
        sub = cfg["subtitles"].get(key, "")
        # id 必须带上目录：app.js 拼的是 SITE_REL + id + ".html"，
        # 而报告页在 entry/ 下（与设定站的 entry/ 同理）
        # id 已是完整路径（entry/<报告名>），故 slug 留空；
        # 约定见 build_site.py 的 app.js：href = rel + id + slug + ".html"
        idx.append({"id": "entry/" + slug, "slug": "", "title": title,
                    "kind": kind_of(key),
                    "tags": [w for w in (sub, key) if w]})
        for i, (hashes, htxt) in enumerate(re.findall(r"^(#{2,3}) (.+)$", md, re.M)):
            t = re.sub(r"\*\*", "", htxt).strip()
            if len(t) < 2 or len(t) > 42:
                continue
            # 章节条目也指向报告页（slug 留空），锚点用 report 页里真实的 h2/h3 的 id
            _a = re.sub(r"[^\w\u4e00-\u9fff]+", "-", t).strip("-")[:48].lower() or "h"
            idx.append({"id": "entry/" + slug, "slug": "", "title": t,
                        "kind": title, "tags": [], "frag": _a})

    # 原著：整篇一条（标题带《》便于与报告区分）+ 每一章一条（带锚点）。
    # 章节必须进索引——否则「妮卡 墓碑」这类查具体情节的搜索只能命中报告，
    # 而命中的报告又要靠原文核对。kind 统一以「原著」开头，结果里一眼分得清。
    for key, (md, parts, has_parts) in NV.items():
        w = works[key]
        idx.append({"id": "works/" + w["slug"], "slug": "",
                    "title": "《%s》原著" % w["title"],
                    "kind": "独立作品 · 原文", "tags": [w["title"]]})
        for p in parts:
            for s in p["secs"]:
                idx.append({"id": "works/" + w["slug"], "slug": "",
                            "title": s["title"], "kind": "原著 · " + w["title"],
                            "tags": [], "frag": s["anchor"]})

    n += write_if_changed(
        os.path.join(OWN, "search.json"),
        json.dumps({"entries": idx}, ensure_ascii=False, separators=(",", ":")))

    # 首页也在 docs/report/ 下，而样式在共享的 docs/assets/ → 必须用 rel="../"
    n += write_if_changed(os.path.join(OUT, "index.html"),
                          page(cfg["site_title"],
                               render_index(cfg, catalog, works)))

    print(json.dumps({"station": "report", "written": n,
                      "reports": len(catalog), "order": len(order),
                      "works": len(works)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
