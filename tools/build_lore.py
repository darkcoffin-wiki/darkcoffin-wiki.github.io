#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成设定站（站点 /lore/）。

数据来自 tools/parse_lore.py 的 lore-data/doc.json。

作者 2026-10-14 定的口径
------------------------
* 站名「**黑柩设定集Wiki**」
* 编纂备注 → **每卷页末尾独立折叠区**，标注「过程记录，非设定内容」
* 前言与编纂说明 → **单开一页**，设定站首页给显眼入口
* 附录「分类词条索引」→ **直接用作导航数据**（作者确认未改过）
* **不与花絮站/跑团站互链**（设定尚不完善）；但提供回联合首页的入口
* 剧透/吃书警告只在 **联合首页 + 设定站首页**；免责声明每页页脚

页面
----
    index.html            设定站首页（警告 + 12 卷卡片 + 前言入口）
    preface.html          前言与编纂说明
    vol/<slug>.html       12 个卷页（节列表 + 本卷词条索引 + 编纂备注折叠区）
    sec/<slug>.html       70 个节页（节内词条目录）
    entry/<slug>.html     568 个词条页（【概述】/【详述】/【异说】分层渲染）

用法：
    python tools/build_lore.py [--clean]
"""
import argparse
import html
import io
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import common  # noqa: E402
import numbering as NB  # noqa: E402

W = common.W
LORE_SRC = os.path.join(W, "lore-data")
OUT = os.path.join(W, "docs", "lore")
SHARED = os.path.join(W, "docs", "assets")

SITE = {
    "title": "黑柩设定集Wiki",
    "subtitle": "《黑柩设定集·第一版》的整理站",
    "description": "把《黑柩设定集》按卷、节、词条整理成可浏览、可跳转的 wiki。",
    "disclaimer": "本网站由 AI 生成，内容准确性无法完全保证。",
}

# 友情链接来自 data/site.json（与花絮站共用一份配置）
try:
    _cfg_path = os.path.join(W, "data", "site.json")
    if os.path.exists(_cfg_path):
        _cfg = json.load(io.open(_cfg_path, encoding="utf-8"))
        if _cfg.get("friend_links"):
            SITE["friend_links"] = _cfg["friend_links"]
except Exception as _e:
    print("  （友情链接配置读取失败：%s）" % _e)
# 只在站首页显示的警告（作者要求：子页面不加）
WARN_SPOILER = "本站内容**包含剧透**。设定集涵盖全书人物、事件与结局，点入即视为接受剧透风险。"
WARN_EATING = ("**吃书警告**：原作设定前后不一致（作者自称「吃书」）之处，"
               "本站**一律照录、不代为圆说**；确有分歧的条目会以【异说】单列。")
WARN_VERSION = "本站整理自《黑柩设定集·**第一版**》，内容仍在演进中，**以最新版设定集为准**。"

# 【】块名 → 渲染角色
BLOCK_META = {
    "源": ("meta", "源", "该条目取材的对话轮次号"),
    "收录范围": ("meta", "收录范围", "该条目收录的边界"),
    "概述": ("lead", "概述", "一句话定义"),
    "详述": ("body", "详述", ""),
    "异说": ("alt", "异说", "与正文不一致的说法，一并保留"),
}
LABEL = re.compile(r"^【([^】]{1,8})】\s*(.*)$")
ORDER = ["概述", "详述", "异说", "收录范围", "源"]


def write_if_changed(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = content.encode("utf-8")
    if os.path.exists(path):
        try:
            if open(path, "rb").read() == data:
                return 0
        except OSError:
            pass
    with open(path, "wb") as fh:
        fh.write(data)
    return 1


# ══════════════════════════════════════════════════════════════
# 正文：把【源】【概述】【详述】【异说】切成块
# ══════════════════════════════════════════════════════════════
def split_blocks(text):
    """→ [(块名 or '', 内容)]，块名可能为空（开头的无标签段落）。"""
    blocks, cur, buf = [], "", []
    for line in (text or "").split("\n"):
        m = LABEL.match(line.strip())
        if m:
            blocks.append((cur, "\n".join(buf).strip()))
            cur, buf = m.group(1), [m.group(2)]
        else:
            buf.append(line)
    blocks.append((cur, "\n".join(buf).strip()))
    # 去掉开头的空块
    return [(k, v) for k, v in blocks if v or k]


def md(text):
    """极简 markdown → HTML（粗体 / 代码 / 引用 / 列表 / 表格 / 换行）。"""
    if not text or not text.strip():
        return ""
    t = html.escape(text)
    lines = t.split("\n")
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        # 表格
        if s.startswith("|") and i + 1 < len(lines) and \
                re.match(r"^\|[\s:\-|]+\|$", lines[i + 1].strip()):
            head = [c.strip() for c in s.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append('<div class="tw"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
                       % ("".join("<th>%s</th>" % c for c in head),
                          "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % c for c in r)
                                  for r in rows)))
            continue
        # 引用
        if s.startswith("&gt;"):
            q = []
            while i < len(lines) and lines[i].strip().startswith("&gt;"):
                q.append(lines[i].strip()[4:].strip())
                i += 1
            out.append("<blockquote>%s</blockquote>" % "<br>".join(q))
            continue
        # 无序列表
        if re.match(r"^[-*]\s+", s):
            items = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append("<li>%s</li>" % lines[i].strip()[2:].strip())
                i += 1
            out.append("<ul>%s</ul>" % "".join(items))
            continue
        # 编号列表
        if re.match(r"^\d+[.、]\s*", s):
            items = []
            while i < len(lines) and re.match(r"^\d+[.、]\s*", lines[i].strip()):
                items.append("<li>%s</li>" % re.sub(r"^\d+[.、]\s*", "", lines[i].strip()))
                i += 1
            out.append("<ol>%s</ol>" % "".join(items))
            continue
        if not s:
            i += 1
            continue
        para = []
        while i < len(lines) and lines[i].strip() and \
                not re.match(r"^[-*]\s+", lines[i].strip()) and \
                not lines[i].strip().startswith(("|", "&gt;")):
            para.append(lines[i].strip())
            i += 1
        out.append("<p>%s</p>" % "<br>".join(para))
    t = "".join(out)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


# ══════════════════════════════════════════════════════════════
# 页面骨架
# ══════════════════════════════════════════════════════════════
def friend_links_html(_cfg=None):
    """页脚友情链接（配置在 data/site.json 的 friend_links）。

    _cfg 缺省时从模块级 SITE / site 里取（各站命名不一，故做兼容）。
    """
    cfg = _cfg
    if not isinstance(cfg, dict):
        for _n in ("SITE", "site"):
            _v = globals().get(_n)
            if isinstance(_v, dict):
                cfg = _v
                break
    out = []
    for f in ((cfg or {}).get("friend_links") or []):
        label = html.escape(f.get("label", ""))
        note = f.get("note", "")
        title = ' title="%s"' % html.escape(note) if note else ""
        out.append('<a href="%s"%s target="_blank" rel="noopener">%s</a>'
                   % (html.escape(f.get("url", "#")), title, label))
    return "".join(out) or "—"


def page(title, body, rel, extra_head="", body_class=""):
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · {html.escape(SITE['title'])}</title>
<meta name="description" content="{html.escape(SITE['description'])}">
{extra_head}<link rel="stylesheet" href="{rel}../assets/style.css">
<link rel="stylesheet" href="{rel}../assets/lore.css">
</head>
<body class="{body_class}">
<header class="site-head">
  <a class="brand" href="{rel}index.html">黑柩设定集Wiki</a>
  <nav class="site-nav">
    <a href="{rel}index.html">本站首页</a>
    <a href="{rel}preface.html">前言与编纂说明</a>
    <a href="{rel}index.html#vols">卷次与词条</a>
    <span class="nav-sep"></span>
    <a class="nav-other" href="{rel}../huaxu/index.html" title="切换到花絮站">花絮站 →</a>
    <a class="nav-other" href="{rel}../trpg/index.html" title="切换到跑团站">跑团站 →</a>
    <a class="nav-other" href="{rel}../report/index.html" title="切换到分析站">分析站 →</a>
    <a class="nav-other" href="{rel}../index.html" title="三站入口">联合首页</a>
  </nav>
  <div class="search-wrap">
    <input id="q" type="search" placeholder="搜索词条…" autocomplete="off" aria-label="搜索">
    <div id="q-results" class="q-results" hidden></div>
  </div>
</header>
<main>
{body}
</main>
<footer class="site-foot">
  <p class="disclaimer">{html.escape(SITE['disclaimer'])}</p>
  <p>《黑柩设定集·第一版》的整理与索引，内容版权归原作者所有。</p>
  <p class="muted">静态站 · 由 <code>tools/build_lore.py</code> 生成</p>
<p class="friend-links">友情链接：{friend_links_html(SITE)}</p>
</footer>
<a class="to-top" href="#" id="to-top" title="回到顶部" aria-label="回到顶部">↑ 顶部</a>
<script>window.SITE_REL = {json.dumps(rel)};window.SITE_LIST = "entry/";</script>
<script src="{rel}../assets/app.js" defer></script>
</body>
</html>
"""


# 注意：卷名/节名可能很长（「卷五、卷六 神圣希望帝国 · 进化者同盟」），
# 早期用 maxlen 截断会让三节撞成同一个 slug → 这里**不截断**，
# 靠全名保证唯一；万一仍有重复，用 SEC_SLUG_FIX 兜底。
SEC_SLUG_FIX = {}


def vol_slug(title):
    return common.slugify(title) or "vol"


def sec_slug(vol, sec):
    base = common.slugify("%s-%s" % (vol, sec))
    return SEC_SLUG_FIX.get((vol, sec), base)


# ══════════════════════════════════════════════════════════════
# 三种页面
# ══════════════════════════════════════════════════════════════
def render_entry(e):
    blocks = split_blocks(e["text"])
    by = {}
    for k, v in blocks:
        if k and k not in by:
            by[k] = v
    lead = by.get("概述", "")
    body = by.get("详述", "")
    alt = by.get("异说", "")
    scope = by.get("收录范围", "")
    src = by.get("源", "")
    unlabeled = [v for k, v in blocks if not k]

    parts = []
    if lead:
        parts.append('<p class="lead">%s</p>' % md(lead).replace("<p>", "").replace("</p>", ""))
    # 作者 2026-10-14：若只有一个内容块，不必显示「详述」标题
    # （实测 562/568 个词条只有一个正文块，只有带【异说】的才有多个）
    body_html = md(body) if body else md("\n".join(unlabeled))
    if alt:
        parts.append('<section class="blk" id="b-body"><h2>一、详述</h2>%s</section>' % body_html)
        parts.append('<section class="blk alt" id="b-alt"><h2>二、异说</h2>'
                     '<p class="muted">与正文不一致的说法，一并保留。</p>%s</section>' % md(alt))
    else:
        parts.append('<section class="blk" id="b-body">%s</section>' % body_html)
    extra = []
    # 另见交叉引用（跨卷同名主题；作者要求标注而非删除）
    sa = e.get("seealso")
    if sa:
        extra.append('<p class="seealso">🔗 <b>另见</b>：%s</p>'
                     % md(sa["note"]).replace("<p>", "").replace("</p>", ""))
    if e.get("replaced_by"):
        extra.append('<details class="meta"><summary>本条正文来源</summary>'
                     '<p>%s</p></details>' % html.escape(e["replaced_by"]))
    if scope:
        extra.append('<details class="meta"><summary>收录范围</summary>%s</details>' % md(scope))
    if src:
        extra.append('<details class="meta"><summary>源（对话轮次号）</summary>%s</details>' % md(src))
    toc = (['<li><a href="#b-body">一、详述</a></li>',
            '<li><a href="#b-alt">二、异说</a></li>'] if alt
           else ['<li><a href="#b-body">正文</a></li>'])
    # 卷直属词条（卷五/卷六）没有所属节
    if e.get("section"):
        SEC_CRUMB = (' · <a href="../sec/%s.html">%s</a>'
                     % (sec_slug(e["vol"], e["section"]), html.escape(e["section"])))
        BACK_URL = "../sec/%s.html" % sec_slug(e["vol"], e["section"])
        BACK_LABEL = "← 返回本节"
    else:
        SEC_CRUMB = ""
        BACK_URL = "../vol/%s.html" % vol_slug(e["vol"])
        BACK_LABEL = "← 返回本卷"
    return f"""<article class="entry">
<nav class="crumbs"><a href="../index.html">设定站</a> ·
  <a href="../vol/{vol_slug(e['vol'])}.html">{html.escape(e['vol'])}</a>{SEC_CRUMB}</nav>
<h1>{html.escape(e['title'])}</h1>
<p class="muted">{e['chars']:,} 字</p>
<nav class="toc"><h2 class="plain">目录</h2><ol>{''.join(toc)}</ol></nav>
{''.join(parts)}
{''.join(extra)}
<p class="back"><a href="{BACK_URL}">{BACK_LABEL}</a></p>
</article>"""


def render_section(vol, s):
    rows = "".join(
        '<li><a href="../entry/%s.html"><b>%s</b></a>'
        '<span class="muted">%d 字</span>'
        '<span class="lead-sm">%s</span></li>'
        % (e["slug"], html.escape(e["title"]), e["chars"],
           html.escape((split_blocks(e["text"])[0][1] if False else
                        next((v for k, v in split_blocks(e["text"]) if k == "概述"), "")
                        )[:78]))
        for e in s["entries"])
    # 节的“直接正文”（词条之外的内容；多半为空）
    body_text = "\n".join(x for x in (s.get("body") or []) if x)
    return f"""<article class="sec-page">
<nav class="crumbs"><a href="../index.html">设定站</a> ·
  <a href="../vol/{vol_slug(vol)}.html">{html.escape(vol)}</a></nav>
<h1>{html.escape(s['title'])}</h1>
<p class="muted">{html.escape(vol)} · 词条 {s['n_entries']} 个 · {s['chars']:,} 字</p>
{md(body_text)}
<section><h2>本节词条</h2><ul class="entry-list">{rows}</ul></section>
</article>"""


def render_vol(vol):
    secs = "".join(
        '<li><a href="../sec/%s.html">%s</a>'
        '<span class="muted">%d 词条 · %s 字</span></li>'
        % (sec_slug(vol["title"], s["title"]), html.escape(s["title"]),
           s["n_entries"], format(s["chars"], ","))
        for s in vol["sections"] if not is_note(s["title"]))
    direct = vol.get("direct_entries") or []
    direct_html = ""
    if direct:
        items = "".join(
            '<li><a href="../entry/%s.html"><b>%s</b></a>'
            '<span class="muted">%d 字</span></li>'
            % (e["slug"], html.escape(e["title"]), e["chars"]) for e in direct)
        direct_html = ('<section><h2>本卷词条</h2>'
                       '<ul class="entry-list">%s</ul></section>' % items)
    notes = [s for s in vol["sections"] if is_note(s["title"])]
    note_html = ""
    if notes:
        note_html = ('<details class="notes"><summary>编纂备注（过程记录，非设定内容）'
                     '　共 %s 字</summary>%s</details>'
                     % (format(sum(s["chars"] for s in notes), ","),
                        "".join("<h3>%s</h3>%s" % (html.escape(s["title"]), md(s["text"]))
                                for s in notes)))
    return f"""<article class="vol-page">
<nav class="crumbs"><a href="../index.html">设定站</a> · 卷</nav>
<h1>{html.escape(vol['title'])}</h1>
<p class="muted">{vol['n_sections']} 节 · {vol['n_entries']} 词条 · {vol['chars']:,} 字</p>
{md(vol['pre_text']) if vol.get('pre_text') else ''}
{('<section><h2>本卷的节</h2><ul class="sec-list">%s</ul></section>' % secs) if secs else ''}
{direct_html}
{note_html}
</article>"""


def is_note(title):
    return "编纂备注" in title


def render_preface(vols):
    pv = next((v for v in vols if v["title"].startswith("前言")), None)
    if not pv:
        return "<p>未找到前言。</p>"
    secs = "".join(
        '<section class="blk" id="s-%d"><h2>%s%s</h2>%s</section>'
        % (i, NB.level1(i), html.escape(s["title"]), md(s["text"]))
        for i, s in enumerate(pv["sections"], 1))
    toc = "".join('<li><a href="#s-%d">%s%s</a></li>'
                  % (i, NB.level1(i), html.escape(s["title"]))
                  for i, s in enumerate(pv["sections"], 1))
    return f"""<article class="preface">
<nav class="crumbs"><a href="index.html">设定站</a> · 前言</nav>
<h1>前言与编纂说明</h1>
<p class="muted">理解全书体例的钥匙：这部书怎么来的、编纂原则、卷次结构、阅读约定。</p>
<nav class="toc"><h2 class="plain">目录</h2><ol>{toc}</ol></nav>
{secs}
</article>"""


def render_index(vols, sess_stats):
    # 作者 2026-10-14：不用卡片，改为「卷」直接列出「节」，节可折叠展开看词条
    cards = []
    for v in vols:
        if v["title"].startswith(("目", "前言")):
            continue
        secs = []
        for sec in v["sections"]:
            if is_note(sec["title"]):
                continue
            ents = "".join(
                '<li><a href="entry/%s.html">%s</a>'
                '<span class="muted">%d 字</span></li>'
                % (e["slug"], html.escape(e["title"]), e["chars"])
                for e in sec["entries"]) or '<li class="muted">（本节无词条）</li>'
            secs.append(
                '<details class="sec-fold"><summary>%s'
                '<span class="muted">%d 词条</span></summary>'
                '<ul class="fold-list">%s</ul>'
                '<p class="fold-more"><a href="sec/%s.html">打开本节页 →</a></p>'
                '</details>'
                % (html.escape(sec["title"]), sec["n_entries"], ents,
                   sec_slug(v["title"], sec["title"])))
        # 卷直属词条（卷五/卷六：拆卷后没有中间层）→ 直接列出
        direct = v.get("direct_entries") or []
        if direct:
            items = "".join(
                '<li><a href="entry/%s.html">%s</a>'
                '<span class="muted">%d 字</span></li>'
                % (e["slug"], html.escape(e["title"]), e["chars"]) for e in direct)
            secs.append('<ul class="fold-list direct-list">%s</ul>' % items)
        cards.append(
            '<section class="vol-block">'
            '<h3><a href="vol/%s.html">%s</a>'
            '<span class="muted">%d 节 · %d 词条 · %s 字</span></h3>%s</section>'
            % (vol_slug(v["title"]), html.escape(v["title"]),
               v["n_sections"], v["n_entries"], format(v["chars"], ","),
               "".join(secs)))
    tot_e = sum(v["n_entries"] for v in vols)
    tot_s = sum(v["n_sections"] for v in vols)
    tot_h = sum(v.get("hanzi", 0) for v in vols)
    return f"""<article class="lore-home">
<header class="hero">
  <h1>黑柩设定集Wiki</h1>
  <p class="sub">{html.escape(SITE['subtitle'])}</p>
  <p class="stats">共 <strong>{len([v for v in vols if not v['title'].startswith(('目', '前言'))])}</strong> 卷 ·
     <strong>{tot_s}</strong> 节 ·
     <strong>{tot_e}</strong> 个词条 ·
     <strong>{format(tot_h, ',')}</strong> 汉字</p>
</header>
<section class="warns">
  <p class="warn spoiler">⚠️ {md(WARN_SPOILER).replace('<p>', '').replace('</p>', '')}</p>
  <p class="warn eating">📕 {md(WARN_EATING).replace('<p>', '').replace('</p>', '')}</p>
  <p class="warn version">🕒 {md(WARN_VERSION).replace('<p>', '').replace('</p>', '')}</p>
</section>
<section class="preface-entry">
  <a href="preface.html"><b>先读：前言与编纂说明 →</b>
  <span class="muted">这部书的来源、编纂原则、卷次结构、阅读约定</span></a>
</section>
<section id="vols"><h2>卷次与词条</h2>
<p class="muted">展开任一卷，可见该卷的节与全部词条。</p>
{''.join(cards)}</section>
<section><h2>怎么读</h2>
<ol class="howto">
  <li>查一个概念 → 用上面的搜索框，直接输入名称。</li>
  <li>按体系浏览 → 从卷进入，卷页列出该卷的全部节与词条。</li>
  <li>词条页分三层：<b>概述</b>（一句话定义）→ <b>详述</b>（正文）→
      <b>异说</b>（与正文不一致的说法，一并保留）。</li>
  <li><b>源</b>与<b>收录范围</b>收在页尾折叠区，供查证用，平时不用看。</li>
  <li>每卷页末尾有<b>编纂备注</b>折叠区，那是编纂过程记录，不是设定内容。</li>
</ol></section>
<section><h2>本书的已知情况</h2>
<ul class="gaps">
  <li>本集为<b>第一版</b>，内容仍在演进；后续修订以最新版为准。</li>
  <li>编纂者遵循「<b>零事实损失、不擅自补齐</b>」原则：无法判定的矛盾集中在附录备查。</li>
  <li>原始文件中有三份在打包时损坏，其内容未进入本集。</li>
  <li>合集中有两处「只有提问、没有回答」，故本集无法收录（详见附录）。</li>
</ul></section>
</article>"""


# ══════════════════════════════════════════════════════════════
LORE_CSS = """/* 黑柩设定集Wiki · 专有样式（共享变量见 ../assets/style.css） */
.nav-sep{width:1px;height:1.1em;background:var(--line);display:inline-block}
.nav-other{color:var(--accent)}
.hero{padding:1.5rem 0 .7rem}
.hero h1{font-size:1.7rem;margin:0 0 .3rem}
.hero .sub{color:var(--muted);margin:0 0 .6rem}
.warns{margin:1rem 0}
.warn{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:.55rem .85rem;margin:.45rem 0;font-size:.92rem}
.warn.spoiler{border-left:3px solid #d98b2b}
.warn.eating{border-left:3px solid var(--accent)}
.warn.version{border-left:3px solid var(--accent2);color:var(--muted)}
.preface-entry a{display:block;background:var(--card);border:1px solid var(--accent2);
border-radius:12px;padding:.75rem 1rem;margin:.8rem 0}
.preface-entry a:hover{text-decoration:none;border-color:var(--accent)}
.preface-entry b{display:block;font-size:1.05rem;margin-bottom:.15rem}
/* 卷区块 + 可折叠的节（作者 2026-10-14 要求：不用卡片） */
.vol-block{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:.7rem .9rem;margin:.7rem 0}
.vol-block>h3{margin:0 0 .5rem;font-size:1.05rem;display:flex;gap:.6rem;
align-items:baseline;flex-wrap:wrap}
.vol-block>h3 .muted{font-weight:400;font-size:.85rem}
details.sec-fold{border-top:1px solid var(--line);padding:.35rem 0}
details.sec-fold>summary{cursor:pointer;font-weight:600;font-size:.95rem;
display:flex;gap:.6rem;align-items:baseline}
details.sec-fold>summary .muted{font-weight:400;font-size:.82rem}
ul.fold-list{list-style:none;padding:0;margin:.4rem 0 .2rem;columns:2;column-gap:1.4rem}
@media(max-width:700px){ul.fold-list{columns:1}}
ul.fold-list li{margin:.12rem 0;font-size:.9rem;break-inside:avoid}
ul.fold-list li a{margin-right:.4rem}
.fold-more{margin:.2rem 0 0;font-size:.82rem}
ul.direct-list{margin:.4rem 0 .2rem;padding-left:0;list-style:none}
ul.sec-list,ul.entry-list{list-style:none;padding:0;margin:.5rem 0}
ul.sec-list li{border-bottom:1px solid var(--line);padding:.4rem 0}
ul.sec-list li a{font-weight:600;margin-right:.5rem}
ul.entry-list li{border-bottom:1px solid var(--line);padding:.45rem 0}
ul.entry-list li a{margin-right:.5rem}
.lead-sm{display:block;color:var(--muted);font-size:.85rem;margin-top:.15rem}
.toc{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:.6rem .9rem;margin:.9rem 0}
.toc h2{margin:.1rem 0 .35rem;font-size:.95rem}
.toc ol{margin:0;padding-left:1.2rem;font-size:.9rem}
.blk{margin:1.3rem 0;scroll-margin-top:1rem}
.blk h2{font-size:1.08rem;border-bottom:1px solid var(--line);
padding-bottom:.25rem;margin-bottom:.5rem}
.blk.alt{border-left:3px solid #d98b2b;padding-left:.9rem}
.entry .lead{background:var(--card);border-left:3px solid var(--accent2);
border-radius:0 10px 10px 0;padding:.6rem .9rem;margin:1rem 0;font-size:1.02rem}
.seealso{background:var(--card);border-left:3px solid var(--accent2);
border-radius:0 10px 10px 0;padding:.5rem .85rem;margin:.8rem 0;font-size:.92rem}
details.meta,details.notes{background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:.45rem .8rem;margin:.5rem 0}
details.meta>summary,details.notes>summary{cursor:pointer;color:var(--muted);
font-size:.88rem}
details.notes{margin-top:1.6rem}
details.notes h3{font-size:.95rem;margin:.7rem 0 .3rem}
.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.9rem}
table th,table td{border:1px solid var(--line);padding:.35rem .5rem;text-align:left;
vertical-align:top}
table th{background:var(--bg);color:var(--muted)}
.prefaces .blk,.preface .blk{margin:1.2rem 0}
.howto,.gaps{padding-left:1.2rem}
.howto li,.gaps li{margin:.25rem 0}
.back{font-size:.85rem;margin:1.2rem 0}
.to-top{position:fixed;right:1.1rem;bottom:1.1rem;z-index:30;
background:var(--card);border:1px solid var(--line);border-radius:99px;
padding:.45rem .9rem;font-size:.85rem;color:var(--fg);opacity:0;pointer-events:none;
transition:opacity .2s,transform .15s;box-shadow:0 4px 18px #0003}
.to-top.show{opacity:.96;pointer-events:auto}
.to-top:hover{border-color:var(--accent2);text-decoration:none;transform:translateY(-2px)}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    d = json.load(io.open(os.path.join(LORE_SRC, "doc.json"), encoding="utf-8"))
    vols = d["vols"]

    # ── 节 slug 唯一化（全名基础上，撞车才加 -2/-3）──
    seen = {}
    for v in vols:
        for sec in v["sections"]:
            base = common.slugify("%s-%s" % (v["title"], sec["title"])) or "sec"
            c = seen.get(base, 0) + 1
            seen[base] = c
            SEC_SLUG_FIX[(v["title"], sec["title"])] = base if c == 1 else "%s-%d" % (base, c)
    if args.clean and os.path.isdir(OUT):
        shutil.rmtree(OUT)

    n = 0
    # 词条页（含卷直属词条 —— 卷五/卷六 没有中间节）
    for v in vols:
        for e in (v.get("direct_entries") or []):
            n += write_if_changed(os.path.join(OUT, "entry", e["slug"] + ".html"),
                                  page(e["title"], render_entry(e), rel="../"))
        for s in v["sections"]:
            for e in s["entries"]:
                n += write_if_changed(os.path.join(OUT, "entry", e["slug"] + ".html"),
                                      page(e["title"], render_entry(e), rel="../"))
    # 节页
    for v in vols:
        for s in v["sections"]:
            n += write_if_changed(
                os.path.join(OUT, "sec", sec_slug(v["title"], s["title"]) + ".html"),
                page(s["title"], render_section(v["title"], s), rel="../"))
    # 卷页
    for v in vols:
        n += write_if_changed(os.path.join(OUT, "vol", vol_slug(v["title"]) + ".html"),
                              page(v["title"], render_vol(v), rel="../"))
    # 前言 + 首页
    n += write_if_changed(os.path.join(OUT, "preface.html"),
                          page("前言与编纂说明", render_preface(vols), rel=""))
    n += write_if_changed(os.path.join(OUT, "index.html"),
                          page("设定站首页", render_index(vols, {}), rel=""))
    # 样式 + 搜索索引
    n += write_if_changed(os.path.join(SHARED, "lore.css"), LORE_CSS)
    search = {"entries": [
        {"id": e["slug"], "slug": "", "title": e["title"], "kind": e["vol"],
         "tags": [e.get("section") or "", e["vol"]]}
        for v in vols
        for e in ((v.get("direct_entries") or [])
                  + [x for s in v["sections"] for x in s["entries"]])]}
    n += write_if_changed(os.path.join(OUT, "assets", "search.json"),
                          json.dumps(search, ensure_ascii=False))

    tot_e = sum(v["n_entries"] for v in vols)
    print(json.dumps({"station": "lore", "written": n, "vols": len(vols),
                      "sections": sum(v["n_sections"] for v in vols),
                      "entries": tot_e}, ensure_ascii=False))


if __name__ == "__main__":
    main()
