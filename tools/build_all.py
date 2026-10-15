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


def joint_index():
    """联合首页：两站入口 + 共用统计。"""
    import html as H
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
    site = {}
    try:
        site = json.load(io.open(os.path.join(W, "data", "site.json"),
                                 encoding="utf-8"))
    except Exception:
        pass
    disc = H.escape(site.get("disclaimer", "本网站由 AI 生成，内容准确性无法完全保证。"))
    domain = H.escape(site.get("domain", ""))
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>黑柩 Wiki</title>
<meta name="description" content="《黑柩》的两套整理：花絮与跑团剧情志。">
<link rel="stylesheet" href="assets/style.css">
<link rel="stylesheet" href="assets/joint.css">
</head>
<body class="joint">
<main>
<header class="joint-hero">
  <h1>黑柩 Wiki</h1>
  <p class="sub">同一个故事宇宙的两套记录</p>
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

  <a class="station-card" href="lore/index.html">
    <h2>设定站</h2>
    <p class="sum">《黑柩设定集·第一版》：按<strong>卷 / 节 / 词条</strong>整理的设定辞书。</p>
    <ul class="nums">
      <li><b>{lore.get('vols', '—')}</b> 卷</li>
      <li><b>{lore.get('entries', '—')}</b> 词条</li>
      <li>{format(lore.get('hanzi', 0), ',') if lore.get('hanzi') else '—'} 汉字</li>
    </ul>
    <span class="enter">进入设定站 →</span>
    <span class="card-warn">⚠️ 含剧透：涵盖全书人物、事件与结局</span>
  </a>

  <a class="station-card" href="trpg/index.html">
    <h2>跑团站</h2>
    <p class="sum">跑团剧情志：场次志与季志，按<strong>季 / 场次 / 现实时间</strong>整理。</p>
    <ul class="nums">
      <li><b>{trpg.get('seasons', '—')}</b> 季</li>
      <li><b>{trpg.get('sessions', '—')}</b> 场</li>
      <li>{format(tot, ',') if tot else '—'} 汉字</li>
    </ul>
    <span class="enter">进入跑团站 →</span>
  </a>
</div>

<section class="joint-warns">
  <p class="warn eating">📕 <strong>吃书警告</strong>：原作设定前后不一致（作者自称「吃书」）之处，
     各站<strong>一律照录、不代为圆说</strong>；设定站对确有分歧的条目以【异说】单列。</p>
</section>

<section class="joint-note">
  <h2>两站的关系</h2>
  <ul>
    <li><strong>花絮站</strong>是作品侧的整理：短篇体裁（花絮／楔子／画外音），强调题材与人物关系。</li>
    <li><strong>跑团站</strong>是记录侧的整理：真实发生的跑团过程，强调时间线与场次。</li>
    <li><strong>设定站</strong>是辞书侧的整理：《黑柩设定集·第一版》按卷／节／词条拆解，便于查概念。</li>
    <li>花絮站与跑团站<strong>互相链接</strong>（跑团站里的名词链到花絮站标签页）。</li>
    <li>设定站<strong>暂不与两站互链</strong>——设定集仍在演进，等它稳定后再接。</li>
    <li>三站<strong>各有一套导航与首页</strong>，标签体系互相独立（跑团含平行世界与 if 线，同名不一定是同一实体）。</li>
  </ul>
</section>

<footer class="site-foot">
  <p class="disclaimer">{disc}</p>
  <p>《黑柩》相关内容版权归原作者所有。</p>
  {f'<p class="muted">{domain}</p>' if domain else ''}
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
.station-card .card-warn{display:block;margin-top:.5rem;font-size:.8rem;
color:#d98b2b;border-top:1px dashed var(--line);padding-top:.4rem}
.joint-warns{margin:1.2rem 0}
.joint-warns .warn{background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:.55rem .9rem;margin:.45rem 0;font-size:.9rem;color:var(--muted)}
.joint-warns .warn.spoiler{border-left:3px solid #d98b2b}
.joint-warns .warn.eating{border-left:3px solid var(--accent)}
.joint-warns strong{color:var(--fg)}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    if args.clean:
        shutil.rmtree(DOCS, ignore_errors=True)
        print("已清空 docs/")

    n = 0
    for tool, label in (("build_site.py", "花絮站"), ("build_trpg.py", "跑团站"),
                        ("build_lore.py", "设定站")):
        code, out = run(tool)
        print("[%s] %s %s" % ("OK " if code == 0 else "FAIL", label, out[:220]))

    n += write_if_changed(os.path.join(DOCS, "index.html"), joint_index())
    n += write_if_changed(os.path.join(DOCS, "assets", "joint.css"), JOINT_CSS)
    print(json.dumps({"joint_index_written": n}, ensure_ascii=False))


if __name__ == "__main__":
    main()
