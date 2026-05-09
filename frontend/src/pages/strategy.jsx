// Strategy page — IPO Breakout rules, candle illustration, parameters, backtest
const { useState: useStateS } = React;

function PageStrategy() {
  const [tab, setTab] = useStateS("rules");
  return (
    <div className="page" data-screen-label="Strategy">
      <div className="page-header">
        <div>
          <div className="row" style={{gap: 10, marginBottom: 6}}>
            <span className="status green"><span className="d"/>ACTIVE</span>
            <span className="status">v3.2 · last edited 2026-04-12</span>
          </div>
          <div className="page-title">IPO Breakout — 2-Week Range</div>
          <div className="page-sub">After listing, wait for 2 weekly candles to print. Mark range high &amp; low. Buy on breakout above 2W high, stop at 2W low. Targets at 1R / 2R / 3R.</div>
        </div>
        <div className="row">
          <button className="btn btn-ghost"><I.history size={14}/> Versions</button>
          <button className="btn btn-ghost"><I.download size={14}/> Export rules</button>
          <button className="btn btn-primary"><I.check size={14}/> Save changes</button>
        </div>
      </div>

      <div className="tabs" style={{marginBottom: 16}}>
        {[
          ["rules", "Setup rules"],
          ["params", "Parameters"],
          ["filters", "Filters"],
          ["backtest", "Backtest"],
        ].map(([id, label]) => (
          <button key={id} className={"tab " + (tab === id ? "active" : "")} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>

      {tab === "rules" && <RulesTab/>}
      {tab === "params" && <ParamsTab/>}
      {tab === "filters" && <FiltersTab/>}
      {tab === "backtest" && <BacktestTab/>}
    </div>
  );
}

function RulesTab() {
  const RULES = [
    { n: "01", t: "Listing day",       d: "Stock lists on NSE/BSE. Day 1 candle is recorded but not used for the range." },
    { n: "02", t: "Wait 2 weekly candles", d: "Skip until the first two full weekly candles after listing have closed. Partial weeks (Friday listings) count from the next Monday." },
    { n: "03", t: "Mark 2W range",     d: "Highest high = entry trigger. Lowest low = invalidation stop. Range must be ≥ 6% wide to qualify." },
    { n: "04", t: "Trigger entry",     d: "BUY when LTP crosses 2W HIGH on volume ≥ 1.2× 10-day avg. Place GTT 0.3% above for confirmation." },
    { n: "05", t: "Risk = HIGH − LOW", d: "Position size from risk %. Stop sits at 2W LOW (or trail to swing low after T1)." },
    { n: "06", t: "Targets at 1R/2R/3R", d: "Exit ⅓ at T1 (1R). Trail rest. Exit ⅓ at T2 (2R). Final ⅓ runs to T3 (3R) or trail stop." },
    { n: "07", t: "Setup voids",       d: "If price closes below 2W LOW before trigger, mark INVALID and remove from universe." },
  ];
  return (
    <div className="grid-2-1">
      {/* Rules list */}
      <div className="card">
        <div className="card-head">
          <div className="card-title">The 7 rules</div>
          <div className="card-sub">canonical · readable by scanner</div>
        </div>
        <div>
          {RULES.map((r, i) => (
            <div key={i} style={{padding: "14px 18px", borderBottom: i < RULES.length - 1 ? "1px solid var(--border)" : "none", display: "flex", gap: 14}}>
              <div className="mono" style={{fontSize: 18, color: "var(--green)", width: 28, fontWeight: 500}}>{r.n}</div>
              <div style={{flex: 1}}>
                <div style={{fontSize: 13.5, fontWeight: 500, marginBottom: 3}}>{r.t}</div>
                <div style={{fontSize: 12.5, color: "var(--text-2)", lineHeight: 1.55}}>{r.d}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Visual explainer */}
      <div className="col" style={{gap: 16}}>
        <div className="card dotted-bg">
          <div className="card-head">
            <div className="card-title">Setup anatomy</div>
            <span className="pill" style={{marginLeft: "auto"}}><I.candle size={11}/>weekly</span>
          </div>
          <div style={{padding: "8px 4px 4px"}}>
            <StrategyCandles/>
          </div>
        </div>
        <div className="card card-pad">
          <div className="card-title" style={{marginBottom: 10}}>Quick math</div>
          <div className="kv"><span className="k">2W HIGH (entry)</span><span className="v up">₹168.00</span></div>
          <div className="kv"><span className="k">2W LOW (stop)</span><span className="v down">₹130.00</span></div>
          <div className="kv"><span className="k">Risk per share (1R)</span><span className="v">₹38.00</span></div>
          <div className="kv"><span className="k">T1 / T2 / T3</span><span className="v">206 / 244 / 282</span></div>
          <div className="divider"/>
          <div className="kv"><span className="k">Risk per trade</span><span className="v">0.50% · ₹5,000</span></div>
          <div className="kv"><span className="k">Position size</span><span className="v">131 shares · ₹22,008</span></div>
        </div>
      </div>
    </div>
  );
}

function ParamsTab() {
  return (
    <div className="grid-2">
      <div className="card card-pad">
        <div className="card-title" style={{marginBottom: 14}}>Range definition</div>
        <div className="col" style={{gap: 14}}>
          <ParamRow label="Range timeframe">
            <div className="seg">
              <button>Daily × 10</button>
              <button className="active">Weekly × 2</button>
              <button>Weekly × 3</button>
              <button>Custom</button>
            </div>
          </ParamRow>
          <ParamRow label="Skip listing day">
            <div className="seg"><button>Off</button><button className="active">On</button></div>
          </ParamRow>
          <ParamRow label="Min range width (%)"><input className="input mono" defaultValue="6.0"/></ParamRow>
          <ParamRow label="Volume confirmation"><input className="input mono" defaultValue="1.2× 10-day avg"/></ParamRow>
          <ParamRow label="Entry buffer above high"><input className="input mono" defaultValue="0.30%"/></ParamRow>
        </div>
      </div>

      <div className="card card-pad">
        <div className="card-title" style={{marginBottom: 14}}>Exits &amp; targets</div>
        <div className="col" style={{gap: 14}}>
          <ParamRow label="Stop loss anchor">
            <div className="seg"><button className="active">2W low</button><button>Swing low</button><button>ATR × 1.5</button></div>
          </ParamRow>
          <div>
            <div className="label">R-multiple targets</div>
            <div style={{display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8}}>
              <input className="input mono" defaultValue="T1 = 1.0R"/>
              <input className="input mono" defaultValue="T2 = 2.0R"/>
              <input className="input mono" defaultValue="T3 = 3.0R"/>
            </div>
          </div>
          <div>
            <div className="label">Scale-out distribution</div>
            <div style={{display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8}}>
              <input className="input mono" defaultValue="33%"/>
              <input className="input mono" defaultValue="33%"/>
              <input className="input mono" defaultValue="34%"/>
            </div>
          </div>
          <ParamRow label="Trail after T1">
            <div className="seg"><button>Off</button><button className="active">Swing low</button><button>2-day low</button></div>
          </ParamRow>
          <ParamRow label="Time stop (sessions)"><input className="input mono" defaultValue="20"/></ParamRow>
        </div>
      </div>
    </div>
  );
}

function ParamRow({ label, children }) {
  return (
    <div>
      <div className="label">{label}</div>
      {children}
    </div>
  );
}

function FiltersTab() {
  return (
    <div className="grid-2">
      <div className="card card-pad">
        <div className="card-title" style={{marginBottom: 14}}>Universe filters</div>
        <div className="col" style={{gap: 12}}>
          <ParamRow label="Days since listing"><input className="input mono" defaultValue="14 — 180"/></ParamRow>
          <ParamRow label="Market cap (₹ Cr)"><input className="input mono" defaultValue="500 — 50,000"/></ParamRow>
          <ParamRow label="Min daily turnover (₹ Cr)"><input className="input mono" defaultValue="2"/></ParamRow>
          <ParamRow label="Exchange">
            <div className="seg"><button className="active">NSE+BSE</button><button>NSE only</button><button>BSE only</button></div>
          </ParamRow>
          <ParamRow label="Sectors">
            <div className="row" style={{flexWrap: "wrap", gap: 4}}>
              {["All", "Tech", "Pharma", "FinTech", "Energy", "Auto", "Consumer"].map((s, i) => (
                <span key={i} className={"pill " + (i === 0 ? "green" : "")}>{s}</span>
              ))}
            </div>
          </ParamRow>
        </div>
      </div>
      <div className="card card-pad">
        <div className="card-title" style={{marginBottom: 14}}>Quality &amp; safety</div>
        <div className="col" style={{gap: 12}}>
          <label className="chk"><input type="checkbox" defaultChecked/><span className="box"/>Skip stocks under ASM/GSM surveillance</label>
          <label className="chk"><input type="checkbox" defaultChecked/><span className="box"/>Skip if F&amp;O ban list</label>
          <label className="chk"><input type="checkbox" defaultChecked/><span className="box"/>Require &gt; 5 sessions since lock-in expiry</label>
          <label className="chk"><input type="checkbox"/><span className="box"/>Require IPO oversubscribed &gt; 2×</label>
          <label className="chk"><input type="checkbox" defaultChecked/><span className="box"/>Skip if anchor lock-in within 7 days</label>
          <label className="chk"><input type="checkbox"/><span className="box"/>Require at least one HNI subscription</label>
        </div>
      </div>
    </div>
  );
}

function BacktestTab() {
  const stats = [
    { l: "Period", v: "Jan 2022 — Apr 2026" },
    { l: "Total trades", v: "184" },
    { l: "Win rate", v: "61.4%" },
    { l: "Avg R", v: "+0.94" },
    { l: "Profit factor", v: "2.31" },
    { l: "Max drawdown", v: "−14.2%" },
    { l: "Sharpe (annual)", v: "1.62" },
    { l: "Avg hold (days)", v: "11.3" },
  ];
  return (
    <div className="col" style={{gap: 16}}>
      <div className="grid-3">
        {stats.slice(0, 3).map((s, i) => (
          <div key={i} className="stat">
            <div className="stat-label">{s.l}</div>
            <div className="stat-value">{s.v}</div>
          </div>
        ))}
      </div>
      <div className="card">
        <div className="card-head">
          <div className="card-title">Backtest equity (₹5L starting)</div>
          <span className="card-sub">· hypothetical, ignores slippage</span>
          <span className="pill green dot" style={{marginLeft: "auto"}}>+82.6% CAGR</span>
        </div>
        <div className="card-pad" style={{paddingTop: 8}}>
          <EquityCurve data={EQUITY_CURVE} h={240}/>
        </div>
      </div>
      <div className="grid-2">
        <div className="card card-pad">
          <div className="card-title" style={{marginBottom: 10}}>Statistics</div>
          {stats.slice(3).map((s, i) => (
            <div key={i} className="kv"><span className="k">{s.l}</span><span className="v">{s.v}</span></div>
          ))}
        </div>
        <div className="card card-pad">
          <div className="card-title" style={{marginBottom: 10}}>R distribution</div>
          <div style={{display: "flex", alignItems: "flex-end", gap: 6, height: 120, padding: "10px 0"}}>
            {[3, 8, 14, 22, 31, 28, 18, 12, 7, 4].map((v, i) => (
              <div key={i} style={{flex: 1, height: v / 31 * 100 + "%", background: i < 3 ? "var(--red)" : "var(--green)", borderRadius: "2px 2px 0 0", opacity: 0.85}}/>
            ))}
          </div>
          <div className="row-between mono" style={{fontSize: 10.5, color: "var(--text-dim)", marginTop: 6}}>
            <span>−2R</span><span>−1R</span><span>0</span><span>1R</span><span>2R</span><span>3R+</span>
          </div>
        </div>
      </div>
    </div>
  );
}

window.PageStrategy = PageStrategy;
