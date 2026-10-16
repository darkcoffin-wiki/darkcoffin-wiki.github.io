/* 黑柩花絮 Wiki · 客户端增强（服务端渲染为主，这里只做筛选/搜索） */
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
