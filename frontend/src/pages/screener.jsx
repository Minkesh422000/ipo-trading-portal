// Screener page — IPO universe with filters and one-click order
const { useState: useScrState, useEffect: useScrEffect } = React;

function PageScreener() {
  const [universe, setUniverse] = useScrState(window.IPO_UNIVERSE || []);
  const [statusFilter, setStatusFilter] = useScrState("all");
  const [scanning, setScanning] = useScrState(false);
  const [scanMsg, setScanMsg] = useScrState(null);
  const [lastScan, setLastScan] = useScrState(null);

  // Keep in sync when live data refreshes
  useScrEffect(() => {
    const onLive = () => setUniverse([...(window.IPO_UNIVERSE || [])]);
    window.addEventListener("livedata", onLive);
    return () => window.removeEventListener("livedata", onLive);
  }, []);

  async function handleRescan() {
    setScanning(true);
    setScanMsg(null);
    try {
      const res = await fetch("/api/scan", { method: "POST" });
      const d = await res.json();
      if (d.ok) {
        window.IPO_UNIVERSE = d.ipo_universe;
        setUniverse([...d.ipo_universe]);
        setLastScan(new Date().toLocaleTimeString());
        setScanMsg({ type: "ok", text: `✓ Scanned ${d.count} IPOs` });
      } else {
        setScanMsg({ type: "err", text: d.error || "Scan failed" });
      }
    } catch (e) {
      setScanMsg({ type: "err", text: "Server unreachable: " + e.message });
    } finally {
      setScanning(false);
    }
  }

  const filtered = universe.filter(s => statusFilter === "all" || s.status === statusFilter);
  const counts = {
    all:     universe.length,
    fired:   universe.filter(s => s.status === "fired").length,
    armed:   universe.filter(s => s.status === "armed").length,
    pending: universe.filter(s => s.status === "pending").length,
    past:    universe.filter(s => s.status === "past").length,
    invalid: universe.filter(s => s.status === "invalid").length,
  };

  return (
    <div className="page" data-screen-label="Screener">
      <div className="page-header">
        <div>
          <div className="page-title">IPO Universe · {universe.length} candidates</div>
          <div className="page-sub">
            Stocks listed in last 180 days. 2W high/low computed from first 2 weeks after listing.
            {lastScan && <span style={{color:"var(--text-dim)"}}> · Last scan: {lastScan}</span>}
          </div>
        </div>
        <div className="row">
          <button className="btn btn-ghost"><I.download size={14}/> Export CSV</button>
          <button className="btn btn-primary" onClick={handleRescan} disabled={scanning}>
            <I.refresh size={14} style={scanning ? {animation:"spin 1s linear infinite"} : {}}/>{" "}
            {scanning ? "Scanning…" : "Re-scan"}
          </button>
        </div>
      </div>

      {scanMsg && (
        <div className={"notice " + (scanMsg.type === "ok" ? "" : "red")} style={{marginBottom:12}}>
          {scanMsg.type === "ok" ? <I.check size={13}/> : <I.x size={13}/>}
          <span>{scanMsg.text}</span>
          <button onClick={() => setScanMsg(null)} style={{marginLeft:"auto",background:"none",border:"none",cursor:"pointer",color:"var(--text-dim)"}}>✕</button>
        </div>
      )}

      {/* status tabs */}
      <div className="card" style={{marginBottom: 14, padding: 6, display: "flex", alignItems: "center", gap: 4}}>
        {[
          ["all",     "All",                counts.all,     ""],
          ["fired",   "🔥 Fired (≤5 bars)", counts.fired,   "green"],
          ["armed",   "⚡ Near trigger",     counts.armed,   "amber"],
          ["pending", "⏳ Building range",   counts.pending, "blue"],
          ["past",    "📋 In trade / past",  counts.past,    ""],
          ["invalid", "✗ Invalidated",       counts.invalid, "red"],
        ].map(([id, label, n, color]) => (
          <button key={id}
            className={"btn " + (statusFilter === id ? "btn-primary" : "btn-ghost")}
            onClick={() => setStatusFilter(id)}
            style={{fontSize: 12}}>
            {label}
            <span className="mono" style={{
              marginLeft: 6, fontSize: 11,
              opacity: statusFilter === id ? 0.8 : 0.6
            }}>{n}</span>
          </button>
        ))}
        <div style={{marginLeft: "auto", display: "flex", gap: 8, alignItems: "center"}}>
          <span className="mono" style={{fontSize: 11, color: "var(--text-dim)"}}>Sort:</span>
          <select className="select" defaultValue="score" style={{width: "auto", padding: "5px 8px", fontSize: 12}}>
            <option value="score">Setup score</option>
            <option value="dist">Distance to trigger</option>
            <option value="vol">Volume surge</option>
            <option value="recent">Most recent</option>
          </select>
        </div>
      </div>

      <div className="card">
        <table className="tbl">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Sector</th>
              <th className="tbl-num">Listed</th>
              <th className="tbl-num">2W HIGH</th>
              <th className="tbl-num">2W LOW</th>
              <th className="tbl-num">LTP</th>
              <th className="tbl-num">Δ to trigger</th>
              <th className="tbl-num">Vol</th>
              <th>Score</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s, i) => {
              const dist = (s.last - s.hi) / s.hi * 100;
              const triggered = s.last >= s.hi;
              return (
                <tr key={i}>
                  <td>
                    <div className="symbol-cell">
                      <span className={"ipo-dot " + s.status}/>
                      <div className="symbol-icon">{s.sym.slice(0,2)}</div>
                      <div>
                        <div className="symbol-name">{s.sym}</div>
                        <div className="symbol-sub">{s.name}</div>
                      </div>
                    </div>
                  </td>
                  <td><span className="pill">{s.sector}</span></td>
                  <td className="tbl-num">{s.listDate.slice(5)}</td>
                  <td className="tbl-num up">{fmt.num(s.hi, 2)}</td>
                  <td className="tbl-num down">{fmt.num(s.lo, 2)}</td>
                  <td className="tbl-num"><strong>{fmt.num(s.last, 2)}</strong></td>
                  <td className={"tbl-num " + (triggered ? "up" : "muted")}>{fmt.pct(dist)}</td>
                  <td className="tbl-num">{s.vol}</td>
                  <td>
                    <div style={{display: "flex", alignItems: "center", gap: 6}}>
                      <div style={{width: 50, height: 4, background: "var(--surface-3)", borderRadius: 999, overflow: "hidden"}}>
                        <div style={{width: s.score + "%", height: "100%", background: s.score >= 80 ? "var(--green)" : s.score >= 60 ? "var(--amber)" : "var(--red)"}}/>
                      </div>
                      <span className="mono" style={{fontSize: 11}}>{s.score}</span>
                    </div>
                  </td>
                  <td>
                    <div>
                      <span className={
                        "status " +
                        (s.status === "fired"   ? "green" :
                         s.status === "armed"   ? "amber" :
                         s.status === "invalid" ? "red"   :
                         s.status === "past"    ? ""      : "blue")
                      }>
                        <span className="d"/>
                        {s.status === "fired"   ? "🔥 FIRED"    :
                         s.status === "armed"   ? "⚡ ARMED"    :
                         s.status === "past"    ? "📋 IN TRADE" :
                         s.status === "invalid" ? "✗ VOID"      : "⏳ BUILDING"}
                      </span>
                      {s.entryStatus && <div className="mono" style={{fontSize:10, color:"var(--text-dim)", marginTop:2}}>{s.entryStatus}</div>}
                    </div>
                  </td>
                  <td>
                    <div className="row-action row" style={{justifyContent: "flex-end"}}>
                      {s.status === "armed" && <button className="btn btn-xs btn-primary"><I.bolt size={11}/>Place GTT</button>}
                      {s.status === "fired" && <button className="btn btn-xs btn-primary"><I.bolt size={11}/>Buy now</button>}
                      <button className="btn btn-xs btn-ghost"><I.external size={11}/></button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="row" style={{marginTop: 12, justifyContent: "space-between", color: "var(--text-dim)", fontSize: 11.5}}>
        <span className="mono">Showing {filtered.length} of {universe.length}{lastScan ? ` · scanned ${lastScan}` : ""}</span>
        <span className="kbd-row">Press <span className="kbd">B</span> on any row to place a bracket order</span>
      </div>
    </div>
  );
}

window.PageScreener = PageScreener;
