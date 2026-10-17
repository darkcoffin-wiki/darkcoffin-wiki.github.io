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
CFG = os.path.join(W, "data", "report_site.json")

SITE = {
    "title": "黑柩分析站",
    "subtitle": "基于《黑柩设定集》的专题研究报告",
    "disclaimer": "本网站由 AI 生成，内容准确性无法完全保证。",
}
HANZI = re.compile(r"[\u4e00-\u9fff]")

# 行内标记：**粗** / *斜*
BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.S)
ITAL_RE = re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)")
# 「推断」类标记：报告用它承载第三方判断，做成醒目小块
INFER_RE = re.compile(r"^\s*(【推断[^】]*】|依据[:：])")


def inline(txt):
    """行内：转义 → 粗体 → 斜体 → `code`。先转义，再用占位符换标记。"""
    t = html.escape(txt, quote=False)
    t = BOLD_RE.sub(lambda m: "<strong>%s</strong>" % m.group(1), t)
    t = ITAL_RE.sub(lambda m: "<em>%s</em>" % m.group(1), t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
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
def md_to_html(md):
    lines = md.split("\n")
    out, toc = [], []
    seen = {}
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        s = ln.strip()

        if not s:
            i += 1
            continue

        # ── 标题 ──
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            lv = len(m.group(1))
            txt = m.group(2).strip()
            aid = slugify_anchor(txt, seen)
            if lv <= 3:
                toc.append((lv, txt, aid))
            # 报告标题块（正文里的《…》设定研究之N）跳过不渲染为标题
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


def page(title, body, self_rel="", up="../", extra_head="", show_search=True):
    """self_rel：本站内资源前缀（首页 ""、entry/ 页 "../"）。

    up：回 docs/ 根的前缀（首页 "../"、entry/ 页 "../../"），用于跨站菜单与品牌链接。
    分析站自带 assets 副本，故本站资源不依赖共享 docs/assets，路径更稳。
    """
    import json as _json
    # SITE_REL = 「回本站根」的前缀。分析站的结果页都在 entry/ 下，
    # app.js 会拼成 SITE_REL + <报告slug>.html → 必须指向 entry/ 所在层的上一层。
    sr_json = _json.dumps(self_rel)
    si_json = _json.dumps("assets/search.json")   # 本站自己的搜索索引（相对本站根）
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
  <p>本站报告由 AI 依据《黑柩》设定集整理撰写，属读者分析，非作者设定原文。</p>
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
# 渲染报告页
# ══════════════════════════════════════════════════════════════
def render_report(key, cfg, md, slug=None):
    """key：原中文名（**查配置用这个**）；slug：ASCII 文件名（只用于文件名，本函数不用）。"""
    meta_t = cfg["titles"].get(key, key)
    meta_s = cfg["subtitles"].get(key, "")
    num = cfg["series"].get(key, "")
    html_body, toc = md_to_html(md)
    hanzi = len(HANZI.findall(md))
    n_tbl = html_body.count('<table class="rp">')

    toc_items = "".join(
        '<li class="l%d"><a href="#%s">%s</a></li>' % (lv, aid, html.escape(txt))
        for lv, txt, aid in toc if lv >= 2)
    num_txt = ('《黑柩》设定研究之%s' % num) if num else "专题报告"

    return f"""<article class="rp-doc">
<nav class="crumbs"><a href="../index.html">分析站</a> · {html.escape(meta_t)}</nav>
<header class="rp-head">
  <p class="rp-series mono">{html.escape(num_txt)}</p>
  <h1>{html.escape(meta_t)}</h1>
  {f'<p class="rp-sub">{html.escape(meta_s)}</p>' if meta_s else ''}
  <p class="rp-meta muted">{hanzi:,} 汉字 · {n_tbl} 张表 · 依据《黑柩设定集》整理</p>
  <p class="rp-ai">⚠️ 本报告由 <strong>AI 撰写</strong>，属读者分析，<strong>非作者设定原文</strong>；
     引用原文处随文标明，推断处标【推断】。</p>
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
def render_index(cfg, catalog):
    # g["reports"] 里写的是**原中文名**，故按 key 建索引
    by = {(c.get("key") or c["slug"]): c for c in catalog}
    blocks = []
    for g in cfg["groups"]:
        cards = []
        for slug in g["reports"]:
            c = by.get(slug)
            if not c:
                continue
            num = cfg["series"].get(slug, "")
            t = cfg["titles"].get(slug, slug)
            sub = cfg["subtitles"].get(slug, "")
            cards.append(
                '<a class="rp-card" href="entry/{slug}.html">'
                '<p class="rp-series mono">{n}</p><h3>{t}</h3>'
                '<p class="rp-sub">{sub}</p>'
                '<p class="muted">{h} 汉字 · {tb} 张表</p></a>'.format(
                    n=("《黑柩》设定研究之%s" % num) if num else "专题报告",
                    t=html.escape(t), sub=html.escape(sub),
                    h=format(c["hanzi"], ","), tb=c["tables"],
                    slug=c["slug"]))   # 卡片链接用 ASCII slug
        blocks.append(
            '<section class="rp-group"><h2>%s</h2>'
            '<p class="muted">%s</p>'
            '<div class="rp-grid">%s</div></section>'
            % (html.escape(g["name"]), html.escape(g["desc"]), "".join(cards)))

    warns = "".join(
        '<p class="rp-warn %s">%s</p>' % (w.get("kind", ""), inline(w["text"]))
        for w in cfg["warnings"])
    tot_h = sum(c["hanzi"] for c in catalog)
    tot_t = sum(c["tables"] for c in catalog)
    return f"""<article class="rp-home">
<header class="hero">
  <h1>{html.escape(cfg['site_title'])}</h1>
  <p class="sub">{html.escape(cfg['subtitle'])}</p>
  <p class="stats">{len(catalog)} 份报告 · {format(tot_h, ',')} 汉字 · {tot_t} 张表</p>
</header>
<section class="rp-warns">{warns}</section>
<section class="rp-intro"><p>{inline(cfg['intro'])}</p></section>
{''.join(blocks)}
<section class="rp-howto"><h2>怎么读</h2>
<ol class="howto">
  <li>本站在<strong>设定站</strong>之外，收录基于设定集的<strong>研究报告</strong>——适合已经知道设定、想看制度与人物怎么被分析的读者。</li>
  <li>每份报告一篇，页内目录可跳转；报告里的<b>表格</b>是它的主要论证骨架。</li>
  <li>只想确认<strong>设定本身</strong>，请去 <a href="../lore/index.html">设定站</a>；想看跑团实录去 <a href="../trpg/index.html">跑团站</a>；花絮在 <a href="../huaxu/index.html">花絮站</a>。</li>
</ol></section>
</article>"""


# ══════════════════════════════════════════════════════════════
# 报告页专用样式
# ══════════════════════════════════════════════════════════════
CSS = r"""
/* ══ 分析站：报告页专用样式（长文阅读优先）══ */
/* 顶部菜单的样式：另三站在各自 CSS（lore.css / trpg.css）里定义了这两条，
   分析站此前没有，导致「本站首页」后的分隔符和不换色。补上以保持一致。 */
.nav-sep{width:1px;height:1.1em;background:var(--line);display:inline-block}
.nav-other{color:var(--accent)}
.rp-body{background:var(--bg);color:var(--fg)}
.rp-head{margin:1rem 0 1.4rem}
.rp-series{font-size:.82rem;color:var(--accent2);margin:0 0 .3rem;letter-spacing:.04em}
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
"""


def main():
    if not os.path.isdir(DATA):
        sys.exit("找不到 report-data/，请先跑 tools/parse_report.py")
    cfg = json.load(io.open(CFG, encoding="utf-8"))
    catalog = json.load(io.open(os.path.join(DATA, "catalog.json"), encoding="utf-8"))
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

    # 报告页
    order = [s for g in cfg["groups"] for s in g["reports"]]
    for c in catalog:
        slug = c["slug"]              # ASCII slug → 文件名
        key = c.get("key") or slug    # 原中文名 → 查 titles/series/subtitles
        md = io.open(os.path.join(DATA, slug + ".md"), encoding="utf-8").read()
        n += write_if_changed(
            os.path.join(OUT, "entry", slug + ".html"),
            page(cfg["titles"].get(key, slug) + " · " + cfg["site_title"],
                 render_report(key, cfg, md, slug=slug), self_rel="../",
                 up="../../"))

    # 本站搜索索引：报告标题 + 各节标题（子项带锚点）
    idx = []
    for c in catalog:
        slug = c["slug"]              # ASCII → 搜索结果链接
        key = c.get("key") or slug    # 原中文名 → 查配置
        md = io.open(os.path.join(DATA, slug + ".md"), encoding="utf-8").read()
        title = cfg["titles"].get(key, slug)
        sub = cfg["subtitles"].get(key, "")
        num = cfg["series"].get(key, "")
        # id 必须带上目录：app.js 拼的是 SITE_REL + id + ".html"，
        # 而报告页在 entry/ 下（与设定站的 entry/ 同理）
        # id 已是完整路径（entry/<报告名>），故 slug 留空；
        # 约定见 build_site.py 的 app.js：href = rel + id + slug + ".html"
        idx.append({"id": "entry/" + slug, "slug": "", "title": title,
                    "kind": ("设定研究之%s" % num) if num else "专题报告",
                    "tags": [w for w in (sub, key) if w]})
        for i, (hashes, htxt) in enumerate(re.findall(r"^(#{2,3}) (.+)$", md, re.M)):
            t = re.sub(r"\*\*", "", htxt).strip()
            if len(t) < 2 or len(t) > 42:
                continue
            # 章节条目也指向报告页（slug 留空），锚点用 report 页里真实的 h2/h3 的 id
            _a = re.sub(r"[^\w\u4e00-\u9fff]+", "-", t).strip("-")[:48].lower() or "h"
            idx.append({"id": "entry/" + slug, "slug": "", "title": t,
                        "kind": title, "tags": [], "frag": _a})
    n += write_if_changed(
        os.path.join(OWN, "search.json"),
        json.dumps({"entries": idx}, ensure_ascii=False, separators=(",", ":")))

    # 首页也在 docs/report/ 下，而样式在共享的 docs/assets/ → 必须用 rel="../"
    n += write_if_changed(os.path.join(OUT, "index.html"),
                          page(cfg["site_title"], render_index(cfg, catalog)))

    print(json.dumps({"station": "report", "written": n,
                      "reports": len(catalog), "order": len(order)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
