/*
 * 전국 저수지 찾기 — Supabase 의 reservoirs 테이블을 읽어 화면에 보여준다.
 *
 * 공개(publishable) 키는 브라우저에 노출돼도 되는 키다. sql/supabase/01_schema.sql 이
 * RLS 로 "읽기만 허용" 해 두었기 때문에 이 키로는 데이터를 바꿀 수 없다.
 */
const SUPABASE_URL = "https://dqcvcxfizoimakcfzldo.supabase.co";
const SUPABASE_KEY = "sb_publishable_LE1E24oHPLUv8gB_Brg-Cg_Cz5OO3IV";

const PAGE_SIZE = 50;
const LIST_COLUMNS = "id,name,sido,sigungu,address,effective_storage,benefit_area,dam_height,completed_year";
const SORTS = {
  name: "name.asc,id.asc",
  storage: "effective_storage.desc.nullslast,id.asc",
  area: "benefit_area.desc.nullslast,id.asc",
  height: "dam_height.desc.nullslast,id.asc",
  newest: "completed_year.desc.nullslast,id.asc",
  oldest: "completed_year.asc.nullslast,id.asc",
};
// 상세 보기에 보여줄 항목: [컬럼, 이름, 단위]
const DETAIL_FIELDS = [
  ["sido", "시도"],
  ["sigungu", "시군구"],
  ["address", "소재지"],
  ["road_address", "도로명주소"],
  ["manager", "관리기관"],
  ["total_storage", "총저수량", "천㎥"],
  ["effective_storage", "유효저수량", "천㎥"],
  ["benefit_area", "수혜면적", "ha"],
  ["basin_area", "유역면적", "ha"],
  ["full_water_area", "만수면적", "ha"],
  ["dam_height", "제당 높이", "m"],
  ["dam_length", "제당 길이", "m"],
  ["completed_year", "준공연도"],
  ["facility_code", "시설코드"],
  ["source", "자료 출처"],
];

const $ = (id) => document.getElementById(id);
const els = {
  form: $("filters"), q: $("q"), sido: $("sido"), sigungu: $("sigungu"), sort: $("sort"),
  reset: $("reset"), status: $("status"), table: $("results"), rows: $("rows"),
  prev: $("prev"), next: $("next"), pageInfo: $("page-info"),
  detail: $("detail"), detailTitle: $("detail-title"), detailList: $("detail-list"),
};

const state = { q: "", sido: "", sigungu: "", sort: "name", page: 0, total: 0 };
let regions = [];          // [{sido, sigungu, reservoir_count}]
let pending = null;        // 진행 중인 요청 (새 검색이 시작되면 취소)

// ---------- Supabase REST 호출 ----------

class ApiError extends Error {
  constructor(status, body) {
    super(body?.message || `HTTP ${status}`);
    this.status = status;
    this.code = body?.code;
  }
}

async function api(path, params, { signal, count = false } = {}) {
  const url = new URL(`/rest/v1/${path}`, SUPABASE_URL);
  for (const [k, v] of params) url.searchParams.append(k, v);
  const headers = { apikey: SUPABASE_KEY, Accept: "application/json" };
  if (count) headers.Prefer = "count=exact";
  const res = await fetch(url, { headers, signal });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, body);
  // Content-Range: 0-49/14366  ->  전체 개수 14366
  const total = count ? Number((res.headers.get("Content-Range") || "").split("/")[1]) : undefined;
  return { data: body, total };
}

// PostgREST 의 or=(...) 안에서는 , ( ) 등이 구분자라서 값을 큰따옴표로 감싸야 한다
function quoteFilterValue(value) {
  return `"${value.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
}

function listParams() {
  const params = [["select", LIST_COLUMNS], ["order", SORTS[state.sort] || SORTS.name],
    ["offset", String(state.page * PAGE_SIZE)], ["limit", String(PAGE_SIZE)]];
  if (state.sido) params.push(["sido", `eq.${state.sido}`]);
  if (state.sigungu) params.push(["sigungu", `eq.${state.sigungu}`]);
  // 사용자가 넣은 * % 는 와일드카드로 해석되지 않도록 지운다
  const q = state.q.replace(/[*%]/g, "").trim();
  if (q) {
    const pattern = quoteFilterValue(`*${q}*`);
    params.push(["or", `(name.ilike.${pattern},address.ilike.${pattern})`]);
  }
  return params;
}

// ---------- 화면 그리기 ----------

const numberFormat = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 });
const smallNumberFormat = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 4 });

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "";
  const n = Number(value);
  return (Math.abs(n) < 1 ? smallNumberFormat : numberFormat).format(n);
}

function el(tag, props = {}, children = []) {
  const node = Object.assign(document.createElement(tag), props);
  for (const child of children) node.append(child);
  return node;
}

function numCell(value, label) {
  const td = el("td", { className: "num", textContent: formatNumber(value) });
  td.dataset.label = label;
  return td;
}

function renderRows(rows) {
  els.rows.replaceChildren();
  if (!rows.length) {
    els.rows.append(el("tr", {}, [el("td", { colSpan: 6, className: "empty",
      textContent: "조건에 맞는 저수지가 없습니다. 검색어나 지역을 바꿔 보세요." })]));
    return;
  }
  for (const r of rows) {
    const region = [r.sido, r.sigungu].filter(Boolean).join(" ");
    const tr = el("tr", { tabIndex: 0 }, [
      el("td", {}, [el("span", { className: "name", textContent: r.name }),
        el("span", { className: "region", textContent: region })]),
      el("td", { textContent: r.address || "" }),
      numCell(r.effective_storage, "유효저수량(천㎥)"),
      numCell(r.benefit_area, "수혜면적(ha)"),
      numCell(r.dam_height, "제당(m)"),
      el("td", { className: "num", textContent: r.completed_year ?? "" }),
    ]);
    tr.lastChild.dataset.label = "준공";
    tr.setAttribute("aria-label", `${r.name} 상세 보기`);
    tr.addEventListener("click", () => showDetail(r.id));
    tr.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); showDetail(r.id); }
    });
    els.rows.append(tr);
  }
}

function renderStatus() {
  const where = [state.sido, state.sigungu].filter(Boolean).join(" ");
  const parts = [];
  if (where) parts.push(where);
  if (state.q) parts.push(`'${state.q}' 검색`);
  els.status.className = "status";
  els.status.replaceChildren(
    parts.length ? `${parts.join(", ")} 결과 ` : "전체 저수지 ",
    el("strong", { textContent: `${state.total.toLocaleString("ko-KR")}개` }),
  );
  const pages = Math.max(1, Math.ceil(state.total / PAGE_SIZE));
  els.pageInfo.textContent = `${state.page + 1} / ${pages.toLocaleString("ko-KR")}`;
  els.prev.disabled = state.page === 0;
  els.next.disabled = state.page >= pages - 1;
}

function showError(err) {
  els.status.className = "status error";
  if (err.code === "PGRST205" || err.code === "42P01" || err.status === 404) {
    els.status.textContent = "Supabase 에 저수지 테이블이 없습니다. sql/supabase 의 스크립트를 먼저 실행해 주세요.";
  } else if (err.status === 401 || err.status === 403) {
    els.status.textContent = "Supabase 접근 권한이 없습니다. 공개 키와 RLS 정책을 확인해 주세요.";
  } else {
    els.status.textContent = `저수지 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요. (${err.message})`;
  }
  els.rows.replaceChildren();
  els.pageInfo.textContent = "";
  els.prev.disabled = els.next.disabled = true;
}

// ---------- 데이터 불러오기 ----------

async function loadList() {
  pending?.abort();
  const controller = (pending = new AbortController());
  els.table.classList.add("loading");
  try {
    const { data, total } = await api("reservoirs", listParams(), { signal: controller.signal, count: true });
    state.total = Number.isFinite(total) ? total : data.length;
    renderRows(data);
    renderStatus();
  } catch (err) {
    if (err.name !== "AbortError") showError(err);
  } finally {
    if (pending === controller) {
      els.table.classList.remove("loading");
      pending = null;
    }
  }
}

async function loadRegions() {
  try {
    const { data } = await api("reservoir_region_counts", [["select", "sido,sigungu,reservoir_count"]]);
    regions = data;
  } catch {
    regions = [];  // 지역 목록이 없어도 검색은 되게 둔다
  }
  const sidos = [...new Set(regions.map((r) => r.sido).filter(Boolean))].sort((a, b) => a.localeCompare(b, "ko"));
  els.sido.replaceChildren(el("option", { value: "", textContent: "전체" }),
    ...sidos.map((s) => el("option", { value: s, textContent: s })));
  els.sido.value = sidos.includes(state.sido) ? state.sido : "";
  state.sido = els.sido.value;
  fillSigungu();
}

function fillSigungu() {
  const list = regions.filter((r) => r.sido === state.sido && r.sigungu)
    .sort((a, b) => a.sigungu.localeCompare(b.sigungu, "ko"));
  els.sigungu.replaceChildren(el("option", { value: "", textContent: "전체" }),
    ...list.map((r) => el("option", { value: r.sigungu,
      textContent: `${r.sigungu} (${Number(r.reservoir_count).toLocaleString("ko-KR")})` })));
  els.sigungu.disabled = !state.sido;
  els.sigungu.value = list.some((r) => r.sigungu === state.sigungu) ? state.sigungu : "";
  state.sigungu = els.sigungu.value;
}

async function showDetail(id) {
  els.detailTitle.textContent = "불러오는 중…";
  els.detailList.replaceChildren();
  if (!els.detail.open) els.detail.showModal();
  try {
    const { data } = await api("reservoirs", [["select", "*"], ["id", `eq.${id}`]]);
    const r = data[0];
    if (!r) throw new Error("저수지를 찾을 수 없습니다.");
    els.detailTitle.textContent = r.name;
    for (const [key, label, unit] of DETAIL_FIELDS) {
      const value = r[key];
      if (value === null || value === undefined || value === "") continue;
      const text = typeof value === "number" && key !== "completed_year"
        ? `${formatNumber(value)}${unit ? ` ${unit}` : ""}` : String(value);
      els.detailList.append(el("dt", { textContent: label }), el("dd", { textContent: text }));
    }
  } catch (err) {
    els.detailTitle.textContent = "정보를 불러오지 못했습니다";
    els.detailList.append(el("dd", { textContent: err.message }));
  }
}

// ---------- 주소창(?q=&sido=) 과 상태 맞추기: 검색 결과를 링크로 공유할 수 있게 ----------

function readUrl() {
  const p = new URLSearchParams(location.search);
  state.q = p.get("q") || "";
  state.sido = p.get("sido") || "";
  state.sigungu = p.get("sigungu") || "";
  state.sort = SORTS[p.get("sort")] ? p.get("sort") : "name";
  state.page = Math.max(0, (parseInt(p.get("page"), 10) || 1) - 1);
  els.q.value = state.q;
  els.sort.value = state.sort;
}

function writeUrl() {
  const p = new URLSearchParams();
  if (state.q) p.set("q", state.q);
  if (state.sido) p.set("sido", state.sido);
  if (state.sigungu) p.set("sigungu", state.sigungu);
  if (state.sort !== "name") p.set("sort", state.sort);
  if (state.page) p.set("page", String(state.page + 1));
  const query = p.toString();
  history.replaceState(null, "", query ? `?${query}` : location.pathname);
}

function update({ resetPage = true } = {}) {
  if (resetPage) state.page = 0;
  writeUrl();
  loadList();
}

// ---------- 이벤트 ----------

let typingTimer;
els.q.addEventListener("input", () => {
  clearTimeout(typingTimer);
  typingTimer = setTimeout(() => { state.q = els.q.value.trim(); update(); }, 300);
});
els.form.addEventListener("submit", (e) => {
  e.preventDefault();
  clearTimeout(typingTimer);
  state.q = els.q.value.trim();
  update();
});
els.sido.addEventListener("change", () => {
  state.sido = els.sido.value;
  state.sigungu = "";
  fillSigungu();
  update();
});
els.sigungu.addEventListener("change", () => { state.sigungu = els.sigungu.value; update(); });
els.sort.addEventListener("change", () => { state.sort = els.sort.value; update(); });
els.reset.addEventListener("click", () => {
  Object.assign(state, { q: "", sido: "", sigungu: "", sort: "name" });
  els.q.value = "";
  els.sort.value = "name";
  els.sido.value = "";
  fillSigungu();
  update();
});
els.prev.addEventListener("click", () => { state.page--; update({ resetPage: false }); scrollTo({ top: 0 }); });
els.next.addEventListener("click", () => { state.page++; update({ resetPage: false }); scrollTo({ top: 0 }); });
els.detail.addEventListener("click", (e) => { if (e.target === els.detail) els.detail.close(); });

readUrl();
loadRegions().then(() => update({ resetPage: false }));
