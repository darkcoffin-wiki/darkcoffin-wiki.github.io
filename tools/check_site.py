#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站点自检：生成后验证链接与完整性（CI 与本地都用）。

检查项
------
1. 每个条目都有 entry/<id>-<slug>.html
2. 每个标签都有 tag/<slug>.html
3. 所有站内链接（href）都能解析到实际文件——**这一项能抓住 slug 不一致**
4. assets/tags.json 与 tags.json 的条目集合一致
5. 无空页面、无未替换的模板占位符

用法：python tools/check_site.py
退出码非 0 表示有错误。
"""
import glob
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

W = common.W
DATA = common.DATA
PREFIX = os.environ.get("DSH_SITE_PREFIX", "huaxu").strip("/")
DOCS = os.path.join(W, "docs", PREFIX)

HREF = re.compile(r'href="([^"#]+)"')


def main():
    errs, warns = [], []
    tag_data = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))

    # 1/2 页面存在性
    missing_entry, missing_tag = [], []
    for e in tag_data["entries"]:
        slug = common.slugify(e["title"])
        p = os.path.join(DOCS, "entry", "%s-%s.html" % (e["id"], slug))
        if not os.path.exists(p):
            missing_entry.append(os.path.basename(p))
    for t, m in tag_data["tags"].items():
        p = os.path.join(DOCS, "tag", "%s.html" % m["slug"])
        if not os.path.exists(p):
            missing_tag.append(m["slug"])
    if missing_entry:
        errs.append("缺少条目页 %d 个：%s" % (len(missing_entry), ", ".join(missing_entry[:8])))
    if missing_tag:
        errs.append("缺少标签页 %d 个：%s" % (len(missing_tag), ", ".join(missing_tag[:8])))

    # 3 站内链接解析
    bad_links = {}
    pages = glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True)
    for p in pages:
        txt = open(p, encoding="utf-8").read()
        for href in HREF.findall(txt):
            if href.startswith(("http://", "https://", "mailto:", "//")):
                continue
            target = os.path.normpath(os.path.join(os.path.dirname(p), href.split("?")[0]))
            if not os.path.exists(target):
                bad_links.setdefault(os.path.relpath(p, DOCS), []).append(href)
    if bad_links:
        sample = list(bad_links.items())[:5]
        errs.append("死链：%d 个页面有无法解析的 href，例：%s"
                    % (len(bad_links), sample))

    # 4 客户端聚合一致性
    client_path = os.path.join(DOCS, "assets", "tags.json")
    if not os.path.exists(client_path):
        errs.append("缺少 docs/assets/tags.json")
    else:
        c = json.load(open(client_path, encoding="utf-8"))
        a, b = set(c.get("entry_tags", {})), {e["id"] for e in tag_data["entries"]}
        if a != b:
            errs.append("客户端聚合条目集不一致：缺 %s，多 %s"
                        % (sorted(b - a)[:5], sorted(a - b)[:5]))

    # 5 占位符 / 空页
    for p in pages:
        txt = open(p, encoding="utf-8").read()
        if "{" in txt and re.search(r"\{[a-z_]+\}", txt):
            warns.append("疑似未替换占位符：%s" % os.path.relpath(p, DOCS))
        if len(txt) < 400:
            warns.append("页面过短（可疑）：%s" % os.path.relpath(p, DOCS))

    print(json.dumps({"pages": len(pages),
                      "entries": len(tag_data["entries"]),
                      "tags": len(tag_data["tags"]),
                      "errors": errs, "warnings": warns[:10]},
                     ensure_ascii=False, indent=1))
    if errs:
        sys.exit(1)


if __name__ == "__main__":
    main()
