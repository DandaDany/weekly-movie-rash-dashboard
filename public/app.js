const MARKET_ORDER = ["TW", "HK", "VN", "ID", "MY", "SG"];

const MARKET_CONFIG = {
  TW: {
    label: "台灣",
    status: "blocked",
    source: "TFAI 全國電影票房統計",
    sourceUrl: "https://boxofficetw.tfai.org.tw/",
    note: "官方首頁週榜 parser 已完成；GitHub-hosted runner 目前仍被來源存取控制擋下。若未來可正常取得，會自動切換為 live。",
  },
  HK: {
    label: "香港",
    status: "blocked",
    source: "HKTDC FILMART",
    sourceUrl: "https://hkfilmart.hktdc.com/conference/hkfilmart/en/hong-kong-weekly-box-office",
    note: "公開來源目前可連線，但尚未取得可穩定驗證的週榜表格契約。",
  },
  VN: {
    label: "越南",
    status: "blocked",
    source: "Box Office Vietnam",
    sourceUrl: "https://v1.boxofficevietnam.com/",
    note: "公開週末榜在 GitHub-hosted runner 觸發 Cloudflare 驗證；P1 不繞過來源存取控制。",
  },
  ID: {
    label: "印尼",
    status: "live",
    source: "Cinepoint",
    sourceUrl: "https://cinepoint.com/",
    note: "Weekly Top Box Office。來源註明數值混合公開資料與 Cinepoint proprietary tracking estimates。",
    estimated: true,
  },
  MY: {
    label: "馬來西亞",
    status: "live",
    source: "Cinema Online",
    sourceUrl: "https://www.cinema.com.my/movies/charts.aspx",
    note: "Weekend Box Office 公開榜。",
  },
  SG: {
    label: "新加坡",
    status: "live",
    source: "Cinema Online",
    sourceUrl: "https://www.cinema.com.my/movies/charts.aspx",
    note: "Weekend Box Office 公開榜。",
  },
};

const state = {
  rows: [],
  status: {},
  market: null,
  periodKey: null,
  search: "",
};

const els = {
  marketTabs: document.querySelector("#marketTabs"),
  periodSelect: document.querySelector("#periodSelect"),
  movieSearch: document.querySelector("#movieSearch"),
  sourceCard: document.querySelector("#sourceCard"),
  marketTitle: document.querySelector("#marketTitle"),
  periodLabel: document.querySelector("#periodLabel"),
  rowCount: document.querySelector("#rowCount"),
  tableWrap: document.querySelector("#tableWrap"),
  emptyState: document.querySelector("#emptyState"),
  globalStatus: document.querySelector("#globalStatus"),
};

function text(value) {
  return value == null ? "" : String(value).trim();
}

function numberValue(value) {
  const raw = text(value).replaceAll(",", "");
  if (!raw) return null;
  const valueNumber = Number(raw);
  return Number.isFinite(valueNumber) ? valueNumber : null;
}

function boolValue(value) {
  if (typeof value === "boolean") return value;
  return ["true", "1", "yes"].includes(text(value).toLowerCase());
}

function escapeHtml(value) {
  return text(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatNumber(value) {
  const n = numberValue(value);
  return n == null ? "—" : new Intl.NumberFormat("zh-TW").format(n);
}

function formatMoney(value, currency) {
  const n = numberValue(value);
  if (n == null) return "—";
  const code = text(currency);
  if (!code) return formatNumber(n);
  try {
    return new Intl.NumberFormat("zh-TW", {
      style: "currency",
      currency: code,
      maximumFractionDigits: 0,
    }).format(n);
  } catch {
    return `${formatNumber(n)} ${escapeHtml(code)}`;
  }
}

function formatDate(value) {
  const raw = text(value);
  if (!raw) return "—";
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return match ? `${match[1]}/${match[2]}/${match[3]}` : raw;
}

function formatPeriod(start, end) {
  const a = formatDate(start);
  const b = formatDate(end);
  return a === b ? a : `${a} – ${b}`;
}

function formatCapturedAt(value) {
  const raw = text(value);
  if (!raw) return null;
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  return new Intl.DateTimeFormat("zh-TW", {
    timeZone: "Asia/Taipei",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function periodKey(row) {
  return `${text(row.period_start)}|${text(row.period_end)}`;
}

function marketRows(market) {
  return state.rows.filter((row) => text(row.market) === market);
}

function periodsForMarket(market) {
  const seen = new Map();
  for (const row of marketRows(market)) {
    const key = periodKey(row);
    if (!seen.has(key)) {
      seen.set(key, {
        key,
        start: text(row.period_start),
        end: text(row.period_end),
        type: text(row.period_type),
      });
    }
  }
  return [...seen.values()].sort((a, b) => b.end.localeCompare(a.end) || b.start.localeCompare(a.start));
}

function effectiveStatus(market) {
  return marketRows(market).length ? "live" : MARKET_CONFIG[market].status;
}

function renderMarketTabs() {
  els.marketTabs.innerHTML = MARKET_ORDER.map((market) => {
    const config = MARKET_CONFIG[market];
    const status = effectiveStatus(market);
    return `
      <button class="market-tab ${status === "blocked" ? "blocked" : ""}"
              type="button"
              role="tab"
              data-market="${market}"
              aria-selected="${state.market === market}">
        <span class="dot" aria-hidden="true"></span>
        ${escapeHtml(config.label)}
      </button>`;
  }).join("");

  els.marketTabs.querySelectorAll(".market-tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.market = button.dataset.market;
      state.periodKey = null;
      render();
    });
  });
}

function renderPeriods() {
  const periods = periodsForMarket(state.market);
  if (!periods.length) {
    state.periodKey = null;
    els.periodSelect.innerHTML = `<option value="">尚無可用週期</option>`;
    els.periodSelect.disabled = true;
    return;
  }

  if (!state.periodKey || !periods.some((period) => period.key === state.periodKey)) {
    state.periodKey = periods[0].key;
  }
  els.periodSelect.disabled = false;
  els.periodSelect.innerHTML = periods.map((period) => `
    <option value="${escapeHtml(period.key)}" ${period.key === state.periodKey ? "selected" : ""}>
      ${escapeHtml(formatPeriod(period.start, period.end))}
    </option>`).join("");
}

function selectedRows() {
  if (!state.periodKey) return [];
  const needle = state.search.trim().toLocaleLowerCase("zh-TW");
  return marketRows(state.market)
    .filter((row) => periodKey(row) === state.periodKey)
    .filter((row) => !needle || text(row.title_source).toLocaleLowerCase("zh-TW").includes(needle))
    .sort((a, b) => Number(a.rank) - Number(b.rank));
}

function periodRows() {
  if (!state.periodKey) return [];
  return marketRows(state.market)
    .filter((row) => periodKey(row) === state.periodKey)
    .sort((a, b) => Number(a.rank) - Number(b.rank));
}

function hasField(rows, field) {
  return rows.some((row) => text(row[field]) !== "");
}

function renderSourceCard() {
  const config = MARKET_CONFIG[state.market];
  const rows = periodRows();
  const live = effectiveStatus(state.market) === "live";
  const row = rows[0];
  const source = text(row?.source) || config.source;
  const sourceUrl = text(row?.source_url) || config.sourceUrl;
  const capturedAt = rows
    .map((item) => text(item.captured_at))
    .filter(Boolean)
    .sort()
    .at(-1);
  const capturedLabel = formatCapturedAt(capturedAt);
  const estimated = config.estimated || rows.some((item) => boolValue(item.is_estimated));

  els.sourceCard.innerHTML = `
    <div class="source-main">
      <span class="source-name">${escapeHtml(source)}</span>
      <span class="badge ${live ? "live" : "blocked"}">${live ? "自動更新" : "尚未接通"}</span>
      ${estimated ? '<span class="badge estimate">含估算數據</span>' : ""}
      <span class="source-note">${escapeHtml(config.note)}</span>
    </div>
    <div>
      ${capturedLabel ? `<div class="source-time">擷取於 ${escapeHtml(capturedLabel)}</div>` : ""}
      <a class="source-link" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">查看來源 ↗</a>
    </div>`;
}

function buildColumns(rows) {
  const columns = [
    { label: "排名", field: "rank", className: "rank", render: (row) => escapeHtml(row.rank) },
    { label: "電影", field: "title_source", className: "movie-title", render: (row) => escapeHtml(row.title_source) },
  ];

  if (hasField(rows, "previous_rank") || hasField(rows, "previous_rank_label")) {
    columns.push({
      label: "上週",
      field: "previous_rank",
      render: (row) => escapeHtml(text(row.previous_rank) || text(row.previous_rank_label) || "—"),
    });
  }
  if (hasField(rows, "period_gross")) {
    columns.push({ label: "本期票房", field: "period_gross", className: "num", render: (row) => formatMoney(row.period_gross, row.currency) });
  }
  if (hasField(rows, "period_admissions")) {
    columns.push({ label: "本期人次", field: "period_admissions", className: "num", render: (row) => formatNumber(row.period_admissions) });
  }
  if (hasField(rows, "period_showtimes")) {
    columns.push({ label: "場次", field: "period_showtimes", className: "num", render: (row) => formatNumber(row.period_showtimes) });
  }
  if (hasField(rows, "cumulative_gross")) {
    columns.push({ label: "累計票房", field: "cumulative_gross", className: "num", render: (row) => formatMoney(row.cumulative_gross, row.currency) });
  }
  if (hasField(rows, "cumulative_admissions")) {
    columns.push({ label: "累計人次", field: "cumulative_admissions", className: "num", render: (row) => formatNumber(row.cumulative_admissions) });
  }
  if (hasField(rows, "release_date")) {
    columns.push({ label: "上映日", field: "release_date", render: (row) => escapeHtml(formatDate(row.release_date)) });
  }
  if (hasField(rows, "distributor")) {
    columns.push({ label: "發行商", field: "distributor", render: (row) => escapeHtml(row.distributor || "—") });
  }
  if (hasField(rows, "origin")) {
    columns.push({ label: "來源地", field: "origin", render: (row) => escapeHtml(row.origin || "—") });
  }
  return columns;
}

function renderTable() {
  const rowsForPeriod = periodRows();
  const rows = selectedRows();
  const config = MARKET_CONFIG[state.market];
  const period = periodsForMarket(state.market).find((item) => item.key === state.periodKey);

  els.marketTitle.textContent = `${config.label}票房排行`;
  els.periodLabel.textContent = period ? `${period.type === "weekend" ? "週末榜" : "週榜"} · ${formatPeriod(period.start, period.end)}` : "";
  els.rowCount.textContent = rowsForPeriod.length ? `${rows.length} / ${rowsForPeriod.length} 部` : "";

  if (!rowsForPeriod.length) {
    els.tableWrap.innerHTML = "";
    els.emptyState.hidden = false;
    if (effectiveStatus(state.market) === "blocked") {
      els.emptyState.innerHTML = `<strong>自動更新尚未接通</strong>${escapeHtml(config.note)}`;
    } else {
      els.emptyState.innerHTML = "<strong>目前沒有榜單資料</strong>來源尚未產生可顯示的有效週期。";
    }
    return;
  }

  if (!rows.length) {
    els.tableWrap.innerHTML = "";
    els.emptyState.hidden = false;
    els.emptyState.innerHTML = "<strong>找不到符合的電影</strong>請調整片名關鍵字。";
    return;
  }

  els.emptyState.hidden = true;
  const columns = buildColumns(rowsForPeriod);
  els.tableWrap.innerHTML = `
    <table>
      <thead><tr>${columns.map((col) => `<th class="${col.className || ""}">${escapeHtml(col.label)}</th>`).join("")}</tr></thead>
      <tbody>
        ${rows.map((row) => `<tr>${columns.map((col) => `<td class="${col.className || ""}">${col.render(row)}</td>`).join("")}</tr>`).join("")}
      </tbody>
    </table>`;
}

function renderGlobalStatus() {
  const liveMarkets = MARKET_ORDER.filter((market) => effectiveStatus(market) === "live");
  const latestCapture = state.rows
    .map((row) => text(row.captured_at))
    .filter(Boolean)
    .sort()
    .at(-1);
  const captureLabel = formatCapturedAt(latestCapture);
  els.globalStatus.textContent = `${liveMarkets.length} / ${MARKET_ORDER.length} 市場已自動化${captureLabel ? ` · 最近擷取 ${captureLabel}` : ""}`;
}

function render() {
  renderMarketTabs();
  renderPeriods();
  renderSourceCard();
  renderTable();
  renderGlobalStatus();
}

async function fetchJson(url, fallback) {
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return await response.json();
  } catch (error) {
    console.warn(`Failed to load ${url}`, error);
    return fallback;
  }
}

async function boot() {
  const [rows, status] = await Promise.all([
    fetchJson("./data/boxoffice.json", []),
    fetchJson("./data/status.json", {}),
  ]);
  state.rows = Array.isArray(rows) ? rows : [];
  state.status = status && typeof status === "object" ? status : {};

  const firstMarketWithData = MARKET_ORDER.find((market) => marketRows(market).length);
  state.market = firstMarketWithData || MARKET_ORDER[0];

  els.periodSelect.addEventListener("change", (event) => {
    state.periodKey = event.target.value || null;
    renderSourceCard();
    renderTable();
  });

  els.movieSearch.addEventListener("input", (event) => {
    state.search = event.target.value || "";
    renderTable();
  });

  render();
}

boot();
