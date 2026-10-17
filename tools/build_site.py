#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成静态站（幂等，可反复运行）。

产出目录：docs/（GitHub Pages 发布目录）
    docs/index.html                    首页：栏目 + 分类标签 + 轻量搜索
    docs/entry/<id>-<slug>.html        每篇一页
    docs/tag/<slug>.html               每个标签一页（服务端已排好，无需 JS）
    docs/assets/style.css
    docs/assets/app.js
    docs/assets/tags.json              客户端聚合数据（entry→tags / tag→entries）
    docs/assets/featured.json          首页栏目定义（无 featured.json 时自动降级）
    docs/.nojekyll

设计
----
* **服务端排好标签页**：SEO 与「禁用 JS 也能看」都成立。
* **客户端只做增量增强**：筛选、搜索、按层级切换。
* **幂等 + 增量**：`--only-changed` 用内容哈希跳过未变页面的重写。
* **相对链接**：站点可挂在任意子路径（GitHub Pages 的 /repo/ 也能用）。
"""
import argparse
import collections
import hashlib
import html
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import categories as catmod  # noqa: E402

W = common.W
DATA = common.DATA
# 花絮站挂在 /huaxu/ 下（作者 2026-10-14 决定：一个站点两个区）
# 用环境变量 DSH_SITE_PREFIX 可以让同一套代码输出到别的子目录（跑团站复用）
PREFIX = os.environ.get("DSH_SITE_PREFIX", "huaxu").strip("/")
SITE_ROOT = os.path.join(W, "docs")
DOCS = os.path.join(SITE_ROOT, PREFIX)
SITE = os.path.join(DATA, "site.json")

DEFAULT_SITE = {
    "title": "黑柩花絮 Wiki",
    "subtitle": "《黑柩》花絮、楔子与画外音的整理站",
    "description": "把《黑柩》的花絮按人物、组织、地理、主题与剧情线整理成可浏览的 wiki。",
    "base_url": "",
    # 免责声明：作者要求标注 AI 生成，提醒读者内容准确性无保证
    "disclaimer": "本网站由 AI 生成，内容准确性无法完全保证。",
}


def site_conf():
    if os.path.exists(SITE):
        c = json.load(open(SITE, encoding="utf-8"))
        return {**DEFAULT_SITE, **c}
    return dict(DEFAULT_SITE)


# ------------------------------------------------------------------ 模板
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


def page(title, body, rel, site, extra_head="", body_class="", rel_root=None,
         site_index=None):
    """rel_root：回**本站根**（docs/huaxu/）的相对前缀。

    条目页在 entry/ 下 → "../"；tag/cat 页也在子目录下 → "../"；首页 → ""。
    搜索结果的 href 是 rel_root + e.id，索引路径是 rel_root + site_index。
    `site_index` 必须写成**相对本站根**的路径。
    """
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title) if title != site['title'] else ''}{' · ' if title != site['title'] else ''}{html.escape(site['title'])}</title>
<meta name="description" content="{html.escape(site['description'])}">
{extra_head}<link rel="icon" type="image/png" href="{rel}../assets/icon.png">
<link rel="apple-touch-icon" href="{rel}../assets/icon.png">
<link rel="stylesheet" href="{rel}../assets/style.css">
</head>
<body class="{body_class}">
<header class="site-head">
  <a class="brand" href="{rel}index.html">{html.escape(site['title'])}</a>
  <nav class="site-nav">
    <a href="{rel}index.html">本站首页</a>
    <a href="{rel}index.html#tags">全部标签</a>
    <span class="nav-sep"></span>
    <a class="nav-other" href="{rel}../trpg/index.html" title="切换到跑团站">跑团站 →</a>
    <a class="nav-other" href="{rel}../lore/index.html" title="切换到设定站">设定站 →</a>
    <a class="nav-other" href="{rel}../report/index.html" title="切换到分析站">分析站 →</a>
    <a class="nav-other" href="{rel}../index.html" title="三站入口">联合首页</a>
  </nav>
  <div class="search-wrap">
    <input id="q" type="search" placeholder="搜索标题或标签…" autocomplete="off" aria-label="搜索">
    <div id="q-results" class="q-results" hidden></div>
  </div>
</header>
<main>
{body}
</main>
<footer class="site-foot">
  <p class="disclaimer">{html.escape(site.get('disclaimer', '本网站由 AI 生成，内容准确性无法完全保证。'))}</p>
  <p>本站为《黑柩》花絮的整理与索引，内容版权归原作者所有。</p>
  <p class="muted">静态站 · 由 <code>tools/build_site.py</code> 生成</p>
<p class="friend-links">友情链接：{friend_links_html(site)}</p>
</footer>
<a class="to-top" href="#" id="to-top" title="回到顶部" aria-label="回到顶部">↑ 顶部</a>
<script>window.SITE_REL = {json.dumps(rel_root)};{('window.SITE_INDEX = ' + json.dumps(site_index) + ';') if site_index else ''}</script>
<script src="{rel}../assets/app.js" defer></script>
</body>
</html>
"""


DIM_COLOR_ORDER = ["文类", "叙事层级", "人物", "组织", "地理", "设施",
                   "剧情线", "主题", "事件类型", "关系", "主题词", "时间", "篇幅"]

# 层级说明条：作者 2026-10-14 修定的定义
LAYER_NOTE = {
    "平行世界线": "本页属<strong>平行世界线</strong>，非正史。",
    "未来可能": "本页为<strong>楔子</strong>：内容是未来可能发生的事情，"
                "或已经发生并为未来做铺垫的事情。",
    "已发生": "",
}


def tag_dims(meta, t):
    """取标签的维度列表（兼容旧的单值 dimension 字段）。"""
    m = meta.get(t) or {}
    d = m.get("dimensions")
    if isinstance(d, list) and d:
        return d
    one = m.get("dimension")
    return [one] if one else ["未分类"]


def color_dim(meta, t):
    """多维度标签在页面上用哪个颜色：按 DIM_COLOR_ORDER 取第一个可用的。"""
    ds = tag_dims(meta, t)
    for d in DIM_COLOR_ORDER:
        if d in ds:
            return d
    return ds[0]


GRADE_CLASS = {"红": "g-red", "橙": "g-orange", "蓝": "g-blue"}
GRADE_LABEL = {"红": "高相关", "橙": "中相关", "蓝": "低相关"}


def chips(tags, meta, rel, primary=(), grades=None, sort_by_grade=True):
    """标签胶囊。实体类标签会按「相关性等级」着色，并按 红→橙→蓝 排序。

    grades: {标签: "红"/"橙"/"蓝"}（来自 tags.json 的每篇等级）
    """
    grades = grades or {}
    order = {"红": 0, "橙": 1, "蓝": 2}

    def gkey(t):
        # 主序：等级（红→橙→蓝）；次序：标签名（确定性、便于查找）
        return (order.get(grades.get(t), 3), t)

    seq = sorted(tags, key=gkey) if sort_by_grade else list(tags)
    out = []
    for t in seq:
        ds = tag_dims(meta, t)
        g = grades.get(t)
        cls = "chip chip-%s%s" % (slugcls(color_dim(meta, t)),
                                  " chip-primary" if t in primary else "")
        title = "、".join(ds)
        if len(ds) > 1:
            cls += " chip-multi"
        if g:
            cls += " " + GRADE_CLASS.get(g, "")
            title = "%s（%s）" % (title, GRADE_LABEL.get(g, g))
        mark = ""
        if len(ds) > 1:
            mark += '<span class="multi-mark" title="跨维度标签">⋈</span>'
        if g:
            mark += '<span class="grade-dot %s" title="%s"></span>' % (
                GRADE_CLASS.get(g, ""), GRADE_LABEL.get(g, g))
        out.append('<a class="%s" href="%stag/%s.html" title="%s">%s%s</a>'
                   % (cls, rel, meta[t]["slug"], html.escape(title),
                      html.escape(t), mark))
    return "".join(out)


def slugcls(dim):
    return {"文类": "kind", "叙事层级": "layer", "人物": "person",
            "组织": "org", "地理": "place", "设施": "facility",
            "剧情线": "series", "主题": "theme", "事件类型": "event",
            "关系": "relation", "主题词": "tone", "时间": "time",
            "篇幅": "length"}.get(dim, "misc")


# ------------------------------------------------------------------ 数据
def load_data():
    tags_path = os.path.join(DATA, "tags.json")
    if not os.path.exists(tags_path):
        sys.exit("缺少 data/tags.json，请先运行 tools/tag_entries.py")
    data = json.load(open(tags_path, encoding="utf-8"))
    entries = common.load_entries()
    by_id = {e["id"]: e for e in entries}
    return data, by_id


def featured_conf():
    p = os.path.join(DATA, "featured.json")
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return None


def subcat_conf():
    """子分类定义（可选）。见 data/subcategories.json。"""
    p = os.path.join(DATA, "subcategories.json")
    if not os.path.exists(p):
        return {}
    d = json.load(open(p, encoding="utf-8"))
    out = {}
    for dim, groups in (d.get("dimensions") or {}).items():
        out[dim] = [{"name": g["name"], "tags": list(g.get("tags") or []),
                     "source": g.get("source", "")}
                    for g in groups]
    return out


def auto_featured(data, top_n=8, min_doc=6):
    """没有 featured.json 时的降级：按篇数自动取热门标签做栏目。"""
    idx = data["tag_index"]
    meta = data["tags"]
    pool = [(len(v), t) for t, v in idx.items()
            if meta[t]["dimension"] in ("人物", "组织", "地理", "剧情线", "主题")
            and len(v) >= min_doc]
    pool.sort(reverse=True)
    cols = []
    for n, t in pool[:top_n]:
        cols.append({"tag": t, "title": t, "blurb": "共 %d 篇相关花絮。" % n,
                     "dimension": meta[t]["dimension"], "auto": True})
    return {"columns": cols, "auto": True}


# ------------------------------------------------------------------ 构建
def render_entries(data, by_id, site, tag_to_cat=None):
    n_written = 0
    tag_to_cat = tag_to_cat or {}
    for e in data["entries"]:
        eid = e["id"]
        rec = by_id[eid]
        slug = common.slugify(rec["fm"].get("title", rec["title"]))
        fn = "%s-%s.html" % (eid, slug)
        rel = "../"
        meta = data["tags"]

        # 页内目录（超过 4000 字才生成）
        body_html = common.body_to_html(rec["body"])
        toc = ""
        heads = re.findall(r"<h[3-6]>(.*?)</h[3-6]>", body_html)
        if len(rec["body"]) > 4000 and len(heads) >= 3:
            items = "".join('<li><a href="#h%d">%s</a></li>' % (i, h)
                            for i, h in enumerate(heads))
            toc = '<nav class="toc"><strong>本页目录</strong><ol>%s</ol></nav>' % items

        layer = next((t for t in e["tags"]
                      if "叙事层级" in tag_dims(meta, t)), "")
        banner = ""
        note = LAYER_NOTE.get(layer, "")
        if note:
            cls = "banner banner-alt" if layer == "平行世界线" else "banner banner-future"
            banner = '<div class="%s">%s</div>' % (cls, note)

        prev_next = prev_next_links(data, eid)
        body = f"""<article class="entry">
{banner}
<header class="entry-head">
  <p class="crumbs"><a href="{rel}index.html">首页</a> · {html.escape(e['collection'])}</p>
  <h1>{html.escape(rec['title'])}</h1>
  <p class="meta">{html.escape(e['kind'])} · {e['chars']} 字 · {html.escape(e['origin'])}
      · <span class="mono">{eid}</span></p>
  <div class="chips">{chips(e['tags'], meta, rel, e['primary'], e.get('grades'))}</div>
  {catmod.chips(eid, e['tags'], None, tag_to_cat, rel)}
</header>
{toc}
<div class="prose">
{body_html}
</div>
<footer class="entry-foot">
  <p class="muted">标签：{'、'.join(e['tags'])}</p>
  <nav class="pn">{prev_next}</nav>
</footer>
</article>"""
        title = rec["title"]
        # 条目页在 entry/ 下 → 回本站根的相对前缀是 rel + "../"
        # rel_root 是「相对**页面自己**」的前缀：条目页在 entry/ 下 → "../"
        # （注意：不能写成 rel + "../" —— rel 是「相对 docs/」，两者不是一回事）
        # 索引在共享 docs/assets/ → 相对页面是 "../../assets/search.json"
        # 花絮站的索引在共享 docs/assets/ 里 → 不输出 SITE_INDEX，用 app.js 的回退分支
        out = page(title, body, rel, site, body_class="entry-page",
                   rel_root="../")
        n_written += write_if_changed(os.path.join(DOCS, "entry", fn), out)
    return n_written


def prev_next_links(data, eid):
    ids = [e["id"] for e in data["entries"]]
    i = ids.index(eid)
    out = []
    if i > 0:
        p = data["entries"][i - 1]
        out.append('<a class="prev" href="%s-%s.html">← %s</a>'
                   % (p["id"], common.slugify(p["title"]), html.escape(p["title"])))
    if i < len(ids) - 1:
        n = data["entries"][i + 1]
        out.append('<a class="next" href="%s-%s.html">%s →</a>'
                   % (n["id"], common.slugify(n["title"]), html.escape(n["title"])))
    return "".join(out)


def render_tags(data, by_id, site, min_doc=2):
    meta = data["tags"]
    idx = data["tag_index"]
    n = 0
    for t, ids in idx.items():
        m = meta[t]
        # 只出现 1 篇的标签页很薄：仍然生成（保证「每个标签都可点」这条承诺成立），
        # 但加 noindex，避免薄页进搜索引擎。
        thin = len(ids) < min_doc
        extra = ('<meta name="robots" content="noindex,follow">\n' if thin else "")
        rows = []
        # 相关性降序：本篇里该标签的权重越大＝越相关（等级也是由它派生的）
        _byid = {x["id"]: x for x in data["entries"]}
        _sorted_ids = sorted(ids, key=lambda i: (-_byid[i]["weights"].get(t, 0), i))
        for eid in _sorted_ids:
            e = next(x for x in data["entries"] if x["id"] == eid)
            _e = _byid[eid]
            _g = (_e.get("grades") or {}).get(t)
            rows.append('<li data-id="%s" data-kind="%s" data-layer="%s">'
                        '<a href="../entry/%s-%s.html">%s</a>'
                        '<span class="muted">%s · %d 字 · %s%s</span></li>'
                        % (eid, _e["kind"], layer_of(_e, meta), eid,
                           common.slugify(_e["title"]), html.escape(_e["title"]),
                           html.escape(_e["kind"]), _e["chars"], eid,
                           (' <span class="grade-dot %s" title="%s"></span>'
                            % (GRADE_CLASS.get(_g, ""), GRADE_LABEL.get(_g, _g)))
                           if _g else ""))
        related = []
        for t2 in sorted(idx, key=lambda x: -len(set(idx[x]) & set(ids))):
            if t2 == t:
                continue
            ov = len(set(idx[t2]) & set(ids))
            if ov >= 3:
                related.append((ov, t2))
            if len(related) >= 12:
                break
        rel_html = "".join('<a class="chip chip-%s" href="%s.html">%s <b>%d</b></a>'
                           % (slugcls(color_dim(meta, t2)), meta[t2]["slug"], t2, ov)
                           for ov, t2 in related)
        dims = tag_dims(meta, t)
        if t == "楔子":
            dim_note = ('<p class="dim-note">楔子 = 未来可能发生的事情，'
                        '或已经发生并为未来做铺垫的事情。</p>')
        elif len(dims) > 1:
            dim_note = ('<p class="dim-note">跨维度标签：本标签同时属于 '
                        '<strong>%s</strong>。同一标签在不同视角下身份不同，'
                        '这不是重复收录。</p>' % "、".join(dims))
        else:
            dim_note = ""
        body = f"""<section class="tag-page">
<header class="tag-head">
  <p class="crumbs"><a href="../index.html">首页</a> · {html.escape("、".join(dims))}</p>
  <h1>{html.escape(t)}</h1>
  <p class="meta">{len(ids)} 篇{(' · 词表内出现于 %d 篇' % m['doc_freq']) if m.get('doc_freq') else ''}</p>
  {dim_note}
</header>
<nav class="filters">
  <span>筛选：</span>
  <button data-filter="kind" data-value="">全部类型</button>
  <button data-filter="layer" data-value="已发生">已发生</button>
  <button data-filter="layer" data-value="未来可能">未来可能</button>
  <button data-filter="layer" data-value="平行世界线">平行世界线</button>
</nav>
<ul class="entry-list">
{''.join(rows)}
</ul>
{('<div class="related"><h2>相关标签</h2><div class="chips">%s</div></div>' % rel_html) if rel_html else ''}
</section>"""
        n += write_if_changed(os.path.join(DOCS, "tag", "%s.html" % m["slug"]),
                              page(t, body, "../", site, extra_head=extra,
                                   body_class="tag-detail", rel_root="../"))
    return n


def layer_of(e, meta):
    for t in e["tags"]:
        if meta[t]["dimension"] == "叙事层级":
            return t
    return ""


def render_index(data, by_id, site, featured, subcats=None, cat_index=None):
    meta = data["tags"]
    idx = data["tag_index"]
    dim_order = data.get("tag_order", [])
    subcats = subcats or {}
    cat_index = cat_index or []
    cat_by_key = {(c["dim"], c["name"]): c for c in cat_index}
    # 每个标签在全集的「典型等级」：出现最多的档，平手取更高的档（首页标签墙染色用）
    _ord = {"红": 0, "橙": 1, "蓝": 2}
    tag_grade = {}
    for _t in meta:
        _cnt = collections.Counter(
            (e.get("grades") or {}).get(_t) for e in data["entries"]
            if (e.get("grades") or {}).get(_t))
        if _cnt:
            tag_grade[_t] = sorted(_cnt.items(), key=lambda kv: (-kv[1], _ord[kv[0]]))[0][0]

    # 栏目
    cols = []
    for c in featured.get("columns", []):
        t = c["tag"]
        if t not in idx:
            continue
        _all = idx[t]
        # 相关性降序：该栏目标签在篇内的权重越大＝越相关
        _w = {e["id"]: e.get("weights", {}) for e in data["entries"]}
        _rank = sorted(_all, key=lambda i: (-_w.get(i, {}).get(t, 0), i))
        picks = c.get("picks") or _rank
        picks = picks[: c.get("limit", 6)]
        rows = "".join(
            '<li><a href="entry/%s-%s.html">%s</a><span class="muted">%d 字</span></li>'
            % (pid, common.slugify(by_id[pid]["title"]),
               html.escape(by_id[pid]["title"]), by_id[pid]["chars"])
            for pid in picks if pid in by_id)
        cols.append(f"""<section class="col">
  <h2><a href="tag/{meta[t]['slug']}.html">{html.escape(c.get('title', t))}</a></h2>
  <p class="blurb">{html.escape(c.get('blurb', ''))}</p>
  <ul class="col-list">{rows}</ul>
  <p class="more"><a href="tag/{meta[t]['slug']}.html">全部 {len(idx[t])} 篇 →</a></p>
</section>""")

    # 全部标签，按维度分组（跨维度标签在它所属的每个维度下都会出现，带 ⋈ 标记）
    groups = collections.defaultdict(list)
    for t, ids in idx.items():
        for d in tag_dims(meta, t):
            groups[d].append((len(ids), t))
    group_html = []
    for d in [x for x in dim_order if x in groups] + sorted(set(groups) - set(dim_order)):
        lst = sorted(groups[d], reverse=True, key=lambda r: (r[0], r[1]))

        def chip_for(n, t):
            ds = tag_dims(meta, t)
            multi = len(ds) > 1
            g = tag_grade.get(t)
            gc = (" g-" + {"红": "red", "橙": "orange", "蓝": "blue"}[g]) if g else ""
            title = "、".join(ds) + (("（%s）" % GRADE_LABEL[g]) if g else "")
            dot = ('<span class="grade-dot g-%s"></span>' % {"红": "red", "橙": "orange", "蓝": "blue"}[g]) if g else ""
            return ('<a class="chip chip-%s%s%s" href="tag/%s.html" title="%s">%s<b>%d</b>%s%s</a>'
                    % (slugcls(color_dim(meta, t)), " chip-multi" if multi else "", gc,
                       meta[t]["slug"], html.escape(title), html.escape(t), n,
                       '<span class="multi-mark">⋈</span>' if multi else "", dot))

        # 有子分类定义就按子分类折叠；否则平铺
        if d in subcats:
            assigned = set()
            sub_html = []
            for g in subcats[d]:
                members = [(len(idx[t]), t) for t in g["tags"] if t in idx and d in tag_dims(meta, t)]
                if not members:
                    continue
                members.sort(reverse=True, key=lambda r: (r[0], r[1]))
                assigned.update(t for _, t in members)
                c = cat_by_key.get((d, g["name"]))
                title = ('<a href="%s">%s</a>' % (c["url"], html.escape(g["name"]))
                         if c else html.escape(g["name"]))
                cnt = ('<span class="muted">%d 个标签 · %d 篇</span>'
                       % (len(members), len(c["entries"])) if c
                       else '<span class="muted">%d</span>' % len(members))
                # 作者 2026-10-14：子分类**默认全部展开**，方便读者一眼看到内容量
                open_attr = ' open'
                sub_html.append(
                    '<details class="subcat"%s><summary><h4>%s<span class="sub-link">'
                    '查看该分类 →</span>%s</h4></summary>'
                    '<div class="chips">%s</div></details>'
                    % (open_attr, title, cnt,
                       "".join(chip_for(n, t) for n, t in members)))
            rest = [(n, t) for n, t in lst if t not in assigned]
            if rest:
                sub_html.append(
                    '<div class="subcat subcat-rest"><h4>未分类<span class="muted">%d</span></h4>'
                    '<div class="chips">%s</div></div>'
                    % (len(rest), "".join(chip_for(n, t) for n, t in rest)))
            # 维度层也默认展开
            group_html.append(
                '<details class="tag-group" open><summary><h3>%s<span class="muted">%d</span>'
                '<span class="sub-hint">%d 个子分类</span></h3></summary>%s</details>'
                % (html.escape(d), len(lst),
                   len([x for x in sub_html]), "".join(sub_html)))
        else:
            chips_html = "".join(chip_for(n, t) for n, t in lst)
            group_html.append('<div class="tag-group"><h3>%s<span class="muted">%d</span>'
                              '%s</h3><div class="chips">%s</div></div>'
                              % (html.escape(d), len(lst),
                                 '<span class="sub-hint">可加子分类（见 data/subcategories.json）</span>'
                                 if len(lst) >= 20 else "", chips_html))

    stat_kinds = collections.Counter(e["kind"] for e in data["entries"])
    layers = collections.Counter(layer_of(e, meta) for e in data["entries"])
    stat = "　".join("%s %d" % (k, v) for k, v in stat_kinds.most_common())
    layer_stat = "　".join("%s %d" % (k, v) for k, v in layers.most_common() if k)
    multi_tags = data.get("multi_dimension_tags") or []
    # 分类总览：把 26 个子分类做成可点入口
    cat_html = ""
    if cat_index:
        by_dim = collections.defaultdict(list)
        for c in cat_index:
            by_dim[c["dim"]].append(c)
        blocks = []
        for d in [x for x in dim_order if x in by_dim] + sorted(set(by_dim) - set(dim_order)):
            links = "".join(
                '<a class="chip chip-cat" href="%s">%s<b>%d</b></a>'
                % (c["url"], html.escape(c["name"]), len(c["entries"]))
                for c in sorted(by_dim[d], key=lambda c: -len(c["entries"])))
            blocks.append('<div class="tag-group"><h3>%s<span class="muted">%d 个分类</span></h3>'
                          '<div class="chips">%s</div></div>' % (html.escape(d), len(by_dim[d]), links))
        cat_html = ('<section id="cats" class="all-tags"><h2>分类浏览</h2>'
                    '<p class="muted">子分类也是可点的入口——点进去看该组所有标签下的篇目。'
                    '归类定义见 <code>data/subcategories.json</code>。</p>'
                    + "".join(blocks) + "</section>")
    multi_html = ""
    if multi_tags:
        multi_html = ('<div class="multi-box"><h3>跨维度标签（⋈）<span class="muted">%d</span></h3>'
                      '<p class="muted">同一个标签可以同时属于多个维度——'
                      '比如「长歌」既是文类也是剧情线，「日本街」既是地理也是剧情线。'
                      '下面这些标签在它所属的每个维度下都会出现。</p><div class="chips">%s</div></div>'
                      % (len(multi_tags),
                         "".join('<a class="chip chip-%s chip-multi" href="tag/%s.html">%s'
                                 '<span class="multi-mark">⋈</span><b>%d</b></a>'
                                 % (slugcls(color_dim(meta, t)), meta[t]["slug"],
                                    html.escape(t), len(idx[t])) for t in multi_tags)))

    body = f"""<section class="hero">
  <h1>{html.escape(site['title'])}</h1>
  <p class="lead">{html.escape(site['subtitle'])}</p>
  <p class="stats">共 <strong>{data['entry_count']}</strong> 篇 · <strong>{data['tag_count']}</strong> 个标签<br>
     <span class="muted">{stat}</span><br><span class="muted">{layer_stat}</span></p>
  <div class="quick">
    <button data-quick="已发生">只看已发生</button>
    <button data-quick="未来可能">只看楔子（未来可能）</button>
    <button data-quick="平行世界线">只看画外音（平行世界线）</button>
    <button data-quick="">全部</button>
  </div>
  <p class="ai-note">{html.escape(site.get('disclaimer', '本网站由 AI 生成，内容准确性无法完全保证。'))}</p>
</section>

<section class="cols">
{''.join(cols) if cols else '<p class="muted">尚未定义首页。请在 data/featured.json 中配置栏目。</p>'}
</section>

<section id="tags" class="all-tags">
  <h2>全部标签</h2>
  <p class="muted">共 {data['tag_count']} 个标签，按维度分组；数字为该标签下的篇数。
     带 <span class="multi-mark">⋈</span> 的标签属于多个维度，会在每个维度下都出现。</p>
  <div class="grade-legend">
    <b>标签与文章的相关性</b>
    <span><i style="background:var(--g-red)"></i>红 · 高相关：全篇围绕它展开</span>
    <span><i style="background:var(--g-orange)"></i>橙 · 中相关：重要参与</span>
    <span><i style="background:var(--g-blue)"></i>蓝 · 低相关：顺带提及</span>
    <span>由频次、篇内占比、篇内排名与发言次数算出（只对人物／组织／地理／设施／剧情线）。
    点开标签后，文章按相关性从高到低排列。</span>
  </div>
  {multi_html}
  {''.join(group_html)}
</section>

{cat_html}

<section class="latest">
  <h2>全部条目</h2>
  <ul id="all-entries" class="entry-list">
  {''.join('<li data-id="%s" data-kind="%s" data-layer="%s"><a href="entry/%s-%s.html">%s</a><span class="muted">%s · %d 字 · %s</span></li>' % (e['id'], e['kind'], layer_of(e, meta), e['id'], common.slugify(e['title']), html.escape(e['title']), html.escape(e['kind']), e['chars'], e['id']) for e in data['entries'])}
  </ul>
</section>"""
    return page(site["title"], body, "", site, body_class="home", rel_root="")


# ------------------------------------------------------------------ 资源
CSS = """/* 黑柩花絮 Wiki */
:root{--bg:#14161a;--fg:#e8e6e3;--muted:#9aa0a6;--line:#2a2e35;--card:#1b1f25;
--accent:#c8553d;--accent2:#7ea8c4;--kind:#8f6f9e;--person:#c8553d;--org:#c9a227;
--place:#4f9d69;--series:#7ea8c4;--theme:#b06fa8;--event:#d2694a;--tone:#a58b57;}
@media (prefers-color-scheme:light){:root{--bg:#faf9f7;--fg:#1e1f22;--muted:#666;
--line:#e2ded8;--card:#fff;--accent:#a83b25;--accent2:#3f6f92;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.75 -apple-system,"Segoe UI","Noto Sans SC","Microsoft YaHei",sans-serif}
a{color:var(--accent2);text-decoration:none}
a:hover{text-decoration:underline}
.muted{color:var(--muted);font-size:.88em}
.mono{font-family:ui-monospace,Consolas,monospace;font-size:.9em;color:var(--muted)}
code{background:var(--card);padding:.1em .35em;border-radius:4px;font-size:.9em}
.site-head{display:flex;gap:1rem;align-items:center;flex-wrap:wrap;
padding:.7rem 1.2rem;border-bottom:1px solid var(--line);background:var(--card);
position:sticky;top:0;z-index:20}
.brand{font-weight:700;font-size:1.1rem;color:var(--fg)}
.site-nav{display:flex;gap:.9rem;font-size:.92rem}
.search-wrap{position:relative;margin-left:auto}
#q{padding:.45rem .7rem;border:1px solid var(--line);border-radius:8px;
background:var(--bg);color:var(--fg);min-width:15rem}
.q-results{position:absolute;right:0;top:110%;background:var(--card);border:1px solid var(--line);
border-radius:10px;min-width:22rem;max-height:60vh;overflow:auto;box-shadow:0 8px 30px #0006}
.q-results a{display:block;padding:.5rem .8rem;border-bottom:1px solid var(--line);color:var(--fg)}
.q-results a:hover{background:var(--bg);text-decoration:none}
main{max-width:56rem;margin:0 auto;padding:1.5rem 1.2rem 4rem}
.hero h1{font-size:1.9rem;margin:.2rem 0 .3rem}
.lead{color:var(--muted);margin:.2rem 0 1rem}
.stats{margin:.4rem 0 1rem}
.quick{display:flex;gap:.5rem;flex-wrap:wrap}
button{cursor:pointer;background:var(--card);color:var(--fg);border:1px solid var(--line);
border-radius:8px;padding:.35rem .7rem;font-size:.9rem}
button:hover{border-color:var(--accent2)}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(17rem,1fr));gap:1rem;margin:2rem 0}
.col{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:1rem 1.1rem}
.col h2{margin:.1rem 0 .4rem;font-size:1.1rem}
.col h2 a{color:var(--fg)}
.blurb{color:var(--muted);font-size:.9rem;margin:.2rem 0 .6rem}
.col-list{list-style:none;padding:0;margin:0}
.col-list li{display:flex;justify-content:space-between;gap:.6rem;
padding:.22rem 0;border-bottom:1px dotted var(--line);font-size:.94rem}
.more{margin:.7rem 0 0;font-size:.9rem}
.all-tags{margin-top:2.5rem}
.tag-group{margin:1rem 0 1.4rem}
.tag-group h3{font-size:1rem;margin:.4rem 0;display:flex;gap:.6rem;align-items:baseline}
.chips{display:flex;flex-wrap:wrap;gap:.4rem}
.chip{display:inline-flex;align-items:center;gap:.3rem;padding:.16rem .55rem;border-radius:999px;
border:1px solid var(--line);background:var(--card);color:var(--fg);font-size:.85rem}
.chip b{color:var(--muted);font-weight:500;font-size:.85em}
.chip:hover{border-color:var(--accent2);text-decoration:none}
.chip-primary{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent)}
.chip-kind{border-left:3px solid var(--kind)}.chip-person{border-left:3px solid var(--person)}
.chip-org{border-left:3px solid var(--org)}.chip-place{border-left:3px solid var(--place)}
.chip-series{border-left:3px solid var(--series)}.chip-theme{border-left:3px solid var(--theme)}
.chip-event{border-left:3px solid var(--event)}.chip-tone{border-left:3px solid var(--tone)}
.chip-layer,.chip-length,.chip-misc{border-left:3px solid var(--line)}
.chip-multi{box-shadow:inset 0 -2px 0 -1px var(--accent2)}
.multi-mark{color:var(--accent2);font-size:.85em;margin-left:.15em}
.multi-box{border:1px dashed var(--line);border-radius:12px;padding:.8rem 1rem;margin:1rem 0}
.multi-box h3{margin:.1rem 0 .3rem;font-size:.98rem;display:flex;gap:.6rem;align-items:baseline}
.tag-group>summary{cursor:pointer;list-style:none}
.tag-group>summary::-webkit-details-marker{display:none}
.tag-group>summary h3{display:inline-flex;margin:.4rem 0}
.tag-group>summary::before{content:"▸";color:var(--muted);display:inline-block;
width:1rem}
details[open]>summary::before{content:"▾"}
.sub-hint{color:var(--muted);font-size:.8em;font-weight:400;margin-left:.6rem}
.subcat{margin:.5rem 0 .8rem;padding-left:.9rem;border-left:2px solid var(--line)}
.subcat h4{margin:.3rem 0 .35rem;font-size:.92rem;font-weight:600;display:flex;gap:.6rem;
align-items:baseline}
.subcat h4 .muted{font-weight:400}
.subcat-rest{border-left-style:dashed;opacity:.85}
.subcat>summary{cursor:pointer;list-style:none}
.subcat>summary::-webkit-details-marker{display:none}
.subcat>summary::before{content:"▸";color:var(--muted);display:inline-block;width:.9rem}
.subcat[open]>summary::before{content:"▾"}
.sub-link{color:var(--accent2);font-size:.78em;font-weight:400;margin-left:auto}
.chip-cat{border-left:3px solid var(--accent2)}
/* 标签↔文章 相关性等级（乙方案：确定性公式）：红 > 橙 > 蓝 */
:root{--g-red:#c8553d;--g-orange:#d98b2b;--g-blue:#5b7f95}
.chip.g-red{border-color:var(--g-red)}
.chip.g-orange{border-color:var(--g-orange)}
.chip.g-blue{border-color:var(--g-blue);opacity:.92}
.grade-dot{display:inline-block;width:.5em;height:.5em;border-radius:50%;
margin-left:.3em;vertical-align:middle;background:var(--muted)}
.grade-dot.g-red{background:var(--g-red)}
.grade-dot.g-orange{background:var(--g-orange)}
.grade-dot.g-blue{background:var(--g-blue)}
.grade-legend{display:flex;gap:.9rem 1.2rem;flex-wrap:wrap;align-items:center;
background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:.55rem .85rem;margin:.9rem 0;font-size:.85rem;color:var(--muted)}
.grade-legend b{color:var(--fg);font-weight:600}
.grade-legend i{display:inline-block;width:.6em;height:.6em;border-radius:50%;
margin-right:.32em;vertical-align:middle}
.cats{margin:.5rem 0 0;font-size:.88rem;color:var(--muted);display:flex;gap:.4rem;
flex-wrap:wrap;align-items:center}
.dim-note{background:var(--card);border-left:3px solid var(--accent2);padding:.5rem .8rem;
border-radius:0 8px 8px 0;font-size:.9rem;color:var(--muted);margin:.6rem 0 0}
.entry-list{list-style:none;padding:0;margin:.8rem 0}
.entry-list li{display:flex;justify-content:space-between;gap:1rem;align-items:baseline;
padding:.45rem .2rem;border-bottom:1px solid var(--line)}
.entry-list li.hide{display:none}
.entry-head h1{font-size:1.6rem;margin:.2rem 0 .5rem;line-height:1.35}
.crumbs{color:var(--muted);font-size:.88rem;margin:0}
.meta{color:var(--muted);font-size:.9rem;margin:.2rem 0 .7rem}
.banner{border-left:4px solid var(--accent2);background:var(--card);padding:.6rem .9rem;
border-radius:0 8px 8px 0;margin:0 0 1rem;font-size:.94rem}
.banner-alt{border-left-color:var(--theme)}
.banner-future{border-left-color:var(--org)}
.prose{margin-top:1.4rem}
.prose p{margin:0 0 1.05em;text-align:justify}
.prose h3,.prose h4{margin:1.6em 0 .6em}
.prose blockquote{margin:1em 0;padding:.4em 1em;border-left:3px solid var(--line);color:var(--muted)}
.toc{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:.7rem 1rem;margin:1rem 0}
.toc ol{margin:.4rem 0 0;padding-left:1.2rem}
.toc a{color:var(--fg)}
.entry-foot{margin-top:2rem;border-top:1px solid var(--line);padding-top:1rem}
.pn{display:flex;justify-content:space-between;gap:1rem;margin-top:.6rem}
.filters{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;margin:1rem 0}
.filters button[aria-pressed=true]{border-color:var(--accent);color:var(--accent)}
.related{margin-top:2.5rem}
.site-foot{border-top:1px solid var(--line);padding:1.2rem;text-align:center;color:var(--muted);
font-size:.85rem}
.friend-links{margin:.35rem 0 0;font-size:.86rem}
.friend-links a{color:var(--accent2)}
.disclaimer{color:var(--accent);font-weight:600;margin:0 0 .4rem}
.ai-note{margin:.9rem 0 0;padding:.5rem .8rem;border-left:3px solid var(--accent);
background:var(--card);border-radius:0 8px 8px 0;color:var(--muted);font-size:.88rem}
/* ── 移动端顶栏：品牌与搜索框同一行，导航落下面 ──────────────────────
   旧版是 display:flex;flex-wrap:wrap，于是「品牌 / 导航 / 搜索框」各占一段：
   品牌一行、导航被挤成 2~3 行、搜索框又单独占一行，顶栏能吃掉约 290px。
   （.site-nav 原本没有 flex-wrap，小屏上链接还会被直接裁掉。）
   这里小屏改用 CSS Grid：品牌和搜索框共占第一行，导航整齐落到第二行。
   大屏（>1024px）完全走原来的 flex 布局，不受影响。
   （断点的取法：原版单行需要「品牌130 + 导航620 + 间距32 + 搜索框200 ≈ 980px」，
     所以 <1000px 时搜索框必然掉到第三行。取 1024 后，1024 及以下一律用紧凑两行版式，
     1025 以上才回原版——避免出现「品牌+导航一行、搜索框又一行」的三行乱版。） */
@media (max-width: 1024px){
  .site-head{
    display:grid;
    grid-template-columns:minmax(0,1fr) auto;
    align-items:center;
    gap:.45rem .7rem;
    padding:.55rem .9rem;
  }
  .site-head > .brand{
    grid-column:1;grid-row:1;
    min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  }
  .site-head > .search-wrap{
    grid-column:2;grid-row:1;
    margin-left:0;justify-self:end;
  }
  .site-head > .site-nav{grid-column:1 / -1;grid-row:2}
  /* 不允许被裁掉：允许换行，并收一点间距让 7 个链接更好挤 */
  .site-head .site-nav{flex-wrap:wrap;gap:.3rem .8rem;font-size:.86rem;line-height:1.5}
  #q{min-width:0;width:min(10rem,42vw)}
  .q-results{right:0;left:auto}
}

/* ── 中间宽度（1025–1280px）：原版单行布局的「收紧」档 ──────────────
   原版单行需要约 1000px：品牌 162 + 导航 647 + 搜索框 160 + 间距 32。
   所以在 1025~1280px 之间虽然还用原版，但导航会把搜索框挤到只剩「…」。
   这里把导航字号/间距收一点，并让搜索框可伸缩（有下限），过渡更平滑。 */
@media (min-width:1025px) and (max-width:1280px){
  .site-nav{gap:.62rem;font-size:.88rem}
  .search-wrap{flex:0 1 auto;min-width:0}
  #q{width:auto;min-width:8.5rem;flex:0 1 auto}
}

@media(max-width:640px){main{padding:1rem .8rem 3rem}#q{min-width:9rem}
.q-results{min-width:16rem;right:-1rem}.entry-list li{flex-direction:column;gap:.1rem}}
"""

APP_JS = """/* 黑柩花絮 Wiki · 客户端增强（服务端渲染为主，这里只做筛选/搜索） */
(function () {
  var rel = window.SITE_REL || "";
  // 链接 = rel + e.id + (slug ? "-" + slug : "") + ".html"
  //   e.id   = 相对本站根的路径（含目录，如 entry/hx-001、session/di-…），**不含** .html
  //   e.slug = 文件名里 id 之后、连字符之后的部分：花絮站必填（→ hx-001-<slug>.html），
  //            跑团/设定/分析三站的文件名里没有这一段，故留空串
  // 早先写死 rel + list + e.id + "-" + e.slug，各站结构不一 → 跑团/设定/分析三站全是坏链。
  var q = document.getElementById("q");
  var box = document.getElementById("q-results");
  var index = null;

  // 索引路径 = rel + 索引相对 docs/ 的路径。
  //   · 跑团/设定/分析三站：SITE_INDEX = "assets/search.json"（各站自带的索引）
  //   · 花絮站：不输出 SITE_INDEX，走下面的回退分支 —— 它的索引就是共享的
  //     docs/assets/search.json（花絮站自己产出的），所以回退值是正确目标
  // 两条分支都拼 rel，因此任意目录深度的页面都能取到。
  var idxPath = window.SITE_INDEX
    ? (rel + window.SITE_INDEX)
    : (rel + "../assets/search.json");

  function loadIndex() {
    if (index) return Promise.resolve(index);
    return fetch(idxPath)
      .then(function (r) { return r.ok ? r.json() : { entries: [] }; })
      .then(function (d) { index = d; return d; });
  }

  function render(list) {
    if (!list.length) { box.hidden = true; return; }
    box.innerHTML = list.slice(0, 20).map(function (e) {
      // id 与 slug 之间原本有个连字符：hx-001 + "-" + <slug>。
    // slug 为空的站（跑团/设定/分析）就没有这个连字符。
    // frag 是可选的**页内锚点**（跑团站的场次卡会把「地点/在场/剧情摘要小节」也编进索引，
    // 点结果直接跳到对应字段或小节）。
    // 所属行：优先用 e.sub；否则用 e.season + e.n（跑团站的紧凑写法）拼出来
    var belong = e.sub || (e.season ? e.season + (e.n ? " 第" + e.n + "场" : "") : "");
    // 标签：优先 e.tags；否则退回 e.season（跑团站的条目只带季名）
    var tg = e.tags && e.tags.length ? e.tags : (e.season ? [e.season] : []);
    return '<a href="' + rel + e.id + (e.slug ? "-" + e.slug : "") + '.html' +
        (e.frag ? "#" + e.frag : "") + '">' +
        e.title + '<br><span class="muted">' + e.kind +
        (belong ? " · " + belong : "") +
        (tg.length ? " · " + tg.slice(0, 5).join("、") : "") + "</span></a>";
    }).join("");
    box.hidden = false;
  }

  if (q) {
    q.addEventListener("input", function () {
      var s = q.value.trim().toLowerCase();
      if (!s) { box.hidden = true; return; }
      loadIndex().then(function (d) {
        render((d.entries || []).filter(function (e) {
          return e.title.toLowerCase().indexOf(s) >= 0 ||
            (e.tags || []).some(function (t) { return t.toLowerCase().indexOf(s) >= 0; });
        }));
      });
    });
    document.addEventListener("click", function (ev) {
      if (box && !box.contains(ev.target) && ev.target !== q) box.hidden = true;
    });
  }

  // 回到顶部：滚动超过一屏后淡入（href="#" 由浏览器原生处理）
  var top = document.getElementById("to-top");
  if (top) {
    var onScroll = function () {
      top.classList.toggle("show", window.scrollY > 600);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  // 标签页筛选
  var filters = document.querySelectorAll(".filters button");
  Array.prototype.forEach.call(filters, function (btn) {
    btn.addEventListener("click", function () {
      var kind = btn.getAttribute("data-filter");
      var val = btn.getAttribute("data-value");
      Array.prototype.forEach.call(filters, function (b) {
        if (b.getAttribute("data-filter") === kind)
          b.setAttribute("aria-pressed", b === btn ? "true" : "false");
      });
      Array.prototype.forEach.call(document.querySelectorAll(".entry-list li"), function (li) {
        var hit = !val || li.getAttribute("data-" + kind) === val;
        li.classList.toggle("hide", !hit);
      });
    });
  });

  // 首页快速筛选（按叙事层级）
  Array.prototype.forEach.call(document.querySelectorAll("[data-quick]"), function (btn) {
    btn.addEventListener("click", function () {
      var v = btn.getAttribute("data-quick");
      Array.prototype.forEach.call(document.querySelectorAll("#all-entries li"), function (li) {
        li.classList.toggle("hide", !!v && li.getAttribute("data-layer") !== v);
      });
    });
  });
})();
"""


def render_assets(data, by_id, featured):
    search = {"note": "标题 + 标签轻量搜索索引",
              "entries": [{"id": "entry/" + e["id"], "title": e["title"],
                           "slug": common.slugify(e["title"]),
                           "kind": e["kind"], "chars": e["chars"],
                           "tags": e["tags"]} for e in data["entries"]]}
    n = write_if_changed(os.path.join(SITE_ROOT, "assets", "search.json"),
                         json.dumps(search, ensure_ascii=False, separators=(",", ":")))
    # 客户端聚合：entry→tags 与 tag→entries
    client = {"entry_count": data["entry_count"], "tag_count": data["tag_count"],
              "tag_order": data.get("tag_order", []),
              "multi_dimension_tags": data.get("multi_dimension_tags", []),
              "tags": data["tags"],
              "entry_tags": {e["id"]: {"tags": e["tags"], "primary": e["primary"],
                                       "grades": e.get("grades") or {},
                                       "kind": e["kind"], "chars": e["chars"],
                                       "dims": e["dims"],
                                       "layer": layer_of(e, data["tags"])}
                             for e in data["entries"]},
              "tag_index": data["tag_index"]}
    n += write_if_changed(os.path.join(SITE_ROOT, "assets", "tags.json"),
                          json.dumps(client, ensure_ascii=False, separators=(",", ":")))
    # 按维度拆分的轻量分片：只想拿某个维度标签的客户端可以按需取用
    by_dim = {}
    for t, m in data["tags"].items():
        for d in (m.get("dimensions") or [m.get("dimension")]):
            by_dim.setdefault(d, {})[t] = m["slug"]
    n += write_if_changed(os.path.join(SITE_ROOT, "assets", "tags-by-dimension.json"),
                          json.dumps(by_dim, ensure_ascii=False, separators=(",", ":")))
    if featured:
        n += write_if_changed(os.path.join(SITE_ROOT, "assets", "featured.json"),
                              json.dumps(featured, ensure_ascii=False, indent=1))
    return n


def prune_stale(keep_under):
    """删除 docs/ 下的过期 .html。

    两件事：
    1. 删掉**本前缀目录内**不再生成的 .html（分类改名/删除后会留下过期页面）
    2. 删掉**站点根下**遗留的 .html 与旧目录（如平移前的 docs/cat、docs/entry），
       否则它们会以 /cat/xxx.html 的形式被访问到
    """
    removed = 0
    for sub in keep_under:
        d = os.path.join(DOCS, sub) if sub else DOCS
        if not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            for f in files:
                if not f.endswith(".html"):
                    continue
                p = os.path.join(root, f)
                rel = os.path.relpath(p, DOCS).replace("\\", "/")
                if rel not in KEEP_FILES:
                    os.remove(p)
                    removed += 1
    # 站点根：清掉旧的内容目录（平移前遗留的 entry/ tag/ cat/），
    # 但**不要动 index.html** —— 那是 tools/build_all.py 生成的联合首页
    siteroot = os.path.join(W, "docs")
    for name in ("entry", "tag", "cat"):
        d = os.path.join(siteroot, name)
        if os.path.isdir(d):
            shutil.rmtree(d)
            removed += 1
    return removed


KEEP_FILES = set()


def write_if_changed(path, content):
    """内容相同则不重写（保住 mtime，增量构建友好）。返回写入数。"""
    rel = os.path.relpath(path, DOCS).replace("\\", "/")
    KEEP_FILES.add(rel)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true", help="先清空 docs/（asset 与页面）")
    args = ap.parse_args()
    site = site_conf()
    data, by_id = load_data()

    if args.clean:
        for sub in ("entry", "tag", "assets"):
            p = os.path.join(DOCS, sub)
            if os.path.isdir(p):
                shutil.rmtree(p)

    featured = featured_conf() or auto_featured(data)
    subcats = subcat_conf()
    cat_index = catmod.build_index(data, {"dimensions": subcats} if subcats else {})
    tag_to_cat = catmod.tag_to_categories(cat_index)
    n = 0
    # 共享资源写到站点根 assets/（两站共用：花絮站引用 ../assets/，跑团站同）
    n += write_if_changed(os.path.join(SITE_ROOT, "assets", "style.css"), CSS)
    n += write_if_changed(os.path.join(SITE_ROOT, "assets", "app.js"), APP_JS)
    # 自定义域名与 .nojekyll **必须放在站点根**（docs/），不能放在 /huaxu/ 里，
    # 否则 GitHub Pages 不认自定义域名
    root = os.path.join(W, "docs")
    os.makedirs(root, exist_ok=True)
    domain = (site.get("domain") or "").strip()
    n += write_if_changed(os.path.join(root, "CNAME"),
                          (domain + "\n") if domain else "")
    n += write_if_changed(os.path.join(root, ".nojekyll"), "")
    n += render_assets(data, by_id, featured)
    n += render_entries(data, by_id, site, tag_to_cat)
    n += render_tags(data, by_id, site)
    n += catmod.render_pages(cat_index, data, site, page, write_if_changed)
    n += write_if_changed(os.path.join(DOCS, "index.html"),
                          render_index(data, by_id, site, featured, subcats, cat_index))
    stale = prune_stale(("entry", "tag", "cat", ""))
    print(json.dumps({"written": n, "entries": data["entry_count"],
                      "tags": data["tag_count"], "categories": len(cat_index),
                      "pruned_stale_pages": stale,
                      "featured_auto": featured.get("auto", False),
                      "subcategorised_dims": sorted(subcats)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
