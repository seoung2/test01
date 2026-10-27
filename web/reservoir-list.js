/*
 * 전국 저수지 목록 위젯
 *
 * 홈페이지 아무 곳에 아래 두 줄을 넣으면 검색·필터·정렬이 되는 저수지 표가 나타난다.
 *
 *   <div class="reservoir-list" data-src="/reservoirs/data/reservoirs.json"></div>
 *   <script src="/reservoirs/reservoir-list.js" defer></script>
 *
 * div 속성
 *   data-src        JSON 경로 (scripts/export_web_data.py 가 만든 파일). 기본값: 이 스크립트 옆 data/reservoirs.json
 *   data-page-size  한 페이지 행 수 (기본 50)
 *   data-sido       처음에 선택해 둘 시도 (예: "경상북도")
 *
 * 색·글꼴은 .rsv 의 CSS 변수(--rsv-accent 등)를 홈페이지 CSS 에서 덮어써서 바꿀 수 있다.
 */
(function () {
  "use strict";

  var SCRIPT_SRC = document.currentScript && document.currentScript.src;
  var DEFAULT_SRC = SCRIPT_SRC ? new URL("data/reservoirs.json", SCRIPT_SRC).href : "data/reservoirs.json";

  // 표에 보여줄 컬럼과 머리글 (데이터에 없는 컬럼은 자동으로 빠진다)
  var TABLE_COLUMNS = [
    { key: "시설명", label: "시설명" },
    { key: "시도", label: "시도" },
    { key: "시군구", label: "시군구" },
    { key: "지번주소", label: "소재지" },
    { key: "총저수량", label: "총저수량(천㎥)", number: true },
    { key: "유효저수량", label: "유효저수량(천㎥)", number: true },
    { key: "수혜면적", label: "수혜면적(ha)", number: true },
    { key: "만수면적", label: "만수면적(ha)", number: true },
    { key: "제당높이", label: "제당높이(m)", number: true },
    { key: "제당길이", label: "제당길이(m)", number: true },
    { key: "준공연도", label: "준공연도", number: true }
  ];

  var CSS = [
    ".rsv{--rsv-accent:#1f6feb;--rsv-border:#d0d7de;--rsv-muted:#57606a;--rsv-bg:#fff;--rsv-stripe:#f6f8fa;",
    "font:inherit;color:inherit;max-width:100%}",
    ".rsv-controls{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px;align-items:center}",
    ".rsv-controls input,.rsv-controls select,.rsv button{font:inherit;padding:6px 8px;border:1px solid var(--rsv-border);",
    "border-radius:6px;background:var(--rsv-bg);color:inherit}",
    ".rsv-controls input{flex:1 1 200px;min-width:0}",
    ".rsv button{cursor:pointer}.rsv button:disabled{opacity:.4;cursor:default}",
    ".rsv-summary{color:var(--rsv-muted);font-size:.9em;margin:4px 0 8px}",
    ".rsv-scroll{overflow-x:auto;border:1px solid var(--rsv-border);border-radius:6px}",
    ".rsv table{border-collapse:collapse;width:100%;font-size:.92em;background:var(--rsv-bg)}",
    ".rsv th,.rsv td{padding:6px 10px;border-bottom:1px solid var(--rsv-border);text-align:left;white-space:nowrap}",
    ".rsv td.rsv-num,.rsv th.rsv-num{text-align:right;font-variant-numeric:tabular-nums}",
    ".rsv tbody tr:nth-child(even){background:var(--rsv-stripe)}",
    ".rsv th{position:sticky;top:0;background:var(--rsv-stripe);cursor:pointer;user-select:none}",
    ".rsv th[aria-sort=ascending]::after{content:' ▲';color:var(--rsv-accent)}",
    ".rsv th[aria-sort=descending]::after{content:' ▼';color:var(--rsv-accent)}",
    ".rsv-pager{display:flex;gap:8px;align-items:center;justify-content:center;margin-top:8px}",
    ".rsv-empty{padding:24px;text-align:center;color:var(--rsv-muted)}"
  ].join("");

  function injectStyle() {
    if (document.getElementById("rsv-style")) return;
    var style = document.createElement("style");
    style.id = "rsv-style";
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { node.appendChild(c); });
    return node;
  }

  function formatNumber(v) {
    if (v === null || v === undefined) return "";
    // 1 미만 값(예: 0.0067)이 0 으로 보이지 않게 소수 자릿수를 늘린다
    return Number(v).toLocaleString("ko-KR", { maximumFractionDigits: Math.abs(v) < 1 ? 4 : 2 });
  }

  function uniqueSorted(values) {
    return Array.from(new Set(values.filter(Boolean))).sort(function (a, b) { return a.localeCompare(b, "ko"); });
  }

  function toCsv(columns, rows) {
    var esc = function (v) {
      v = v === null || v === undefined ? "" : String(v);
      return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
    };
    return "﻿" + [columns.map(esc).join(",")].concat(rows.map(function (r) {
      return r.map(esc).join(",");
    })).join("\n");
  }

  function Widget(root, data) {
    var idx = {};
    data.columns.forEach(function (c, i) { idx[c] = i; });
    this.root = root;
    this.data = data;
    this.idx = idx;
    this.columns = TABLE_COLUMNS.filter(function (c) { return c.key in idx; });
    this.pageSize = parseInt(root.getAttribute("data-page-size"), 10) || 50;
    this.state = { sido: root.getAttribute("data-sido") || "", sigungu: "", query: "", sort: null, desc: false, page: 0 };
    this.build();
    this.update();
  }

  Widget.prototype.value = function (row, key) {
    return key in this.idx ? row[this.idx[key]] : null;
  };

  Widget.prototype.build = function () {
    var self = this;
    this.search = el("input", { type: "search", placeholder: "저수지 이름·소재지 검색", "aria-label": "검색" });
    this.sidoSelect = el("select", { "aria-label": "시도" });
    this.sigunguSelect = el("select", { "aria-label": "시군구" });
    this.download = el("button", { type: "button", text: "CSV 내려받기" });
    this.summary = el("div", { class: "rsv-summary", "aria-live": "polite" });
    this.thead = el("thead");
    this.tbody = el("tbody");
    this.prev = el("button", { type: "button", text: "이전" });
    this.next = el("button", { type: "button", text: "다음" });
    this.pageInfo = el("span");

    var sidos = uniqueSorted(this.data.rows.map(function (r) { return self.value(r, "시도"); }));
    this.fillSelect(this.sidoSelect, "전체 시도", sidos, this.state.sido);

    var headRow = el("tr");
    this.columns.forEach(function (col) {
      var th = el("th", { scope: "col", text: col.label, tabindex: "0", class: col.number ? "rsv-num" : "" });
      var sortBy = function () {
        self.state.desc = self.state.sort === col.key ? !self.state.desc : false;
        self.state.sort = col.key;
        self.state.page = 0;
        self.update();
      };
      th.addEventListener("click", sortBy);
      th.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sortBy(); } });
      col.th = th;
      headRow.appendChild(th);
    });
    this.thead.appendChild(headRow);

    var timer;
    this.search.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () { self.state.query = self.search.value.trim(); self.state.page = 0; self.update(); }, 150);
    });
    this.sidoSelect.addEventListener("change", function () {
      self.state.sido = self.sidoSelect.value;
      self.state.sigungu = "";
      self.state.page = 0;
      self.update();
    });
    this.sigunguSelect.addEventListener("change", function () {
      self.state.sigungu = self.sigunguSelect.value;
      self.state.page = 0;
      self.update();
    });
    this.prev.addEventListener("click", function () { self.state.page--; self.render(); });
    this.next.addEventListener("click", function () { self.state.page++; self.render(); });
    this.download.addEventListener("click", function () { self.downloadCsv(); });

    this.root.classList.add("rsv");
    this.root.textContent = "";
    this.root.appendChild(el("div", { class: "rsv-controls" }, [this.search, this.sidoSelect, this.sigunguSelect, this.download]));
    this.root.appendChild(this.summary);
    this.root.appendChild(el("div", { class: "rsv-scroll" }, [el("table", {}, [this.thead, this.tbody])]));
    this.root.appendChild(el("div", { class: "rsv-pager" }, [this.prev, this.pageInfo, this.next]));
  };

  Widget.prototype.fillSelect = function (select, allLabel, options, selected) {
    select.textContent = "";
    select.appendChild(el("option", { value: "", text: allLabel }));
    options.forEach(function (o) { select.appendChild(el("option", { value: o, text: o })); });
    select.value = options.indexOf(selected) >= 0 ? selected : "";
  };

  // 필터·정렬을 다시 계산하고 그린다
  Widget.prototype.update = function () {
    var self = this, s = this.state;
    var inSido = this.data.rows.filter(function (r) { return !s.sido || self.value(r, "시도") === s.sido; });
    var sigungus = uniqueSorted(inSido.map(function (r) { return self.value(r, "시군구"); }));
    this.fillSelect(this.sigunguSelect, "전체 시군구", sigungus, s.sigungu);
    this.sigunguSelect.disabled = !s.sido;
    s.sigungu = this.sigunguSelect.value;

    var q = s.query.replace(/\s+/g, "").toLowerCase();
    this.filtered = inSido.filter(function (r) {
      if (s.sigungu && self.value(r, "시군구") !== s.sigungu) return false;
      if (!q) return true;
      return ["시설명", "지번주소", "시군구"].some(function (k) {
        var v = self.value(r, k);
        return v && String(v).replace(/\s+/g, "").toLowerCase().indexOf(q) >= 0;
      });
    });

    if (s.sort) {
      var i = this.idx[s.sort], dir = s.desc ? -1 : 1;
      var isNum = this.columns.some(function (c) { return c.key === s.sort && c.number; });
      this.filtered = this.filtered.slice().sort(function (a, b) {
        var x = a[i], y = b[i];
        if (x === null || x === undefined) return 1;   // 빈 값은 항상 뒤로
        if (y === null || y === undefined) return -1;
        return dir * (isNum ? Number(x) - Number(y) : String(x).localeCompare(String(y), "ko"));
      });
    }
    this.columns.forEach(function (c) {
      if (c.key === s.sort) c.th.setAttribute("aria-sort", s.desc ? "descending" : "ascending");
      else c.th.removeAttribute("aria-sort");
    });
    this.render();
  };

  Widget.prototype.render = function () {
    var self = this, s = this.state;
    var pages = Math.max(1, Math.ceil(this.filtered.length / this.pageSize));
    s.page = Math.min(Math.max(0, s.page), pages - 1);
    var start = s.page * this.pageSize;

    this.tbody.textContent = "";
    var pageRows = this.filtered.slice(start, start + this.pageSize);
    if (!pageRows.length) {
      this.tbody.appendChild(el("tr", {}, [el("td", { colspan: String(this.columns.length), class: "rsv-empty", text: "조건에 맞는 저수지가 없습니다." })]));
    }
    var frag = document.createDocumentFragment();
    pageRows.forEach(function (r) {
      frag.appendChild(el("tr", {}, self.columns.map(function (c) {
        var v = self.value(r, c.key);
        var text = c.number && c.key !== "준공연도" ? formatNumber(v) : (v === null ? "" : String(v));
        return el("td", { text: text, class: c.number ? "rsv-num" : "" });
      })));
    });
    this.tbody.appendChild(frag);

    this.summary.textContent = "전체 " + this.data.rows.length.toLocaleString("ko-KR") + "개 중 " +
      this.filtered.length.toLocaleString("ko-KR") + "개";
    this.pageInfo.textContent = (s.page + 1) + " / " + pages;
    this.prev.disabled = s.page === 0;
    this.next.disabled = s.page >= pages - 1;
  };

  Widget.prototype.downloadCsv = function () {
    var blob = new Blob([toCsv(this.data.columns, this.filtered)], { type: "text/csv;charset=utf-8" });
    var a = el("a", { href: URL.createObjectURL(blob), download: "reservoirs.csv" });
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  };

  function mount(root) {
    if (root.getAttribute("data-rsv-mounted")) return;
    root.setAttribute("data-rsv-mounted", "1");
    root.textContent = "저수지 목록을 불러오는 중…";
    fetch(root.getAttribute("data-src") || DEFAULT_SRC)
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) { root.reservoirList = new Widget(root, data); })
      .catch(function (err) {
        root.textContent = "저수지 목록을 불러오지 못했습니다. (" + err.message + ")";
      });
  }

  function init() {
    injectStyle();
    Array.prototype.forEach.call(document.querySelectorAll(".reservoir-list, #reservoir-list"), mount);
  }

  window.ReservoirList = { mount: function (root) { injectStyle(); mount(root); } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
