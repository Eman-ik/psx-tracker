const COMPANY_NAMES = {
  EFERT: "Engro Fertilizers Limited",
  ENGROH: "Engro Holdings Limited",
  FFC: "Fauji Fertilizer Company",
  LUCK: "Lucky Cement Limited",
  HBL: "Habib Bank Limited",
};

const elements = {
  grid: document.querySelector("#quote-grid"),
  refreshButton: document.querySelector("#refresh-button"),
  lastUpdated: document.querySelector("#last-updated"),
  countdown: document.querySelector("#refresh-countdown"),
  banner: document.querySelector("#status-banner"),
  tracked: document.querySelector("#tracked-count"),
  advancing: document.querySelector("#advancing-count"),
  declining: document.querySelector("#declining-count"),
  volume: document.querySelector("#total-volume"),
  clock: document.querySelector("#local-clock"),
};

const number = new Intl.NumberFormat("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const compact = new Intl.NumberFormat("en-PK", { notation: "compact", maximumFractionDigits: 1 });
let refreshIntervalMs = 15 * 60 * 1000;
let refreshAt = Date.now() + refreshIntervalMs;
let hasData = false;
let loading = false;

function formatNumber(value, fallback = "—") {
  return Number.isFinite(Number(value)) ? number.format(Number(value)) : fallback;
}

function formatCompact(value) {
  return Number.isFinite(Number(value)) ? compact.format(Number(value)) : "—";
}

function signed(value, suffix = "") {
  if (!Number.isFinite(Number(value))) return "—";
  const numeric = Number(value);
  return `${numeric > 0 ? "+" : ""}${number.format(numeric)}${suffix}`;
}

function movementClass(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric === 0) return "neutral";
  return numeric > 0 ? "positive" : "negative";
}

function rangePosition(quote) {
  const low = Number(quote.low);
  const high = Number(quote.high);
  const price = Number(quote.price);
  if (![low, high, price].every(Number.isFinite) || high <= low) return 50;
  return Math.min(100, Math.max(0, ((price - low) / (high - low)) * 100));
}

function quoteCard(quote) {
  const movement = movementClass(quote.change_percentage);
  const position = rangePosition(quote);
  const symbol = String(quote.symbol || "—").replace(/[^A-Z0-9-]/g, "");
  const name = COMPANY_NAMES[symbol] || "Pakistan Stock Exchange";

  return `
    <article class="quote-card">
      <div class="quote-top">
        <div><h3 class="symbol">${symbol}</h3><span class="company-name">${name}</span></div>
        <span class="change-pill ${movement}">${signed(quote.change_percentage, "%")}</span>
      </div>
      <span class="price-label">Last price</span>
      <div class="price-row"><span class="currency">PKR</span><strong class="price">${formatNumber(quote.price)}</strong></div>
      <div class="absolute-change ${movement}">${signed(quote.change)} today</div>
      <div class="range" aria-label="Day range from ${formatNumber(quote.low)} to ${formatNumber(quote.high)}">
        <div class="range-labels"><span>L ${formatNumber(quote.low)}</span><span>H ${formatNumber(quote.high)}</span></div>
        <div class="range-track"><div class="range-fill" style="width:${position}%"></div><span class="range-marker" style="left:${position}%"></span></div>
      </div>
      <div class="quote-footer">
        <div class="metric"><span>Volume</span><strong>${formatCompact(quote.volume)}</strong></div>
        <div class="metric"><span>Day range</span><strong>${formatNumber(Number(quote.high) - Number(quote.low))}</strong></div>
      </div>
    </article>`;
}

function renderQuotes(quotes) {
  if (!quotes.length) {
    elements.grid.innerHTML = '<div class="empty-state">No quotes are available right now.</div>';
  } else {
    elements.grid.innerHTML = quotes.map(quoteCard).join("");
  }
  elements.grid.setAttribute("aria-busy", "false");
  elements.tracked.textContent = quotes.length;
  elements.advancing.textContent = quotes.filter((q) => Number(q.change_percentage) > 0).length;
  elements.declining.textContent = quotes.filter((q) => Number(q.change_percentage) < 0).length;
  const totalVolume = quotes.reduce((sum, q) => sum + (Number(q.volume) || 0), 0);
  elements.volume.textContent = formatCompact(totalVolume);
}

function showBanner(message) {
  elements.banner.textContent = message;
  elements.banner.classList.remove("hidden");
}

function hideBanner() {
  elements.banner.classList.add("hidden");
}

function formatTimestamp(timestamp) {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return "Update time unavailable";
  return `Updated ${new Intl.DateTimeFormat("en-PK", {
    timeZone: "Asia/Karachi",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  }).format(parsed)}`;
}

async function loadQuotes() {
  if (loading) return;
  loading = true;
  elements.refreshButton.disabled = true;
  elements.refreshButton.classList.add("loading");
  elements.refreshButton.querySelector("span").textContent = "Updating…";

  try {
    const response = await fetch("/api/quotes", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail?.message || `API returned ${response.status}`);

    renderQuotes(payload.quotes || []);
    hasData = true;
    refreshIntervalMs = (payload.refresh_interval_seconds || 900) * 1000;
    refreshAt = Date.now() + refreshIntervalMs;
    elements.lastUpdated.textContent = formatTimestamp(payload.fetched_at);

    if (payload.errors?.length) {
      showBanner(`${payload.errors.length} symbol${payload.errors.length === 1 ? "" : "s"} could not be updated. Available prices are still shown.`);
    } else {
      hideBanner();
    }
  } catch (error) {
    showBanner(`${hasData ? "Prices may be stale. " : "Unable to load prices. "}${error.message}`);
    elements.grid.setAttribute("aria-busy", "false");
    if (!hasData) elements.grid.innerHTML = '<div class="empty-state">The market feed could not be reached. Use “Refresh prices” to try again.</div>';
    refreshAt = Date.now() + 60_000;
  } finally {
    loading = false;
    elements.refreshButton.disabled = false;
    elements.refreshButton.classList.remove("loading");
    elements.refreshButton.querySelector("span").textContent = "Refresh prices";
  }
}

function tick() {
  const now = new Date();
  elements.clock.textContent = new Intl.DateTimeFormat("en-PK", {
    timeZone: "Asia/Karachi",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(now) + " PKT";

  const remaining = Math.max(0, refreshAt - Date.now());
  const minutes = Math.floor(remaining / 60_000);
  const seconds = Math.floor((remaining % 60_000) / 1000);
  elements.countdown.textContent = `Next refresh in ${minutes}:${String(seconds).padStart(2, "0")}`;
  if (remaining === 0 && !loading) loadQuotes();
}

elements.refreshButton.addEventListener("click", loadQuotes);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && Date.now() >= refreshAt) loadQuotes();
});

tick();
setInterval(tick, 1000);
loadQuotes();
