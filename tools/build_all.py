#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键构建整个站点：

    docs/
    ├─ index.html      ← 联合首页（两站入口）
    ├─ CNAME / .nojekyll
    ├─ assets/         ← 共享样式与脚本（花絮站写入，跑团站也引用）
    ├─ huaxu/          ← 花絮站（tools/build_site.py）
    ├─ trpg/           ← 跑团站（tools/build_trpg.py）
    └─ lore/           ← 设定站（tools/build_lore.py）

用法：
    python tools/build_all.py            # 增量构建
    python tools/build_all.py --clean    # 先清空 docs/
    python tools/check_all.py            # 全套自检（另见该脚本）
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import common  # noqa: E402
import html as H  # noqa: E402  页脚/模板转义（模块级，供 friend_links_html 使用）

W = common.W
DOCS = os.path.join(W, "docs")
PY = sys.executable


def run(tool, *extra):
    p = subprocess.run([PY, os.path.join(W, "tools", tool)] + list(extra), cwd=W,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


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


def latest_source_mtime():
    """站点「最近更新」＝内容源的最新修改时间。

    **不用构建时刻**：那会让每次构建的时间戳都变，破坏幂等（written 永远不为 0）。
    数据源变化才会变，正是「最近更新」的语义。
    """
    import glob as _glob
    cands = []
    for pat in (os.path.join(W, "source", "*.md"),
                os.path.join(W, "data", "*.json"),
                os.path.join(W, "trpg-data", "*.json"),
                os.path.join(W, "lore-data", "*.json"),
                os.path.join(W, "tools", "*.py")):
        cands += _glob.glob(pat)
    if not cands:
        return ""
    t = max(os.path.getmtime(p) for p in cands)
    import datetime as _dt
    return _dt.datetime.fromtimestamp(t).strftime("%Y-%m-%d")


def friend_links_html(site):
    """页脚友情链接（配置在 data/site.json 的 friend_links）。本文件里 html 的别名是 H。"""
    out = []
    for f in (site or {}).get("friend_links") or []:
        label = H.escape(f.get("label", ""))
        url = f.get("url", "#")
        note = f.get("note", "")
        title = ' title="%s"' % H.escape(note) if note else ""
        out.append('<a href="%s"%s target="_blank" rel="noopener">%s</a>'
                   % (H.escape(url), title, label))
    return "".join(out) or "—"


def joint_index():
    """联合首页：两站入口 + 共用统计。"""
    huaxu = {}
    trpg = {}
    try:
        t = json.load(io.open(os.path.join(W, "data", "tags.json"), encoding="utf-8"))
        huaxu = {"entries": t["entry_count"], "tags": t["tag_count"]}
    except Exception:
        pass
    try:
        c = json.load(io.open(os.path.join(W, "trpg-data", "corpus.json"),
                              encoding="utf-8"))
        trpg = {"seasons": c["counts"]["seasons"], "sessions": c["counts"]["sessions"]}
        tot = sum(v for k, v in (c["index"] or {}).items() if isinstance(v, int))
    except Exception:
        tot = 0
    lore = {}
    try:
        ld = json.load(io.open(os.path.join(W, "lore-data", "doc.json"),
                               encoding="utf-8"))
        lore = {"vols": ld["counts"]["vols"] - 2,      # 去掉「目录」「前言」两个 H1
                "sections": ld["counts"]["sections"],
                "entries": ld["counts"]["entries"],
                "hanzi": ld["counts"]["hanzi"]}
    except Exception:
        pass
    # 分析站统计（来自 report-data/catalog.json）
    report = {}
    try:
        rc = json.load(io.open(os.path.join(W, "report-data", "catalog.json"),
                               encoding="utf-8"))
        report = {"reports": len(rc),
                  "tables": sum(c.get("tables", 0) for c in rc),
                  "hanzi": sum(c.get("hanzi", 0) for c in rc)}
    except Exception:
        pass
    site = {}
    try:
        site = json.load(io.open(os.path.join(W, "data", "site.json"),
                                 encoding="utf-8"))
    except Exception:
        pass
    disc = H.escape(site.get("disclaimer", "本网站由 AI 生成，内容准确性无法完全保证。"))
    _upd = latest_source_mtime() or "—"
    domain = H.escape(site.get("domain", ""))
    # ── 《黑柩》是什么（内容依据作者官网《黑柩TRPG·简介&规则2026版》的「背景资料」一节）
    # 数字取构建时的真实统计，避免像「113 场、12 季」那样过期。
    # 注意：这里用 % 格式化生成**普通字符串**，再在 f-string 里以 {about_html} 插入；
    # 千万不要把 {占位符} 直接写进 return 的 f-string —— 那会被当表达式求值并抛 NameError。
    about_html = (
        '<section class="joint-about">\n'
        '  <h2>《黑柩》是什么</h2>\n'
        '  <p>这是一个<strong>后启示录的彷徨世界</strong>：五百年前，高热射线把地表烧成地狱，'
        '只有「古中国」内陆被一道<strong>神圣障壁</strong>护住，成了人类仅存的圣地。'
        '圣地里，掌握魔法的<strong>天空教</strong>统治了两百余年；一场大革命推翻它之后，'
        '革命的两个成果——<strong>希望联邦</strong>与<strong>进化者同盟</strong>——各自走向极端。'
        '进盟研究「灵魂学」，造出被植入杀意的<strong>天使</strong>，'
        '在「和平纪念日」以数十万天使屠尽希联首都星都。</p>\n'
        '  <p>战后的圣地再没有统一秩序：希联退守青都、进盟南北分裂，'
        '南部的<strong>启示录教团国</strong>、夜都的<strong>神圣希望帝国</strong>、'
        '北沙的<strong>戡乱政府</strong>、夹在中间的<strong>走廊区</strong>各据一方。'
        '<strong>烽火未断，战乱不休。</strong></p>\n'
        '  <ul class="about-forms">'
        '<li><b>原典</b>设定集 %d 卷 · %s 词条</li>'
        '<li><b>实录</b>跑团 %d 季 · %d 场</li>'
        '<li><b>短篇</b>花絮与画外音 %d 篇</li>'
        '</ul>\n'
        '  <p class="about-hint"><b>第一次来？</b>'
        '想看这是什么样的世界 → <a href="lore/index.html">设定站</a>（从卷一读起）；'
        '想看故事怎么真实发生 → <a href="trpg/index.html">跑团站</a>；'
        '想读短篇 → <a href="huaxu/index.html">花絮站</a>。</p>\n'
        '</section>\n\n'
    ) % (lore.get("vols", 11), format(lore.get("entries", 0), ","),
         trpg.get("seasons", 0), trpg.get("sessions", 0), huaxu.get("entries", 0))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>黑柩 Wiki</title>
<meta name="description" content="《黑柩》的四套整理：花絮 · 跑团剧情志 · 设定集 · 分析报告。">
<link rel="stylesheet" href="assets/style.css">
<link rel="icon" type="image/png" href="assets/icon.png">
<link rel="apple-touch-icon" href="assets/icon.png">
<link rel="stylesheet" href="assets/joint.css">
</head>
<body class="joint">
<main>
<header class="joint-hero">
  <h1>黑柩 Wiki</h1>
  <p class="sub">后启示录的彷徨世界</p>
</header>

<div class="station-grid">
  <a class="station-card" href="huaxu/index.html">
    <h2>花絮站</h2>
    <p class="sum">作品的花絮、楔子与画外音，按<strong>人物 / 组织 / 地理 / 主题</strong>等维度整理。</p>
    <ul class="nums">
      <li><b>{huaxu.get('entries', '—')}</b> 篇</li>
      <li><b>{huaxu.get('tags', '—')}</b> 个标签</li>
      <li>红橙蓝相关性分级</li>
    </ul>
    <span class="enter">进入花絮站 →</span>
  </a>

  <a class="station-card" href="trpg/index.html">
    <h2>跑团站</h2>
    <p class="sum">跑团剧情志：场次志与季志，按<strong>主线 / 短团 / 场次 / 现实时间</strong>整理。</p>
    <ul class="nums">
      <li><b>{trpg.get('seasons', '—')}</b> 季</li>
      <li><b>{trpg.get('sessions', '—')}</b> 场</li>
      <li>{format(tot, ',') if tot else '—'} 汉字</li>
    </ul>
    <span class="enter">进入跑团站 →</span>
  </a>

  <a class="station-card" href="lore/index.html">
    <h2>设定站</h2>
    <p class="sum">《黑柩设定集·1.1版》：按<strong>卷 / 节 / 词条</strong>整理的设定辞书。</p>
    <ul class="nums">
      <li><b>{lore.get('vols', '—')}</b> 卷</li>
      <li><b>{lore.get('entries', '—')}</b> 词条</li>
      <li>{format(lore.get('hanzi', 0), ',') if lore.get('hanzi') else '—'} 汉字</li>
    </ul>
    <span class="enter">进入设定站 →</span>
    <span class="card-warn">⚠️ 含剧透：涵盖全书人物、事件与结局</span>
  </a>

  <a class="station-card warn" id="station-report" href="report/index.html">
    <h2>分析站</h2>
    <p class="sum">基于《黑柩设定集》的<strong>专题研究报告</strong>：制度 · 法律 · 刑罚 · 意识形态 · 政权 · 人物。</p>
    <ul class="nums">
      <li><b>{report.get('reports', '—')}</b> 份报告</li>
      <li><b>{report.get('tables', '—')}</b> 张表</li>
      <li>{format(report.get('hanzi', 0), ',') if report.get('hanzi') else '—'} 汉字</li>
    </ul>
    <span class="enter">进入分析站 →</span>
    <span class="card-warn">⚠️ 全部报告由 <b>AI 撰写</b>，属读者分析、非作者设定</span>
  </a>
</div>

<section class="joint-warns">
  <p class="warn eating">📕 <strong>吃书警告</strong>：原作设定前后不一致（作者自称「吃书」）之处，
     各站<strong>一律照录、不代为圆说</strong>；设定站对确有分歧的条目以【异说】单列。</p>
</section>

{about_html}<section class="joint-note">
  <h2>四个站的关系</h2>
  <p class="muted">四站共用一套视觉与导航，但<strong>内容性质不同</strong>，按「原典 → 实录 → 花絮 → 解读」
  的顺序逐层展开：</p>
  <ul>
    <li><strong>设定站</strong>（<code>/lore/</code>）是<strong>原典</strong>：作者写的《黑柩设定集·1.1版》，
        按<strong>卷／节／词条</strong>拆解，便于查概念。<strong>要确认设定是什么，以这里为准。</strong></li>
    <li><strong>跑团站</strong>（<code>/trpg/</code>）是<strong>实录</strong>：真实发生的跑团记录，
        按<strong>主线 12 季 + 短团 4 个</strong>、共 152 场整理，强调时间线与场次。</li>
    <li><strong>花絮站</strong>（<code>/huaxu/</code>）是<strong>花絮与画外音</strong>：作者的短篇体裁作品，
        按人物／组织／地理／主题等维度整理，强调题材与人物关系。</li>
    <li><strong>分析站</strong>（<code>/report/</code>）是<strong>读者解读</strong>：基于设定集撰写的专题研究报告
        （制度 · 法律 · 刑罚 · 意识形态 · 政权 · 人物）。⚠️ <strong>全部由 AI 撰写，不是作者设定</strong>。</li>
  </ul>
  <p class="muted"><strong>互链情况</strong>：</p>
  <ul>
    <li>跑团站里的名词会<strong>链到花絮站的标签页</strong>（只链结构化名单字段，剧情摘要正文不链）。</li>
    <li><strong>设定站暂不外链</strong>——设定集仍在演进，等它稳定后再接；但它本身接受别站链接。</li>
    <li>分析站的报告<strong>引用设定集</strong>，凡与设定冲突处一律以设定为准。</li>
    <li>四站<strong>各有导航与首页</strong>，顶部菜单可互相切换；标签体系各自独立
        （跑团含平行世界与 if 线，同名不一定是同一实体）。</li>
  </ul>
</section>

<footer class="site-foot">
  <p class="disclaimer">{disc}</p>
  <p>《黑柩》相关内容版权归原作者所有。</p>
  <p class="muted">最近更新：{_upd}</p>
  {f'<p class="muted">{domain}</p>' if domain else ''}
<p class="friend-links">友情链接：{friend_links_html(site)}</p>
</footer>
</main>
</body>
</html>
"""


JOINT_CSS = """/* 联合首页 */
body.joint{display:block}
body.joint main{max-width:56rem;margin:0 auto;padding:2rem 1.2rem 3rem}
.joint-hero{text-align:center;padding:1.5rem 0 1rem}
.joint-hero h1{font-size:2rem;margin:0 0 .3rem}
.joint-hero .sub{color:var(--muted);margin:0}
.station-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(19rem,1fr));
gap:1rem;margin:1.4rem 0}
.station-card{display:block;background:var(--card);border:1px solid var(--line);
border-radius:14px;padding:1.1rem 1.2rem;color:var(--fg);transition:border-color .15s}
.station-card:hover{border-color:var(--accent);text-decoration:none}
.station-card h2{margin:0 0 .4rem;font-size:1.25rem}
.station-card .sum{margin:0 0 .7rem;color:var(--muted);font-size:.92rem}
.station-card .nums{list-style:none;display:flex;gap:1rem;padding:0;margin:0 0 .8rem;
flex-wrap:wrap;font-size:.88rem;color:var(--muted)}
.station-card .nums b{color:var(--fg);font-size:1.05rem}
.station-card .enter{color:var(--accent);font-size:.92rem}
.joint-note{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:.9rem 1.1rem;margin:1.2rem 0}
.joint-note h2{font-size:1rem;margin:.1rem 0 .5rem}
.joint-note ul{margin:0;padding-left:1.2rem}
.joint-note li{margin:.3rem 0;font-size:.92rem;color:var(--muted)}
.joint-note strong{color:var(--fg)}
.friend-links{margin:.45rem 0 0;font-size:.88rem}
.friend-links a{color:var(--accent2)}
.station-card .card-warn{display:block;margin-top:.5rem;font-size:.8rem;
color:#d98b2b;border-top:1px dashed var(--line);padding-top:.4rem}
.joint-warns{margin:1.2rem 0}
.joint-warns .warn{background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:.55rem .9rem;margin:.45rem 0;font-size:.9rem;color:var(--muted)}
.joint-warns .warn.spoiler{border-left:3px solid #d98b2b}
.joint-warns .warn.eating{border-left:3px solid var(--accent)}
.joint-warns strong{color:var(--fg)}
.joint-about{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:1rem 1.15rem;margin:1.4rem 0}
.joint-about h2{font-size:1.05rem;margin:.1rem 0 .6rem}
.joint-about p{margin:.55rem 0;font-size:.94rem;line-height:1.78;color:var(--muted)}
.joint-about strong{color:var(--fg)}
.joint-about .about-forms{display:flex;flex-wrap:wrap;gap:.35rem 1.1rem;
margin:.75rem 0 .3rem;padding:0;list-style:none;font-size:.88rem;color:var(--muted)}
.joint-about .about-forms li{white-space:nowrap}
.joint-about .about-forms b{color:var(--accent2);margin-right:.35rem}
.joint-about .about-hint{font-size:.88rem;color:var(--muted);
border-top:1px dashed var(--line);padding-top:.65rem;margin-top:.75rem}
.joint-about .about-hint a{color:var(--accent2)}
"""


def build_ask():
    """把 tools/ask/ 的跨站检索组件分发到 docs/。

    源码（ask.html / ask.css / ask.js）放在 tools/ask/ 而不是直接在 docs/，
    这样 `build_all.py --clean` 清空 docs/ 之后能原样重建，不会丢文件。

    产出：
      docs/ask.html          —— 检索页：跨四站检索 + 一次性 AI 解释
      docs/chat.html         —— 问答页：黑柩问答，自由多轮对话
      docs/assets/ask.css    —— 样式（所有规则以 #heijiu-ask 前缀隔离）
      docs/assets/ask.js     —— 逻辑（ES5，无依赖）
    嵌入 WordPress 只需要：<div id="heijiu-ask"></div> + 引用这两个资源。
    """
    src = os.path.join(W, "tools", "ask")
    if not os.path.isdir(src):
        return 0
    pairs = [
        ("ask.html", os.path.join(DOCS, "ask.html")),
        ("chat.html", os.path.join(DOCS, "chat.html")),
        ("ask.css", os.path.join(DOCS, "assets", "ask.css")),
        ("ask.js", os.path.join(DOCS, "assets", "ask.js")),
    ]
    n = 0
    for name, dst in pairs:
        p = os.path.join(src, name)
        if not os.path.exists(p):
            continue
        n += write_if_changed(dst, io.open(p, encoding="utf-8").read())
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    if args.clean:
        shutil.rmtree(DOCS, ignore_errors=True)
        print("已清空 docs/")

    n = 0
    for tool, label in (("build_site.py", "花絮站"), ("build_trpg.py", "跑团站"),
                        ("build_lore.py", "设定站"),
                        ("build_report.py", "分析站")):
        code, out = run(tool)
        print("[%s] %s %s" % ("OK " if code == 0 else "FAIL", label, out[:220]))

    n += write_if_changed(os.path.join(DOCS, "index.html"), joint_index())
    n += write_if_changed(os.path.join(DOCS, "assets", "joint.css"), JOINT_CSS)
    n += build_ask()
    print(json.dumps({"joint_index_written": n}, ensure_ascii=False))


if __name__ == "__main__":
    main()
