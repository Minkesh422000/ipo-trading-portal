// Dashboard page — overview of signals, positions, equity, portfolio heat
function PageDashboard() {
  const totalPnL = POSITIONS.reduce((s, p) => s + (p.last - p.entry) * p.qty, 0);
  const exposure = POSITIONS.reduce((s, p) => s + p.entry * p.qty, 0);
  const openR = POSITIONS.reduce((s, p) => s + p.r, 0);
  const totalCap = STRATEGIES.reduce((s, x) => s + x.capital, 0);
  const usedCap  = STRATEGIES.reduce((s, x) => s + x.used, 0);

  // sparkline of last 30 sessions
  const spark = EQUITY_CURVE.slice(-30).map(d => d.val);

  return (
    <div className="page" data-screen-label="Dashboard">
      <div className="page-header">
        <div>
          <div className="page-title">Good afternoon, Ravi.</div>
          <div className="page-sub">4 open positions · 3 GTT armed · 2 IPO setups completing this Friday. Strategy edge holding above target.</div>
        </div>
        <div className="row">
          <button className="btn btn-ghost"><I.refresh size={14}/> Refresh universe</button>
          <button className="btn btn-primary"><I.bolt size={14}/> Run scanner</button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="stat-grid" style={{marginBottom: 16}}>
        <div className="stat">
          <div className="stat-label">Open P&amp;L (MTM)</div>
          <div className="stat-value up">{fmt.signed(totalPnL)}</div>
          <div className="stat-delta up">{fmt.signed(openR, 2)}R · across 4 positions</div>
        </div>
        <div className="stat">
          <div className="stat-label">Capital deployed</div>
          <div className="stat-value">{fmt.inr(usedCap)}</div>
          <div className="stat-delta muted">{(usedCap / totalCap * 100).toFixed(1)}% of {fmt.inr(totalCap)}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Portfolio heat</div>
          <div className="stat-value">2.4%</div>
          <div className="stat-delta warn">of 4.0% max · 4 R at risk</div>
        </div>
        <div className="stat">
          <div className="stat-label">30-day return</div>
          <div className="stat-value up">+8.42%</div>
          <div className="stat-delta up">+{fmt.inr(63420)} · win rate 64%</div>
        </div>
      </div>

      <div className="grid-2-1" style={{marginBottom: 16}}>
        {/* Equity curve */}
        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">Equity curve</div>
              <div className="card-sub">120 sessions · all strategies</div>
            </div>
            <div style={{marginLeft: "auto"}} className="seg">
              <button>1W</button>
              <button>1M</button>
              <button className="active">3M</button>
              <button>YTD</button>
              <button>ALL</button>
            </div>
          </div>
          <div className="card-pad" style={{paddingTop: 8}}>
            <EquityCurve data={EQUITY_CURVE} h={220}/>
          </div>
        </div>

        {/* Today's signals */}
        <div className="card">
          <div className="card-head">
            <div className="card-title">Today's signals</div>
            <span className="pill green dot" style={{marginLeft: "auto"}}>2 fired</span>
          </div>
          <div style={{maxHeight: 280, overflow: "auto"}}>
            {SIGNALS_TODAY.map((s, i) => (
              <div key={i} style={{padding: "10px 16px", borderBottom: "1px solid var(--border)", display: "flex", gap: 10, alignItems: "center"}}>
                <span className="mono" style={{fontSize: 11, color: "var(--text-dim)", width: 38}}>{s.time}</span>
                <span className="symbol-icon" style={{width: 24, height: 24, fontSize: 10}}>{s.sym.slice(0,2)}</span>
                <div style={{flex: 1, minWidth: 0}}>
                  <div style={{fontSize: 12.5, fontWeight: 500}}>{s.sym}</div>
                  <div style={{fontSize: 11, color: "var(--text-dim)"}}>{s.msg}</div>
                </div>
                <span className={"pill dot " + (s.action === "FIRED" ? "green" : s.action === "VOID" ? "red" : "amber")}>{s.action}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Open positions + portfolio heat */}
      <div className="grid-2-1">
        <div className="card">
          <div className="card-head">
            <div className="card-title">Open positions</div>
            <span className="card-sub">· bracket orders linked</span>
            <button className="btn btn-sm btn-ghost" style={{marginLeft: "auto"}}>View all <I.chev size={12}/></button>
          </div>
          <table className="tbl">
            <thead>
              <tr>
                <th>Symbol</th>
                <th className="tbl-num">Qty</th>
                <th className="tbl-num">Entry</th>
                <th className="tbl-num">LTP</th>
                <th className="tbl-num">SL</th>
                <th className="tbl-num">Open R</th>
                <th className="tbl-num">P&amp;L</th>
                <th>Trail</th>
              </tr>
            </thead>
            <tbody>
              {POSITIONS.map((p, i) => {
                const pnl = (p.last - p.entry) * p.qty;
                const moveR = (p.last - p.entry) / (p.entry - p.sl);
                return (
                  <tr key={i}>
                    <td>
                      <div className="symbol-cell">
                        <div className="symbol-icon">{p.sym.slice(0,2)}</div>
                        <div>
                          <div className="symbol-name">{p.sym}</div>
                          <div className="symbol-sub">{p.broker} · {p.strategy}</div>
                        </div>
                      </div>
                    </td>
                    <td className="tbl-num">{p.qty}</td>
                    <td className="tbl-num">{fmt.num(p.entry, 2)}</td>
                    <td className="tbl-num">{fmt.num(p.last, 2)}</td>
                    <td className="tbl-num down">{fmt.num(p.sl, 2)}</td>
                    <td className={"tbl-num " + (moveR >= 0 ? "up" : "down")}>{fmt.signed(moveR, 2)}R</td>
                    <td className={"tbl-num " + (pnl >= 0 ? "up" : "down")}>{fmt.signed(pnl)}</td>
                    <td>
                      <div style={{display: "flex", alignItems: "center", gap: 6}}>
                        <div style={{width: 80, height: 4, background: "var(--surface-3)", borderRadius: 999, overflow: "hidden"}}>
                          <div style={{width: Math.min(100, Math.max(0, moveR / 3 * 100)) + "%", height: "100%", background: "var(--green)"}}/>
                        </div>
                        <span className="mono" style={{fontSize: 10.5, color: "var(--text-dim)"}}>→ T3</span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Portfolio heat panel */}
        <div className="card">
          <div className="card-head">
            <div className="card-title">Portfolio heat</div>
            <div className="card-sub">live exposure</div>
          </div>
          <div className="card-pad">
            <div style={{textAlign: "center", marginBottom: 12}}>
              <div style={{fontSize: 36, fontWeight: 500, fontFamily: "IBM Plex Mono", letterSpacing: "-0.02em"}} className="warn">2.4%</div>
              <div style={{fontSize: 11.5, color: "var(--text-dim)", marginTop: 4}}>of 4.0% max risk</div>
            </div>
            <div className="bar amber" style={{height: 8, marginBottom: 16}}><i style={{width: "60%"}}/></div>
            {STRATEGIES.filter(s => s.active).map((s, i) => (
              <div key={i} style={{marginBottom: 12}}>
                <div className="row-between" style={{marginBottom: 5}}>
                  <span style={{fontSize: 12.5}}>{s.name}</span>
                  <span className="mono" style={{fontSize: 11, color: "var(--text-dim)"}}>{s.openR.toFixed(1)}R</span>
                </div>
                <div className="bar"><i style={{width: (s.used / s.capital * 100) + "%"}}/></div>
                <div style={{fontSize: 10.5, color: "var(--text-faint)", marginTop: 4}} className="mono">
                  {fmt.inr(s.used)} / {fmt.inr(s.capital)}
                </div>
              </div>
            ))}
            <div className="divider"/>
            <div className="kv"><span className="k">Daily loss limit</span><span className="v">{fmt.inr(15000)}</span></div>
            <div className="kv"><span className="k">Used today</span><span className="v down">-{fmt.inr(0)}</span></div>
            <div className="kv"><span className="k">Headroom</span><span className="v up">{fmt.inr(15000)}</span></div>
          </div>
        </div>
      </div>
    </div>
  );
}

window.PageDashboard = PageDashboard;
