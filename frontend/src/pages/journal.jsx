// Journal page — closed trades + analytics
function PageJournal() {
  const totalPnL = CLOSED_TRADES.reduce((s, t) => s + t.pnl, 0);
  const wins = CLOSED_TRADES.filter(t => t.pnl > 0);
  const winRate = wins.length / CLOSED_TRADES.length;
  const avgR = CLOSED_TRADES.reduce((s, t) => s + t.r, 0) / CLOSED_TRADES.length;
  const maxDD = Math.min(...EQUITY_CURVE.map(d => (d.val - d.peak) / d.peak * 100));

  return (
    <div className="page" data-screen-label="Journal">
      <div className="page-header">
        <div>
          <div className="page-title">Trade Journal</div>
          <div className="page-sub">Auto-recorded from broker fills. Tagged by setup quality, sector, and outcome. Patterns surface what's working.</div>
        </div>
        <div className="row">
          <div className="seg">
            <button>1M</button>
            <button className="active">3M</button>
            <button>6M</button>
            <button>YTD</button>
            <button>ALL</button>
          </div>
          <button className="btn btn-ghost"><I.download size={14}/> Export</button>
        </div>
      </div>

      <div className="stat-grid" style={{marginBottom: 16}}>
        <div className="stat">
          <div className="stat-label">Net P&amp;L</div>
          <div className="stat-value up">{fmt.signed(totalPnL)}</div>
          <div className="stat-delta up">{CLOSED_TRADES.length} trades · 12 wks</div>
        </div>
        <div className="stat">
          <div className="stat-label">Win rate</div>
          <div className="stat-value">{(winRate * 100).toFixed(1)}%</div>
          <div className="stat-delta muted">{wins.length}W / {CLOSED_TRADES.length - wins.length}L</div>
        </div>
        <div className="stat">
          <div className="stat-label">Avg R</div>
          <div className="stat-value up">{fmt.signed(avgR, 2)}R</div>
          <div className="stat-delta muted">expectancy {fmt.signed(avgR * winRate, 2)}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Max drawdown</div>
          <div className="stat-value down">{maxDD.toFixed(1)}%</div>
          <div className="stat-delta muted">recovered in 11 sessions</div>
        </div>
      </div>

      <div className="grid-2-1" style={{marginBottom: 16}}>
        <div className="card">
          <div className="card-head">
            <div className="card-title">Equity curve</div>
            <span className="card-sub">peak — — —</span>
          </div>
          <div className="card-pad" style={{paddingTop: 8}}>
            <EquityCurve data={EQUITY_CURVE} h={200}/>
          </div>
          <div style={{padding: "0 18px 14px"}}>
            <div className="label" style={{marginTop: 6}}>Drawdown</div>
            <DrawdownChart data={EQUITY_CURVE} h={80}/>
          </div>
        </div>

        <div className="card">
          <div className="card-head"><div className="card-title">Setup quality vs outcome</div></div>
          <div className="card-pad">
            {[
              { q: 5, label: "★★★★★", n: 4, win: 4, color: "var(--green)" },
              { q: 4, label: "★★★★",  n: 4, win: 3, color: "var(--green)" },
              { q: 3, label: "★★★",   n: 0, win: 0, color: "var(--amber)" },
              { q: 2, label: "★★",    n: 4, win: 0, color: "var(--red)" },
              { q: 1, label: "★",     n: 0, win: 0, color: "var(--red)" },
            ].map((s, i) => (
              <div key={i} style={{marginBottom: 10}}>
                <div className="row-between" style={{marginBottom: 4}}>
                  <span className="mono" style={{fontSize: 12, color: s.color}}>{s.label}</span>
                  <span className="mono" style={{fontSize: 11, color: "var(--text-dim)"}}>{s.win}/{s.n} · {s.n ? Math.round(s.win / s.n * 100) : 0}%</span>
                </div>
                <div style={{display: "flex", gap: 2, height: 10}}>
                  {[...Array(s.n)].map((_, j) => (
                    <div key={j} style={{flex: 1, background: j < s.win ? s.color : "var(--surface-3)", borderRadius: 2, opacity: j < s.win ? 0.85 : 1}}/>
                  ))}
                  {s.n === 0 && <div style={{flex: 1, background: "var(--surface-3)", borderRadius: 2, opacity: 0.4}}/>}
                </div>
              </div>
            ))}
            <div className="notice" style={{marginTop: 14}}>
              <I.target size={14}/>
              <span>Stop taking ★★ setups — 0/4 win rate is dragging expectancy down.</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid-2" style={{marginBottom: 16}}>
        <div className="card">
          <div className="card-head"><div className="card-title">Sector performance</div><span className="card-sub">last 90 days</span></div>
          <table className="tbl">
            <thead>
              <tr>
                <th>Sector</th>
                <th className="tbl-num">Trades</th>
                <th className="tbl-num">Win %</th>
                <th className="tbl-num">Avg R</th>
                <th className="tbl-num">P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {SECTOR_PNL.sort((a, b) => b.pnl - a.pnl).map((s, i) => (
                <tr key={i}>
                  <td>{s.sector}</td>
                  <td className="tbl-num">{s.trades}</td>
                  <td className="tbl-num">{Math.round(s.win / s.trades * 100)}%</td>
                  <td className={"tbl-num " + (s.avgR >= 0 ? "up" : "down")}>{fmt.signed(s.avgR, 2)}</td>
                  <td className={"tbl-num " + (s.pnl >= 0 ? "up" : "down")}>{fmt.signed(s.pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="card-head"><div className="card-title">Pattern detection</div><span className="card-sub">auto-tagged</span></div>
          <div className="card-pad">
            {[
              { tag: "Tight base (<8% range)", n: 6, win: 5, r: 2.04, color: "var(--green)" },
              { tag: "Volume surge ≥ 2×",      n: 8, win: 6, r: 1.42, color: "var(--green)" },
              { tag: "Friday breakouts",        n: 4, win: 1, r: -0.32, color: "var(--red)" },
              { tag: "Holds &gt; 5 sessions",   n: 9, win: 7, r: 1.88, color: "var(--green)" },
              { tag: "Gap-up entries (>2%)",    n: 5, win: 1, r: -0.61, color: "var(--red)" },
            ].map((p, i) => (
              <div key={i} style={{padding: "10px 0", borderBottom: i < 4 ? "1px solid var(--border)" : "none"}}>
                <div className="row-between" style={{marginBottom: 5}}>
                  <span style={{fontSize: 12.5}} dangerouslySetInnerHTML={{__html: p.tag}}/>
                  <span className="mono" style={{fontSize: 11, color: p.color}}>{fmt.signed(p.r, 2)}R</span>
                </div>
                <div className="row-between mono" style={{fontSize: 10.5, color: "var(--text-dim)"}}>
                  <span>{p.n} trades · {Math.round(p.win/p.n*100)}% win</span>
                  <div style={{width: 120, height: 4, background: "var(--surface-3)", borderRadius: 999, overflow: "hidden"}}>
                    <div style={{width: Math.min(100, Math.abs(p.r) * 30) + "%", height: "100%", background: p.color, marginLeft: p.r < 0 ? "auto" : 0}}/>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <div className="card-title">Closed trades</div>
          <span className="card-sub">· {CLOSED_TRADES.length} trades</span>
          <div className="row" style={{marginLeft: "auto", gap: 8}}>
            <button className="btn btn-sm btn-ghost"><I.filter size={12}/> Filter</button>
            <button className="btn btn-sm btn-ghost"><I.search size={12}/> Search</button>
          </div>
        </div>
        <table className="tbl">
          <thead>
            <tr>
              <th>Date</th>
              <th>Symbol</th>
              <th className="tbl-num">Qty</th>
              <th className="tbl-num">Entry</th>
              <th className="tbl-num">Exit</th>
              <th>Setup</th>
              <th>Quality</th>
              <th>Outcome</th>
              <th className="tbl-num">R</th>
              <th className="tbl-num">P&amp;L</th>
            </tr>
          </thead>
          <tbody>
            {CLOSED_TRADES.map((t, i) => (
              <tr key={i}>
                <td className="muted mono" style={{fontSize: 11.5}}>{t.date.slice(5)}</td>
                <td><div className="symbol-cell"><div className="symbol-icon">{t.sym.slice(0,2)}</div><div className="symbol-name">{t.sym}</div></div></td>
                <td className="tbl-num">{t.qty}</td>
                <td className="tbl-num">{fmt.num(t.entry, 2)}</td>
                <td className="tbl-num">{fmt.num(t.exit, 2)}</td>
                <td><span className="pill">{t.setup}</span></td>
                <td><span className="mono" style={{color: t.quality >= 4 ? "var(--green)" : t.quality === 3 ? "var(--amber)" : "var(--red)"}}>{"★".repeat(t.quality) + "☆".repeat(5 - t.quality)}</span></td>
                <td><span className={"pill " + (t.outcome.startsWith("T") ? "green" : t.outcome === "SL" ? "red" : "amber")}>{t.outcome}</span></td>
                <td className={"tbl-num " + (t.r >= 0 ? "up" : "down")}>{fmt.signed(t.r, 2)}</td>
                <td className={"tbl-num " + (t.pnl >= 0 ? "up" : "down")}><strong>{fmt.signed(t.pnl)}</strong></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

window.PageJournal = PageJournal;
