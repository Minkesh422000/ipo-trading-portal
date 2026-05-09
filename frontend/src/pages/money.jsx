// Money management page — capital allocation, risk settings, position sizing calculator
function PageMoney() {
  const totalCap = STRATEGIES.reduce((s, x) => s + x.capital, 0);
  const usedCap  = STRATEGIES.reduce((s, x) => s + x.used, 0);
  const free = totalCap - usedCap;

  const allocItems = STRATEGIES.map((s, i) => ({
    label: s.name,
    value: s.capital,
    color: ["var(--green)", "var(--blue)", "var(--violet)"][i % 3],
  }));

  return (
    <div className="page" data-screen-label="Money management">
      <div className="page-header">
        <div>
          <div className="page-title">Money Management</div>
          <div className="page-sub">Capital allocation across strategies. Per-trade and daily risk limits. Live portfolio heat.</div>
        </div>
        <div className="row">
          <button className="btn btn-ghost"><I.history size={14}/> Audit log</button>
          <button className="btn btn-primary"><I.check size={14}/> Save limits</button>
        </div>
      </div>

      <div className="stat-grid" style={{marginBottom: 16}}>
        <div className="stat">
          <div className="stat-label">Total capital</div>
          <div className="stat-value">{fmt.inr(totalCap)}</div>
          <div className="stat-delta muted">across 3 strategies</div>
        </div>
        <div className="stat">
          <div className="stat-label">Deployed</div>
          <div className="stat-value">{fmt.inr(usedCap)}</div>
          <div className="stat-delta muted">{(usedCap/totalCap*100).toFixed(1)}% utilised</div>
        </div>
        <div className="stat">
          <div className="stat-label">Free margin</div>
          <div className="stat-value up">{fmt.inr(free)}</div>
          <div className="stat-delta up">available across brokers</div>
        </div>
        <div className="stat">
          <div className="stat-label">Open risk (R)</div>
          <div className="stat-value warn">7.6R</div>
          <div className="stat-delta warn">2.4% of equity</div>
        </div>
      </div>

      <div className="grid-2-1" style={{marginBottom: 16}}>
        <div className="card">
          <div className="card-head"><div className="card-title">Capital allocation</div><span className="card-sub">across strategies</span></div>
          <div className="card-pad">
            <table className="tbl" style={{margin: "-10px -2px 0"}}>
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th className="tbl-num">Allocated</th>
                  <th className="tbl-num">Used</th>
                  <th className="tbl-num">Open R</th>
                  <th className="tbl-num">30d trades</th>
                  <th className="tbl-num">Win %</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {STRATEGIES.map((s, i) => (
                  <tr key={i}>
                    <td>
                      <div style={{display: "flex", alignItems: "center", gap: 8}}>
                        <span style={{width: 8, height: 8, borderRadius: 2, background: ["var(--green)", "var(--blue)", "var(--violet)"][i % 3]}}/>
                        <span style={{fontWeight: 500}}>{s.name}</span>
                      </div>
                    </td>
                    <td className="tbl-num">{fmt.inr(s.capital)}</td>
                    <td className="tbl-num">
                      <div style={{display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4}}>
                        <span>{fmt.inr(s.used)}</span>
                        <div style={{width: 100, height: 4, background: "var(--surface-3)", borderRadius: 999, overflow: "hidden"}}>
                          <div style={{width: (s.used/s.capital*100) + "%", height: "100%", background: ["var(--green)", "var(--blue)", "var(--violet)"][i % 3]}}/>
                        </div>
                      </div>
                    </td>
                    <td className="tbl-num">{s.openR.toFixed(1)}R</td>
                    <td className="tbl-num">{s.trades30d}</td>
                    <td className={"tbl-num " + (s.winRate >= 0.55 ? "up" : "muted")}>{(s.winRate*100).toFixed(0)}%</td>
                    <td><span className={"status " + (s.active ? "green" : "")}><span className="d"/>{s.active ? "ACTIVE" : "PAUSED"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card card-pad" style={{display: "flex", flexDirection: "column", alignItems: "center"}}>
          <div className="card-title" style={{marginBottom: 14, alignSelf: "flex-start"}}>Allocation split</div>
          <Donut items={allocItems} size={160} thick={20}/>
          <div style={{width: "100%", marginTop: 16}}>
            {allocItems.map((it, i) => (
              <div key={i} className="row-between" style={{padding: "6px 0", borderBottom: i < allocItems.length - 1 ? "1px dashed var(--border)" : "none"}}>
                <div className="row" style={{gap: 8}}>
                  <span style={{width: 8, height: 8, borderRadius: 2, background: it.color}}/>
                  <span style={{fontSize: 12.5}}>{it.label}</span>
                </div>
                <span className="mono" style={{fontSize: 12, color: "var(--text-dim)"}}>{(it.value/totalCap*100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid-2" style={{marginBottom: 16}}>
        <div className="card card-pad">
          <div className="card-title" style={{marginBottom: 14}}>Risk limits</div>
          <div className="col" style={{gap: 14}}>
            <RiskRow label="Risk per trade" value="0.50%" detail="₹5,000 of ₹10,00,000"/>
            <RiskRow label="Max risk per trade" value="1.50%" detail="hard cap" warn/>
            <RiskRow label="Daily loss limit" value="1.50%" detail="₹15,000 — halts trading"/>
            <RiskRow label="Weekly loss limit" value="3.00%" detail="₹30,000 — halts trading"/>
            <RiskRow label="Max portfolio heat" value="4.00%" detail="sum of open risk"/>
            <RiskRow label="Max concurrent positions" value="6" detail="per strategy"/>
            <RiskRow label="Max sector concentration" value="35%" detail="of capital"/>
          </div>
        </div>

        <div className="card card-pad">
          <div className="card-title" style={{marginBottom: 14}}>Position size calculator</div>
          <div className="col" style={{gap: 12}}>
            <div className="grid-2" style={{gap: 12}}>
              <div><div className="label">Capital</div><input className="input mono" defaultValue="10,00,000"/></div>
              <div><div className="label">Risk %</div><input className="input mono" defaultValue="0.50"/></div>
              <div><div className="label">Entry</div><input className="input mono" defaultValue="868.00"/></div>
              <div><div className="label">Stop loss</div><input className="input mono" defaultValue="712.30"/></div>
            </div>
            <div className="divider"/>
            <div className="kv"><span className="k">Risk in ₹</span><span className="v">{fmt.inr(5000)}</span></div>
            <div className="kv"><span className="k">Per share risk</span><span className="v">{fmt.num(155.70, 2)}</span></div>
            <div className="kv"><span className="k">Position size</span><span className="v">32 shares</span></div>
            <div className="kv"><span className="k">Capital deployed</span><span className="v">{fmt.inr(27776)} <span className="muted">(2.78%)</span></span></div>
            <div className="kv"><span className="k">T1 target (1R)</span><span className="v up">+{fmt.inr(5000)}</span></div>
            <div className="kv"><span className="k">T3 target (3R)</span><span className="v up">+{fmt.inr(15000)}</span></div>
            <button className="btn btn-primary" style={{marginTop: 8, justifyContent: "center"}}><I.bolt size={13}/> Send to order builder</button>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head"><div className="card-title">Portfolio heat — live exposure</div><span className="card-sub">sum of open risk</span></div>
        <div className="card-pad">
          <div className="row" style={{gap: 24, marginBottom: 16}}>
            <div>
              <div className="label">Current heat</div>
              <div style={{fontSize: 28, fontFamily: "IBM Plex Mono", fontWeight: 500, color: "var(--amber)"}}>2.4%</div>
            </div>
            <div style={{flex: 1}}>
              <div className="row-between mono" style={{fontSize: 10.5, color: "var(--text-dim)", marginBottom: 4}}>
                <span>0%</span>
                <span>SAFE 2%</span>
                <span>WATCH 3%</span>
                <span style={{color: "var(--red)"}}>MAX 4%</span>
              </div>
              <div style={{height: 16, background: "linear-gradient(90deg, var(--green) 0%, var(--green) 50%, var(--amber) 50%, var(--amber) 75%, var(--red) 75%, var(--red) 100%)", borderRadius: 8, position: "relative"}}>
                <div style={{position: "absolute", left: "60%", top: -4, bottom: -4, width: 2, background: "var(--text)", borderRadius: 2}}/>
              </div>
            </div>
          </div>
          <div className="grid-3" style={{gap: 10}}>
            {POSITIONS.map((p, i) => {
              const risk = (p.entry - p.sl) * p.qty;
              const riskPct = risk / 1000000 * 100;
              return (
                <div key={i} className="heat-cell">
                  <div className="row-between">
                    <span style={{fontSize: 12, fontWeight: 500, fontFamily: "IBM Plex Sans"}}>{p.sym}</span>
                    <span className="mono" style={{fontSize: 11, color: "var(--amber)"}}>{riskPct.toFixed(2)}%</span>
                  </div>
                  <div className="bar amber thin"><i style={{width: Math.min(100, riskPct/4*100) + "%"}}/></div>
                  <div className="row-between" style={{fontSize: 10, color: "var(--text-dim)", marginTop: 4}}>
                    <span>−{fmt.inr(risk)} risk</span>
                    <span>{p.qty}× @ {fmt.num(p.entry, 0)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function RiskRow({ label, value, detail, warn }) {
  return (
    <div className="row-between" style={{padding: "8px 0", borderBottom: "1px dashed var(--border)"}}>
      <div>
        <div style={{fontSize: 13}}>{label}</div>
        <div className="mono" style={{fontSize: 11, color: "var(--text-dim)", marginTop: 2}}>{detail}</div>
      </div>
      <div className="row" style={{gap: 8}}>
        <input className="input mono" defaultValue={value} style={{width: 90, textAlign: "right", padding: "5px 8px"}}/>
        {warn && <span style={{color: "var(--amber)"}}><I.flag size={13}/></span>}
      </div>
    </div>
  );
}

window.PageMoney = PageMoney;
