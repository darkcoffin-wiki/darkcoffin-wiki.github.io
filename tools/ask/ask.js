/* ══════════════════════════════════════════════════════════════
   黑柩 Wiki · 跨站检索 + AI 问答
   ══════════════════════════════════════════════════════════════
   一个页面做完两件事：
     · 跨四站关键词检索（零成本、零风险）
     · 在检索结果之上，用用户自己的 DeepSeek API key 让 AI 回答，并可持续追问
   API key 只填一次，检索与问答共用。

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
  var AI_PICKS = 5;          // 喂给模型的资料条数（wiki 四站）
  var AI_CTX_CHARS = 2600;   // 每条资料截断字数
  var REC_INDEX = "records/index.json";   // 跑团原始记录索引（152 场）
  var TABLES = [                          // 两张人物表（问答时按行摘录）
    { key: "npc", file: "records/npc.md", label: "NPC 总表", take: 3 },
    { key: "ply", file: "records/players.md", label: "玩家用名总表", take: 2 }
  ];
  var REC_MAX_SESSIONS = 2;  // 每次最多取几场原始记录（列举类问题会放大）
  var REC_MAX_LINES = 36;    // 每场最多摘几行台词（列举类问题会放大）
  var INVERT_FILE = "records/invert.json";   // 词 → 场次 倒排索引（原始记录的独立入口）

  // 列举型问题：「有哪些 / 都有谁 / 全部 / 列举」。
  // 这类问题的答案是**散布在整个语料**里的集合，不是某一篇文档里的一个事实。
  // 靠 top-5 片段必然答不全，必须扩大召回范围，并且在回答里说明「可能不全」。
  // 注意要收「哪些」本身，而不只是「有哪些 / 哪些人 / 哪些场」。
  // 实测「鸣做过哪些有趣的事」因为只写了「哪些」而没被判成列举，
  // 于是只取 2 场原始记录，答案单薄；补上后取 8 场。
  var ENUM_RE = /哪些|有哪些|有些什么|有什么|都有谁|都有哪些|都有什么|有谁|全部|所有|列举|列出|哪几位|哪几场|一共|总共|几次|多少次|多少个|名单/;

  // 「讲解 / 概述」类问题：要的是整场脉络，不是「同时含某几个关键词的那几行」
  var OVERVIEW_RE = /讲解|讲讲|说说|概述|经过|发生了什么|怎么回事|复盘|梳理|介绍一下|详细讲|具体讲|来龙去脉|前因后果/;

  function isOverview(q) {
    return OVERVIEW_RE.test(String(q || ""));
  }

  // 字符级停用表：扫描台词时剔除没有辨识度的单字。
  // 「碗」这种单字道具名要保留，「的」「了」「上」必须排除。
  var STOP_CHARS = (function () {
    var set = {};
    var chars = "的了是我你他她它们这那有和与就都也不没很太更最个上下来到去把被让给对从为以于而但可" +
      "能要会什怎谁哪吗呢吧啊呀哦嗯请您些过做说讲看想去来点样时候在用拿" +
      "一二三四五六七八九十百千万亿么呢吧";
    for (var i = 0; i < chars.length; i++) set[chars[i]] = 1;
    return set;
  })();

  function isEnumeration(q) {
    return ENUM_RE.test(String(q || ""));
  }

  // ══════════════════════════════════════════════════════════
  // 工具
  // ══════════════════════════════════════════════════════════
  function norm(s) {
    return String(s == null ? "" : s)
      .toLowerCase()
      .replace(/[\u3000\s]+/g, "")
      .replace(/[（）()「」『』【】《》〈〉·・,，、。.;；:：!！?？"'“”‘’\-—–_/\\|~～*]/g, "");
  }

  // ── 词典（来自原始记录的倒排索引，供长串切分用）──
  var DICT = null;

  function setDict(terms) {
    DICT = {};
    for (var k in terms) {
      if (Object.prototype.hasOwnProperty.call(terms, k)) DICT[k] = 1;
    }
  }

  // 最长匹配切分：一段中文在没有空格的情况下，只能靠词表切开。
  // 「北沙希共党员」不在任何标题里，但切开成「北沙 / 希共 / 党员」就能命中。
  function segmentByDict(text) {
    if (!DICT) return [];
    var out = [], i = 0, n = text.length, len, sub, matched;
    while (i < n) {
      matched = false;
      for (len = Math.min(4, n - i); len >= 2; len--) {
        sub = text.substr(i, len);
        if (DICT[sub]) { out.push(sub); i += len; matched = true; break; }
      }
      if (!matched) i++;
    }
    return out;
  }

  // ── 中文长句的分词 ──
  // 中文没有空格，整句当一个词去匹配必然落空。
  // 实测：「希联的意识形态是什么」按整串匹配 = 0 条；
  // 按下面的停用词切开后 → ["希联", "意识形态"]，立刻能命中几十条。
  // 停用词只收**明确的虚词/疑问词**，并且按长度降序替换（先长后短），
  // 避免把「形态」这种实词切碎。
  var STOPWORDS = [
    // 疑问 / 语气
    "为什么", "什么", "怎么", "怎样", "如何", "哪些", "哪个", "多少",
    "是谁", "是什么", "请问", "介绍", "讲讲", "说说", "关于", "一下",
    "会不会", "是不是", "有没有", "可以", "能否", "能不能", "的话",
    "以及", "还有", "到底", "究竟",
    // 感情 / 关系 / 口语动词
    // 「李伊喜欢谁」若只切掉「谁」会得到「李伊喜欢」，而没有任何条目叫这个名字，
    // 命中直接归零。把这类词切掉才能落回核心实体「李伊」。
    "喜欢", "讨厌", "最爱", "最爱谁", "恨", "爱",
    "关系", "交情", "认识", "见过", "说过", "做过", "干过",
    "名字", "别名", "称呼", "叫法", "绰号",
    "用过", "使过", "换过", "改过", "起过", "取过", "演过", "担任", "扮演",
    "在哪", "哪里", "哪儿", "何处",
    "一直", "曾经", "以前", "后来", "现在", "当年", "最初",
    "叫", "改名", "改成", "换成", "也叫", "还叫", "又叫",
    // 虚词
    "的", "了", "是", "在", "有", "和", "与", "及", "或", "也", "都",
    "吗", "呢", "吧", "啊", "呀", "谁", "这", "那", "个", "就", "还",
    "我", "你", "他", "她", "它", "们", "要", "想", "能"
  ].sort(function (a, b) { return b.length - a.length; });

  // 取字符串里重复出现（>= 2 次）的 2~3 字子串。
  // 用于「李伊一直都叫李伊吗」这类句子：同一个实体出现两次，切完停用词后
  // 变成「李伊李伊」，谁也匹配不到；而它的「李伊」出现了两次，正是核心实体。
  function repeatedSubstrings(str) {
    var counts = {}, out = [], len, i, sub;
    for (len = 2; len <= 3; len++) {
      for (i = 0; i + len <= str.length; i++) {
        sub = str.substr(i, len);
        counts[sub] = (counts[sub] || 0) + 1;
      }
    }
    for (sub in counts) {
      if (Object.prototype.hasOwnProperty.call(counts, sub) && counts[sub] >= 2) {
        out.push(sub);
      }
    }
    return out;
  }

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

    // 3.6) 长片段里重复出现的实体（「李伊李伊」→「李伊」）
    var reps = [];
    for (i = 0; i < out.length; i++) {
      if (out[i].length > 4) {
        var rr = repeatedSubstrings(out[i]);
        for (j = 0; j < rr.length; j++) reps.push(rr[j]);
      }
    }
    for (i = 0; i < reps.length; i++) out.push(reps[i]);

    // 3.7) 词典切分：长串用倒排词典切开（「北沙希共党员」→ 北沙 / 希共 / 党员）
    if (DICT) {
      var segs2 = [];
      for (i = 0; i < out.length; i++) {
        if (out[i].length > 4) {
          var ss = segmentByDict(out[i]);
          for (j = 0; j < ss.length; j++) segs2.push(ss[j]);
        }
      }
      for (i = 0; i < segs2.length; i++) out.push(segs2[i]);
    }

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

  function fetchPicks(groups, limit, perStation) {
    // 按「设定 → 花絮 → 跑团 → 分析」的顺序挑，每站最多 perStation 条，总数 limit
    limit = limit || AI_PICKS;
    perStation = perStation || 2;
    var picks = [], i, j, g;
    for (i = 0; i < groups.length && picks.length < limit; i++) {
      g = groups[i];
      for (j = 0; j < g.hits.length && j < perStation && picks.length < limit; j++) {
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

  // ── 跑团原始记录：索引 + 按场取证 ──
  //
  // 记录检索比 wiki 检索更依赖「季名 + 实体名」这类**短词**。
  // 用户问「第八季发生了什么」，通用 termsOf 只会切出「第八季发生了」这种长串，
  // 在季名「第八季·人民万岁」里匹配不到。所以这里再洗一遍常见动词/泛词。
  var REC_STOP = [
    "发生", "出现", "内容", "剧情", "经过", "结果", "情况", "后来", "然后",
    "讲了", "说了", "说了什么", "什么样", "什么事", "做什么", "干什么",
    "大概", "具体", "详细", "简单", "总结", "概括", "描述", "介绍"
  ].sort(function (a, b) { return b.length - a.length; });

  function recordTermsOf(q) {
    var t = String(q || ""), i;
    for (i = 0; i < REC_STOP.length; i++) {
      if (t.indexOf(REC_STOP[i]) >= 0) t = t.split(REC_STOP[i]).join(" ");
    }
    return termsOf(t);
  }
  var recCache = null, recLoading = null;

  function loadRecords() {
    if (recCache) return Promise.resolve(recCache);
    if (recLoading) return recLoading;
    recLoading = fetch(BASE + REC_INDEX, { cache: "force-cache" })
      .then(function (r) { return r.ok ? r.json() : { entries: [] }; })
      .then(function (d) { recCache = d.entries || []; recLoading = null; return recCache; })
      .catch(function () { recCache = []; recLoading = null; return []; });
    return recLoading;
  }

  // 在记录索引里找与问题最相关的几场
  // 打分：季名/地点/在场/结尾状态命中 → 加分；摘要命中的词越多分越高
  function searchRecords(entries, query) {
    var list = recordTermsOf(query);
    if (!list.length || !entries.length) return [];
    var out = [], i, j, w, e, s, hit, hay;
    for (i = 0; i < entries.length; i++) {
      e = entries[i];
      hay = norm(e.season + " " + (e.places || "") + " " + (e.present || "") + " "
                 + (e.end_state || "") + " " + (e.summary || ""));
      s = 0; hit = 0;
      for (j = 0; j < list.length; j++) {
        w = list[j];
        if (!w) continue;
        if (hay.indexOf(w) >= 0) { s += 10; hit++; }
        // 季名里出现该词，权重更高（用户常直接点名季）
        if (norm(e.season).indexOf(w) >= 0) { s += 25; hit++; }
      }
      if (!hit) continue;
      // 摘要里出现次数越多越相关
      for (j = 0; j < list.length; j++) {
        var n = (e.summary || "").split(list[j]).length - 1;
        if (n > 0) s += Math.min(20, n * 2);
      }
      out.push({ e: e, s: s });
    }
    out.sort(function (a, b) { return b.s - a.s; });
    return out.slice(0, REC_MAX_SESSIONS).map(function (x) { return x.e; });
  }

  // ── 倒排索引：原始记录的独立入口 ──
  var invCache = null, invLoading = null;

  function loadInvert() {
    if (invCache) return Promise.resolve(invCache);
    if (invLoading) return invLoading;
    invLoading = fetch(BASE + INVERT_FILE, { cache: "force-cache" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { invCache = d || { terms: {}, speakers: {} }; invLoading = null; return invCache; })
      .catch(function () { invCache = { terms: {}, speakers: {} }; invLoading = null; return invCache; });
    return invLoading;
  }

  // 问题里点名了某一季？（「第九季」→ 第九季上/下 的所有场次）
  // 必须特殊处理：否则「第九季发生了什么」会被「什么 / 发生」这类子串刷分，
  // 实测会命中第七季第 20 场。
  // 从问题里认出「哪一季 / 哪一个团」。
  // 旧实现只认「第X季」，「竖棺」「食龙则肥」这类短团名完全匹配不到；
  // 而团名很少出现在台词正文里，倒排索引也覆盖不到。
  function matchSeason(q, records) {
    var qn = norm(q);
    if (!qn) return "";
    var seasons = [], seen = {}, i;
    for (i = 0; i < (records || []).length; i++) {
      var sn = records[i].season;
      if (sn && !seen[sn]) { seen[sn] = 1; seasons.push(sn); }
    }
    var best = "", bestLen = 0;
    for (i = 0; i < seasons.length; i++) {
      var sname = seasons[i];
      var cands = [sname, sname.replace(/^短团·/, "")];
      var m = /^第([一二三四五六七八九十]+)季/.exec(sname);
      if (m) cands.push("第" + m[1] + "季");
      var mp = /^幕间季([一二三四五六七八九十]+)/.exec(sname);
      if (mp) cands.push("幕间季" + mp[1]);
      for (var j = 0; j < cands.length; j++) {
        var cn = norm(cands[j]);
        if (cn && cn.length >= 2 && qn.indexOf(cn) >= 0 && cn.length > bestLen) {
          best = sname;
          bestLen = cn.length;
        }
      }
    }
    return best;
  }

  // 顺序词：把「最后」真正翻译成「最后一场」
  var LAST_RE = /最后|结尾|结局|最终|末尾|末场|收尾|尾声|决战|终战|终局|大结局|最后一战/;
  var FIRST_RE = /开头|最初|起始|第一场|开场|刚开始/;

  function ordinalHint(q) {
    var t = String(q || "");
    if (LAST_RE.test(t)) return "last";
    if (FIRST_RE.test(t)) return "first";
    return "";
  }

  // 扫描/筛台词用的关键词：保留单字（「碗」），按长度给权重
  function scanTermsOf(q) {
    var GENERIC = {
      "讲解": 1, "剧情": 1, "故事": 1, "内容": 1, "情节": 1, "经过": 1,
      "细节": 1, "介绍": 1, "情况": 1, "大概": 1, "具体": 1, "详细": 1,
      "简单": 1, "总结": 1, "经典": 1, "台词": 1, "名句": 1, "名言": 1,
      "有趣": 1, "好玩": 1
    };
    var out = [], seen = {}, i, j;
    function push(w, weight) {
      if (!w || seen[w]) return;
      seen[w] = 1;
      out.push({ w: w, weight: weight });
    }

    var base = termsOf(q);
    var multi = [];

    for (i = 0; i < base.length; i++) {
      var t = base[i];
      if (GENERIC[t]) continue;

      // 只对**纯中文长串**做切分/丢弃。
      // 英文名（joy、joy-llk）不能被当成切分残渣丢掉——
      // 「讲解一下joy和顺风车在厕所的剧情」正是因为把 joy 丢了，
      // 三个关键词只剩两个，扫不到那场。
      if (t.length >= 3 && /^[\u4e00-\u9fff]+$/.test(t)) {
        var segs = segmentByDict(t);
        for (j = 0; j < segs.length; j++) {
          if (GENERIC[segs[j]]) continue;
          push(segs[j], segs[j].length - 1);
          multi.push(segs[j]);
        }
        continue;
      }
      if (t.length >= 2) {
        push(t, t.length - 1);
        multi.push(t);
      }
    }

    // GENERIC 词被整词过滤后，它们的字（讲/解/剧/情/台/词）不该再作为单字补回来，
    // 否则会把分母撑大、稀释真正的关键词。
    var genericChars = {};
    for (var gk in GENERIC) {
      if (!Object.prototype.hasOwnProperty.call(GENERIC, gk)) continue;
      for (var gi = 0; gi < gk.length; gi++) genericChars[gk.charAt(gi)] = 1;
    }

    // 单字只补「没有被任何多字词覆盖」的
    var qn = norm(q);
    for (i = 0; i < qn.length; i++) {
      var ch = qn.charAt(i);
      if (!/[\u4e00-\u9fff]/.test(ch)) continue;
      if (STOP_CHARS[ch]) continue;
      if (genericChars[ch]) continue;
      var covered = false;
      for (j = 0; j < multi.length; j++) {
        if (multi[j].indexOf(ch) >= 0) { covered = true; break; }
      }
      if (covered) continue;
      push(ch, 1);
    }

    return out;
  }
  function seasonHint(q) {
    var m = /第([一二三四五六七八九十]+)季/.exec(String(q || ""));
    return m ? "第" + m[1] + "季" : "";
  }

  function sessionsOfSeason(entries, hint) {
    var out = [], i;
    if (!hint) return out;
    for (i = 0; i < entries.length; i++) {
      if ((entries[i].season || "").indexOf(hint) >= 0) out.push(entries[i]);
    }
    return out;
  }

  // 在文本里找出**字典中的所有名字**。
  //
  // 为什么不复用 substrsOf：那条路只生成 2~4 字子串，
  // 而「鸣」「白」这种单字玩家名永远成不了候选——实测 ask「鸣做过哪些有趣的事」
  // 完全查不到，但 speakers 索引里「鸣」有 40 场 3949 行。
  // 名字表很小（发言人 48、NPC 379），遍历键做 indexOf 反而又快又全。
  // 单字名（鸣 / 白）非常容易误伤：「明白」「白菜」都会命中。
  // 折中办法：单字名只在前几个字里出现才算——提问里点名某人通常在开头。
  var SINGLE_CHAR_POS = 4;

  function namesInText(text, dict, limit) {
    var t = norm(text), out = [], k, at;
    if (!t || !dict) return out;
    for (k in dict) {
      if (!Object.prototype.hasOwnProperty.call(dict, k)) continue;
      if (!k) continue;
      at = t.indexOf(norm(k));
      if (at < 0) continue;
      if (k.length === 1 && at > SINGLE_CHAR_POS) continue;   // 单字名限制位置
      out.push(k);
    }
    // 长名优先（「顺风车」先于「车」这类包含关系）
    out.sort(function (a, b) { return b.length - a.length; });
    return limit ? out.slice(0, limit) : out;
  }

  // 把问题拆成 2~4 字的所有子串（中文没有空格，穷举子串查索引最可靠）
  function substrsOf(q) {
    var s2 = norm(q), out = [], len, i;
    for (len = 4; len >= 2; len--) {
      for (i = 0; i + len <= s2.length; i++) out.push(s2.substr(i, len));
    }
    return out;
  }

  // 用倒排索引定位场次。返回 [{season, no, score}]，按相关度降序。
  function sessionsFromInvert(inv, question, maxN) {
    if (!inv || !inv.terms) return [];
    var subs = substrsOf(question);
    var score = {}, i, j, parts, sid, w;

    function add(sidRaw, cnt, weight) {
      score[sidRaw] = (score[sidRaw] || 0) + cnt * weight;
    }

    // ① 正文提到的词：词越长越具体，权重越高
    for (i = 0; i < subs.length; i++) {
      var arr = inv.terms[subs[i]];
      if (!arr) continue;
      w = subs[i].length - 1;                 // 2字→1, 3字→2, 4字→3
      for (j = 0; j < arr.length; j++) {
        parts = arr[j].split(":");
        add(parts[0], parseInt(parts[1], 10), w);
      }
    }
    // ② 发言人：问「余烬说过什么」时，正文里不一定提到余烬，必须查发言人索引。
    //    用名字扫描而不是子串，否则单字的「鸣」「白」永远匹配不到。
    var asked = namesInText(question, inv.speakers, 3);
    for (i = 0; i < asked.length; i++) {
      var sp = inv.speakers[asked[i]];
      if (!sp) continue;
      for (j = 0; j < sp.length; j++) {
        parts = sp[j].split(":");
        add(parts[0], parseInt(parts[1], 10), 3);   // 发言人权重给足
      }
    }

    var list = [];
    for (sid in score) {
      if (!Object.prototype.hasOwnProperty.call(score, sid)) continue;
      list.push({ sid: sid, score: score[sid] });
    }
    list.sort(function (a, b) { return b.score - a.score; });
    return list.slice(0, maxN || 6);
  }

  // ── 人物表：NPC 总表 / 玩家用名总表 ──
  var tableCache = null, tableLoading = null;

  function loadTables() {
    if (tableCache) return Promise.resolve(tableCache);
    if (tableLoading) return tableLoading;
    tableLoading = Promise.all(TABLES.map(function (t) {
      return fetch(BASE + t.file, { cache: "force-cache" })
        .then(function (r) { return r.ok ? r.text() : ""; })
        .catch(function () { return ""; });
    })).then(function (texts) {
      tableCache = TABLES.map(function (t, i) { return { def: t, text: texts[i] || "" }; });
      tableLoading = null;
      return tableCache;
    });
    return tableLoading;
  }

  // 从一张 markdown 表里挑出与问题相关的行。
  // 打分：名字列（第 2 个单元格）命中 +30，别名列（第 3 个）+18，其它 +6。
  function tableRowsFor(text, terms, take, question) {
    if (!text) return [];
    var qn = norm(question || "");
    var lines = text.split("\n"), out = [], i, j, w;
    for (i = 0; i < lines.length; i++) {
      var ln = lines[i];
      if (ln.charAt(0) !== "|") continue;
      if (ln.indexOf("---") >= 0) continue;            // 分隔行
      if (ln.indexOf("| # |") >= 0) continue;          // 表头
      var cells = ln.split("|");
      if (cells.length < 4) continue;
      var nameCell = norm(cells[2] || "");
      var aliasCell = norm(cells[3] || "");
      var whole = norm(ln);
      var score = 0, hit = false;
      // 先做「名字整体出现在提问里」的精确判断——
      // 这一条对单字名（鸣 / 白）至关重要，因为下面的 terms 都 >= 2 字。
      var rawName = norm((cells[2] || "").replace(/\s/g, ""));
      if (qn && rawName && rawName.length >= 1) {
        var at2 = qn.indexOf(rawName);
        // 单字 NPC 名同样只认靠前出现，避免误伤
        if (at2 >= 0 && (rawName.length > 1 || at2 <= 4)) {
          score += 40; hit = true;
        }
      }
      for (j = 0; j < terms.length; j++) {
        w = terms[j];
        if (!w || w.length < 2) continue;
        if (nameCell.indexOf(w) >= 0) { score += 30; hit = true; }
        else if (aliasCell.indexOf(w) >= 0) { score += 18; hit = true; }
        else if (whole.indexOf(w) >= 0) { score += 6; hit = true; }
      }
      if (!hit) continue;
      out.push({ line: ln.trim(), score: score });
    }
    out.sort(function (a, b) { return b.score - a.score; });
    return out.slice(0, take).map(function (x) { return x.line; });
  }

  // 两张表合成**一条**资料（编号只占一位），避免挤掉别的资料
  function tablesToSource(tables, question) {
    var terms = termsOf(question);
    var parts = [], urls = [], i, rows;
    for (i = 0; i < tables.length; i++) {
      rows = tableRowsFor(tables[i].text, terms, tables[i].def.take, question);
      if (!rows.length) continue;
      parts.push("〔" + tables[i].def.label + "〕");
      parts.push(rows.join("\n"));
      parts.push("");
      urls.push(BASE + tables[i].def.file);
    }
    if (!parts.length) return null;
    return {
      st: "人物表",
      stKey: "table",
      title: "NPC 总表 / 玩家用名总表（相关行）",
      meta: "按问题里的人名摘录；「别名·异写」列为空写作「未明」",
      url: urls[0],
      text: parts.join("\n")
    };
  }

  // wiki 跑团站的命中条目里带着 season / n，可以直接反查是哪一场。
  // 这比在 record index 的 600 字摘要里碰运气可靠：
  // 实测「四季常村」在 record 摘要里一个都没命中，但在跑团站索引里有精确命中。
  function sessionsFromGroups(groups) {
    var out = [], seen = {}, i, j, g, e, k;
    for (i = 0; i < groups.length; i++) {
      g = groups[i];
      if (g.st.key !== "trpg") continue;
      for (j = 0; j < g.hits.length; j++) {
        e = g.hits[j].e;
        if (!e || !e.season || !e.n) continue;
        k = e.season + "|" + e.n;
        if (seen[k]) continue;
        seen[k] = 1;
        out.push({ season: e.season, no: e.n });
      }
    }
    return out;
  }

  function findRecord(entries, season, no) {
    for (var i = 0; i < entries.length; i++) {
      if (entries[i].season === season && entries[i].no === no) return entries[i];
    }
    return null;
  }

  // 拉一场的脱敏 TSV，按关键词挑出相关台词（带前一行上下文）
  function fetchRecordLines(entry, query, maxLines, maxChars, speakerSet) {
    maxLines = maxLines || REC_MAX_LINES;
    maxChars = maxChars || 2400;
    var list = recordTermsOf(query);
    return fetch(BASE + "records/" + entry.file, { cache: "force-cache" })
      .then(function (r) { return r.ok ? r.text() : ""; })
      .then(function (txt) {
        if (!txt) return null;
        var lines = txt.split("\n");
        var head = lines[0].split("\t");
        var iTime = head.indexOf("时间"), iName = head.indexOf("规范名"),
            iBody = head.indexOf("正文"), iType = head.indexOf("类型");
        // ── 按相关度排序，而不是从原文开头凑够就停 ──
        //
        // 旧实现从头往后扫，够 maxLines 就 break。
        // 实测踩坑：问「顺风车筷子和碗」时，竖棺第 7 场前面是「用鼻孔吃面」的戏，
        // 顺势把后面的「筷子立起、碗盖住肚脐」全挤掉了，模型只能答吃面。
        //
        // 现在先收全部命中行并打分，再按「多字词命中数 → 单字命中数 → 原文顺序」排序，
        // 保证最相关的那几行一定进得来。
        var terms2 = scanTermsOf(query);
        var candidates = [], i, j, p, body, strong, weak, isSp;
        for (i = 1; i < lines.length; i++) {
          p = lines[i].split("\t");
          if (p.length < head.length) continue;
          body = p[iBody] || "";
          strong = 0; weak = 0;
          for (j = 0; j < terms2.length; j++) {
            if (terms2[j].w && body.indexOf(terms2[j].w) >= 0) {
              if (terms2[j].w.length >= 2) strong++; else weak++;
            }
          }
          // 问「某人说过什么」时正文里不会出现他自己的名字，必须看规范名
          isSp = !!(speakerSet && speakerSet[p[iName]]);
          if (strong === 0 && weak === 0 && !isSp) continue;
          candidates.push({ p: p, strong: strong, weak: weak, isSp: isSp, idx: candidates.length });
        }
        candidates.sort(function (a, b) {
          return (b.strong - a.strong) || (b.weak - a.weak) || (a.idx - b.idx);
        });

        var picked = [], total = 0;
        for (i = 0; i < candidates.length; i++) {
          if (picked.length >= maxLines || total > maxChars) break;
          var c = candidates[i];
          picked.push({
            t: c.p[iTime] || "", n: c.p[iName] || "",
            ty: c.p[iType] || "", b: c.p[iBody] || ""
          });
          total += (c.p[iBody] || "").length;
        }
        // 原来是「命中 < 4 行就整个退回摘要、原文全丢」——这正是「原始记录相当于没用」的主因。
        // 现在改成：命中多少用多少；摘要**始终附上**作为背景，两者并存。
        var useSummary = !picked.length;
        return {
          season: entry.season, no: entry.no, file: entry.file,
          lines: picked,
          summary: entry.summary || "",
          places: entry.places || "",
          present: entry.present || "",
          useSummary: useSummary,
          // 只留日期与起止时间，去掉「（时长 X 小时）」——那句话在来源卡里太长，
          // 会把标题挤扁，对「是哪一场」的判断也没有帮助。
          date: ((entry.realtime || "").split("｜")[0] || "")
                  .replace(/（时长[^）]*）/g, "")
                  .replace(/\s+/g, " ")
                  .trim()
        };
      })
      .catch(function () { return null; });
  }

  // 把一场记录转成「资料」对象（与 wiki 资料同构，编号稍后统一分配）
  function recordToSource(rec, opts) {
    opts = opts || {};
    var text, meta;

    // 概述类问题：「场次提要」（整场脉络，几千字）+「台词摘录」（原话细节）都要。
    // 二选一的话，只给台词会丢掉整体经过，只给提要又缺原话。
    if (opts.withSummary && rec.lines.length && rec.summary) {
      var ps = [];
      if (rec.places) ps.push("地点：" + rec.places);
      if (rec.present) ps.push("在场：" + rec.present);
      ps.push("提要：" + rec.summary);
      ps.push("台词摘录：");
      for (var li = 0; li < rec.lines.length; li++) {
        var l = rec.lines[li];
        ps.push("[" + (l.t || "") + "] " + (l.n || "") + "：" + (l.b || ""));
      }
      text = ps.join("\n");
      meta = (rec.date || "") + " · 提要 + " + rec.lines.length + " 条台词";
    } else if (rec.useSummary || !rec.lines.length) {
      // 关键词没落在正文里 → 用场次提要（含地点/在场/结局），更有信息量
      var parts = [];
      if (rec.places) parts.push("地点：" + rec.places);
      if (rec.present) parts.push("在场：" + rec.present);
      if (rec.summary) parts.push("提要：" + rec.summary);
      text = parts.join("\n");
      meta = (rec.date || "") + " · 场次提要";
    } else {
      var body = [], i, l;
      for (i = 0; i < rec.lines.length; i++) {
        l = rec.lines[i];
        body.push("[" + (l.t || "") + "] " + (l.n || "") + "：" + (l.b || ""));
      }
      text = body.join("\n");
      meta = (rec.date || "") + " · " + rec.lines.length + " 条台词摘录";
    }
    return {
      st: "跑团原始记录",
      stKey: "record",
      title: rec.season + " 第 " + rec.no + " 场",
      meta: meta,
      url: BASE + "records/" + rec.file,
      text: text.slice(0, 3000)
    };
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
      "8. 用户问「有哪些 / 都有谁 / 全部 / 列举」这类问题时，你看到的资料只是从全库检索到的**一部分**。",
      "   必须明确说明「以下是检索到的，可能不全」，并给出你判断的依据（出现在哪几场/哪一季），",
      "   **绝对不要装作已经穷举完整，也不要把没查到的说成不存在**。",
      "",
      "7. 你面对的是一段多轮对话，但用户随时可能换话题。**判断依据只看本次问题与本次资料**：",
      "   如果本次问题跟前面的对话无关，就当之前的对话不存在，不要把它们扯进来。",
      "   反过来说，如果资料里查不到本次问题涉及的东西，就说查不到，**不要拿之前聊过的人或事来顶替**。",
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
  // 回调里的异常必须就地吞掉并打日志。
  // 否则它会冒泡到 fetch 的 .catch()，被当成「网络错误」——
  // 实测就出现过：一个 null.textContent 的 TypeError 显示成了「跨域被拦或断网」。
  function safeCall(fn, a, b) {
    if (typeof fn !== "function") return;
    try {
      fn(a, b);
    } catch (e) {
      if (window.console && console.error) {
        console.error("[黑柩问答] 回调出错：", e);
      }
    }
  }

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
            safeCall(onDone, full, usage);
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
              if (d && d.content) { full += d.content; safeCall(onDelta, d.content, full); }
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
      // 元信息在窄屏会被省略号截断，补个 title 让悬停能看全
      var metaText = s.st + (s.meta ? " · " + s.meta : "");
      html += '<a class="ha-src" id="ha-ref-' + s.n + '" href="' + esc(s.url) + '">' +
        '<span class="n">[' + s.n + "]</span>" +
        '<span class="t">' + esc(s.title) + "</span>" +
        '<span class="m" title="' + esc(metaText) + '">' + esc(metaText) + "</span>" +
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
  // 单一挂载：问答搜索
  //   检索与问答合并在同一个界面、共用同一份 API key 与同一段对话状态。
  //   原来的 mountSearch / mountChat 两个入口已合并成 mountAsk。
  // ══════════════════════════════════════════════════════════
  var MAX_TURNS = 8;       // 对话最多轮数
  var MAX_SOURCES = 12;    // 资料总数上限（首次 5 + 追问每次最多 2 + 人物表 1）

  // 回答正文统一包在 .ha-ans 里（样式与测试都依赖这个容器）
  function ansHtml(text, sources) {
    return '<div class="ha-ans">' + renderAnswer(text, sources) + "</div>";
  }

  var HISTORY_TURNS = 3;   // 历史最多保留几轮（不含当前轮）

  // 把一批资料拼成交给模型的文本块
  function sourcesBlock(list) {
    if (!list || !list.length) return "";
    var parts = ["<资料>"], i;
    for (i = 0; i < list.length; i++) {
      parts.push("[" + list[i].n + "] " + list[i].st + " · " + list[i].title +
        (list[i].meta ? "（" + list[i].meta + "）" : ""));
      parts.push(list[i].text);
      parts.push("");
    }
    parts.push("</资料>");
    return parts.join("\n");
  }

  // 两段文本是否共享 >=2 字的公共子串。
  // 不能直接比字符串相等：「李伊喜欢谁」切成「李伊喜欢」，而「那李伊呢」只切出「李伊」，
  // 字面不等但明显是同一话题，必须按子串重叠判断。
  function sharesTerm(a, b) {
    var maxLen = Math.min(a.length, b.length);
    for (var len = maxLen; len >= 2; len--) {
      for (var i = 0; i + len <= a.length; i++) {
        if (b.indexOf(a.substr(i, len)) >= 0) return true;
      }
    }
    return false;
  }

  // 判断新问题是不是「换了话题」：
  //   · 新问题里没有 >=2 字的实词（如「那他呢」）→ 视为延续
  //   · 与上一轮问题没有任何共同实词 → 视为换话题
  // 承接词开头的问题一定是在延续话题，不能因为「没有共同实词」就判成换话题。
  // 实测：「希联」之后问「那进盟呢？」，两边没有共同实词，被误判成换话题、
  // 历史被清空，于是「进盟」变成冷启动，AI 不知道这是在跟希联做对比。
  var CONTINUE_RE = /^(那|那么|那这个|那个|还有|另外|再|然后|所以|因此|它|他|她|这位|此|上述|上面|刚才|接着|继续|同样|反之|相比)/;

  function isNewTopic(newQ, lastQ) {
    if (!lastQ) return false;
    if (CONTINUE_RE.test(String(newQ).trim())) return false;   // 承接词 → 延续
    var a = recordTermsOf(newQ), b = recordTermsOf(lastQ);
    var i, j, meaningful = 0;
    for (i = 0; i < a.length; i++) {
      if (a[i].length < 2) continue;
      meaningful++;
      for (j = 0; j < b.length; j++) {
        if (b[j].length < 2) continue;
        if (sharesTerm(a[i], b[j])) return false;   // 有重叠 → 同话题
      }
    }
    if (!meaningful) return false;
    return true;                                     // 全是新词 → 换话题
  }

  function trimHistory(hist) {
    var keep = HISTORY_TURNS * 2;
    if (hist.length <= keep) return hist;
    return hist.slice(hist.length - keep);
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

  function keyRowHtml(okLabel) {
    return '<div class="ha-key-row">' +
      '<input class="ha-key" type="password" autocomplete="off" spellcheck="false" ' +
        'placeholder="sk-… （DeepSeek API key，仅本标签页有效）" value="' + esc(getKey()) + '">' +
      '<button class="ha-start" type="button">' + esc(okLabel || "开始") + "</button>" +
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
  // 问答搜索（合并版）
  //   一个输入框、一份 API key、一条时间线：
  //     输入 → 跨四站检索结果 → 「用 AI 回答这个问题」 → 可继续追问
  //   搜索与问答共用 sess（资料/历史/费用），key 只填一次。
  // ══════════════════════════════════════════════════════════
  function mountAsk(host) {
    host.classList.add("heijiu-ui");
    host.innerHTML =
      // ══════ 搜索区（不需要 API）══════
      '<section class="ha-block ha-blk-search">' +
        '<p class="ha-block-h">搜索<span class="ha-free">免费 · 不需要 API key</span></p>' +
        '<div class="ha-bar">' +
          '<input class="ha-q" type="search" autocomplete="off" ' +
            'placeholder="搜关键词，比如：希联、四季常村、镜缘" aria-label="检索《黑柩》四个站">' +
          '<button class="ha-go" type="button">搜索</button>' +
          '<button class="ha-clear" type="button" title="清空搜索与结果">清空</button>' +
        "</div>" +
        '<p class="ha-meta">跨四站检索：设定 · 花絮 · 跑团 · 分析</p>' +
        '<div class="ha-out"></div>' +
        '<div class="ha-aibar"></div>' +
        '<div class="ha-oneshot" hidden></div>' +
        '<p class="ha-legend">结果按站分组：<b>设定站</b>是作者原典（含剧透），' +
          "<b>分析站</b>是读者的 AI 分析、不是作者设定。点任一条进入原文核对。</p>" +
      "</section>" +

      // ══════ 问答区（需要 API）══════
      '<section class="ha-block ha-blk-chat">' +
        '<p class="ha-block-h">问答<span class="ha-need">需要你自己的 DeepSeek API key</span>' +
          '<button class="ha-setkey" type="button">设置 API key</button></p>' +
        '<div class="ha-chat"></div>' +
        '<div class="ha-keyinline" hidden></div>' +
        '<div class="ha-ask-row">' +
          '<input class="ha-follow" type="search" autocomplete="off" ' +
            'placeholder="问一句，比如：希联的意识形态是什么" aria-label="向助手提问">' +
          '<button class="ha-send" type="button">发送</button>' +
          '<button class="ha-end" type="button" title="清空对话">清空对话</button>' +
        "</div>" +
        '<p class="ha-status"></p>' +
      "</section>";

    var q = host.querySelector(".ha-q");
    var go = host.querySelector(".ha-go");
    var clearBtn = host.querySelector(".ha-clear");
    var out = host.querySelector(".ha-out");
    var aibar = host.querySelector(".ha-aibar");
    var oneshot = host.querySelector(".ha-oneshot");

    // 统一清空一次性解读，并让进行中的流式回调失效。
    // 之前各处直接写 oneshot.innerHTML = ""，正在生成的回答结束时
    // 还会去写 .ha-usage-slot，那时它已经是 null 了。
    function clearOneShot() {
      oneshotToken++;
      oneshot.innerHTML = "";
      oneshot.hidden = true;
    }
    var chat = host.querySelector(".ha-chat");
    var keyInline = host.querySelector(".ha-keyinline");
    var followIn = host.querySelector(".ha-follow");
    var sendBtn = host.querySelector(".ha-send");
    var endBtn = host.querySelector(".ha-end");
    var statusEl = host.querySelector(".ha-status");

    var cur = { query: "", groups: [] };     // 当前搜索结果
    var oneshotToken = 0;                    // 一次性解读的失效令牌
    var sess = {                             // 问答会话（与搜索无关）
      system: systemPrompt(), sources: [], history: [],
      turns: 0, cost: 0, lastQuestion: ""
    };
    var busy = false;

    // ══════════════════════════════════════════════
    // 共用的 key 输入：只有 AI 功能才需要，出现在被点击的地方
    // ══════════════════════════════════════════════
    var setKeyBtn = host.querySelector(".ha-setkey");

    // 按钮文案跟着状态走：没填过 → 「设置 API key」；填过 → 「改 API key」
    function updateKeyBtn() {
      if (setKeyBtn) {
        setKeyBtn.textContent = getKey() ? "改 API key" : "设置 API key";
      }
    }

    // 就地渲染 key 输入框并绑定。与「有没有 key」无关，
    // 这样 401 之后可以重新把输入框摆出来让用户改。
    function renderKeyBox(box, hint, onReady) {
      box.hidden = false;
      box.innerHTML =
        '<p class="ha-keytip">' + esc(hint) + "</p>" + keyRowHtml("保存");
      var ki = box.querySelector(".ha-key");
      var st = box.querySelector(".ha-start");
      var fg = box.querySelector(".ha-forget");
      fg.addEventListener("click", function () {
        clearKey();
        updateKeyBtn();
        box.hidden = true;
        box.innerHTML = "";
      });
      function submit() {
        var v = (ki.value || "").trim();
        if (!v) { ki.focus(); return; }
        setKey(v);
        updateKeyBtn();
        box.hidden = true;
        box.innerHTML = "";
        if (onReady) onReady();
      }
      st.addEventListener("click", submit);
      ki.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.keyCode === 13) { ev.preventDefault(); submit(); }
      });
      ki.focus();
    }

    function askKey(box, onReady, hint) {
      if (getKey()) { onReady(); return true; }
      renderKeyBox(box, hint, onReady);
      return false;
    }

    // key 无效时：清掉旧值、把输入框重新摆出来，让用户能直接改
    function recoverKey() {
      clearKey();
      updateKeyBtn();
      renderKeyBox(keyInline,
        "API key 无效或已过期，请重新填写（旧值已清除）。",
        function () { followIn.focus(); });
    }

    // ══════════════════════════════════════════════
    // 搜索（免费，不需要 key）
    // ══════════════════════════════════════════════
    function runSearch() {
      var query = q.value.trim();
      if (!query) { out.innerHTML = ""; aibar.innerHTML = ""; return; }
      out.innerHTML = '<p class="ha-loading">正在加载索引…</p>';
      aibar.innerHTML = "";
      clearOneShot();

      loadInvert().then(function (inv) {
        if (inv && inv.terms) setDict(inv.terms);
        return loadAll(function (d, n) {
          out.innerHTML = '<p class="ha-loading">正在加载索引… ' + d + "/" + n + "</p>";
        });
      }).then(function (data) {
        var t0 = (window.performance && performance.now) ? performance.now() : 0;
        var groups = search(data, query);
        var t1 = (window.performance && performance.now) ? performance.now() : 0;
        render(out, groups, query);
        cur.query = query; cur.groups = groups;
        renderAIEntry();
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

    function renderAIEntry() {
      if (!cur.groups.length) { aibar.innerHTML = ""; return; }
      aibar.innerHTML =
        '<div class="ha-ai-bar">' +
          '<button class="ha-aibtn" type="button">✨ 用 AI 解释这些结果</button>' +
          '<span class="ha-ai-note">一次性解读，需要 API key</span>' +
        "</div>";
      aibar.querySelector(".ha-aibtn").addEventListener("click", startOneShot);
    }

    // ══════════════════════════════════════════════
    // 一次性解读搜索结果（与下面的问答互不影响）
    // ══════════════════════════════════════════════
    function startOneShot() {
      askKey(oneshot, runOneShot,
        "用 AI 解读搜索结果需要 DeepSeek API key。填一次即可，下面的问答也会共用。");
    }

    function runOneShot() {
      var myToken = ++oneshotToken;          // 本次解读的令牌
      function stale() { return myToken !== oneshotToken; }
      var question = cur.query;
      var picks = fetchPicks(cur.groups, AI_PICKS, 2);
      oneshot.hidden = false;
      oneshot.innerHTML = '<p class="ha-loading">正在读取资料…</p>';

      buildContext(picks, function (d, n) {
        if (stale()) return;
        oneshot.innerHTML = '<p class="ha-loading">正在读取资料… ' + d + "/" + n + "</p>";
      }).then(function (sources) {
        if (stale()) return;
        if (!sources.length) {
          oneshot.innerHTML = '<p class="ha-empty">没能读到资料正文，无法作答。</p>';
          return;
        }
        var chars = 0, i;
        for (i = 0; i < sources.length; i++) chars += sources[i].text.length;
        oneshot.innerHTML =
          '<div class="ha-oneshot-head">✨ AI 对「' + esc(question) + '」的解读' +
          '<button class="ha-oneshot-close" type="button" title="收起">×</button></div>' +
          '<div class="ha-oneshot-body"><p class="ha-loading">正在生成…</p></div>' +
          '<div class="ha-oneshot-src"></div>' +
          '<p class="ha-usage-slot"></p>';
        var bodyEl = oneshot.querySelector(".ha-oneshot-body");
        var srcEl = oneshot.querySelector(".ha-oneshot-src");
        oneshot.querySelector(".ha-oneshot-close").addEventListener("click", clearOneShot);

        streamChat(
          getKey(),
          [
            { role: "system", content: sess.system },
            { role: "user", content: contextPrompt(picks, sources, question) }
          ],
          function (d, body) {
            if (stale()) return;
            bodyEl.innerHTML = ansHtml(body, sources);
          },
          function (body, usage) {
            if (stale()) return;                 // 已被清空/重新搜索，丢弃结果
            bodyEl.innerHTML = ansHtml(body, sources);
            var cite = citedSources(body, sources);
            srcEl.innerHTML = cite.length ? sourcesHtml(cite) : "";
            var c = estCost(chars, body.length);
            var slot = oneshot.querySelector(".ha-usage-slot");
            if (slot) {
              slot.className = "ha-usage";
              slot.textContent =
                "以上为 AI 生成，请以资料来源为准。　" +
                (usage ? "输入 " + fmtNum(usage.prompt_tokens || 0) + " / 输出 " +
                  fmtNum(usage.completion_tokens || 0) + " tokens" : "") +
                "　本次约 ¥" + c.toFixed(4) +
                "　想接着问？用下面的对话框。";
            }
          },
          function (st, msg) {
            if (stale()) return;
            bodyEl.innerHTML = '<p class="ha-empty"><b>' + esc(failHint(st)) +
              "</b><br>" + esc(String(msg || "").slice(0, 300)) + "</p>";
            if (st === 401) { recoverKey(); }     // 直接把输入框摆出来让用户改
          }
        );
      });
    }

    // ══════════════════════════════════════════════
    // 问答：聊天气泡，AI 在左、用户在右
    // ══════════════════════════════════════════════
    function addMsg(role, html) {
      var d = document.createElement("div");
      d.className = "ha-msg " + role;
      d.innerHTML = '<div class="ha-bubble">' + html + "</div>";
      chat.appendChild(d);
      if (d.scrollIntoView) { d.scrollIntoView({ block: "nearest" }); }
      return d;
    }

    function greet() {
      chat.innerHTML = "";
      addMsg("ai",
        "<p>你好，我是黑柩 Wiki 的助手 👋</p>" +
        "<p>可以直接问我关于《黑柩》的任何问题 —— 人物、势力、某一段剧情、" +
        "某一季某一场发生了什么、某人说过什么话，都可以。</p>" +
        "<p>我会先检索 wiki 四站和跑团原始记录，再依据查到的原文回答，" +
        "并标出来源编号；资料里没有的我会直说没有。</p>" +
        '<p class="ha-greet-tip">第一次使用需要填一次 DeepSeek API key（只存在本页）。</p>');
    }

    function setBusy(v) {
      busy = v;
      go.disabled = v;
      sendBtn.disabled = v;
      followIn.disabled = v;
    }

    function updateStatus() {
      var chars = 0, i;
      for (i = 0; i < sess.sources.length; i++) chars += sess.sources[i].text.length;
      statusEl.textContent = sess.turns
        ? "已 " + sess.turns + " 轮 · 资料 " + sess.sources.length + " 条（约 " +
          fmtNum(chars) + " 字）· 累计估算 ¥" + sess.cost.toFixed(4) +
          (sess.turns >= MAX_TURNS ? "　｜　已达上限，点「清空对话」重开" : "")
        : "";
    }

    function send() {
      var text = (followIn.value || "").trim();
      if (!text) { followIn.focus(); return; }
      if (sess.turns >= MAX_TURNS) {
        statusEl.textContent = "已达轮数上限，点「清空对话」重新开始。";
        return;
      }
      askKey(keyInline, function () {
        followIn.value = "";
        addMsg("user", esc(text));
        askTurn(text);
      }, "问答复一次也不落地，需要 DeepSeek API key（只存本页，检索与解读共用）。");
    }

    function askTurn(question) {
      if (busy) return;
      var enumer = isEnumeration(question);
      var nPicks = enumer ? 12 : AI_PICKS;
      var nPerStation = enumer ? 3 : 2;
      var nRecSess = enumer ? 8 : 2;
      var overview = isOverview(question);
      var nRecLines = enumer ? 150 : (overview ? 80 : REC_MAX_LINES);
      var nRecChars = enumer ? 9000 : (overview ? 8000 : 3600);
      var maxSrc = enumer ? 20 : MAX_SOURCES;

      var switched = isNewTopic(question, sess.lastQuestion);
      if (switched) {
        sess.history = []; sess.sources = [];
        sess.turns = 0; sess.cost = 0;
      }
      sess.lastQuestion = question;

      setBusy(true);
      var placeholder = addMsg("ai",
        '<p class="ha-loading">正在检索资料…</p>');

      Promise.all([loadAll(), loadInvert()]).then(function (pre) {
        var data = pre[0], inv = pre[1];
        if (inv && inv.terms) setDict(inv.terms);

        var groups = search(data, question);
        var picks = fetchPicks(groups, nPicks, nPerStation) || [];

        var have = {}, i;
        for (i = 0; i < sess.sources.length; i++) {
          have[sess.sources[i].stKey + "|" + sess.sources[i].url] = 1;
        }
        var first = sess.turns === 0;
        var wantFresh = first ? nPicks : (enumer ? 6 : 2);
        var fresh = [];
        for (i = 0; i < picks.length && fresh.length < wantFresh; i++) {
          var kk = picks[i].st.key + "|" + urlOf(picks[i].st.key, picks[i].e);
          if (have[kk]) continue;
          fresh.push(picks[i]);
        }
        if (sess.sources.length >= maxSrc) fresh = [];

        var wikiP = fresh.length
          ? buildContext(fresh, function (d, n) {
              placeholder.querySelector(".ha-bubble").innerHTML =
                '<p class="ha-loading">正在读取 wiki 资料… ' + d + "/" + n + "</p>";
            })
          : Promise.resolve([]);

        var recP = loadRecords().then(function (entries) {
          var hits = [], seen = {}, i6;
          function push(e) {
            if (!e || seen[e.file]) return;
            seen[e.file] = 1; hits.push(e);
          }
          // ── 场次选取：统一打分，不再「分阶段先到先得」 ──
          // 旧实现是「季名→倒排→wiki→摘要」依次 push，先到的占满名额，
          // 问「顺风车筷子和碗」时「顺风车」先把名额吃光，含筷子的那场反而进不来。
          var season = matchSeason(question, entries);
          var ord = ordinalHint(question);
          var locked = false;

          // 顺序词 + 季名 = 唯一确定，直接锁死
          if (season && ord) {
            var pool = [], pi;
            for (pi = 0; pi < entries.length; pi++) {
              if (entries[pi].season === season) pool.push(entries[pi]);
            }
            if (pool.length) {
              // 网页版没有全量缓存，无法按实体行数定位，只能给季末/季首 3 场让模型自己挑。
              // （插件版能按「该实体在这一季出现了几行」精确取，见 answer.js）
              var tgt = ord === "last" ? pool.slice(-3) : pool.slice(0, 3);
              for (pi = 0; pi < tgt.length; pi++) push(tgt[pi]);
              locked = true;
            }
          }

          if (!locked) {
            // 发言人 → 每场说了多少行
            var speakerStats = {};
            var snames = namesInText(question, inv && inv.speakers, 3), si, sj;
            for (si = 0; si < snames.length; si++) {
              var spArr = (inv.speakers && inv.speakers[snames[si]]) || [];
              for (sj = 0; sj < spArr.length; sj++) {
                var pp = spArr[sj].split(":");
                var ff = "session/" + pp[0] + ".tsv";
                speakerStats[ff] = (speakerStats[ff] || 0) + (parseInt(pp[1], 10) || 0);
              }
            }

            // 倒排索引
            var invScores = {};
            var invFound = sessionsFromInvert(inv, question, 30);
            for (si = 0; si < invFound.length; si++) {
              invScores["session/" + invFound[si].sid + ".tsv"] = invFound[si].score;
            }

            // wiki 跑团站已点名
            var wikiPairs = {};
            var fw0 = sessionsFromGroups(groups);
            for (si = 0; si < fw0.length; si++) wikiPairs[fw0[si].season + "|" + fw0[si].no] = 1;

            var scored = [], e6;
            for (si = 0; si < entries.length; si++) {
              e6 = entries[si];
              var sc = 0;
              if (season && e6.season === season) sc += 1000;
              if (speakerStats[e6.file]) sc += Math.min(200, speakerStats[e6.file] * 0.5);
              if (invScores[e6.file]) sc += invScores[e6.file] * 0.3;
              if (wikiPairs[e6.season + "|" + e6.no]) sc += 80;
              if (sc > 0) scored.push({ e: e6, sc: sc });
            }
            scored.sort(function (a, b) { return b.sc - a.sc; });
            for (si = 0; si < scored.length && hits.length < nRecSess; si++) push(scored[si].e);

            // 兜底：摘要关键词
            if (!hits.length) {
              var bk = searchRecords(entries, question);
              for (si = 0; si < bk.length; si++) push(bk[si]);
            }
          }

          if (!hits.length) return [];
          // 同样是名字扫描，保证「鸣」「白」这类单字名能命中自己的台词
          var speakerSet = {}, asked2 = namesInText(question, inv && inv.speakers, 3), k7;
          for (k7 = 0; k7 < asked2.length; k7++) speakerSet[asked2[k7]] = 1;
          return Promise.all(hits.map(function (h) {
            return fetchRecordLines(h, question, nRecLines, nRecChars, speakerSet);
          }));
        }).then(function (recs) {
          var a2 = [], i2;
          for (i2 = 0; i2 < (recs || []).length; i2++) if (recs[i2]) a2.push(recs[i2]);
          return a2;
        }).catch(function () { return []; });

        var tblP = loadTables().then(function (t) {
          return tablesToSource(t, question);
        }).catch(function () { return null; });

        Promise.all([wikiP, recP, tblP]).then(function (res) {
          var arr = res[0] || [], recs = res[1] || [], tblSrc = res[2];
          var base = sess.sources.length;
          var added = [], i3, s2;
          for (i3 = 0; i3 < arr.length && (base + added.length) < maxSrc; i3++) {
            s2 = arr[i3]; s2.n = base + added.length + 1;
            sess.sources.push(s2); added.push(s2);
          }
          for (i3 = 0; i3 < recs.length && sess.sources.length < maxSrc; i3++) {
            s2 = recordToSource(recs[i3], { withSummary: overview });
            s2.n = sess.sources.length + 1;
            sess.sources.push(s2); added.push(s2);
          }
          if (tblSrc && sess.sources.length < maxSrc) {
            tblSrc.n = sess.sources.length + 1;
            sess.sources.push(tblSrc); added.push(tblSrc);
          }
          proceed(added, first, switched);
        });

        function proceed(added, first, switched) {
          var recAdded = [], i4;
          for (i4 = 0; i4 < added.length; i4++) {
            if (added[i4].stKey === "record") recAdded.push(added[i4]);
          }
          var useSources = added.length ? added : sess.sources.slice(-3);
          var block = sourcesBlock(useSources);
          var curUser = (block ? block + "\n\n" : "") +
            (first ? "问题：" : "追问：") + question;
          var msgs = [{ role: "system", content: sess.system }]
            .concat(trimHistory(sess.history))
            .concat([{ role: "user", content: curUser }]);

          var chars = 0, i5;
          for (i5 = 0; i5 < useSources.length; i5++) chars += useSources[i5].text.length;
          placeholder.querySelector(".ha-bubble").innerHTML =
            '<p class="ha-loading">正在生成回答…</p>';

          streamChat(
            getKey(), msgs,
            function (d, body) {
              placeholder.querySelector(".ha-bubble").innerHTML = ansHtml(body, sess.sources);
            },
            function (body, usage) {
              setBusy(false);
              sess.turns++;
              sess.history.push({ role: "user", content: question });
              sess.history.push({ role: "assistant", content: body });
              sess.history = trimHistory(sess.history);

              var bubble = placeholder.querySelector(".ha-bubble");
              bubble.innerHTML = ansHtml(body, sess.sources);
              var cite = citedSources(body, sess.sources);
              if (cite.length) {
                var sd = document.createElement("div");
                sd.className = "ha-turn-src";
                sd.innerHTML = sourcesHtml(cite);
                bubble.appendChild(sd);
              }
              var c = estCost(chars, body.length);
              sess.cost += c;
              var u = document.createElement("p");
              u.className = "ha-msg-usage";
              u.textContent = (usage ? fmtNum(usage.prompt_tokens || 0) + "/" +
                fmtNum(usage.completion_tokens || 0) + " tokens" : "") +
                "　本轮约 ¥" + c.toFixed(4) +
                (recAdded.length ? "　含 " + recAdded.length + " 场原始记录" : "");
              bubble.appendChild(u);
              updateStatus();
              if (switched) { statusEl.textContent = "（已按新话题重置上下文）"; }
              followIn.focus();
            },
            function (st, msg) {
              setBusy(false);
              placeholder.querySelector(".ha-bubble").innerHTML =
                '<p class="ha-empty"><b>' + esc(failHint(st)) + "</b><br>" +
                esc(String(msg || "").slice(0, 300)) + "</p>";
              if (st === 401) { recoverKey(); }
            }
          );
        }
      });
    }

    // ── 设置 / 修改 API key（常驻入口，随时可改）──
    if (setKeyBtn) {
      setKeyBtn.addEventListener("click", function () {
        renderKeyBox(keyInline,
          getKey()
            ? "当前已保存一个 key。填入新的会覆盖它；也可以点「清除 key」后重填。"
            : "填入你的 DeepSeek API key。检索区的一键解读与这里的问答共用同一个 key，只存在本页。",
          function () { followIn.focus(); });
      });
    }

    // ── 事件 ──
    clearBtn.addEventListener("click", function () {
      q.value = ""; out.innerHTML = ""; aibar.innerHTML = "";
      clearOneShot();
      cur.query = ""; cur.groups = [];
      host.querySelector(".ha-meta").innerHTML = "跨四站检索：设定 · 花絮 · 跑团 · 分析";
      if (window.history && history.replaceState) {
        history.replaceState(null, "", location.pathname + location.search);
      }
      q.focus();
    });

    go.addEventListener("click", runSearch);
    q.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" || ev.keyCode === 13) { ev.preventDefault(); runSearch(); }
    });

    sendBtn.addEventListener("click", send);
    followIn.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" || ev.keyCode === 13) { ev.preventDefault(); send(); }
    });

    endBtn.addEventListener("click", function () {
      sess.sources = []; sess.history = []; sess.turns = 0; sess.cost = 0;
      sess.lastQuestion = "";
      greet();
      statusEl.textContent = "对话已清空。";
      setBusy(false);
      followIn.value = "";
      followIn.focus();
    });

    // ── 初始化：问答区一开始就在，先打招呼 ──
    updateKeyBtn();
    greet();
    loadInvert().then(function (inv) {
      if (inv && inv.terms) setDict(inv.terms);
      return loadAll();
    });

    var m = /[#&]q=([^&]+)/.exec(location.hash || "");
    if (m) {
      try { q.value = decodeURIComponent(m[1]); } catch (e) { q.value = m[1]; }
      runSearch();
    }
    q.focus();
  }

  // ══════════════════════════════════════════════════════════
  function boot() {
    // 合并后两个容器都渲染同一套界面：
    //   #heijiu-ask（推荐）／ #heijiu-chat（旧页面兼容）
    var host = document.getElementById("heijiu-ask") ||
               document.getElementById("heijiu-chat");
    if (host) { mountAsk(host); return; }
    var alt = document.querySelector("[data-heijiu-ask]") ||
              document.querySelector("[data-heijiu-chat]");
    if (alt) { mountAsk(alt); }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
