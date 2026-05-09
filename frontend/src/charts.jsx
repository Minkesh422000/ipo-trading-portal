// Charts (SVG) — sparkline, equity curve, drawdown, candle visual, donut, bars
const { useMemo } = React;

function Sparkline({ data, w = 120, h = 32, color = "var(--green)", area = true }) {
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const step = w / (data.length - 1);
  const pts = data.map((v, i) => [i * step, h - ((v - min) / range) * (h - 4) - 2]);
  const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  const areaD = d + ` L ${w} ${h} L 0 ${h} Z`;
  return (
    <svg width={w} height={h} className="spark">
      {area && <path d={areaD} fill={color} opacity="0.12"/>}
      <path d={d} fill="none" stroke={color} strokeWidth="1.5"/>
    </svg>
  );
}

function EquityCurve({ data, w = 800, h = 240, peak = true }) {
  const min = Math.min(...data.map(d => d.val)) * 0.995;
  const max = Math.max(...data.map(d => d.val)) * 1.005;
  const range = max - min;
  const step = w / (data.length - 1);
  const pts = data.map((d, i) => [i * step, h - ((d.val - min) / range) * (h - 24) - 12]);
  const peakPts = data.map((d, i) => [i * step, h - ((d.peak - min) / range) * (h - 24) - 12]);
  const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  const peakLine = peakPts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  const area = line + ` L ${w} ${h} L 0 ${h} Z`;
  // y gridlines
  const ticks = 4;
  const yLines = Array.from({length: ticks + 1}).map((_, i) => {
    const y = (h - 24) * (i / ticks) + 12;
    const val = max - (range * i / ticks);
    return { y, val };
  });
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{display:"block"}}>
      <defs>
        <linearGradient id="eqg" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="var(--green)" stopOpacity="0.28"/>
          <stop offset="100%" stopColor="var(--green)" stopOpacity="0"/>
        </linearGradient>
      </defs>
      {yLines.map((t, i) => (
        <g key={i}>
          <line x1="0" x2={w} y1={t.y} y2={t.y} stroke="var(--border)" strokeDasharray="2 4"/>
        </g>
      ))}
      <path d={area} fill="url(#eqg)"/>
      {peak && <path d={peakLine} fill="none" stroke="var(--text-faint)" strokeWidth="1" strokeDasharray="3 3"/>}
      <path d={line} fill="none" stroke="var(--green)" strokeWidth="1.75"/>
    </svg>
  );
}

function DrawdownChart({ data, w = 800, h = 120 }) {
  const dd = data.map(d => (d.val - d.peak) / d.peak * 100); // negative %
  const min = Math.min(...dd);
  const range = Math.abs(min) || 1;
  const step = w / (dd.length - 1);
  const pts = dd.map((v, i) => [i * step, ((-v) / range) * (h - 16) + 4]);
  const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  const area = d + ` L ${w} 0 L 0 0 Z`;
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{display:"block"}}>
      <defs>
        <linearGradient id="ddg" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="var(--red)" stopOpacity="0"/>
          <stop offset="100%" stopColor="var(--red)" stopOpacity="0.28"/>
        </linearGradient>
      </defs>
      <path d={area} fill="url(#ddg)"/>
      <path d={d} fill="none" stroke="var(--red)" strokeWidth="1.5"/>
    </svg>
  );
}

// Stylized candle chart for the strategy explainer
function StrategyCandles({ w = 720, h = 280 }) {
  // Hand-tuned candles to tell the IPO breakout story
  // Phase: listing day -> week 1 -> week 2 -> breakout
  const candles = [
    // listing day big up
    { o: 100, h: 142, l: 98,  c: 138, label: "Listing", phase: "list" },
    // week 1 (5 daily candles, but compressed -> 5 candles forming the W1 range)
    { o: 138, h: 156, l: 130, c: 152, phase: "w1" },
    { o: 152, h: 162, l: 144, c: 148, phase: "w1" },
    { o: 148, h: 158, l: 138, c: 156, phase: "w1" },
    { o: 156, h: 164, l: 150, c: 144, phase: "w1" },
    { o: 144, h: 154, l: 140, c: 150, phase: "w1" },
    // week 2
    { o: 150, h: 168, l: 146, c: 162, phase: "w2" },
    { o: 162, h: 174, l: 156, c: 158, phase: "w2" },
    { o: 158, h: 166, l: 148, c: 152, phase: "w2" },
    { o: 152, h: 162, l: 142, c: 156, phase: "w2" },
    { o: 156, h: 168, l: 150, c: 160, phase: "w2" },
    // breakout zone
    { o: 160, h: 188, l: 158, c: 184, phase: "bo" },
    { o: 184, h: 198, l: 178, c: 196, phase: "bo" },
    { o: 196, h: 214, l: 192, c: 210, phase: "bo" },
    { o: 210, h: 222, l: 204, c: 218, phase: "bo" },
  ];
  const all = candles.flatMap(c => [c.h, c.l]);
  const max = Math.max(...all) * 1.06;
  const min = Math.min(...all) * 0.94;
  const range = max - min;
  const padL = 50, padR = 60, padT = 16, padB = 36;
  const cw = (w - padL - padR) / candles.length;
  const yOf = v => padT + ((max - v) / range) * (h - padT - padB);

  // 2-week range derived from W1 + W2 candles
  const wkCandles = candles.filter(c => c.phase === "w1" || c.phase === "w2");
  const hi2w = Math.max(...wkCandles.map(c => c.h));
  const lo2w = Math.min(...wkCandles.map(c => c.l));
  const t1 = hi2w + (hi2w - lo2w) * 1;
  const t2 = hi2w + (hi2w - lo2w) * 2;
  const t3 = hi2w + (hi2w - lo2w) * 3;

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{display:"block"}}>
      {/* week shading */}
      {(() => {
        const w1 = candles.findIndex(c => c.phase === "w1");
        const w1End = candles.findLastIndex(c => c.phase === "w1");
        const w2 = candles.findIndex(c => c.phase === "w2");
        const w2End = candles.findLastIndex(c => c.phase === "w2");
        return (
          <g>
            <rect x={padL + w1 * cw} y={padT} width={(w1End - w1 + 1) * cw} height={h - padT - padB} fill="rgba(255,255,255,0.025)"/>
            <rect x={padL + w2 * cw} y={padT} width={(w2End - w2 + 1) * cw} height={h - padT - padB} fill="rgba(255,255,255,0.045)"/>
            <text x={padL + (w1 + (w1End - w1 + 1)/2) * cw} y={h - padB + 18} textAnchor="middle" fontSize="9" fill="var(--text-dim)" fontFamily="IBM Plex Mono" letterSpacing="0.1em">WEEK 1</text>
            <text x={padL + (w2 + (w2End - w2 + 1)/2) * cw} y={h - padB + 18} textAnchor="middle" fontSize="9" fill="var(--text-dim)" fontFamily="IBM Plex Mono" letterSpacing="0.1em">WEEK 2</text>
            <text x={padL + cw/2} y={h - padB + 18} textAnchor="middle" fontSize="9" fill="var(--text-dim)" fontFamily="IBM Plex Mono" letterSpacing="0.1em">LIST</text>
            <text x={padL + (candles.length - 2.5) * cw} y={h - padB + 18} textAnchor="middle" fontSize="9" fill="var(--green)" fontFamily="IBM Plex Mono" letterSpacing="0.1em">BREAKOUT</text>
          </g>
        );
      })()}

      {/* horizontal lines: 2W high, 2W low, T1, T2, T3 */}
      {[
        { y: yOf(hi2w), color: "var(--green)", label: "2W HIGH · ENTRY", val: hi2w, dash: "0", strong: true },
        { y: yOf(lo2w), color: "var(--red)",   label: "2W LOW · STOP",   val: lo2w, dash: "0", strong: true },
        { y: yOf(t1),   color: "var(--text-dim)", label: "T1 · 1R",      val: t1, dash: "3 3" },
        { y: yOf(t2),   color: "var(--text-dim)", label: "T2 · 2R",      val: t2, dash: "3 3" },
        { y: yOf(t3),   color: "var(--text-dim)", label: "T3 · 3R",      val: t3, dash: "3 3" },
      ].map((ln, i) => (
        <g key={i}>
          <line x1={padL} x2={w - padR} y1={ln.y} y2={ln.y} stroke={ln.color} strokeWidth={ln.strong ? 1.25 : 1} strokeDasharray={ln.dash} opacity={ln.strong ? 0.9 : 0.55}/>
          <text x={w - padR + 6} y={ln.y + 3} fontSize="9.5" fill={ln.color} fontFamily="IBM Plex Mono" letterSpacing="0.04em">{ln.label}</text>
          <text x={padL - 6} y={ln.y + 3} fontSize="9.5" fill={ln.color} fontFamily="IBM Plex Mono" textAnchor="end">{ln.val.toFixed(0)}</text>
        </g>
      ))}

      {/* candles */}
      {candles.map((c, i) => {
        const x = padL + i * cw + cw / 2;
        const up = c.c >= c.o;
        const top = yOf(Math.max(c.o, c.c));
        const bot = yOf(Math.min(c.o, c.c));
        const fill = c.phase === "bo" ? "var(--green)" : up ? "var(--green)" : "var(--red)";
        const stroke = fill;
        return (
          <g key={i}>
            <line x1={x} x2={x} y1={yOf(c.h)} y2={yOf(c.l)} stroke={stroke} strokeWidth="1"/>
            <rect x={x - cw * 0.32} y={top} width={cw * 0.64} height={Math.max(2, bot - top)} fill={fill} opacity={c.phase === "bo" ? 1 : 0.85}/>
          </g>
        );
      })}

      {/* breakout marker */}
      <g>
        <circle cx={padL + 11.5 * cw} cy={yOf(hi2w)} r="4" fill="var(--green)"/>
        <circle cx={padL + 11.5 * cw} cy={yOf(hi2w)} r="9" fill="none" stroke="var(--green)" opacity="0.4"/>
      </g>
    </svg>
  );
}

// Donut chart
function Donut({ items, size = 140, thick = 18 }) {
  const total = items.reduce((s, it) => s + it.value, 0) || 1;
  const r = size / 2 - thick / 2;
  const c = size / 2;
  let acc = 0;
  return (
    <svg width={size} height={size}>
      <circle cx={c} cy={c} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={thick}/>
      {items.map((it, i) => {
        const frac = it.value / total;
        const dash = 2 * Math.PI * r;
        const seg = frac * dash;
        const offset = -acc * dash;
        acc += frac;
        return (
          <circle key={i} cx={c} cy={c} r={r} fill="none"
            stroke={it.color} strokeWidth={thick}
            strokeDasharray={`${seg} ${dash - seg}`}
            strokeDashoffset={offset}
            transform={`rotate(-90 ${c} ${c})`}/>
        );
      })}
    </svg>
  );
}

// Horizontal bar
function HBar({ value, max, color = "var(--green)", w = 200 }) {
  const pct = Math.max(0, Math.min(1, value / max));
  return (
    <div style={{ width: w, height: 6, background: "var(--surface-3)", borderRadius: 999, overflow: "hidden" }}>
      <div style={{ width: pct * 100 + "%", height: "100%", background: color }}/>
    </div>
  );
}

window.Sparkline = Sparkline;
window.EquityCurve = EquityCurve;
window.DrawdownChart = DrawdownChart;
window.StrategyCandles = StrategyCandles;
window.Donut = Donut;
window.HBar = HBar;
