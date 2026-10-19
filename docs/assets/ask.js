/* ══════════════════════════════════════════════════════════════
   黑柩 Wiki · 跨站检索 + AI 问答
   ══════════════════════════════════════════════════════════════
   档 1：跨四站关键词检索（零成本、零风险）。
   档 2：在检索结果之上，让用户用自己的 DeepSeek API key 问一句。

   设计要点
   · 纯前端：GitHub Pages 的 JSON 带 `Access-Control-Allow-Origin: *`，
     DeepSeek API 也回显任意 Origin，所以宿主页（WordPress）能直连两者，
     不需要任何后端、不经过本站服务器。
   · API key 只存 sessionStorage（关掉标签页即失效），绝不外传。
   · 只把检索到的 5 条正文作为资料喂给模型，并强制标注来源编号，
     避免模型脱离资料自由发挥。
   · 依赖：无。ES5 语法。
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

  // ── 四站索引 ──
  var STATIONS = [
    { key: "lore",   name: "设定站", json: "lore/assets/search.json",   note: "作者原典 · 含剧透" },
    { key: "huaxu",  name: "花絮站", json: "assets/search.json",        note: "短篇与画外音" },
    { key: "trpg",   name: "跑团站", json: "trpg/assets/search.json",   note: "跑团实录" },
    { key: "report", name: "分析站", json: "report/assets/search.json", note: "读者分析 · AI 撰写" }
  ];

  // ── 别名（中文设定里简称/全称并存）──
  var ALIAS = {
    "希联": ["希望联邦"], "希望联邦": ["希联"],
    "进盟": ["进化者同盟"], "进化者同盟": ["进盟"],
    "教团国": ["启示录教团国"], "启示录教团国": ["教团国"],
    "戡乱政府": ["北沙政府"], "北沙政府": ["戡乱政府"],
    "神帝": ["神圣希望帝国"], "神圣希望帝国": ["神帝"],
    "门廊中立国": ["走廊区"], "走廊区": ["门廊中立国"],
    "斯卡雷特": ["斯卡雷特家族", "斯卡雷特帝国"],
    "适格者": ["适格者等级制度"],
    "天使": ["天使作战兵器"],
    "灵魂学": ["灵魂"]
  };

  var LIMIT_PER_STATION = 6;
  var LIMIT_TOTAL = 20;
  var AI_PICKS = 5;          // 喂给模型的资料条数
  var AI_CTX_CHARS = 2600;   // 每条资料截断字数

  // ══════════════════════════════════════════════════════════
  // 工具
  // ══════════════════════════════════════════════════════════
  function norm(s) {
    return String(s == null ? "" : s)
      .toLowerCase()
      .replace(/[\u3000\s]+/g, "")
      .replace(/[（）()「」『』【】《》〈〉·・,，、。.;；:：!！?？"'“”‘’\-—–_/\\|~～*]/g, "");
  }

  // ── 中文长句的分词 ──
  // 中文没有空格，整句当一个词去匹配必然落空。
  // 实测：「希联的意识形态是什么」按整串匹配 = 0 条；
  // 按下面的停用词切开后 → ["希联", "意识形态"]，立刻能命中几十条。
  // 停用词只收**明确的虚词/疑问词**，并且按长度降序替换（先长后短），
  // 避免把「形态」这种实词切碎。
  var STOPWORDS = [
    "为什么", "什么", "怎么", "怎样", "如何", "哪些", "哪个", "多少",
    "请问", "介绍", "讲讲", "说说", "关于", "一下", "会不会", "是不是",
    "有没有", "可以", "能否", "能不能", "的话", "以及", "还有",
    "的", "了", "是", "在", "有", "和", "与", "及", "或", "也", "都",
    "吗", "呢", "吧", "啊", "呀", "谁", "这", "那", "个", "就", "还",
    "我", "你", "他", "她", "它", "们", "要", "想", "能"
  ].sort(function (a, b) { return b.length - a.length; });

  function termsOf(q) {
    var raw = String(q || "").trim();
    if (!raw) return [];
    var out = [], i, j, n, ext, seg, cut;

    // 1) 先按空格/标点粗切
    var segs = raw.split(/[\s,，、。；;？?!！]+/);

    // 2) 每段再用停用词切开
    for (i = 0; i < segs.length; i++) {
      seg = segs[i];
      if (!seg) continue;
      cut = seg;
      for (j = 0; j < STOPWORDS.length; j++) {
        cut = cut.split(STOPWORDS[j]).join("\u0001");
      }
      var parts = cut.split("\u0001");
      for (j = 0; j < parts.length; j++) {
        n = norm(parts[j]);
        if (n) out.push(n);
      }
    }

    // 3) 切完什么都不剩（整句都是虚词）→ 退回原句
    if (!out.length) {
      n = norm(raw);
      if (n) out.push(n);
    }

    // 3.5) 丢掉单字词——「一个根本不存在的词」会被切成 ["根本不存在", "词"]，
    //      而单字「词」能匹配到所有含「词条」的标题，造成满屏假阳性。
    //      只有「过滤后什么都不剩」时才保留（否则搜单字人名如「渊」就搜不到了）。
    var multi = [];
    for (i = 0; i < out.length; i++) {
      if (out[i].length >= 2) multi.push(out[i]);
    }
    if (multi.length) out = multi;

    // 4) 短句额外保留「整句」这一个 term，提高精确匹配的权重
    var full = norm(raw);
    if (full && full.length >= 2 && full.length <= 10) out.push(full);

    // 5) 别名扩展（希联 ↔ 希望联邦 …）
    var expanded = [];
    for (i = 0; i < out.length; i++) {
      expanded.push(out[i]);
      ext = ALIAS[out[i]];
      if (ext) { for (j = 0; j < ext.length; j++) expanded.push(norm(ext[j])); }
    }

    // 6) 去重
    var uniq = [];
    for (i = 0; i < expanded.length; i++) {
      if (expanded[i] && uniq.indexOf(expanded[i]) < 0) uniq.push(expanded[i]);
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

    var fq = norm(fullQuery);
    if (fq && t.indexOf(fq) >= 0) s += 55;
    s += Math.max(0, 24 - Math.min(24, Math.floor(t.length / 3)));
    if (e.kind === "场次" || e.kind === "剧情" || e.kind === "在场" || e.kind === "地点") s -= 10;
    return s;
  }

  // ══════════════════════════════════════════════════════════
  // 索引加载
  // ══════════════════════════════════════════════════════════
  var cache = null, loading = null;

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
          return { key: st.key, name: st.name, note: st.note, entries: (d && d.entries) || [] };
        })
        .catch(function () {
          done++;
          if (onProgress) onProgress(done, STATIONS.length);
          return { key: st.key, name: st.name, note: st.note, entries: [] };
        });
    })).then(function (res) {
      cache = res; loading = null; return res;
    });
    return loading;
  }

  // ══════════════════════════════════════════════════════════
  // 检索
  // ══════════════════════════════════════════════════════════
  function search(data, query) {
    var list = termsOf(query);
    if (!list.length) return [];
    var out = [], i, j, st, arr, sc, e;

    for (i = 0; i < data.length; i++) {
      st = data[i];
      arr = [];
      for (j = 0; j < st.entries.length; j++) {
        e = st.entries[j];
        sc = scoreOf(e, list, query);
        if (sc > 0) arr.push({ e: e, sc: sc });
      }
      arr.sort(function (a, b) { return b.sc - a.sc; });
      if (arr.length > LIMIT_PER_STATION) arr = arr.slice(0, LIMIT_PER_STATION);
      if (arr.length) out.push({ st: st, hits: arr });
    }

    var total = 0;
    for (i = 0; i < out.length; i++) total += out[i].hits.length;

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
      var bySt = {}, k;
      for (i = 0; i < cut.length; i++) {
        k = cut[i].st.key;
        if (!bySt[k]) bySt[k] = { st: cut[i].st, hits: [] };
        bySt[k].hits.push(cut[i].hit);
      }
      var reduced = [];
      for (i = 0; i < out.length; i++) {
        k = out[i].st.key;
        if (bySt[k]) reduced.push(bySt[k]);
      }
      out = reduced;
    }
    return out;
  }

  // ══════════════════════════════════════════════════════════
  // 渲染检索结果
  // ══════════════════════════════════════════════════════════
  function hitHtml(st, hit) {
    var e = hit.e, meta = metaOf(st.key, e), tags = (e.tags || []).slice(0, 4);
    var tagHtml = "", i;
    for (i = 0; i < tags.length; i++) {
      tagHtml += '<span class="ha-tag">' + esc(tags[i]) + "</span>";
    }
    return '<a class="ha-hit" href="' + esc(urlOf(st.key, e)) + '">' +
      '<span class="ha-hit-t">' + esc(e.title || "(无标题)") + "</span>" +
      '<p class="ha-hit-m">' +
      (meta ? '<span class="ha-from">' + esc(meta) + "</span>" : "") +
      tagHtml + "</p></a>";
  }

  function render(box, groups, query) {
    if (!groups.length) {
      box.innerHTML = '<p class="ha-empty"><b>没找到</b>「' + esc(query) + '」。' +
        "试试更短的关键词（比如只输入「希联」「北沙」「天使」），或去掉引号和标点。</p>";
      return;
    }
    var html = "", i, j, g;
    for (i = 0; i < groups.length; i++) {
      g = groups[i];
      html += '<div class="ha-group"><p class="ha-group-h">' + esc(g.st.name) +
        ' <span class="n">' + g.hits.length + " 条</span>" +
        '<span class="n">· ' + esc(g.st.note) + "</span></p>";
      for (j = 0; j < g.hits.length; j++) html += hitHtml(g.st, g.hits[j]);
      html += "</div>";
    }
    box.innerHTML = html;
  }

  // ══════════════════════════════════════════════════════════
  // 档 2：AI 问答
  // ══════════════════════════════════════════════════════════

  var KEY_STORE = "heijiu_ds_key";
  var API_URL = "https://api.deepseek.com/chat/completions";
  var MODEL = "deepseek-flash";

  function getKey() { try { return sessionStorage.getItem(KEY_STORE) || ""; } catch (e) { return ""; } }
  function setKey(k) { try { sessionStorage.setItem(KEY_STORE, k); } catch (e) {} }
  function clearKey() { try { sessionStorage.removeItem(KEY_STORE); } catch (e) {} }

  // 从页面 HTML 里抽出正文纯文本
  function textFromHtml(html) {
    var doc;
    try { doc = new DOMParser().parseFromString(html, "text/html"); }
    catch (e) { return ""; }
    if (!doc) return "";
    var drop = doc.querySelectorAll(
      "script,style,nav,header.site-head,footer,.search-wrap,.q-results,.toc,.pn,.pn-nav,.back,.crumbs,.chips,.cats,.meta,.site-foot"
    );
    for (var i = 0; i < drop.length; i++) {
      if (drop[i].parentNode) drop[i].parentNode.removeChild(drop[i]);
    }
    // 表格单元格之间加分隔，避免文字粘在一起
    var tds = doc.querySelectorAll("td,th");
    for (i = 0; i < tds.length; i++) {
      if (tds[i].nextSibling) tds[i].appendChild(doc.createTextNode(" | "));
    }
    var main = doc.querySelector("main") || doc.body;
    var txt = (main && main.textContent) || "";
    return txt.replace(/\s+/g, " ").trim();
  }

  function fetchPicks(groups) {
    // 按「设定 → 花絮 → 跑团 → 分析」的顺序挑，每站最多 2 条，总数 AI_PICKS
    var picks = [], i, j, g;
    var perStation = 2;
    for (i = 0; i < groups.length && picks.length < AI_PICKS; i++) {
      g = groups[i];
      for (j = 0; j < g.hits.length && j < perStation && picks.length < AI_PICKS; j++) {
        picks.push({ st: g.st, e: g.hits[j].e });
      }
    }
    return picks;
  }

  function buildContext(picks, onProgress) {
    var done = 0;
    return Promise.all(picks.map(function (p, idx) {
      var url = urlOf(p.st.key, p.e);
      return fetch(url, { cache: "force-cache" })
        .then(function (r) { return r.ok ? r.text() : ""; })
        .then(function (html) {
          done++;
          if (onProgress) onProgress(done, picks.length);
          return {
            n: idx + 1,
            st: p.st.name, stKey: p.st.key,
            title: p.e.title || "",
            meta: metaOf(p.st.key, p.e),
            url: url,
            text: textFromHtml(html).slice(0, AI_CTX_CHARS)
          };
        })
        .catch(function () {
          done++;
          if (onProgress) onProgress(done, picks.length);
          return null;
        });
    })).then(function (arr) {
      var out = [], i;
      for (i = 0; i < arr.length; i++) if (arr[i] && arr[i].text) out.push(arr[i]);
      // 重新编号，保证与 prompt 里的 [n] 一致
      for (i = 0; i < out.length; i++) out[i].n = i + 1;
      return out;
    });
  }

  function systemPrompt() {
    return [
      "你是《黑柩》wiki 的检索助手。用户会问关于《黑柩》世界观的问题，",
      "下面会给你从 wiki 里检索到的资料（编号资料）。",
      "",
      "回答规则（必须遵守）：",
      "1. 只能依据资料回答。资料里没有的，直接说「wiki 里没有这一条」，并建议换个关键词或去对应站点查。不要用你的一般知识补充。",
      "2. 每处结论后面用 [编号] 标注依据，例如 [1]、[2]。",
      "3. 资料之间互相矛盾时（这个 wiki 存在作者自称的「吃书」），如实说「这里存在异说」并并列列出，不要自行调和。",
      "4. 标注为「分析站」的资料是读者的 AI 分析，不是作者设定；引用时必须说明这一点。",
      "5. 不要编造资料里没有的人物、事件、数字。",
      "6. 简洁：一般 150~400 字；用户要求展开时才写长。",
      "",
      "风格：中文，直接回答，不要客套话，不要重复问题。"
    ].join("\n");
  }

  function contextPrompt(picks, sources, question) {
    var parts = ["<资料>"];
    for (var i = 0; i < sources.length; i++) {
      var s = sources[i];
      parts.push("[" + s.n + "] " + s.st + " · " + s.title +
        (s.meta ? "（" + s.meta + "）" : ""));
      parts.push(s.text);
      parts.push("");
    }
    parts.push("</资料>");
    parts.push("");
    parts.push("问题：" + question);
    return parts.join("\n");
  }

  // SSE 流式读取
  function streamChat(key, messages, onDelta, onDone, onError) {
    var ctrl = null;
    try { ctrl = new AbortController(); } catch (e) {}

    fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key
      },
      body: JSON.stringify({
        model: MODEL,
        messages: messages,
        stream: true,
        stream_options: { include_usage: true },
        temperature: 0.2
      }),
      signal: ctrl ? ctrl.signal : undefined
    }).then(function (r) {
      if (!r.ok) {
        return r.text().then(function (t) {
          var msg = t;
          try { msg = JSON.parse(t).error.message || t; } catch (e) {}
          onError(r.status, msg);
        });
      }
      var reader = r.body.getReader();
      var dec = new TextDecoder("utf-8");
      var buf = "", full = "", usage = null;

      function pump() {
        return reader.read().then(function (res) {
          if (res.done) {
            onDone(full, usage);
            return;
          }
          buf += dec.decode(res.value, { stream: true });
          var lines = buf.split("\n");
          buf = lines.pop();
          for (var i = 0; i < lines.length; i++) {
            var ln = lines[i].trim();
            if (!ln || ln.indexOf("data:") !== 0) continue;
            var payload = ln.slice(5).trim();
            if (payload === "[DONE]") continue;
            try {
              var j = JSON.parse(payload);
              if (j.usage) usage = j.usage;
              var d = j.choices && j.choices[0] && j.choices[0].delta;
              if (d && d.content) { full += d.content; onDelta(d.content, full); }
            } catch (e) {}
          }
          return pump();
        });
      }
      return pump();
    }).catch(function (err) {
      onError(0, String(err && err.message || err));
    });

    return { abort: function () { if (ctrl) ctrl.abort(); } };
  }

  // 把回答里的 [n] 变成可点击的引用上标
  function renderAnswer(text, sources) {
    var out = esc(text);
    out = out.replace(/\[(\d{1,2})\]/g, function (m, d) {
      var n = parseInt(d, 10);
      if (n >= 1 && n <= sources.length) {
        return '<sup class="ha-cite"><a href="#ha-ref-' + n + '">[' + n + "]</a></sup>";
      }
      return m;
    });
    // 粗体
    out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    // 换行
    out = out.replace(/\n{2,}/g, "</p><p>").replace(/\n/g, "<br>");
    return "<p>" + out + "</p>";
  }

  function sourcesHtml(sources) {
    var html = '<p class="ha-src-h">资料来源（点开可核对原文）</p>';
    for (var i = 0; i < sources.length; i++) {
      var s = sources[i];
      html += '<a class="ha-src" id="ha-ref-' + s.n + '" href="' + esc(s.url) + '">' +
        '<span class="n">[' + s.n + "]</span>" +
        '<span class="t">' + esc(s.title) + "</span>" +
        '<span class="m">' + esc(s.st) + (s.meta ? " · " + esc(s.meta) : "") + "</span>" +
        "</a>";
    }
    return html;
  }

  function estCost(srcChars, outChars) {
    // deepseek-flash 高峰价：输入未命中 2 元/M、输出 8 元/M；中文 1 字≈0.6 token
    var tin = (srcChars * 0.6 + 420);
    var tout = outChars * 0.6;
    return (tin / 1e6 * 2 + tout / 1e6 * 8);
  }

  // ══════════════════════════════════════════════════════════
  // 挂载
  // ══════════════════════════════════════════════════════════
  // ══════════════════════════════════════════════════════════
  // 两种挂载模式
  //   mountSearch —— 检索页：跨四站检索 + 一次性 AI 解释（无追问）
  //   mountChat   —— 黑柩问答：自由对话，每轮自动检索并补料
  // ══════════════════════════════════════════════════════════
  var MAX_TURNS = 8;       // 对话最多轮数
  var MAX_SOURCES = 10;    // 资料总数上限（首次 5 + 追问每次最多 2）

  // 回答正文统一包在 .ha-ans 里（样式与测试都依赖这个容器）
  function ansHtml(text, sources) {
    return '<div class="ha-ans">' + renderAnswer(text, sources) + "</div>";
  }

  function fmtNum(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  function warningHtml() {
    return '<p class="ha-warn">⚠️ 回答由 AI 依据检索到的资料生成，<b>可能出错或遗漏</b>；' +
      "以链接到的原文为准。资料矛盾处会标「异说」。</p>" +
      '<p class="ha-warn">🔑 你的 API key <b>只存在本页会话里</b>（关闭标签页即失效），' +
      "不会上传到本站服务器，也不会被记录。</p>";
  }

  function keyRowHtml() {
    return '<div class="ha-key-row">' +
      '<input class="ha-key" type="password" autocomplete="off" spellcheck="false" ' +
        'placeholder="sk-… （DeepSeek API key，仅本标签页有效）" value="' + esc(getKey()) + '">' +
      '<button class="ha-start" type="button">开始</button>' +
      '<button class="ha-forget" type="button" title="清除本标签页里的 key">清除 key</button>' +
      "</div>";
  }

  // 从回答里挑出真正被引用的资料
  function citedSources(text, sources) {
    var seen = {}, out = [], m, i;
    var re = /\[(\d{1,2})\]/g;
    while ((m = re.exec(text))) {
      var n = parseInt(m[1], 10);
      if (n >= 1 && n <= sources.length && !seen[n]) {
        seen[n] = 1;
        for (i = 0; i < sources.length; i++) {
          if (sources[i].n === n) { out.push(sources[i]); break; }
        }
      }
    }
    return out;
  }

  function failHint(status) {
    if (status === 401) return "API key 无效或已过期。";
    if (status === 402) return "账户余额不足。";
    if (status === 429) return "请求太频繁，稍后再试。";
    if (status === 0) return "网络错误（可能是跨域被拦或断网）。";
    return "请求失败（HTTP " + status + "）。";
  }

  // ══════════════════════════════════════════════════════════
  // ① 检索页
  // ══════════════════════════════════════════════════════════
  function mountSearch(host) {
    host.classList.add("heijiu-ui");
    host.innerHTML =
      '<div class="ha-bar">' +
        '<input class="ha-q" type="search" autocomplete="off" ' +
          'placeholder="搜一句话，比如：希联的意识形态" aria-label="检索《黑柩》四个站">' +
        '<button class="ha-go" type="button">检索</button>' +
      "</div>" +
      '<p class="ha-meta">跨四站检索：设定 · 花絮 · 跑团 · 分析</p>' +
      '<div class="ha-out"></div>' +
      '<div class="ha-ai"></div>' +
      '<p class="ha-legend">结果按站分组：<b>设定站</b>是作者原典（含剧透），' +
        "<b>分析站</b>是读者的 AI 分析、不是作者设定。点任一条进入原文核对。" +
        ' 想连续对话？去 <a href="chat.html">黑柩问答</a>。</p>';

    var q = host.querySelector(".ha-q");
    var go = host.querySelector(".ha-go");
    var out = host.querySelector(".ha-out");
    var aiBox = host.querySelector(".ha-ai");
    var cur = { query: "", groups: [] };

    function run() {
      var query = q.value.trim();
      if (!query) { out.innerHTML = ""; aiBox.innerHTML = ""; return; }
      out.innerHTML = '<p class="ha-loading">正在加载索引…</p>';
      loadAll(function (d, n) {
        out.innerHTML = '<p class="ha-loading">正在加载索引… ' + d + "/" + n + "</p>";
      }).then(function (data) {
        var t0 = (window.performance && performance.now) ? performance.now() : 0;
        var groups = search(data, query);
        var t1 = (window.performance && performance.now) ? performance.now() : 0;
        render(out, groups, query);
        cur.query = query; cur.groups = groups;
        renderAIBar(aiBox, cur);
        var n = 0, i;
        for (i = 0; i < groups.length; i++) n += groups[i].hits.length;
        host.querySelector(".ha-meta").innerHTML =
          "跨四站检索：设定 · 花絮 · 跑团 · 分析　｜　找到 <b>" + n + "</b> 条" +
          (t1 ? '　<span style="opacity:.6">' + Math.round(t1 - t0) + " ms</span>" : "");
        if (window.history && history.replaceState) {
          history.replaceState(null, "", "#q=" + encodeURIComponent(query));
        }
      });
    }

    go.addEventListener("click", run);
    q.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" || ev.keyCode === 13) { ev.preventDefault(); run(); }
    });

    var m = /[#&]q=([^&]+)/.exec(location.hash || "");
    if (m) {
      try { q.value = decodeURIComponent(m[1]); } catch (e) { q.value = m[1]; }
      run();
    } else {
      loadAll();
    }
    q.focus();
  }

  // ── 检索页的 AI 入口 ──
  function renderAIBar(aiBox, cur) {
    if (!cur.groups.length) { aiBox.innerHTML = ""; return; }
    aiBox.innerHTML =
      '<div class="ha-ai-bar">' +
        '<button class="ha-aibtn" type="button">用 AI 解释这个问题</button>' +
        '<span class="ha-ai-note">读取上面最相关的 5 条正文作为资料；' +
        "需要你自己的 DeepSeek API key。想连续追问请用「黑柩问答」</span>" +
      "</div>";
    aiBox.querySelector(".ha-aibtn").addEventListener("click", function () {
      openOneShot(aiBox, cur);
    });
  }

  // ── 检索页：一次性问答（**没有追问**）──
  function openOneShot(aiBox, cur) {
    aiBox.innerHTML =
      '<div class="ha-ai-panel">' +
        warningHtml() +
        keyRowHtml() +
        '<div class="ha-chat"></div>' +
        '<div class="ha-again" hidden>' +
          '<button class="ha-restart" type="button">用同一批资料重新回答</button>' +
          '<a class="ha-tochead" href="chat.html">想连续追问 → 黑柩问答</a>' +
        "</div>" +
        '<p class="ha-status"></p>' +
      "</div>";

    var keyIn = aiBox.querySelector(".ha-key");
    var startBtn = aiBox.querySelector(".ha-start");
    var forgetBtn = aiBox.querySelector(".ha-forget");
    var chat = aiBox.querySelector(".ha-chat");
    var again = aiBox.querySelector(".ha-again");
    var restart = aiBox.querySelector(".ha-restart");
    var statusEl = aiBox.querySelector(".ha-status");
    var sources = [];
    var userMsg = "";

    forgetBtn.addEventListener("click", function () {
      clearKey(); keyIn.value = "";
      statusEl.textContent = "已清除本标签页保存的 key。";
    });

    function setBusy(v) {
      startBtn.disabled = v;
      keyIn.disabled = v;
      restart.disabled = v;
    }

    function turnEl(question) {
      chat.innerHTML = "";
      var wrap = document.createElement("div");
      wrap.className = "ha-turn";
      wrap.innerHTML =
        '<p class="ha-q-line"><span class="who">问</span>' + esc(question) + "</p>" +
        '<div class="ha-a-line"><span class="who ai">AI</span><div class="ha-body">' +
          '<p class="ha-loading">正在生成回答…</p></div></div>' +
        '<div class="ha-turn-src"></div>';
      chat.appendChild(wrap);
      return { body: wrap.querySelector(".ha-body"), src: wrap.querySelector(".ha-turn-src") };
    }

    function ask() {
      var k = (keyIn.value || "").trim();
      if (!k) { keyIn.focus(); return; }
      setKey(k);
      setBusy(true);
      statusEl.textContent = "正在读取资料…";
      chat.innerHTML = "";
      again.hidden = true;

      var picks = fetchPicks(cur.groups);
      buildContext(picks, function (d, n) {
        statusEl.textContent = "正在读取资料… " + d + "/" + n;
      }).then(function (src) {
        if (!src.length) {
          statusEl.textContent = "没能读到资料正文（网络或路径问题），无法作答。";
          setBusy(false);
          return;
        }
        sources = src.slice(0, 5);
        userMsg = contextPrompt(picks, sources, cur.query);

        var handle = turnEl(cur.query);
        var chars = 0, i;
        for (i = 0; i < sources.length; i++) chars += sources[i].text.length;
        statusEl.textContent = "正在生成回答…";

        var full = "";
        streamChat(
          k,
          [{ role: "system", content: systemPrompt() }, { role: "user", content: userMsg }],
          function (delta, body) {
            full = body;
            handle.body.innerHTML = ansHtml(body, sources);
          },
          function (body, usage) {
            setBusy(false);
            handle.body.innerHTML = ansHtml(body, sources);
            var cited = citedSources(body, sources);
            handle.src.innerHTML = cited.length ? sourcesHtml(cited) : "";

            var cost = estCost(chars, body.length);
            var u = document.createElement("p");
            u.className = "ha-usage";
            u.textContent = "以上为 AI 生成，请以资料来源为准。　" +
              (usage ? "输入 " + fmtNum(usage.prompt_tokens || 0) + " / 输出 " +
                fmtNum(usage.completion_tokens || 0) + " tokens"
                : "约 " + fmtNum(Math.round(chars * 0.6)) + " 输入 tokens") +
              "　本轮约 ¥" + cost.toFixed(4);
            handle.body.parentNode.appendChild(u);
            statusEl.textContent = "资料 " + sources.length + " 条（约 " +
              fmtNum(chars) + " 字）。想继续追问请去「黑柩问答」。";
            again.hidden = false;
          },
          function (status, msg) {
            setBusy(false);
            handle.body.innerHTML = '<p class="ha-empty"><b>' + esc(failHint(status)) +
              "</b><br>" + esc(String(msg || "").slice(0, 300)) + "</p>";
          }
        );
      });
    }

    startBtn.addEventListener("click", ask);
    restart.addEventListener("click", ask);
    keyIn.focus();
  }

  // ══════════════════════════════════════════════════════════
  // ② 黑柩问答（自由对话）
  // ══════════════════════════════════════════════════════════
  function mountChat(host) {
    var sess = {
      system: systemPrompt(),
      sources: [],
      history: [],
      turns: 0,
      cost: 0
    };
    var busy = false;

    host.classList.add("heijiu-ui");
    host.innerHTML =
      '<div class="ha-chatpanel">' +
        warningHtml() +
        keyRowHtml() +
        '<div class="ha-chat"></div>' +
        '<div class="ha-ask-row">' +
          '<input class="ha-follow" type="search" autocomplete="off" ' +
            'placeholder="问一句，比如：希联的意识形态是什么" aria-label="向黑柩问答提问">' +
          '<button class="ha-send" type="button">发送</button>' +
          '<button class="ha-end" type="button" title="清空对话，重新开始">清空对话</button>' +
        "</div>" +
        '<p class="ha-status"></p>' +
      "</div>";

    var keyIn = host.querySelector(".ha-key");
    var forgetBtn = host.querySelector(".ha-forget");
    var chat = host.querySelector(".ha-chat");
    var followIn = host.querySelector(".ha-follow");
    var sendBtn = host.querySelector(".ha-send");
    var endBtn = host.querySelector(".ha-end");
    var statusEl = host.querySelector(".ha-status");

    forgetBtn.addEventListener("click", function () {
      clearKey(); keyIn.value = "";
      statusEl.textContent = "已清除本标签页保存的 key。";
    });

    function setBusy(v) {
      busy = v;
      sendBtn.disabled = v;
      keyIn.disabled = v;
      followIn.disabled = v;
    }

    function updateStatus(extra) {
      var chars = 0, i;
      for (i = 0; i < sess.sources.length; i++) chars += sess.sources[i].text.length;
      statusEl.textContent = (extra ? extra + "　" : "") +
        (sess.turns
          ? "已 " + sess.turns + " 轮 · 资料 " + sess.sources.length + " 条（约 " +
            fmtNum(chars) + " 字）· 累计估算 ¥" + sess.cost.toFixed(4) +
            (sess.turns >= MAX_TURNS ? "　｜　已达轮数上限，点「清空对话」重开" : "")
          : "");
    }

    function addTurn(question) {
      var wrap = document.createElement("div");
      wrap.className = "ha-turn";
      wrap.innerHTML =
        '<p class="ha-q-line"><span class="who">问</span>' + esc(question) + "</p>" +
        '<div class="ha-a-line"><span class="who ai">AI</span><div class="ha-body">' +
          '<p class="ha-loading">正在检索并生成回答…</p></div></div>' +
        '<div class="ha-turn-src"></div>';
      chat.appendChild(wrap);
      if (wrap.scrollIntoView) { wrap.scrollIntoView({ block: "nearest" }); }
      return {
        root: wrap,
        body: wrap.querySelector(".ha-body"),
        src: wrap.querySelector(".ha-turn-src")
      };
    }

    // 一轮对话：先检索 → 补料 → 拼消息 → 流式
    function askOnce(question) {
      if (busy) return;
      if (sess.turns >= MAX_TURNS) {
        statusEl.textContent = "已达轮数上限，点「清空对话」重新开始。";
        return;
      }
      if (!getKey() && !(keyIn.value || "").trim()) {
        keyIn.focus();
        statusEl.textContent = "请先填入 DeepSeek API key。";
        return;
      }
      if ((keyIn.value || "").trim()) setKey(keyIn.value.trim());

      setBusy(true);
      statusEl.textContent = "正在检索资料…";

      loadAll().then(function (data) {
        var groups = search(data, question);
        var picks = fetchPicks(groups) || [];

        // 已有资料的签名，用于去重
        var have = {}, i;
        for (i = 0; i < sess.sources.length; i++) {
          have[sess.sources[i].stKey + "|" + sess.sources[i].url] = 1;
        }

        var first = sess.turns === 0;
        var wantFresh = first ? AI_PICKS : 2;
        var fresh = [];
        for (i = 0; i < picks.length && fresh.length < wantFresh; i++) {
          var key = picks[i].st.key + "|" + urlOf(picks[i].st.key, picks[i].e);
          if (have[key]) continue;
          fresh.push(picks[i]);
        }
        // 资料已满则不再补
        if (sess.sources.length >= MAX_SOURCES) fresh = [];

        function proceed(added) {
          var prefix = "";
          if (!first && added.length) {
            var parts = ["<补充资料>"], x;
            for (x = 0; x < added.length; x++) {
              parts.push("[" + added[x].n + "] " + added[x].st + " · " + added[x].title +
                (added[x].meta ? "（" + added[x].meta + "）" : ""));
              parts.push(added[x].text);
              parts.push("");
            }
            parts.push("</补充资料>");
            prefix = parts.join("\n") + "\n\n";
          } else if (!first) {
            /* 没有新料，直接追问 */
          }
          var userMsg = first
            ? contextPrompt(picks, sess.sources, question)
            : prefix + "追问：" + question;
          sess.history.push({ role: "user", content: userMsg });

          var handle = addTurn(question);
          statusEl.textContent = "正在生成回答…";
          var chars = 0, i2;
          for (i2 = 0; i2 < sess.sources.length; i2++) chars += sess.sources[i2].text.length;

          streamChat(
            getKey(),
            [{ role: "system", content: sess.system }].concat(sess.history),
            function (delta, body) {
              handle.body.innerHTML = ansHtml(body, sess.sources);
            },
            function (body, usage) {
              setBusy(false);
              sess.turns++;
              sess.history.push({ role: "assistant", content: body });
              handle.body.innerHTML = ansHtml(body, sess.sources);

              var cited = citedSources(body, sess.sources);
              handle.src.innerHTML = cited.length ? sourcesHtml(cited) : "";

              var c = estCost(chars, body.length);
              sess.cost += c;
              var u = document.createElement("p");
              u.className = "ha-usage";
              u.textContent = "以上为 AI 生成，请以资料来源为准。　" +
                (usage ? "输入 " + fmtNum(usage.prompt_tokens || 0) + " / 输出 " +
                  fmtNum(usage.completion_tokens || 0) + " tokens"
                  : "本轮约 " + fmtNum(Math.round(chars * 0.6)) + " 输入 tokens") +
                "　本轮约 ¥" + c.toFixed(4) +
                (added.length ? "　（本轮补充 " + added.length + " 条资料）" : "");
              handle.root.appendChild(u);
              updateStatus();
            },
            function (status, msg) {
              setBusy(false);
              handle.body.innerHTML = '<p class="ha-empty"><b>' + esc(failHint(status)) +
                "</b><br>" + esc(String(msg || "").slice(0, 300)) + "</p>";
              updateStatus();
            }
          );
        }

        if (!fresh.length) { proceed([]); return; }
        buildContext(fresh, function (d, n) {
          statusEl.textContent = "正在读取资料… " + d + "/" + n;
        }).then(function (arr) {
          var base = sess.sources.length;
          var added = [], i3;
          for (i3 = 0; i3 < arr.length && (base + added.length) < MAX_SOURCES; i3++) {
            var s2 = arr[i3];
            s2.n = base + added.length + 1;
            sess.sources.push(s2);
            added.push(s2);
          }
          proceed(added);
        });
      });
    }

    sendBtn.addEventListener("click", function () {
      var q = (followIn.value || "").trim();
      if (!q) { followIn.focus(); return; }
      followIn.value = "";
      askOnce(q);
    });
    followIn.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" || ev.keyCode === 13) {
        ev.preventDefault();
        var q = (followIn.value || "").trim();
        if (!q) return;
        followIn.value = "";
        askOnce(q);
      }
    });

    endBtn.addEventListener("click", function () {
      sess.sources = []; sess.history = []; sess.turns = 0; sess.cost = 0;
      chat.innerHTML = "";
      statusEl.textContent = "对话已清空，可以重新开始。";
      setBusy(false);
      followIn.focus();
    });

    followIn.focus();
  }

  // ══════════════════════════════════════════════════════════
  function boot() {
    var searchHost = document.getElementById("heijiu-ask");
    var chatHost = document.getElementById("heijiu-chat");
    if (searchHost) mountSearch(searchHost);
    if (chatHost) mountChat(chatHost);
    if (searchHost || chatHost) return;
    // 兼容 data 属性
    var alt = document.querySelector("[data-heijiu-ask]");
    if (alt) { mountSearch(alt); return; }
    var alt2 = document.querySelector("[data-heijiu-chat]");
    if (alt2) { mountChat(alt2); }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
