// Orders page — bracket order builder + open / pending orders
function PageOrders() {
  const [sym, setSym] = React.useState("AERON");
  const stock = IPO_UNIVERSE.find(s => s.sym === sym) || IPO_UNIVERSE[1];
  const [riskPct, setRiskPct] = React.useState(0.5);
  const [capital] = React.useState(600000);
  const [orderType, setOrderType] = React.useState("GTT");

  const entry = stock.hi;
  const sl = stock.lo;
  const t1 = +(entry + (entry - sl) * 1).toFixed(2);
  const t2 = +(entry + (entry - sl) * 2).toFixed(2);
  const t3 = +(entry + (entry - sl) * 3).toFixed(2);
  const riskRupees = capital * riskPct / 100;
  const perShareRisk = entry - sl;
  const qty = Math.floor(riskRupees / perShareRisk);
  const exposure = qty * entry;

  return (
    <div className="page" data-screen-label="Orders">
      <div className="page-header">
        <div>
          <div className="page-title">Order Manager</div>
          <div className="page-sub">Bracket order builder. Auto-sized from your risk %. Routed to selected broker via API.</div>
        </div>
        <div className="row">
          <button className="btn btn-ghost"><I.history size={14}/> Order history</button>
          <button className="btn btn-ghost"><I.settings size={14}/> Defaults</button>
        </div>
      </div>

      <div className="grid-2-1" style={{marginBottom: 16}}>
        {/* Order builder */}
        <div className="card">
          <div className="card-head">
            <div className="card-title">New bracket order</div>
            <span className="card-sub">· strategy: IPO Breakout</span>
            <div style={{marginLeft: "auto"}} className="seg">
              {["MARKET", "LIMIT", "SL-M", "GTT"].map(t => (
                <button key={t} className={orderType === t ? "active" : ""} onClick={() => setOrderType(t)}>{t}</button>
              ))}
            </div>
          </div>
          <div className="card-pad">
            <div className="grid-2" style={{gap: 14}}>
              <div>
                <div className="label">Symbol</div>
                <select className="select mono" value={sym} onChange={e => setSym(e.target.value)}>
                  {IPO_UNIVERSE.filter(s => s.status === "armed" || s.status === "fired").map(s => (
                    <option key={s.sym} value={s.sym}>{s.sym} — {s.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <div className="label">Broker</div>
                <select className="select" defaultValue="zerodha">
                  {BROKERS.filter(b => b.connected).map(b => (
                    <option key={b.id} value={b.id}>{b.name} · {b.account}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="divider"/>

            {/* RR visualizer */}
            <div className="label">Risk · Reward visualizer</div>
            <RRViz entry={entry} sl={sl} t1={t1} t2={t2} t3={t3} last={stock.last}/>

            <div className="divider"/>

            <div className="grid-3" style={{gap: 14}}>
              <div>
                <div className="label">Entry (2W HIGH)</div>
                <input className="input mono" value={fmt.num(entry, 2)} readOnly/>
              </div>
              <div>
                <div className="label">Stop loss (2W LOW)</div>
                <input className="input mono down" value={fmt.num(sl, 2)} readOnly/>
              </div>
              <div>
                <div className="label">Order validity</div>
                <select className="select"><option>Day</option><option>IOC</option><option>GTT (1 year)</option></select>
              </div>
            </div>

            <div className="grid-3" style={{gap: 14, marginTop: 14}}>
              <div>
                <div className="label">T1 · 1R (33%)</div>
                <input className="input mono up" value={fmt.num(t1, 2)} readOnly/>
              </div>
              <div>
                <div className="label">T2 · 2R (33%)</div>
                <input className="input mono up" value={fmt.num(t2, 2)} readOnly/>
              </div>
              <div>
                <div className="label">T3 · 3R (34%)</div>
                <input className="input mono up" value={fmt.num(t3, 2)} readOnly/>
              </div>
            </div>

            <div className="divider"/>

            <div className="grid-3" style={{gap: 14}}>
              <div>
                <div className="label">Risk per trade</div>
                <div className="row" style={{gap: 8}}>
                  <input type="range" min="0.1" max="1.5" step="0.1" value={riskPct}
                    onChange={e => setRiskPct(parseFloat(e.target.value))}
                    style={{flex: 1, accentColor: "var(--green)"}}/>
                  <span className="mono" style={{minWidth: 42, textAlign: "right"}}>{riskPct.toFixed(1)}%</span>
                </div>
                <div className="mono muted" style={{fontSize: 10.5, marginTop: 4}}>= {fmt.inr(riskRupees)} of {fmt.inr(capital)}</div>
              </div>
              <div>
                <div className="label">Quantity (auto)</div>
                <input className="input mono" value={qty} readOnly style={{fontWeight: 500}}/>
                <div className="mono muted" style={{fontSize: 10.5, marginTop: 4}}>{fmt.num(perShareRisk, 2)} risk × {qty} = {fmt.inr(qty * perShareRisk)}</div>
              </div>
              <div>
                <div className="label">Exposure</div>
                <input className="input mono" value={fmt.inr(exposure)} readOnly/>
                <div className="mono muted" style={{fontSize: 10.5, marginTop: 4}}>{(exposure / capital * 100).toFixed(1)}% of capital</div>
              </div>
            </div>

            <div className="row" style={{marginTop: 18, gap: 10}}>
              <button className="btn btn-primary" style={{flex: 1, justifyContent: "center", padding: "10px"}}>
                <I.bolt size={14}/> Place {orderType} bracket order
              </button>
              <button className="btn btn-ghost"><I.x size={13}/> Cancel</button>
            </div>
            <div className="notice green" style={{marginTop: 10}}>
              <I.shield size={14}/>
              <span>Safe — risk {riskPct.toFixed(1)}% within 1.5% per-trade cap. Portfolio heat after fill: <strong className="mono">2.9%</strong></span>
            </div>
          </div>
        </div>

        {/* Order context */}
        <div className="col" style={{gap: 16}}>
          <div className="card card-pad">
            <div className="card-title" style={{marginBottom: 10}}>Trade math</div>
            <div className="kv"><span className="k">Risk per share</span><span className="v">{fmt.num(perShareRisk, 2)}</span></div>
            <div className="kv"><span className="k">Risk total (1R)</span><span className="v down">−{fmt.inr(qty * perShareRisk)}</span></div>
            <div className="kv"><span className="k">Reward at T1</span><span className="v up">+{fmt.inr(qty * (t1 - entry))}</span></div>
            <div className="kv"><span className="k">Reward at T2</span><span className="v up">+{fmt.inr(qty * (t2 - entry))}</span></div>
            <div className="kv"><span className="k">Reward at T3</span><span className="v up">+{fmt.inr(qty * (t3 - entry))}</span></div>
            <div className="divider"/>
            <div className="kv"><span className="k">Blended R (33/33/34)</span><span className="v up">+2.00R</span></div>
            <div className="kv"><span className="k">Expected value</span><span className="v up">+{fmt.inr(Math.round(qty * perShareRisk * 1.22))}</span></div>
          </div>
          <div className="card card-pad">
            <div className="card-title" style={{marginBottom: 10}}>Pre-flight checks</div>
            <CheckRow ok label="Daily loss limit headroom" detail={fmt.inr(15000) + " available"}/>
            <CheckRow ok label="Portfolio heat under 4%" detail="2.9% post-fill"/>
            <CheckRow ok label="Strategy capital available" detail={fmt.inr(187200) + " in IPO Breakout"}/>
            <CheckRow ok label="Symbol not on ASM/GSM" detail="Stage-1: clear"/>
            <CheckRow warn label="Earnings within 14 days" detail="Q4 results May 18"/>
            <CheckRow ok label="Broker margin sufficient" detail="3.2× required"/>
          </div>
        </div>
      </div>

      {/* Pending + open orders */}
      <div className="card" style={{marginBottom: 16}}>
        <div className="card-head">
          <div className="card-title">Pending orders · {PENDING_ORDERS.length}</div>
          <span className="card-sub">GTT &amp; limit · waiting on trigger</span>
          <button className="btn btn-sm btn-ghost" style={{marginLeft: "auto"}}>Cancel all</button>
        </div>
        <table className="tbl">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Type</th>
              <th>Side</th>
              <th className="tbl-num">Qty</th>
              <th className="tbl-num">Trigger</th>
              <th className="tbl-num">Limit</th>
              <th className="tbl-num">SL</th>
              <th className="tbl-num">Target</th>
              <th>Broker</th>
              <th>Placed</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {PENDING_ORDERS.map((o, i) => (
              <tr key={i}>
                <td><div className="symbol-cell"><div className="symbol-icon">{o.sym.slice(0,2)}</div><div className="symbol-name">{o.sym}</div></div></td>
                <td><span className="pill blue">{o.type}</span></td>
                <td><span className="pill green">{o.side}</span></td>
                <td className="tbl-num">{o.qty}</td>
                <td className="tbl-num">{fmt.num(o.trigger, 2)}</td>
                <td className="tbl-num">{fmt.num(o.limit, 2)}</td>
                <td className="tbl-num down">{fmt.num(o.sl, 2)}</td>
                <td className="tbl-num up">{fmt.num(o.target, 2)}</td>
                <td className="muted">{o.broker}</td>
                <td className="muted mono" style={{fontSize: 11}}>{o.placed.slice(5)}</td>
                <td>
                  <div className="row-action row" style={{justifyContent: "flex-end"}}>
                    <button className="btn btn-xs btn-ghost"><I.edit size={11}/></button>
                    <button className="btn btn-xs btn-ghost"><I.trash size={11}/></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <div className="card-head">
          <div className="card-title">Open positions · {POSITIONS.length}</div>
          <span className="card-sub">live MTM</span>
        </div>
        <table className="tbl">
          <thead>
            <tr>
              <th>Symbol</th>
              <th className="tbl-num">Qty</th>
              <th className="tbl-num">Entry</th>
              <th className="tbl-num">LTP</th>
              <th className="tbl-num">SL</th>
              <th className="tbl-num">T1</th>
              <th className="tbl-num">T2</th>
              <th className="tbl-num">T3</th>
              <th className="tbl-num">P&amp;L</th>
              <th className="tbl-num">R</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {POSITIONS.map((p, i) => {
              const pnl = (p.last - p.entry) * p.qty;
              return (
                <tr key={i}>
                  <td><div className="symbol-cell"><div className="symbol-icon">{p.sym.slice(0,2)}</div><div className="symbol-name">{p.sym}</div></div></td>
                  <td className="tbl-num">{p.qty}</td>
                  <td className="tbl-num">{fmt.num(p.entry, 2)}</td>
                  <td className="tbl-num"><strong>{fmt.num(p.last, 2)}</strong></td>
                  <td className="tbl-num down">{fmt.num(p.sl, 2)}</td>
                  <td className="tbl-num up">{fmt.num(p.target1, 2)}</td>
                  <td className="tbl-num up">{fmt.num(p.target2, 2)}</td>
                  <td className="tbl-num up">{fmt.num(p.target3, 2)}</td>
                  <td className={"tbl-num " + (pnl >= 0 ? "up" : "down")}>{fmt.signed(pnl)}</td>
                  <td className={"tbl-num " + (p.r >= 0 ? "up" : "down")}>{fmt.signed(p.r, 2)}R</td>
                  <td>
                    <div className="row-action row" style={{justifyContent: "flex-end"}}>
                      <button className="btn btn-xs btn-ghost">Trail</button>
                      <button className="btn btn-xs btn-danger">Exit</button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RRViz({ entry, sl, t1, t2, t3, last }) {
  const min = sl * 0.985;
  const max = t3 * 1.01;
  const range = max - min;
  const yOf = v => 100 - (v - min) / range * 100;
  return (
    <div style={{position: "relative", height: 96, padding: "8px 0", marginTop: 6}}>
      <svg width="100%" height="100%" style={{position: "absolute", inset: 0}}>
        {/* track */}
        <rect x="0" y="44" width="100%" height="8" rx="4" fill="var(--surface-3)"/>
        {/* sl→entry zone (red) */}
        <rect x={`${(sl - min) / range * 100}%`} y="44" width={`${(entry - sl) / range * 100}%`} height="8" rx="4" fill="var(--red)" opacity="0.45"/>
        {/* entry→t3 (green) */}
        <rect x={`${(entry - min) / range * 100}%`} y="44" width={`${(t3 - entry) / range * 100}%`} height="8" rx="4" fill="var(--green)" opacity="0.5"/>
      </svg>
      {/* markers */}
      {[
        { v: sl,    label: "SL",    sub: fmt.num(sl, 2),    color: "var(--red)" },
        { v: entry, label: "ENTRY", sub: fmt.num(entry, 2), color: "var(--text)", bold: true },
        { v: t1,    label: "T1",    sub: fmt.num(t1, 2),    color: "var(--green)" },
        { v: t2,    label: "T2",    sub: fmt.num(t2, 2),    color: "var(--green)" },
        { v: t3,    label: "T3",    sub: fmt.num(t3, 2),    color: "var(--green)" },
      ].map((m, i) => {
        const left = ((m.v - min) / range) * 100;
        return (
          <div key={i} style={{position: "absolute", left: left + "%", top: 0, transform: "translateX(-50%)", textAlign: "center"}}>
            <div style={{height: 8, width: 2, background: m.color, margin: "20px auto 0"}}/>
            <div style={{width: 8, height: 8, borderRadius: "50%", background: m.color, margin: "0 auto"}}/>
            <div className="mono" style={{fontSize: 9.5, color: m.color, marginTop: 4, letterSpacing: "0.06em"}}>{m.label}</div>
            <div className="mono" style={{fontSize: 10, color: "var(--text-dim)", fontWeight: m.bold ? 500 : 400}}>{m.sub}</div>
          </div>
        );
      })}
      {/* current price marker */}
      <div style={{position: "absolute", left: `${((last - min) / range) * 100}%`, top: 38, transform: "translateX(-50%)"}}>
        <div className="pill" style={{background: "var(--surface-2)", border: "1px solid var(--border-2)", fontSize: 9.5, padding: "1px 5px"}}>LTP {fmt.num(last, 2)}</div>
      </div>
    </div>
  );
}

function CheckRow({ ok, warn, label, detail }) {
  return (
    <div className="row-between" style={{padding: "6px 0", borderBottom: "1px dashed var(--border)"}}>
      <div className="row" style={{gap: 8}}>
        {ok && <span style={{color: "var(--green)"}}><I.check size={13}/></span>}
        {warn && <span style={{color: "var(--amber)"}}><I.flag size={13}/></span>}
        <span style={{fontSize: 12.5}}>{label}</span>
      </div>
      <span className="mono" style={{fontSize: 11, color: "var(--text-dim)"}}>{detail}</span>
    </div>
  );
}

window.PageOrders = PageOrders;
