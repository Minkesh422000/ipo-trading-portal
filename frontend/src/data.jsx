// Mock data for the IPO Breakout Trading Platform
// All values are illustrative — not real market data.

const IPO_UNIVERSE = [
  // status: armed (waiting for breakout), fired (entry triggered), invalid (broke low first), pending (still in 2w setup)
  { sym: "VEDARA",   name: "Vedara Biosciences",        sector: "Pharma",     listDate: "2025-11-14", listPrice: 482, hi: 612.40, lo: 528.10, last: 614.80, status: "fired",   score: 88, vol: "2.4x", marketCap: 8420 },
  { sym: "AERON",    name: "Aeron Industries",          sector: "Capital Gds",listDate: "2025-12-05", listPrice: 318, hi: 364.20, lo: 312.50, last: 359.10, status: "armed",   score: 76, vol: "1.6x", marketCap: 4230 },
  { sym: "KIRTIQ",   name: "Kirti Quantitative",        sector: "FinTech",    listDate: "2026-01-09", listPrice: 740, hi: 868.00, lo: 712.30, last: 870.55, status: "fired",   score: 92, vol: "3.1x", marketCap: 12640 },
  { sym: "NEOMSL",   name: "Neom Steel & Logistics",    sector: "Logistics",  listDate: "2026-01-30", listPrice: 196, hi: 224.80, lo: 188.10, last: 218.40, status: "armed",   score: 71, vol: "1.3x", marketCap: 3120 },
  { sym: "AURORA",   name: "Aurora Renewables",         sector: "Energy",     listDate: "2026-02-13", listPrice: 612, hi: 728.00, lo: 590.20, last: 612.30, status: "pending", score: 64, vol: "0.9x", marketCap: 18900 },
  { sym: "PIXMA",    name: "Pixma Semiconductor",       sector: "Semis",      listDate: "2026-02-27", listPrice: 1240, hi: 1488.00, lo: 1192.00, last: 1496.30, status: "fired", score: 95, vol: "4.2x", marketCap: 24800 },
  { sym: "RIVAYAT",  name: "Rivayat Hospitality",       sector: "Consumer",   listDate: "2026-03-06", listPrice: 268, hi: 289.40, lo: 246.10, last: 244.60, status: "invalid", score: 38, vol: "1.1x", marketCap: 2840 },
  { sym: "SAARTHI",  name: "Saarthi Mobility",          sector: "Auto",       listDate: "2026-03-20", listPrice: 442, hi: 510.30, lo: 416.80, last: 488.20, status: "armed",   score: 82, vol: "1.8x", marketCap: 6780 },
  { sym: "OBELIQ",   name: "Obeliq Cybersecurity",      sector: "Tech",       listDate: "2026-04-03", listPrice: 924, hi: 1080.00, lo: 892.50, last: 1102.80, status: "fired", score: 89, vol: "2.7x", marketCap: 14600 },
  { sym: "MAHIRA",   name: "Mahira Specialty Chem",     sector: "Chem",       listDate: "2026-04-10", listPrice: 356, hi: 402.00, lo: 332.40, last: 388.10, status: "armed",   score: 74, vol: "1.5x", marketCap: 4960 },
  { sym: "TARANG",   name: "Tarang Digital Media",      sector: "Media",      listDate: "2026-04-17", listPrice: 178, hi: 198.40, lo: 162.30, last: 164.20, status: "pending", score: 52, vol: "0.8x", marketCap: 1820 },
  { sym: "ELYSIO",   name: "Elysio Diagnostics",        sector: "Healthcare", listDate: "2026-04-24", listPrice: 540, hi: 612.50, lo: 516.20, last: 581.40, status: "armed",   score: 79, vol: "1.7x", marketCap: 9120 },
];

// open positions (already entered)
const POSITIONS = [
  { sym: "PIXMA",   qty: 24,  entry: 1488.00, sl: 1192.00, last: 1496.30, target1: 1784.00, target2: 2080.00, target3: 2376.00, entered: "2026-04-22 09:34", broker: "Zerodha", strategy: "IPO Breakout", r: 0.03 },
  { sym: "KIRTIQ",  qty: 38,  entry: 868.00,  sl: 712.30,  last: 932.40,  target1: 1023.70, target2: 1179.40, target3: 1335.10, entered: "2026-04-15 10:12", broker: "Zerodha", strategy: "IPO Breakout", r: 0.41 },
  { sym: "VEDARA",  qty: 56,  entry: 612.40,  sl: 528.10,  last: 614.80,  target1: 696.70,  target2: 781.00,  target3: 865.30,  entered: "2026-04-30 11:48", broker: "Upstox",  strategy: "IPO Breakout", r: 0.03 },
  { sym: "OBELIQ",  qty: 18,  entry: 1080.00, sl: 892.50,  last: 1102.80, target1: 1267.50, target2: 1455.00, target3: 1642.50, entered: "2026-04-28 14:02", broker: "Zerodha", strategy: "IPO Breakout", r: 0.12 },
];

// pending orders (GTT or limit)
const PENDING_ORDERS = [
  { sym: "AERON",   type: "GTT",     side: "BUY",  qty: 60,  trigger: 364.20, limit: 365.50, sl: 312.50, target: 416.20, placed: "2026-04-28 09:15", broker: "Zerodha" },
  { sym: "SAARTHI", type: "GTT",     side: "BUY",  qty: 42,  trigger: 510.30, limit: 512.00, sl: 416.80, target: 603.80, placed: "2026-04-29 10:24", broker: "Upstox"  },
  { sym: "ELYSIO",  type: "LIMIT",   side: "BUY",  qty: 32,  trigger: 612.50, limit: 614.00, sl: 516.20, target: 708.80, placed: "2026-05-02 09:47", broker: "Zerodha" },
];

// recent trade journal entries (closed)
const CLOSED_TRADES = [
  { sym: "ZIRACO", date: "2026-04-23", entry: 264.20, exit: 318.40, qty: 80, pnl: 4336, r: 2.05, outcome: "T2",  setup: "Clean breakout", quality: 4 },
  { sym: "MARANI", date: "2026-04-19", entry: 412.00, exit: 384.10, qty: 42, pnl: -1172, r: -1.00, outcome: "SL", setup: "Failed BO",     quality: 2 },
  { sym: "INDOQX", date: "2026-04-14", entry: 728.50, exit: 920.30, qty: 28, pnl: 5370, r: 3.00, outcome: "T3",  setup: "Tight base",     quality: 5 },
  { sym: "CRESVA", date: "2026-04-09", entry: 196.40, exit: 224.10, qty: 120,pnl: 3324, r: 1.95, outcome: "T2",  setup: "Volume surge",   quality: 4 },
  { sym: "BHATIK", date: "2026-04-04", entry: 884.00, exit: 856.20, qty: 22, pnl: -612, r: -0.78, outcome: "Trail",setup: "Choppy",        quality: 2 },
  { sym: "PORVAL", date: "2026-03-28", entry: 1168.00,exit: 1452.00,qty: 18, pnl: 5112, r: 3.00, outcome: "T3",  setup: "Tight base",     quality: 5 },
  { sym: "AVISHK", date: "2026-03-21", entry: 332.10, exit: 298.40, qty: 90, pnl: -3033,r: -1.00, outcome: "SL", setup: "Failed BO",     quality: 2 },
  { sym: "GURBAN", date: "2026-03-14", entry: 484.00, exit: 538.50, qty: 50, pnl: 2725, r: 1.05, outcome: "T1",  setup: "Clean breakout", quality: 4 },
  { sym: "TANIQO", date: "2026-03-07", entry: 142.30, exit: 168.20, qty: 200,pnl: 5180, r: 1.98, outcome: "T2",  setup: "Volume surge",   quality: 4 },
  { sym: "HEMANI", date: "2026-02-28", entry: 596.80, exit: 564.20, qty: 30, pnl: -978, r: -0.95, outcome: "SL", setup: "Choppy",         quality: 2 },
  { sym: "DRUVAS", date: "2026-02-21", entry: 1024.00,exit: 1280.00,qty: 16, pnl: 4096, r: 2.50, outcome: "T2",  setup: "Tight base",     quality: 5 },
  { sym: "KESHAV", date: "2026-02-14", entry: 268.00, exit: 320.40, qty: 86, pnl: 4506, r: 2.00, outcome: "T2",  setup: "Clean breakout", quality: 4 },
];

// equity curve data — daily MTM over ~120 sessions
const EQUITY_CURVE = (() => {
  const out = [];
  let val = 500000;
  let peak = val;
  for (let i = 0; i < 120; i++) {
    // simulate steady upward bias with drawdowns
    const drift = 1850;
    const vol = (Math.sin(i * 0.7) + Math.sin(i * 0.31) * 0.6) * 4200;
    const noise = (Math.cos(i * 1.2) - 0.5) * 1800;
    val += drift + vol + noise;
    if (val > peak) peak = val;
    out.push({ i, val: Math.round(val), peak: Math.round(peak), dd: Math.round(val - peak) });
  }
  return out;
})();

// Sector breakdown for journal analytics
const SECTOR_PNL = [
  { sector: "Semis",       trades: 6,  win: 5, pnl: 28400, avgR: 1.92 },
  { sector: "FinTech",     trades: 8,  win: 5, pnl: 21240, avgR: 1.31 },
  { sector: "Pharma",      trades: 5,  win: 3, pnl: 12180, avgR: 0.84 },
  { sector: "Energy",      trades: 4,  win: 2, pnl:  6240, avgR: 0.42 },
  { sector: "Capital Gds", trades: 7,  win: 4, pnl:  9420, avgR: 0.61 },
  { sector: "Consumer",    trades: 6,  win: 2, pnl: -2840, avgR: -0.18 },
  { sector: "Auto",        trades: 5,  win: 3, pnl:  7180, avgR: 0.92 },
  { sector: "Logistics",   trades: 3,  win: 1, pnl: -1240, avgR: -0.21 },
];

// Capital allocation across strategies
const STRATEGIES = [
  { name: "IPO Breakout",      capital: 600000, used: 412800, openR: 6.4,  active: true,  trades30d: 14, winRate: 0.64 },
  { name: "52W High Pullback", capital: 250000, used:  62500, openR: 1.2,  active: true,  trades30d: 6,  winRate: 0.50 },
  { name: "Episodic Pivot",    capital: 150000, used:      0, openR: 0,    active: false, trades30d: 0,  winRate: 0.00 },
];

const BROKERS = [
  { id: "zerodha",  name: "Zerodha",    api: "Kite Connect",  connected: true,  account: "ZX48721", balance: 612480 },
  { id: "upstox",   name: "Upstox",     api: "Upstox API",    connected: true,  account: "UP-90213", balance: 184320 },
  { id: "angelone", name: "Angel One",  api: "SmartAPI",      connected: false, account: "—",        balance: 0 },
  { id: "dhan",     name: "Dhan",       api: "DhanHQ API",    connected: false, account: "—",        balance: 0 },
  { id: "groww",    name: "Groww",      api: "Groww API",     connected: false, account: "—",        balance: 0 },
];

// Today's signals for dashboard
const SIGNALS_TODAY = [
  { time: "09:18", sym: "PIXMA",  type: "BREAKOUT",  msg: "Crossed 2W high ₹1,488", action: "FIRED" },
  { time: "10:42", sym: "OBELIQ", type: "BREAKOUT",  msg: "Crossed 2W high ₹1,080", action: "FIRED" },
  { time: "11:14", sym: "AERON",  type: "WATCH",     msg: "Within 1.2% of 2W high", action: "ARMED" },
  { time: "12:33", sym: "RIVAYAT",type: "INVALID",   msg: "Broke 2W low — setup voided", action: "VOID" },
  { time: "13:50", sym: "ELYSIO", type: "WATCH",     msg: "Within 5.4% of 2W high", action: "ARMED" },
  { time: "14:21", sym: "SAARTHI",type: "WATCH",     msg: "Within 4.7% of 2W high", action: "ARMED" },
];

// expose
Object.assign(window, {
  IPO_UNIVERSE, POSITIONS, PENDING_ORDERS, CLOSED_TRADES,
  EQUITY_CURVE, SECTOR_PNL, STRATEGIES, BROKERS, SIGNALS_TODAY,
});

// Helpers
window.fmt = {
  inr(n, d=0) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    const sign = n < 0 ? "-" : "";
    n = Math.abs(n);
    const fixed = n.toFixed(d);
    const [int, dec] = fixed.split(".");
    // Indian comma format
    let last3 = int.slice(-3);
    const rest = int.slice(0, -3);
    const formatted = rest.length ? rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + last3 : last3;
    return sign + "₹" + formatted + (dec ? "." + dec : "");
  },
  num(n, d=0) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    return n.toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
  },
  pct(n, d=2) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    const sign = n > 0 ? "+" : "";
    return sign + n.toFixed(d) + "%";
  },
  signed(n, d=0) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    return (n > 0 ? "+" : "") + n.toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
  }
};

// ── Live data loader ──────────────────────────────────────────────────────────
let _refreshTimer = null;
const REFRESH_INTERVAL_MS = 60_000; // refresh every 60 seconds

async function fetchLiveData() {
  try {
    const res = await fetch('/api/data');
    if (!res.ok) { console.warn('[live] /api/data returned', res.status); return; }
    const d = await res.json();
    if (d.ipo_universe?.length)   window.IPO_UNIVERSE   = d.ipo_universe;
    if (d.positions?.length)      window.POSITIONS       = d.positions;
    if (d.pending_orders?.length) window.PENDING_ORDERS  = d.pending_orders;
    if (d.closed_trades?.length)  window.CLOSED_TRADES   = d.closed_trades;
    if (d.equity_curve?.length)   window.EQUITY_CURVE    = d.equity_curve;
    if (d.strategies?.length)     window.STRATEGIES      = d.strategies;
    if (d.brokers?.length)        window.BROKERS         = d.brokers;
    if (d.signals_today?.length)  window.SIGNALS_TODAY   = d.signals_today;
    window._liveDataSource = 'live';
    window._lastFetchAt = Date.now();
    window.dispatchEvent(new CustomEvent('livedata'));
    console.log('[live] Data loaded ✓', Object.keys(d).map(k => `${k}:${(d[k]||[]).length}`).join(' '));
  } catch(e) {
    console.warn('[live] Unavailable — using mock data', e);
    window._liveDataSource = 'mock';
    window.dispatchEvent(new CustomEvent('livedata'));
  }
}

function startLiveRefresh() {
  // Initial fetch
  fetchLiveData();

  // Periodic refresh every 60s
  if (_refreshTimer) clearInterval(_refreshTimer);
  _refreshTimer = setInterval(fetchLiveData, REFRESH_INTERVAL_MS);

  // Refresh when tab regains focus (user switches back from Kite/Zerodha)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      const stale = !window._lastFetchAt || (Date.now() - window._lastFetchAt) > 30_000;
      if (stale) fetchLiveData();
    }
  });
}

window.fetchLiveData = fetchLiveData;
window.startLiveRefresh = startLiveRefresh;
