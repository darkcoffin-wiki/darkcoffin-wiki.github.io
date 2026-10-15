#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成跑团站（站点 /trpg/）。

数据来自 tools/parse_trpg.py 的产出（trpg-data/*.json）。
页面：
    index.html            跑团首页：12 季卡片 + 统计 + 时间轴入口
    season/<slug>.html    12 个季志页（十节 + 分层序号 + sticky 目录 + 季摘要折叠）
    session/<slug>.html   113 张场次卡（12 字段 + 分层序号 + 上一场/下一场）
    timeline.html         现实时间轴（按季分组；世界层标注）
    assets/*              样式、脚本、搜索索引

跨站互链：只对「结构化名单字段」（在场/地点/登场人物/场次索引）做链接，
数据来自 trpg-data/link_whitelist.json（作者复核后生成；文件不存在则不链）。
**剧情摘要正文一律不链。**

用法：
    python tools/build_trpg.py
    python tools/build_trpg.py --clean
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
TRPG_SRC = os.path.join(W, "trpg-data")
OUT = os.path.join(W, "docs", "trpg")

SITE = {
    "title": "黑柩跑团Wiki",
    "subtitle": "《黑柩》跑团剧情志 · 主线 12 季 + 短团 4 个 · 152 场",
    "description": "把《黑柩》跑团的场次志与季志整理成可浏览、可跳转的 wiki。",
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

# 「剧情摘要」以外的字段才允许做跨站链接
LINKABLE_KEYS = ("present", "places")

# 作者要求的季顺序（不是字典序，也不是纯数字序：第四季要拆上/下，幕间季二在第八季之后）
SEASON_ORDER = [
    "第一季·星灯之谜", "第二季·星都陨落", "第三季·青都疑云",
    "第四季上·夜都曙光", "第四季下·夜都曙光", "第五季·青都大选",
    "第六季·血与火", "第七季·太阳照常升起", "第八季·人民万岁",
    "幕间季二·狂飙", "第九季上·阳谋", "第九季下·再聚",
]
_ORDER_IDX = {n: i for i, n in enumerate(SEASON_ORDER)}


def season_key(name):
    """按作者指定顺序排序；不在表里的排最后（按名字）。"""
    return (_ORDER_IDX.get(name, 999), name)


# ── 短团（作者 2026-10-14：与主线分开归类，首页与时间轴单列）──
SHORT_PREFIX = "短团·"
SHORT_ORDER = [
    "短团·重置版·星都陨落", "短团·西沙", "短团·食龙则肥", "短团·竖棺",
]
_SHORT_IDX = {n: i for i, n in enumerate(SHORT_ORDER)}


def is_short(name):
    return (name or "").startswith(SHORT_PREFIX)


def short_key(name):
    """短团按现实时间先后排；表里没列到的排最后（按名字）。"""
    return (_SHORT_IDX.get(name, 999), name)


def group_label(name):
    """展示名：短团去掉「短团·」前缀。"""
    return name[len(SHORT_PREFIX):] if is_short(name) else name


def clean_time(rt):
    """时间轴用：只保留时间起止，去掉「时长」与「依据」。

    例：
      '2020-01-12 16:45 ~ 2020-01-13 02:18（时长 9.6 小时）｜依据：[…]'
      → '2020-01-12 16:45 ~ 2020-01-13 02:18'
      '2020-01-14 00:43（仅一条时间戳，无结束时间）'
      → 原样保留（无法标记结束时间的情况要说明）
    """
    if not rt:
        return ""
    t = rt.split("｜依据")[0]
    t = t.split("依据：")[0]
    # ① 整段就是时长括号 → 去掉整段（含全角/半角括号）
    t = re.sub("（[^）]*?时长[^）]*?）", "", t)
    t = re.sub(r"\([^)]*?时长[^)]*?\)", "", t)
    # ② 时长嵌在别的说明括号里 → 只摘掉那一小段
    t = re.sub(
        "[\uff1b\uff0c\u3001,;]?\\s*\u65f6\u957f[\\s\\d.]*?(?:\u5c0f\u65f6|\u5206\u949f|\u79d2|\u4e0d\u53ef\u8ba1)", "", t)
    t = re.sub(
        "[\uff1b\uff0c\u3001,;]\\s*(?=\uff09)", "", t)
    t = re.sub(
        "[\uff1b\uff0c\u3001,;]\\s*(?=\\))", "", t)
    t = t.rstrip()
    # ③ 没有区间（缺结束时间戳）→ 统一标注，避免读者误以为「这场就这么短」
    if t and "~" not in t and t.endswith("\uff09"):
        t = re.sub("\uff08[^\uff09]*\uff09$", "", t).rstrip()
    if t and "~" not in t:
        return t + SHORT_TIME_LABEL
    return t.rstrip("\uff5c").strip()


def parse_dt(text):
    """从 '2020-01-12 16:45 ~ …' 里取起始时间，用于排序（无则空串）。"""
    m = re.search(r"(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?", text or "")
    return (m.group(1) + " " + (m.group(2) or "00:00")) if m else ""


# ══════════════════════════════════════════════════════════════
# 极简 markdown → HTML（够用即可：粗体、代码、引用、行内换行）
# ══════════════════════════════════════════════════════════════
BOLD = re.compile(r"\*\*(.+?)\*\*")
CODE = re.compile(r"`([^`]+)`")


def inline(text):
    t = html.escape(text or "")
    t = CODE.sub(lambda m: "<code>%s</code>" % m.group(1), t)
    t = BOLD.sub(lambda m: "<strong>%s</strong>" % m.group(1), t)
    return t


def md(text, link=True, linkable_keys=()):
    """把一段 markdown 转成 HTML。link=False 时不做跨站链接。"""
    if not text or not text.strip():
        return ""
    t = html.escape(text)
    # 引用块
    lines, out, quote = t.split("\n"), [], []
    for line in lines:
        if line.startswith("&gt;"):
            quote.append(line[4:].strip())
            continue
        if quote:
            out.append('<blockquote>%s</blockquote>' % "<br>".join(quote))
            quote = []
        out.append(line)
    if quote:
        out.append('<blockquote>%s</blockquote>' % "<br>".join(quote))
    t = "\n".join(out)
    t = CODE.sub(lambda m: "<code>%s</code>" % m.group(1), t)
    t = BOLD.sub(lambda m: "<strong>%s</strong>" % m.group(1), t)
    if link and linkable_keys:
        t = crosslink(t, linkable_keys)
    t = re.sub(r"\n{2,}", "</p><p>", t)
    t = t.replace("\n", "<br>")
    return "<p>%s</p>" % t


# ══════════════════════════════════════════════════════════════
# 跨站互链（只用于结构化名单字段）
# ══════════════════════════════════════════════════════════════
WHITELIST = None
MATCHERS = None


def load_whitelist():
    """读取作者复核过的白名单；不存在则不做任何链接。"""
    global WHITELIST, MATCHERS
    p = os.path.join(TRPG_SRC, "link_whitelist.json")
    if not os.path.exists(p):
        WHITELIST, MATCHERS = set(), []
        return "（白名单尚未生成 → 本版不做跨站链接）"
    d = json.load(io.open(p, encoding="utf-8"))
    WHITELIST = {t for t, ok in (d.get("approved") or {}).items() if ok}
    # 用花絮站的匹配器（词表 + 别名），只保留白名单里的标签
    try:
        import tag_entries as TE
        labels, matchers, entities, ov, contained = TE.load_vocab()
        MATCHERS = [m for m in matchers if m[0] in WHITELIST]
    except Exception as ex:
        MATCHERS = []
        return "（匹配器加载失败：%s）" % ex
    return "已启用：白名单 %d 个标签、%d 条写法" % (len(WHITELIST), len(MATCHERS))


def crosslink(escaped_html, _keys):
    """在已转义的 HTML 里把白名单名字变成指向花絮站标签页的链接。

    注意：入参是**已转义**的 HTML，所以按转义后的名字匹配。
    """
    if not MATCHERS:
        return escaped_html
    # 按名字长度降序，做最长匹配
    cands = sorted(MATCHERS, key=lambda m: -len(m[0]))
    out, i, n = [], 0, len(escaped_html)
    while i < n:
        hit = None
        for variant, label, dim in cands:
            if escaped_html.startswith(variant, i):
                hit = (variant, label)
                break
        if hit:
            variant, label = hit
            slug = SLUGS.get(label)
            if slug:
                out.append('<a class="xlink" href="%shuaxu/tag/%s.html" '
                           'title="花絮站：%s">%s</a>'
                           % (XLINK_REL, slug, html.escape(label), variant))
            else:
                out.append(variant)
            i += len(variant)
        else:
            out.append(escaped_html[i])
            i += 1
    return "".join(out)


SLUGS = {}
XLINK_REL = "../../"   # 从 session/ 或 season/ 回到站点根

# 只有起始时间戳、无法标记结束时间的场次，统一加这句标注（改这里即可换措辞）
SHORT_TIME_LABEL = "（单条时间戳）"


# ══════════════════════════════════════════════════════════════
# 页面骨架（与花絮站同一套视觉，多一个跨站菜单）
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
{extra_head}<link rel="icon" type="image/png" href="{rel}../assets/icon.png">
<link rel="apple-touch-icon" href="{rel}../assets/icon.png">
<link rel="stylesheet" href="{rel}../assets/style.css">
<link rel="stylesheet" href="{rel}assets/trpg.css">
</head>
<body class="{body_class}">
<header class="site-head">
  <a class="brand" href="{rel}index.html">黑柩跑团Wiki</a>
  <nav class="site-nav">
    <a href="{rel}index.html">本站首页</a>
    <a href="{rel}index.html#seasons">季志</a>
    <a href="{rel}timeline.html">时间轴</a>
    <span class="nav-sep"></span>
    <a class="nav-other" href="{rel}../huaxu/index.html" title="切换到花絮站">花絮站 →</a>
    <a class="nav-other" href="{rel}../lore/index.html" title="切换到设定站">设定站 →</a>
    <a class="nav-other" href="{rel}../report/index.html" title="切换到分析站">分析站 →</a>
    <a class="nav-other" href="{rel}../index.html" title="三站入口">联合首页</a>
  </nav>
  <div class="search-wrap">
    <input id="q" type="search" placeholder="搜索场次或季…" autocomplete="off" aria-label="搜索">
    <div id="q-results" class="q-results" hidden></div>
  </div>
</header>
<main>
{body}
</main>
<footer class="site-foot">
  <p class="disclaimer">{html.escape(SITE['disclaimer'])}</p>
  <p>《黑柩》跑团剧情志的整理与索引，内容版权归原作者所有。</p>
  <p class="muted">静态站 · 由 <code>tools/build_trpg.py</code> 生成 ·
     数据源：<code>E:\\黑柩\\黑柩跑团剧情志</code></p>
<p class="friend-links">友情链接：{friend_links_html(SITE)}</p>
</footer>
<a class="to-top" href="#" id="to-top" title="回到顶部" aria-label="回到顶部">↑ 顶部</a>
<script>window.SITE_REL = {json.dumps(rel)};window.SITE_LIST = "session/";</script>
<script src="{rel}../assets/app.js" defer></script>
</body>
</html>
"""


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
# 页类型
# ══════════════════════════════════════════════════════════════
def session_slug(s):
    return "%s-%02d" % (common.slugify(s["season"]), s["no"])


def season_slug(name):
    return common.slugify(name)


def nav_prev_next(sess, i):
    out = []
    if i > 0:
        p = sess[i - 1]
        out.append('<a class="pn prev" href="%s.html">← 上一场：%s 第%d场</a>'
                   % (session_slug(p), p["season"], p["no"]))
    if i + 1 < len(sess):
        n = sess[i + 1]
        out.append('<a class="pn next" href="%s.html">下一场：%s 第%d场 →</a>'
                   % (session_slug(n), n["season"], n["no"]))
    return '<nav class="pn-nav">%s</nav>' % "".join(out)


def render_season(s, sess_of_season, all_sess):
    # 第 1 层锚到小节，第 2 层锚到对应的折叠块（否则点了没反应）
    toc_parts, beat_i = [], 0
    for i, t in enumerate(s["toc"], 1):
        if t["level"] == 1:
            toc_parts.append('<li class="l1"><a href="#sec-%d">%s</a></li>'
                             % (i, html.escape(t["title"])))
        else:
            beat_i += 1
            toc_parts.append('<li class="l2"><a href="#beat-%d">%s</a></li>'
                             % (beat_i, html.escape(t["title"])))
    toc = "".join(toc_parts)
    parts = []
    for i, sec in enumerate(s["sections_numbered"], 1):
        pure = sec["pure"]
        body = sec["text"]
        # 季摘要：按小节折叠（最大的一节 5.7 万字，必须折叠）
        if pure == "季摘要" and s["summary"]:
            blocks = "".join(
                '<details class="sub" id="beat-%d"%s><summary>%s</summary>%s</details>'
                % (j + 1, " open" if j == 0 else "", html.escape(p["numbered"]),
                   md(p["text"]))
                for j, p in enumerate(s["summary"]))
            parts.append(
                '<section class="sec" id="sec-%d"><h2>%s</h2>'
                '<p class="muted">本季摘要共 %d 个小节，点击标题展开。</p>%s'
                '<p class="back"><a href="#toc">↑ 回到目录</a></p></section>'
                % (i, html.escape(sec["title"] if "title" in sec else sec["no"] + pure),
                   len(s["summary"]), blocks))
            continue
        if pure == "场次索引" and s["index"]:
            rows = "".join(
                "<tr><td>%s</td><td class=\"mono\">%s</td><td>%s</td><td>%s</td></tr>"
                % (html.escape(r["id"]), html.escape(r["realtime"]),
                   html.escape(r["place"]), md(r["gist"]).replace("<p>", "").replace("</p>", ""))
                for r in s["index"])
            table = ('<div class="tw"><table class="idx"><thead><tr>'
                     '<th>场</th><th>现实时间</th><th>地点</th><th>一句话</th>'
                     '</tr></thead><tbody>%s</tbody></table></div>' % rows)
            cards = ('<div class="sess-grid">%s</div>' % "".join(
                '<a class="sess-card" href="../session/%s.html"><b>第 %d 场</b>'
                '<span class="mono">%s</span><span class="muted">%d 字 · 决策 %d · 骰点 %d</span></a>'
                % (session_slug(x), x["no"], html.escape(
                    (x["fields"].get("realtime") or "")[:38]),
                   x["hanzi"], x["n_decisions"], x["n_dice"])
                for x in sess_of_season))
            parts.append('<section class="sec" id="sec-%d"><h2>%s</h2>%s%s'
                         '<p class="back"><a href="#toc">↑ 回到目录</a></p></section>'
                         % (i, html.escape(sec["no"] + pure), table, cards))
            continue
        parts.append('<section class="sec" id="sec-%d"><h2>%s</h2>%s'
                     '<p class="back"><a href="#toc">↑ 回到目录</a></p></section>'
                     % (i, html.escape(sec["no"] + pure), md(body)))

    ov = s.get("overview") or {}
    meta_rows = "".join('<tr><th>%s</th><td>%s</td></tr>'
                        % (html.escape(k), md(v).replace("<p>", "").replace("</p>", ""))
                        for k, v in ov.items())
    # 短团用「团」的措辞（作者 2026-10-14：短团与主线分开归类）
    _short = is_short(s["name"])
    _sh = group_label(s["name"]) if _short else s["name"]
    _zhi = "团志" if _short else "季志"
    _anchor = "shorts" if _short else "seasons"
    _ov = "本团概览" if _short else "本季概览"
    body = f"""<article class="season-page">
<nav class="crumbs"><a href="../index.html">跑团首页</a> · <a href="../index.html#{_anchor}">{_zhi}</a> · {html.escape(_sh)}</nav>
<h1>{html.escape(_sh)} <span class="muted">{_zhi}</span></h1>
<p class="muted">{len(sess_of_season)} 场 · {sum(x['hanzi'] for x in sess_of_season):,} 汉字 ·
   本页 {sum(len(x['text']) for x in s['sections_numbered']):,} 字符</p>
<section class="card"><h2 class="plain">{_ov}</h2><div class="tw"><table class="kv">{meta_rows}</table></div></section>
<nav class="toc" id="toc"><h2 class="plain">目录</h2><ol>{toc}</ol></nav>
{''.join(parts)}
{nav_season_all(all_sess, s['name'])}
</article>"""
    return body


def nav_season_all(all_sess, cur):
    """季导航：主线与短团分两组列出（短团展示名不带前缀）。"""
    def link(n):
        return ('<a class="%s" href="%s.html">%s</a>'
                % ("cur" if n == cur else "", season_slug(n),
                   html.escape(group_label(n))))

    mains = [x["name"] for x in sorted(all_sess, key=lambda x: season_key(x["name"]))
             if not is_short(x["name"])]
    shorts = [x["name"] for x in sorted(all_sess, key=lambda x: short_key(x["name"]))
              if is_short(x["name"])]
    html_ = '<nav class="season-nav"><h3>主线</h3>%s' % "".join(link(n) for n in mains)
    if shorts:
        html_ += '<h3>短团</h3>%s' % "".join(link(n) for n in shorts)
    return html_ + "</nav>"


def render_session(s, i, sess, seasons_by_name):
    fields = []
    for f in s["fields_numbered"]:
        key, title, text = f["key"], f["title"], f["text"]
        if not text.strip():
            continue
        if key == "summary" and s["summary_parts"]:
            # 第 1 节默认展开（作者要求）
            blocks = "".join(
                '<details class="sub" id="beat-%d"%s><summary>%s</summary>%s</details>'
                % (j + 1, " open" if j == 0 else "",
                   html.escape(p["numbered"]), md(p["text"]))
                for j, p in enumerate(s["summary_parts"]))
            inner = blocks
        elif key == "decisions" and s["decisions"]:
            inner = "<ol class=\"dec\">%s</ol>" % "".join(
                "<li>%s</li>" % md(d).replace("<p>", "").replace("</p>", "")
                for d in s["decisions"])
        elif key == "dice" and s["dice"]:
            rows = ""
            for d in s["dice"]:
                cells = d["parts"]
                verdict = next((c for c in cells if "成功" in c or "失败" in c), "")
                cls = "ok" if "成功" in verdict else ("bad" if "失败" in verdict else "")
                rows += "<tr class=\"%s\">%s</tr>" % (
                    cls, "".join("<td>%s</td>" % html.escape(c) for c in cells))
            inner = ('<div class="tw"><table class="dice"><tbody>%s</tbody></table></div>'
                     '<p class="muted">共 %d 条骰点；其中可判定成败的已标注颜色。</p>'
                     % (rows, len(s["dice"])))
        elif key == "hooks" and s["hooks"]:
            inner = "<ul class=\"hooks\">%s</ul>" % "".join(
                "<li>%s</li>" % md(h).replace("<p>", "").replace("</p>", "")
                for h in s["hooks"])
        else:
            # 只有「在场」「地点」这类结构化名单才做跨站链接
            inner = md(text, link=(key in LINKABLE_KEYS),
                       linkable_keys=(key,))
        fields.append('<section class="field" id="f-%s"><h2>%s</h2>%s'
                      '<p class="back"><a href="#toc">↑ 回到目录</a></p></section>'
                      % (key, html.escape(title), inner))

    _l1 = [t for t in s["toc"] if t["level"] == 1]
    _tp, _beat = [], 0
    for _k, _t in enumerate(_l1):
        _tp.append('<li class="l1"><a href="#f-%s">%s</a></li>'
                   % (s["fields_numbered"][_k]["key"], html.escape(_t["title"])))
    for _t in [t for t in s["toc"] if t["level"] == 2]:
        _beat += 1
        _tp.append('<li class="l2"><a href="#beat-%d">%s</a></li>'
                   % (_beat, html.escape(_t["title"])))
    toc = "".join(_tp)
    extra = ""
    if s.get("extra"):
        extra = ('<section class="sec"><h2>附加条目</h2>%s</section>'
                 % "".join('<h3>%s</h3>%s' % (html.escape(k), md(v))
                           for k, v in s["extra"].items()))
    season = seasons_by_name.get(s["season"], {})
    ov = (season.get("overview") or {})
    badge = ("本季完整度：" + ov.get("完整度", "—")[:60]) if ov else ""
    return f"""<article class="sess-page">
<nav class="crumbs"><a href="../index.html">跑团首页</a> ·
  <a href="../season/{season_slug(s['season'])}.html">{html.escape(group_label(s['season']))}</a> ·
  第 {s['no']} 场</nav>
<h1>{html.escape(group_label(s['season']))} · 第 {s['no']} 场</h1>
<p class="muted">{s['hanzi']:,} 汉字 · 决策点 {s['n_decisions']} 条 · 骰点 {s['n_dice']} 条
   {('· ' + html.escape(badge)) if badge else ''}</p>
<nav class="toc" id="toc"><h2 class="plain">目录</h2><ol>{toc}</ol></nav>
{''.join(fields)}
{extra}
{nav_prev_next(sess, i)}
</article>"""


def render_timeline(sess, seasons):
    """按季分组列出现实时间；世界层用标记显示。

    作者 2026-10-14：分「主线」与「短团」两组，短团单列在时间轴末尾。
    """
    by_season = {}
    for s in sorted(sess, key=lambda x: (season_key(x["season"]), x["no"])):
        by_season.setdefault(s["season"], []).append(s)

    def build_group(sel, keyf):
        out = []
        for s in sorted([x for x in seasons if sel(x["name"])],
                        key=lambda x: keyf(x["name"])):
            items = by_season.get(s["name"], [])
            if not items:
                continue
            rows = ""
            for x in items:
                rt = clean_time(x["fields"].get("realtime", ""))
                wl = x["fields"].get("world_layer", "")
                tier = ("主世界" if wl.startswith("主世界") else
                        ("未明" if wl.startswith("未明") else "多层/其他"))
                key = ("main" if tier == "主世界"
                       else ("unk" if tier == "未明" else "multi"))
                rows += ('<li class="tl-item" data-wl="%s">'
                         '<a href="session/%s.html">第 %d 场</a>'
                         '<span class="tl-time mono">%s</span>'
                         '<span class="wl wl-%s">%s</span></li>'
                         % (key, session_slug(x), x["no"], html.escape(rt),
                            key, tier))
            out.append('<section class="tl-season"><h2>%s '
                       '<span class="muted">%d 场</span> '
                       '<span class="muted mono">%s</span></h2>'
                       '<ul class="timeline">%s</ul></section>'
                       % (html.escape(group_label(s["name"])), len(items),
                          html.escape((s.get("overview") or {}).get("现实时间", "")[:44]),
                          rows))
        return out

    blocks = []
    main_blocks = build_group(lambda n: not is_short(n), season_key)
    if main_blocks:
        blocks.append('<section class="tl-group"><h2 class="group-h">主线</h2>%s</section>'
                      % "".join(main_blocks))
    short_blocks = build_group(is_short, short_key)
    if short_blocks:
        blocks.append('<section class="tl-group tl-short"><h2 class="group-h">短团</h2>'
                      '<p class="muted">与主线分开的短团，现实时间靠后、与主季不重叠。</p>'
                      '%s</section>' % "".join(short_blocks))
    return """<article class="timeline-page">
<nav class="crumbs"><a href="index.html">跑团首页</a> · 时间轴</nav>
<h1>时间轴</h1>
<p class="muted">按**现实时间**（跑团实际发生的时刻）排列，来自记录时间戳。
游戏内时间在原作里有意模糊，故此处不作为主轴。短团另列一组，见页面末尾。</p>
<div class="filters">
  <button data-filter="wl" data-value="">全部</button>
  <button data-filter="wl" data-value="main">主世界</button>
  <button data-filter="wl" data-value="multi">多层/其他</button>
  <button data-filter="wl" data-value="unk">未明</button>
  <button data-filter="" data-value="">清除</button>
</div>
%s
</article>""" % "".join(blocks)


def render_index(sess, seasons, whitelist_note):
    def card(s):
        items = [x for x in sess if x["season"] == s["name"]]
        ov = s.get("overview") or {}
        comp = ov.get("完整度", "")
        warn = "" if comp.startswith("**完整**") or comp.startswith("完整") else " warn"
        return ('<a class="season-card%s" href="season/%s.html">'
                '<h3>%s</h3>'
                '<p class="mono">%s</p>'
                '<p class="muted">%d 场 · %s 汉字 · 伏笔 %d 条</p>'
                '<p class="comp">%s</p></a>'
                % (warn, season_slug(s["name"]),
                   html.escape(group_label(s["name"])),
                   html.escape(ov.get("现实时间", "—")[:46]),
                   len(items), format(sum(x["hanzi"] for x in items), ","),
                   sum(len(x["hooks"]) for x in items),
                   md(comp[:150]).replace("<p>", "").replace("</p>", "") if comp else "—"))

    # 主线 12 季（作者指定顺序）
    main_cards = [card(s) for s in sorted(
        [x for x in seasons if not is_short(x["name"])],
        key=lambda x: season_key(x["name"]))]
    # 短团（作者 2026-10-14：单独归类，首页单列一块）
    short_ss = sorted([x for x in seasons if is_short(x["name"])],
                      key=lambda x: short_key(x["name"]))
    short_cards = [card(s) for s in short_ss]
    n_main_sess = sum(1 for x in sess if not is_short(x["season"]))
    n_short_sess = sum(1 for x in sess if is_short(x["season"]))
    short_block = ""
    if short_cards:
        short_block = (
            '<section id="shorts"><h2>短团</h2>'
            '<p class="muted">与主线<b>分开归类</b>的短团：现实时间靠后、与主季不重叠，'
            '每个短团同样有季志与场次卡。</p>'
            '<div class="season-grid short-grid">%s</div></section>'
            % "".join(short_cards))
    tot_h = sum(x["hanzi"] for x in sess)
    return f"""<article class="trpg-home">
<header class="hero">
  <h1>黑柩跑团Wiki</h1>
  <p class="sub">{html.escape(SITE['subtitle'])}</p>
  <p class="stats">主线 <strong>{len([x for x in seasons if not is_short(x['name'])])}</strong> 季
     + 短团 <strong>{len(short_ss)}</strong> 个 ·
     <strong>{len(sess)}</strong> 场（主线 {n_main_sess} / 短团 {n_short_sess}） ·
     <strong>{format(tot_h, ',')}</strong> 汉字 ·
     决策点 {sum(x['n_decisions'] for x in sess)} 条 ·
     骰点 {sum(x['n_dice'] for x in sess)} 条</p>
  <p class="muted">{html.escape(whitelist_note)}</p>
</header>
<section class="disc">
  <p>{html.escape(SITE['disclaimer'])}　另：本站整理自跑团记录，
  <strong>未经作者逐条核对</strong>；原作设定冲突（作者自称「吃书」）一律照录，不代为圆说。</p>
</section>
<section id="seasons"><h2>主线</h2><div class="season-grid">{''.join(main_cards)}</div></section>
{short_block}
<section><h2>怎么读</h2>
<ol class="howto">
  <li>先看 <strong>季志</strong>——本季概览、场次索引、季摘要、登场人物、势力动态、骰点统计、伏笔汇总。</li>
  <li>需要细节再翻同季的 <strong>场次卡</strong>——一场一张卡，12 个字段。</li>
  <li>按现实时间浏览用 <a href="timeline.html">时间轴</a>。</li>
  <li>名词（人物／组织／地名）会链到 <a href="../huaxu/index.html">花絮站</a> 的对应标签页。</li>
</ol></section>
<section><h2>已知缺口</h2>
<p class="muted">以下缺口来自原始记录本身，本站如实保留、不做补写：</p>
<ul class="gaps"><li>第二季：仅存开局 3 天，中段缺失</li>
<li>第三季：缺开局</li>
<li>第四季上：结局为 KP 口述、从未实跑</li>
<li>第五季：原始记录缺第 1~4 天，该段补自「准正式记录」、无现实时间戳</li>
<li>第六季：已按上游考证裁掉 2021-07-24 之前的他团内容</li>
<li>第八季：两处缺场次</li>
<li>九上／九下：相隔两年，不是连续接续</li>
<li>第七季起：大量检定只留 <code>ra 技能 目标值</code>、无出目，故部分场次骰点栏无法判定成败</li></ul>
</section>
</article>"""


# ══════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    sess = json.load(io.open(os.path.join(TRPG_SRC, "sessions.json"), encoding="utf-8"))
    seasons = json.load(io.open(os.path.join(TRPG_SRC, "seasons.json"), encoding="utf-8"))

    # 按作者指定顺序排列（季卡片、季导航、「各季」列表、时间轴共用）
    seasons.sort(key=lambda x: season_key(x["name"]))
    sess.sort(key=lambda x: (season_key(x["season"]), x["no"]))

    global SLUGS
    try:
        huaxu_tags = json.load(io.open(os.path.join(W, "data", "tags.json"),
                                       encoding="utf-8"))
        SLUGS = {t: m["slug"] for t, m in huaxu_tags["tags"].items()}
    except Exception:
        SLUGS = {}

    if args.clean and os.path.isdir(OUT):
        shutil.rmtree(OUT)

    note = load_whitelist()
    by_name = {s["name"]: s for s in seasons}
    n = 0

    # 各页
    for s in seasons:
        mine = [x for x in sess if x["season"] == s["name"]]
        n += write_if_changed(os.path.join(OUT, "season", "%s.html" % season_slug(s["name"])),
                              page(s["name"] + " · 季志",
                                   render_season(s, mine, seasons), rel="../"))
    for i, s in enumerate(sess):
        n += write_if_changed(os.path.join(OUT, "session", "%s.html" % session_slug(s)),
                              page("%s 第%d场" % (s["season"], s["no"]),
                                   render_session(s, i, sess, by_name), rel="../",
                                   body_class="session"))
    n += write_if_changed(os.path.join(OUT, "timeline.html"),
                          page("时间轴", render_timeline(sess, seasons), rel=""))
    n += write_if_changed(os.path.join(OUT, "index.html"),
                          page("跑团首页", render_index(sess, seasons, note), rel=""))

    # 搜索索引（复用花絮站的 app.js：需要 id/slug/title/kind/tags）
    search = {"entries": ([{"id": session_slug(s), "slug": "",
                            "title": "%s 第%d场" % (s["season"], s["no"]),
                            "kind": "场次",
                            "tags": [s["season"]]} for s in sess]
                          + [{"id": season_slug(s["name"]), "slug": "",
                              "title": s["name"] + " · 季志", "kind": "季志",
                              "tags": []} for s in seasons])}
    n += write_if_changed(os.path.join(OUT, "assets", "search.json"),
                          json.dumps(search, ensure_ascii=False))

    # 跑团特有的样式（共享 style.css 由 build_site 写在 docs/assets/）
    n += write_if_changed(os.path.join(OUT, "assets", "trpg.css"), TRPG_CSS)

    print(json.dumps({"station": "trpg", "written": n, "seasons": len(seasons),
                      "sessions": len(sess), "crosslink": note},
                     ensure_ascii=False))


TRPG_CSS = """/* 黑柩跑团 Wiki · 专有样式（共享样式见 ../assets/style.css） */
.nav-sep{width:1px;height:1.1em;background:var(--line);display:inline-block}
.nav-other{color:var(--accent)}
.hero{padding:1.6rem 0 .8rem}
.hero h1{font-size:1.7rem;margin:0 0 .3rem}
.hero .sub{color:var(--muted);margin:0 0 .6rem}
.hero .stats{margin:0 0 .3rem}
.disc{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);
border-radius:0 10px 10px 0;padding:.7rem .9rem;margin:1rem 0;font-size:.92rem}
.season-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(17rem,1fr));gap:.8rem}
.season-card{display:block;background:var(--card);border:1px solid var(--line);
border-radius:12px;padding:.8rem .9rem;color:var(--fg)}
.season-card:hover{border-color:var(--accent2);text-decoration:none}
.season-card.warn{border-left:3px solid #d98b2b}
.season-card h3{margin:0 0 .35rem;font-size:1.02rem}
.season-card p{margin:.15rem 0}
.season-card .comp{color:var(--muted);font-size:.82rem;
display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.season-card .mono{font-size:.82rem;color:var(--muted)}
.howto,.gaps{padding-left:1.2rem}
.howto li,.gaps li{margin:.25rem 0}
.toc{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:.7rem 1rem;margin:1rem 0}
.toc h2{margin:.1rem 0 .4rem;font-size:.95rem}
.toc ol{list-style:none;padding-left:0;margin:0;columns:2;column-gap:1.6rem}
@media(max-width:700px){.toc ol{columns:1}}
.toc li{margin:.1rem 0;font-size:.88rem}
.toc li.l2{padding-left:1.1rem;color:var(--muted)}
.sec,.field{margin:1.4rem 0;scroll-margin-top:3.8rem}
.sec h2,.field h2{font-size:1.1rem;border-bottom:1px solid var(--line);
padding-bottom:.25rem;margin-bottom:.5rem}
h2.plain{border:0;font-size:1rem}
.back{font-size:.8rem;margin:.4rem 0 0}
.back a{color:var(--muted)}
details.sub{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:.45rem .7rem;margin:.4rem 0}
details.sub>summary{cursor:pointer;font-weight:600;font-size:.94rem}
details.sub[open]>summary{margin-bottom:.4rem}
.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.9rem}
table th,table td{border:1px solid var(--line);padding:.35rem .5rem;text-align:left;
vertical-align:top}
table.kv th{width:8.5rem;color:var(--muted);font-weight:600;background:var(--bg)}
table.idx th{background:var(--bg);color:var(--muted)}
table.dice td:first-child{color:var(--muted)}
table.dice tr.ok td:last-child{color:#4f9d69}
table.dice tr.bad td:last-child{color:#c8553d}
.sess-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(13rem,1fr));
gap:.5rem;margin-top:.6rem}
.sess-card{display:flex;flex-direction:column;gap:.15rem;background:var(--card);
border:1px solid var(--line);border-radius:10px;padding:.5rem .6rem;color:var(--fg);
font-size:.88rem}
.sess-card:hover{border-color:var(--accent2);text-decoration:none}
.sess-card .mono{font-size:.78rem;color:var(--muted)}
.sess-card .muted{font-size:.76rem}
ol.dec,ul.hooks{padding-left:1.3rem}
ol.dec li,ul.hooks li{margin:.25rem 0}
.pn-nav{display:flex;justify-content:space-between;gap:.6rem;margin:1.6rem 0;
flex-wrap:wrap}
.pn{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:.5rem .8rem;font-size:.9rem}
.pn:hover{border-color:var(--accent2);text-decoration:none}
.season-grid.short-grid .season-card{border-left:3px solid var(--accent2)}
.tl-group{margin:1.4rem 0}
.tl-group .group-h{font-size:1.15rem;margin:.2rem 0 .6rem;padding-bottom:.3rem;
border-bottom:2px solid var(--line)}
.tl-group.tl-short .group-h{border-bottom-color:var(--accent2)}
.tl-group.tl-short{margin-top:2.2rem;padding-top:1rem;border-top:2px dashed var(--line)}
.season-nav{margin:2rem 0;padding-top:.8rem;border-top:1px solid var(--line)}
.season-nav h3{font-size:.95rem;color:var(--muted);margin:.2rem 0 .5rem}
.season-nav a{display:inline-block;margin:.15rem .3rem .15rem 0;padding:.2rem .6rem;
border:1px solid var(--line);border-radius:99px;font-size:.85rem}
.season-nav a.cur{border-color:var(--accent);color:var(--accent)}
.tl-season{margin:1.4rem 0}
.tl-season h2{font-size:1.05rem}
ul.timeline{list-style:none;padding:0;margin:.4rem 0}
li.tl-item{display:flex;gap:.7rem;align-items:baseline;padding:.3rem 0;
border-bottom:1px dashed var(--line);flex-wrap:wrap}
li.tl-item a{min-width:5.5rem}
.tl-time{flex:1;min-width:14rem}
.wl{font-size:.75rem;padding:.05rem .45rem;border-radius:99px;border:1px solid var(--line);
color:var(--muted)}
.wl-main{border-color:#4f9d69;color:#4f9d69}
.wl-multi{border-color:#7ea8c4;color:#7ea8c4}
.wl-unk{border-color:#d98b2b;color:#d98b2b}
.filters{display:flex;gap:.4rem;flex-wrap:wrap;margin:.6rem 0 1rem}
.filters button{cursor:pointer;background:var(--card);color:var(--fg);
border:1px solid var(--line);border-radius:99px;padding:.25rem .7rem;font-size:.85rem}
.filters button:hover{border-color:var(--accent2)}
a.xlink{border-bottom:1px dotted var(--accent2)}
/* 回到顶部：随滚动淡入（浏览器原生支持 href="#" 回顶，无需 JS） */
.to-top{position:fixed;right:1.1rem;bottom:1.1rem;z-index:30;
background:var(--card);border:1px solid var(--line);border-radius:99px;
padding:.45rem .9rem;font-size:.85rem;color:var(--fg);
opacity:0;pointer-events:none;transition:opacity .2s,transform .15s;
box-shadow:0 4px 18px #0003}
.to-top.show{opacity:.96;pointer-events:auto}
.to-top:hover{border-color:var(--accent2);text-decoration:none;transform:translateY(-2px)}
li.tl-item.hide{display:none}
"""


if __name__ == "__main__":
    main()
