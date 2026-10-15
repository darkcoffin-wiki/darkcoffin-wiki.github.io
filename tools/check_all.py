#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全站自检：花絮站 + 跑团站 + 联合首页。

检查项
------
1. 花絮站：每个条目/标签/分类都有页面（沿用 check_site 的逻辑）
2. 跑团站：12 季志、113 场次卡、时间轴、首页都在
3. **跨站链接**：所有站内 href 都能解析到实际文件（含 huaxu ↔ trpg 互链）
4. 联合首页存在，且指向两站首页
5. 共享资源在位：docs/assets/{style.css,app.js,joint.css}
6. 无未替换占位符、无过短页面
7. 跑团站：分层序号渲染正确（抽样：h2 带 `一、` 等）

用法：python tools/check_all.py      退出码非 0 表示有错误
"""
import glob
import html
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import common  # noqa: E402

W = common.W
DOCS = os.path.join(W, "docs")
HREF = re.compile(r'href="([^"#]+)"')


def main():
    errs, warns, stats = [], [], {}

    tag_data = json.load(io.open(os.path.join(W, "data", "tags.json"), encoding="utf-8"))
    sess = json.load(io.open(os.path.join(W, "trpg-data", "sessions.json"),
                             encoding="utf-8"))
    seasons = json.load(io.open(os.path.join(W, "trpg-data", "seasons.json"),
                                encoding="utf-8"))
    lore = json.load(io.open(os.path.join(W, "lore-data", "doc.json"),
                             encoding="utf-8"))

    # 1) 花絮站页面存在性
    miss_e = [os.path.basename(p) for e in tag_data["entries"]
              for p in [os.path.join(DOCS, "huaxu", "entry",
                                     "%s-%s.html" % (e["id"], common.slugify(e["title"])))]
              if not os.path.exists(p)]
    miss_t = [m["slug"] for _t, m in tag_data["tags"].items()
              if not os.path.exists(os.path.join(DOCS, "huaxu", "tag", "%s.html" % m["slug"]))]
    if miss_e:
        errs.append("花絮站缺条目页 %d 个：%s" % (len(miss_e), miss_e[:6]))
    if miss_t:
        errs.append("花絮站缺标签页 %d 个：%s" % (len(miss_t), miss_t[:6]))

    # 2) 跑团站页面存在性
    miss_s = [s["season"] + " 第%d场" % s["no"] for s in sess
              if not os.path.exists(os.path.join(
                  DOCS, "trpg", "session",
                  "%s-%02d.html" % (common.slugify(s["season"]), s["no"])))]
    miss_season = [s["name"] for s in seasons
                   if not os.path.exists(os.path.join(
                       DOCS, "trpg", "season", "%s.html" % common.slugify(s["name"])))]
    if miss_s:
        errs.append("跑团站缺场次卡 %d 个：%s" % (len(miss_s), miss_s[:6]))
    if miss_season:
        errs.append("跑团站缺季志页 %d 个：%s" % (len(miss_season), miss_season[:6]))
    for f in ("index.html", "timeline.html"):
        if not os.path.exists(os.path.join(DOCS, "trpg", f)):
            errs.append("跑团站缺 %s" % f)

    # 2b) 设定站页面存在性
    miss_lore, miss_lvol, miss_lsec = [], [], []
    for v in lore["vols"]:
        vp = os.path.join(DOCS, "lore", "vol", "%s.html" % common.slugify(v["title"]))
        if not os.path.exists(vp):
            miss_lvol.append(v["title"])
        for sec in v["sections"]:
            sp = os.path.join(DOCS, "lore", "sec",
                              "%s.html" % common.slugify("%s-%s" % (v["title"], sec["title"])))
            if not os.path.exists(sp):
                miss_lsec.append(sec["title"])
            for e in sec["entries"]:
                ep = os.path.join(DOCS, "lore", "entry", "%s.html" % e["slug"])
                if not os.path.exists(ep):
                    miss_lore.append(e["title"])
    if miss_lore:
        errs.append("设定站缺词条页 %d 个：%s" % (len(miss_lore), miss_lore[:6]))
    if miss_lvol:
        errs.append("设定站缺卷页 %d 个：%s" % (len(miss_lvol), miss_lvol[:6]))
    if miss_lsec:
        errs.append("设定站缺节页 %d 个：%s" % (len(miss_lsec), miss_lsec[:6]))
    for f in ("index.html", "preface.html"):
        if not os.path.exists(os.path.join(DOCS, "lore", f)):
            errs.append("设定站缺 %s" % f)

    # 3) 全部站内链接解析（跨站也在这里检查）
    pages = glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True)
    bad = {}
    for p in pages:
        txt = io.open(p, encoding="utf-8").read()
        for href in HREF.findall(txt):
            if href.startswith(("http://", "https://", "mailto:", "//", "#")):
                continue
            target = os.path.normpath(os.path.join(
                os.path.dirname(p), href.split("?")[0].split("#")[0]))
            if not os.path.exists(target):
                bad.setdefault(os.path.relpath(p, DOCS), []).append(href)
    if bad:
        sample = [(k, v[:4]) for k, v in list(bad.items())[:4]]
        errs.append("死链：%d 个页面有无法解析的 href，例：%s" % (len(bad), sample))

    # 4) 联合首页
    jp = os.path.join(DOCS, "index.html")
    if not os.path.exists(jp):
        errs.append("缺联合首页 docs/index.html")
    else:
        t = io.open(jp, encoding="utf-8").read()
        for need in ("huaxu/index.html", "trpg/index.html", "lore/index.html"):
            if need not in t:
                errs.append("联合首页缺少入口：%s" % need)

    # 5) 共享资源
    for f in ("style.css", "app.js", "joint.css"):
        if not os.path.exists(os.path.join(DOCS, "assets", f)):
            errs.append("缺共享资源 docs/assets/%s" % f)
    if not os.path.exists(os.path.join(DOCS, "CNAME")):
        errs.append("站点根缺 CNAME（自定义域名会失效）")
    if not os.path.exists(os.path.join(DOCS, ".nojekyll")):
        errs.append("站点根缺 .nojekyll")

    # 6) 占位符 / 过短
    for p in pages:
        t = io.open(p, encoding="utf-8").read()
        if re.search(r"\{[a-z_]+\}", t):
            warns.append("疑似未替换占位符：%s" % os.path.relpath(p, DOCS))
        if len(t) < 400:
            warns.append("页面过短：%s" % os.path.relpath(p, DOCS))

    # 7) 跑团站分层序号抽样
    probe = os.path.join(DOCS, "trpg", "session",
                         "%s-%02d.html" % (common.slugify("第二季·星都陨落"), 1))
    if os.path.exists(probe):
        t = io.open(probe, encoding="utf-8").read()
        h2 = re.findall(r"<h2>([^<]+)</h2>", t)
        need = ["一、现实时间", "二、游戏内时间", "六、剧情摘要", "十二、出处"]
        lack = [x for x in need if x not in h2]
        if lack:
            errs.append("跑团站分层序号缺失：%s（实际 %s）" % (lack, h2[:4]))
        if "（一）" not in t:
            warns.append("跑团站第 2 层编号（（一））未见，检查剧情摘要小节")

    stats = {"总页数": len(pages),
             "花絮站": len(glob.glob(os.path.join(DOCS, "huaxu", "**", "*.html"),
                                    recursive=True)),
             "跑团站": len(glob.glob(os.path.join(DOCS, "trpg", "**", "*.html"),
                                    recursive=True)),
             "设定站": len(glob.glob(os.path.join(DOCS, "lore", "**", "*.html"),
                                    recursive=True)),
             "条目": tag_data["entry_count"], "标签": tag_data["tag_count"],
             "季": len(seasons), "场次": len(sess),
             "设定卷": len(lore["vols"]), "设定词条": lore["counts"]["entries"]}
    print(json.dumps({"stats": stats, "errors": errs, "warnings": warns[:10]},
                     ensure_ascii=False, indent=1))
    if errs:
        sys.exit(1)


if __name__ == "__main__":
    main()
