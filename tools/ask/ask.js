/* ══════════════════════════════════════════════════════════════
   黑柩 Wiki · 跨站检索组件  ask.js
   ──────────────────────────────────────────────────────────────
   用途：把「花絮 / 跑团 / 设定 / 分析」四站的搜索索引合并成一个
        跨站检索框。可独立成页（docs/ask.html），也可嵌进 WordPress
        （只要一个 <div id="heijiu-ask"></div> + 引用本文件与 ask.css）。

   为什么不做后端：GitHub Pages 对 JSON 发 `Access-Control-Allow-Origin: *`，
        所以宿主页（如 darkcoffin.hubingsf.cn）能直接跨域读取索引。

   为什么不用向量检索：DeepSeek 没有 embedding API；而本站有 7,267 条
        结构化索引（标题/标签/卷名/季场），关键词加权已够用，且零成本。

   依赖：无。ES5 语法，兼容老浏览器。
   ══════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  // ── 站点根 URL：从本脚本自身的 src 推断，WP 引用时也能正确得出 ──
  var BASE = (function () {
    var s = document.currentScript;
    if (!s) {
      var all = document.getElementsByTagName("script");
      for (var i = all.length - 1; i >= 0; i--) {
        if (/ask\.js(\?|$)/.test(all[i].src)) { s = all[i]; break; }
      }
    }
    if (s && s.src) return s.src.replace(/assets\/ask\.js(\?.*)?$/, "");
    return "https://darkcoffin-wiki.hubingsf.cn/";
  })();

  // ── 四站索引：顺序 = 显示顺序 = 「原典 → 短篇 → 实录 → 解读」 ──
  //    注意花絮站的索引在共享的 assets/ 下（它自己产出的那份）
  var STATIONS = [
    { key: "lore",   name: "设定站", json: "lore/assets/search.json",   note: "作者原典 · 含剧透" },
    { key: "huaxu",  name: "花絮站", json: "assets/search.json",        note: "短篇与画外音" },
    { key: "trpg",   name: "跑团站", json: "trpg/assets/search.json",   note: "跑团实录" },
    { key: "report", name: "分析站", json: "report/assets/search.json", note: "读者分析 · AI 撰写" }
  ];

  // ── 别名：中文设定里同一事物常有简称/全称并存，纯子串匹配会漏 ──
  var ALIAS = {
    "希联": ["希望联邦"],
    "希望联邦": ["希联"],
    "进盟": ["进化者同盟"],
    "进化者同盟": ["进盟"],
    "教团国": ["启示录教团国"],
    "启示录教团国": ["教团国"],
    "戡乱政府": ["北沙政府"],
    "北沙政府": ["戡乱政府"],
    "神帝": ["神圣希望帝国"],
    "神圣希望帝国": ["神帝"],
    "门廊中立国": ["走廊区"],
    "走廊区": ["门廊中立国"],
    "斯卡雷特": ["斯卡雷特家族", "斯卡雷特帝国"],
    "始源血族": ["血族"],
    "适格者": ["适格者等级制度"],
    "天空教": ["天空教"],
    "天使": ["天使作战兵器"],
    "灵魂学": ["灵魂"]
  };

  var LIMIT_PER_STATION = 6;
  var LIMIT_TOTAL = 20;

  // ══════════════════════════════════════════════════════════
  // 工具
  // ══════════════════════════════════════════════════════════
  function norm(s) {
    return String(s == null ? "" : s)
      .toLowerCase()
      .replace(/[\u3000\s]+/g, "")
      .replace(/[（）()「」『』【】《》〈〉·・,，、。.;；:：!！?？"'“”‘’\-—–_/\\|~～*]/g, "");
  }

  function termsOf(q) {
    var raw = String(q || "").split(/[\s,，、。；;]+/);
    var out = [], i, j, n, ext;
    for (i = 0; i < raw.length; i++) {
      n = norm(raw[i]);
      if (!n) continue;
      out.push(n);
      ext = ALIAS[n];
      if (ext) { for (j = 0; j < ext.length; j++) out.push(norm(ext[j])); }
    }
    // 去重
    var uniq = [];
    for (i = 0; i < out.length; i++) {
      if (out[i] && uniq.indexOf(out[i]) < 0) uniq.push(out[i]);
    }
    return uniq;
  }

  function urlOf(st, e) {
    var u = BASE + st + "/" + (e.id || "");
    if (e.slug) u += "-" + e.slug;
    u += ".html";
    if (e.frag) u += "#" + e.frag;
    return u;
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // 结果卡片的第二行：按站取不同字段
  function metaOf(st, e) {
    var bits = [];
    if (st === "trpg") {
      if (e.season) bits.push(e.season + (e.n ? " 第" + e.n + "场" : ""));
      if (e.kind) bits.push(e.kind);
    } else if (st === "report") {
      if (e.kind) bits.push(e.kind);
    } else {
      if (e.kind) bits.push(e.kind);
      if (e.chars) bits.push(e.chars + " 字");
    }
    return bits.join(" · ");
  }

  // ══════════════════════════════════════════════════════════
  // 打分
  // ══════════════════════════════════════════════════════════
  function scoreOf(e, list, fullQuery) {
    var t = norm(e.title);
    var tags = norm((e.tags || []).join(" "));
    var kind = norm(e.kind || "");
    var season = norm(e.season || "");
    var s = 0, hit = 0, i, w;

    for (i = 0; i < list.length; i++) {
      w = list[i];
      if (!w) continue;
      if (t.indexOf(w) >= 0) { s += 42; hit++; }
      else if (tags.indexOf(w) >= 0) { s += 18; hit++; }
      else if (kind.indexOf(w) >= 0 || season.indexOf(w) >= 0) { s += 9; hit++; }
    }
    if (!hit) return 0;

    // 整串出现在标题里，说明是高度相关的条目
    var fq = norm(fullQuery);
    if (fq && t.indexOf(fq) >= 0) s += 55;

    // 标题越短越可能是「定义条」，比长标题更值得排前面
    s += Math.max(0, 24 - Math.min(24, Math.floor(t.length / 3)));

    // 跑团站的场内细目（场次/剧情/在场/地点）数量极大，
    // 不压权重会把设定词条整个淹掉
    if (e.kind === "场次" || e.kind === "剧情" || e.kind === "在场" || e.kind === "地点") s -= 10;
    return s;
  }

  // ══════════════════════════════════════════════════════════
  // 数据加载（懒加载 + 缓存）
  // ══════════════════════════════════════════════════════════
  var cache = null;       // [{key,name,note,entries}]
  var loading = null;

  function loadAll(onProgress) {
    if (cache) return Promise.resolve(cache);
    if (loading) return loading;

    var done = 0;
    loading = Promise.all(STATIONS.map(function (st) {
      return fetch(BASE + st.json, { cache: "force-cache" })
        .then(function (r) {
          if (!r.ok) throw new Error(st.name + " 索引 HTTP " + r.status);
          return r.json();
        })
        .then(function (d) {
          done++;
          if (onProgress) onProgress(done, STATIONS.length);
          return {
            key: st.key, name: st.name, note: st.note,
            entries: (d && d.entries) || []
          };
        })
        .catch(function (err) {
          done++;
          if (onProgress) onProgress(done, STATIONS.length);
          return { key: st.key, name: st.name, note: st.note, entries: [], failed: String(err) };
        });
    })).then(function (res) {
      cache = res;
      loading = null;
      return res;
    });
    return loading;
  }

  // ══════════════════════════════════════════════════════════
  // 检索
  // ══════════════════════════════════════════════════════════
  function search(data, query) {
    var list = termsOf(query);
    if (!list.length) return [];
    var out = [], total = 0, i, j, st, arr, sc;

    for (i = 0; i < data.length; i++) {
      st = data[i];
      arr = [];
      for (j = 0; j < st.entries.length; j++) {
        var e = st.entries[j];
        sc = scoreOf(e, list, query);
        if (sc > 0) arr.push({ e: e, sc: sc });
      }
      arr.sort(function (a, b) { return b.sc - a.sc; });
      if (arr.length > LIMIT_PER_STATION) arr = arr.slice(0, LIMIT_PER_STATION);
      total += arr.length;
      if (arr.length) out.push({ st: st, hits: arr });
    }

    // 总数超限时，按「每站第一条的分数」轮流取，尽量各站都有
    if (total > LIMIT_TOTAL) {
      var cut = [], picked = 0, round = 0, more = true;
      while (more && picked < LIMIT_TOTAL) {
        more = false;
        for (i = 0; i < out.length && picked < LIMIT_TOTAL; i++) {
          if (out[i].hits[round]) {
            cut.push({ st: out[i].st, hit: out[i].hits[round] });
            picked++;
            if (out[i].hits[round + 1]) more = true;
          }
        }
        round++;
      }
      // 重新按站聚合
      var bySt = {};
      for (i = 0; i < cut.length; i++) {
        var k = cut[i].st.key;
        if (!bySt[k]) bySt[k] = { st: cut[i].st, hits: [] };
        bySt[k].hits.push(cut[i].hit);
      }
      var reduced = [];
      for (i = 0; i < out.length; i++) {
        var kk = out[i].st.key;
        if (bySt[kk]) reduced.push(bySt[kk]);
      }
      out = reduced;
    }
    return out;
  }

  // ══════════════════════════════════════════════════════════
  // 渲染
  // ══════════════════════════════════════════════════════════
  function hitHtml(st, hit) {
    var e = hit.e, meta = metaOf(st.key, e), tags = (e.tags || []).slice(0, 4);
    var tagHtml = "";
    for (var i = 0; i < tags.length; i++) {
      tagHtml += '<span class="ha-tag">' + esc(tags[i]) + "</span>";
    }
    return '<a class="ha-hit" href="' + esc(urlOf(st.key, e)) + '">' +
      '<span class="ha-hit-t">' + esc(e.title || "(无标题)") + "</span>" +
      '<p class="ha-hit-m">' +
      (meta ? '<span class="ha-from">' + esc(meta) + "</span>" : "") +
      (tagHtml ? tagHtml : "") +
      "</p></a>";
  }

  function render(box, groups, query) {
    if (!groups.length) {
      box.innerHTML = '<p class="ha-empty"><b>没找到</b>「' + esc(query) + '」。' +
        "试试更短的关键词（比如只输入「希联」「北沙」「天使」），" +
        "或去掉引号和标点。</p>";
      return;
    }
    var html = "";
    for (var i = 0; i < groups.length; i++) {
      var g = groups[i];
      html += '<div class="ha-group"><p class="ha-group-h">' + esc(g.st.name) +
        ' <span class="n">' + g.hits.length + " 条</span>" +
        '<span class="n">· ' + esc(g.st.note) + "</span></p>";
      for (var j = 0; j < g.hits.length; j++) {
        html += hitHtml(g.st, g.hits[j]);
      }
      html += "</div>";
    }
    box.innerHTML = html;
  }

  // ══════════════════════════════════════════════════════════
  // 启动
  // ══════════════════════════════════════════════════════════
  function mount(host) {
    host.innerHTML =
      '<div class="ha-bar">' +
        '<input class="ha-q" type="search" autocomplete="off" ' +
          'placeholder="问一句，比如：希联的意识形态是什么" aria-label="检索《黑柩》四个站">' +
        '<button class="ha-go" type="button">检索</button>' +
      "</div>" +
      '<p class="ha-meta">跨四站检索：设定 · 花絮 · 跑团 · 分析</p>' +
      '<div class="ha-out"></div>' +
      '<p class="ha-legend">结果按站分组：<b>设定站</b>是作者原典（含剧透），' +
        "<b>分析站</b>是读者的 AI 分析、不是作者设定。点任一条进入原文核对。</p>";

    var q = host.querySelector(".ha-q");
    var go = host.querySelector(".ha-go");
    var out = host.querySelector(".ha-out");

    function run() {
      var query = q.value.trim();
      if (!query) { out.innerHTML = ""; return; }
      out.innerHTML = '<p class="ha-loading">正在加载索引…</p>';
      loadAll(function (d, n) {
        out.innerHTML = '<p class="ha-loading">正在加载索引… ' + d + "/" + n + "</p>";
      }).then(function (data) {
        var t0 = (window.performance && performance.now) ? performance.now() : 0;
        var groups = search(data, query);
        var t1 = (window.performance && performance.now) ? performance.now() : 0;
        render(out, groups, query);
        var n = 0;
        for (var i = 0; i < groups.length; i++) n += groups[i].hits.length;
        host.querySelector(".ha-meta").innerHTML =
          "跨四站检索：设定 · 花絮 · 跑团 · 分析　｜　找到 <b>" + n + "</b> 条" +
          (t1 ? '　<span style="opacity:.6">' + Math.round(t1 - t0) + " ms</span>" : "");
        // 便于分享
        if (window.history && history.replaceState) {
          history.replaceState(null, "", "#q=" + encodeURIComponent(query));
        }
      });
    }

    go.addEventListener("click", run);
    q.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" || ev.keyCode === 13) { ev.preventDefault(); run(); }
    });

    // 直接从 #q=… 恢复（分享链接）
    var m = /[#&]q=([^&]+)/.exec(location.hash || "");
    if (m) {
      try { q.value = decodeURIComponent(m[1]); } catch (e) { q.value = m[1]; }
      run();
    } else {
      // 预热索引，让第一次输入不用等
      loadAll();
    }
    q.focus();
  }

  function boot() {
    var host = document.getElementById("heijiu-ask");
    if (host) { mount(host); return; }
    // 允许宿主用 data-ask 标记任意容器
    var alt = document.querySelector("[data-heijiu-ask]");
    if (alt) { alt.id = "heijiu-ask"; mount(alt); }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
