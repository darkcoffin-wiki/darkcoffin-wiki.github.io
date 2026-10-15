/* 黑柩花絮 Wiki · 客户端增强（服务端渲染为主，这里只做筛选/搜索） */
(function () {
  var rel = window.SITE_REL || "";
  // 列表页所在目录：花絮站是 entry/，跑团站是 session/（两站共用本脚本）
  var list = window.SITE_LIST || "entry/";
  var q = document.getElementById("q");
  var box = document.getElementById("q-results");
  var index = null;

  // 索引路径：优先用各站自带的 window.SITE_INDEX（相对本站根），
  // 否则退回共享的 ../assets/search.json（花絮/跑团/设定三站沿用原行为）
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
      return '<a href="' + rel + list + e.id + "-" + e.slug + '.html">' +
        e.title + '<br><span class="muted">' + e.kind + " · " +
        (e.tags || []).slice(0, 5).join("、") + "</span></a>";
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
