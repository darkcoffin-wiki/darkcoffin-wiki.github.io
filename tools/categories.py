#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子分类 → 可点分类页。

作者要求：「子分类本身也可以是标签」。实现方式是**从 data/subcategories.json 推导**，
不新增任何标签数据、也不改动打标结果：

* 每个子分类生成一页 `docs/cat/<维度slug>-<分类slug>.html`
* 该页列出「组内所有标签的篇目并集」，按权重排序
* 首页的子分类标题、条目页的「所属分类」都会链过去
* 支持嵌套：子分类可有 `children`，父页包含子页的全部标签（目前未启用嵌套）

用法（被 build_site.py 调用，也可单独跑）：
    python tools/categories.py            # 只打印统计
"""
import collections
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

DATA = common.DATA


def build_index(tags_data, sc):
    """→ [ {dim, name, slug, url, member_tags, entries(排序后), weight} ... ]

    entries 为组内标签的篇目并集；weight 记录每篇在该组内的累计权重，用于排序。
    """
    meta = tags_data["tags"]
    idx = tags_data["tag_index"]
    by_id = {e["id"]: e for e in tags_data["entries"]}
    out = []
    for dim, groups in (sc.get("dimensions") or {}).items():
        for g in groups:
            members = [t for t in (g.get("tags") or []) if t in idx]
            if not members:
                continue
            weight = collections.Counter()
            for t in members:
                for eid in idx[t]:
                    weight[eid] += by_id[eid]["weights"].get(t, 1)
            entries = sorted(weight, key=lambda e: (-weight[e], -by_id[e]["chars"]))
            slug = "%s-%s" % (common.slugify(dim), common.slugify(g["name"]))
            out.append({
                "dim": dim, "name": g["name"], "slug": slug,
                "url": "cat/%s.html" % slug,
                "source": (sc.get("dimensions_sources") or {}).get(
                    "%s/%s" % (dim, g["name"])) or g.get("source", ""),
                "member_tags": sorted(members, key=lambda t: -len(idx[t])),
                "entries": entries,
                "weight": dict(weight),
            })
    return out


def tag_to_categories(cat_index):
    """标签 → 它所属的分类列表（用于条目页的「所属分类」与首页锚点）。"""
    m = collections.defaultdict(list)
    for c in cat_index:
        for t in c["member_tags"]:
            m[t].append(c)
    return m


def chips(eid, tag_dims, cat_index, tag_to_cat, rel="", limit=6):
    """条目页的「所属分类」小标签（去重后最多 limit 个）。"""
    seen, out = set(), []
    for t in tag_dims:
        for c in tag_to_cat.get(t, []):
            key = (c["dim"], c["name"])
            if key in seen:
                continue
            seen.add(key)
            out.append(c)
    out = out[:limit]
    if not out:
        return ""
    return ('<p class="cats">所属分类：' + "".join(
        '<a class="chip chip-cat" href="%s%s">%s<span class="muted">%s</span></a>'
        % (rel, c["url"], c["name"], c["dim"]) for c in out) + "</p>")


def render_pages(cat_index, tags_data, site, page_fn, write_fn, rel="../", min_doc=1):
    """生成分类页。page_fn(title, body, rel, site, extra_head, body_class) 由 build_site 提供。"""
    meta = tags_data["tags"]
    idx = tags_data["tag_index"]
    by_id = {e["id"]: e for e in tags_data["entries"]}
    n = 0
    for c in cat_index:
        rows = []
        for eid in c["entries"]:
            e = by_id[eid]
            dims = e["dims"]
            layer = next((t for t in e["tags"]
                          if "叙事层级" in (dims.get(t) or [])), "")
            rows.append('<li data-id="%s" data-kind="%s" data-layer="%s">'
                        '<a href="../entry/%s-%s.html">%s</a>'
                        '<span class="muted">%s · %d 字 · %s</span></li>'
                        % (eid, e["kind"], layer, eid, common.slugify(e["title"]),
                           e["title"], e["kind"], e["chars"], eid))
        tag_chips = "".join(
            '<a class="chip chip-%s%s" href="../tag/%s.html">%s<b>%d</b>%s</a>'
            % (tag_color(meta, t), " chip-multi" if len(meta[t].get("dimensions") or []) > 1 else "",
               meta[t]["slug"], t, len(idx[t]),
               '<span class="multi-mark">⋈</span>'
               if len(meta[t].get("dimensions") or []) > 1 else "")
            for t in c["member_tags"])
        body = """<section class="cat-page">
<header class="tag-head">
  <p class="crumbs"><a href="../index.html">首页</a> · %s · 分类</p>
  <h1>%s</h1>
  <p class="meta">%d 篇（组内 %d 个标签的并集）</p>
  %s
</header>
<nav class="filters">
  <span>筛选：</span>
  <button data-filter="layer" data-value="">全部</button>
  <button data-filter="layer" data-value="已发生">已发生</button>
  <button data-filter="layer" data-value="未来可能">未来可能</button>
  <button data-filter="layer" data-value="平行世界线">平行世界线</button>
</nav>
<ul class="entry-list">
%s
</ul>
<div class="related"><h2>组内标签（%d）</h2><div class="chips">%s</div></div>
</section>""" % (c["dim"], c["name"], len(c["entries"]), len(c["member_tags"]),
                 ('<p class="dim-note">分组依据：%s</p>' % c["source"]) if c.get("source") else "",
                 "".join(rows), len(c["member_tags"]), tag_chips)
        n += write_fn(os.path.join(common.W, "docs", c["url"]),
                      page_fn(c["name"], body, rel, site, body_class="cat-detail"))
    return n


def tag_color(meta, t):
    order = ["文类", "叙事层级", "人物", "组织", "地理", "设施",
             "剧情线", "主题", "事件类型", "关系", "主题词", "时间", "篇幅"]
    ds = meta[t].get("dimensions") or [meta[t].get("dimension")]
    for d in order:
        if d in ds:
            return {"文类": "kind", "叙事层级": "layer", "人物": "person",
                    "组织": "org", "地理": "place", "设施": "facility",
                    "剧情线": "series", "主题": "theme", "事件类型": "event",
                    "关系": "relation", "主题词": "tone", "时间": "time",
                    "篇幅": "length"}.get(d, "misc")
    return "misc"


def main():
    tags_data = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    sc = json.load(open(os.path.join(DATA, "subcategories.json"), encoding="utf-8"))
    ci = build_index(tags_data, sc)
    print(json.dumps({"categories": len(ci),
                      "by_dim": dict(collections.Counter(c["dim"] for c in ci)),
                      "sample": [{"name": c["name"], "entries": len(c["entries"]),
                                  "tags": len(c["member_tags"])} for c in ci[:5]]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
