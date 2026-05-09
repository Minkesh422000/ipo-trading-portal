// Connections page — broker API integrations
const { useState: useConnState, useEffect: useConnEffect } = React;

function PageConnections() {
  const [brokers, setBrokers] = useConnState(window.BROKERS || []);
  const [connecting, setConnecting] = useConnState(null);  // account id being connected
  const [editing, setEditing] = useConnState(null);        // account id being edited
  const [editForm, setEditForm] = useConnState({ api_key: "", api_secret: "" });
  const [manualToken, setManualToken] = useConnState("");
  const [status, setStatus] = useConnState(null);  // {type: "ok"|"err", msg}

  // Keep in sync when live data refreshes
  useConnEffect(() => {
    const onLive = () => setBrokers([...(window.BROKERS || [])]);
    window.addEventListener("livedata", onLive);
    return () => window.removeEventListener("livedata", onLive);
  }, []);

  async function handleSaveCredentials(brokerId) {
    if (!editForm.api_key.trim() || !editForm.api_secret.trim()) return;
    setStatus({ type: "info", msg: "Saving credentials…" });
    try {
      const res = await fetch("/api/kite/update-credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account_id: brokerId, ...editForm }),
      });
      const d = await res.json();
      if (d.ok) {
        setStatus({ type: "ok", msg: "✓ Credentials updated. Now click Connect Kite to log in." });
        setEditing(null);
        setEditForm({ api_key: "", api_secret: "" });
      } else {
        setStatus({ type: "err", msg: d.error || "Save failed" });
      }
    } catch (e) {
      setStatus({ type: "err", msg: "Request failed: " + e.message });
    }
  }

  async function handleConnect(broker) {
    setStatus(null);
    try {
      const res = await fetch(`/api/kite/login-url/${broker.id}`);
      const d = await res.json();
      if (!d.ok) { setStatus({ type: "err", msg: d.error }); return; }

      // Open Kite login in new tab
      window.open(d.url, "_blank");

      // Show manual-paste fallback (for users whose redirect URL isn't set to localhost:7654)
      setConnecting(broker.id);
      setManualToken("");
      setStatus({
        type: "info",
        msg: `Logged in on Kite? If you weren't redirected automatically, paste the request_token from the redirect URL below.`,
      });
    } catch (e) {
      setStatus({ type: "err", msg: "Could not reach server: " + e.message });
    }
  }

  async function handleSubmitToken(brokerId) {
    if (!manualToken.trim()) return;
    setStatus({ type: "info", msg: "Exchanging token…" });
    try {
      const res = await fetch("/api/kite/complete-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account_id: brokerId, request_token: manualToken.trim() }),
      });
      const d = await res.json();
      if (d.ok) {
        setStatus({ type: "ok", msg: "✓ Connected! Refreshing data…" });
        setConnecting(null);
        setManualToken("");
        setTimeout(() => window.fetchLiveData(), 1000);
      } else {
        setStatus({ type: "err", msg: d.error || "Token exchange failed" });
      }
    } catch (e) {
      setStatus({ type: "err", msg: "Request failed: " + e.message });
    }
  }

  return (
    <div className="page" data-screen-label="Connections">
      <div className="page-header">
        <div>
          <div className="page-title">Broker Connections</div>
          <div className="page-sub">Connect your Zerodha account via Kite Connect API. Tokens are encrypted at rest and expire daily at 6:30 AM IST.</div>
        </div>
      </div>

      <div className="notice" style={{marginBottom: 16}}>
        <I.shield size={14}/>
        <span>
          <strong>Setup:</strong> In your{" "}
          <a href="https://developers.kite.trade/apps" target="_blank" style={{color: "var(--blue)", textDecoration: "underline"}}>
            Kite Connect app
          </a>
          , set the Redirect URL to{" "}
          <code style={{background: "var(--surface-3)", padding: "1px 6px", borderRadius: 4, fontSize: 11.5}}>
            http://localhost:7654/kite-callback
          </code>
          {" "}for auto-login. Or paste the request_token manually below.
        </span>
      </div>

      {/* Status banner */}
      {status && (
        <div className={"notice " + (status.type === "ok" ? "green" : status.type === "err" ? "red" : "")}
             style={{marginBottom: 16, color: status.type === "ok" ? "var(--green)" : status.type === "err" ? "var(--red)" : "var(--text)"}}>
          {status.type === "ok" ? <I.check size={14}/> : status.type === "err" ? <I.x size={14}/> : <I.refresh size={14}/>}
          <span>{status.msg}</span>
          <button onClick={() => setStatus(null)} style={{marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "var(--text-dim)", fontSize: 14}}>✕</button>
        </div>
      )}

      <div style={{display: "flex", flexDirection: "column", gap: 12, marginBottom: 16}}>
        {brokers.map((b) => (
          <div key={b.id} className="card">
            <div className="card-pad">
              <div className="row-between">
                {/* Left: broker info */}
                <div className="row" style={{gap: 12}}>
                  <div style={{
                    width: 44, height: 44, borderRadius: 10,
                    background: "rgba(59,130,246,0.12)",
                    border: "1px solid var(--border-2)",
                    display: "grid", placeItems: "center",
                    fontFamily: "IBM Plex Mono", fontSize: 15, fontWeight: 600,
                    color: "#3b82f6", flexShrink: 0,
                  }}>{b.name?.[0] || "Z"}</div>
                  <div>
                    <div style={{fontSize: 14, fontWeight: 500}}>{b.name}</div>
                    <div className="mono" style={{fontSize: 11, color: "var(--text-dim)"}}>
                      Zerodha · Kite Connect · {b.account || "—"}
                    </div>
                  </div>
                </div>

                {/* Right: status + action */}
                <div className="row" style={{gap: 10}}>
                  <div className="kv" style={{marginRight: 8}}>
                    <span className="k">Balance</span>
                    <span className="v">{b.connected && b.balance != null ? fmt.inr(b.balance) : "—"}</span>
                  </div>
                  <span className={"pill " + (b.connected ? "green dot" : "")}>
                    {b.connected ? "● Live" : "○ Offline"}
                  </span>
                  {b.connected ? (
                    <button className="btn btn-sm btn-ghost" onClick={() => window.fetchLiveData()}>
                      <I.refresh size={12}/> Resync
                    </button>
                  ) : (
                    <button className="btn btn-sm btn-primary" onClick={() => handleConnect(b)}>
                      <I.link size={12}/> Connect Kite
                    </button>
                  )}
                  <button className="btn btn-sm btn-ghost" title="Edit API credentials"
                    onClick={() => { setEditing(editing === b.id ? null : b.id); setEditForm({ api_key: "", api_secret: "" }); setStatus(null); }}>
                    <I.edit size={12}/>
                  </button>
                </div>
              </div>

              {/* Edit credentials form */}
              {editing === b.id && (
                <div style={{marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--border)"}}>
                  <div style={{fontSize: 12, color: "var(--text-dim)", marginBottom: 10}}>
                    Update Kite Connect API credentials (from{" "}
                    <a href="https://developers.kite.trade/apps" target="_blank" style={{color: "var(--blue)"}}>developers.kite.trade</a>)
                  </div>
                  <div style={{display: "flex", flexDirection: "column", gap: 8}}>
                    <div className="row" style={{gap: 8, alignItems: "center"}}>
                      <label style={{fontSize: 11.5, color: "var(--text-dim)", width: 80, flexShrink: 0}}>API Key</label>
                      <input
                        type="text"
                        placeholder="e.g. foe25i7t8ph3jdjm"
                        value={editForm.api_key}
                        onChange={e => setEditForm(f => ({...f, api_key: e.target.value}))}
                        style={{
                          flex: 1, background: "var(--surface-2)", border: "1px solid var(--border-2)",
                          borderRadius: 6, padding: "7px 12px", color: "var(--text)",
                          fontFamily: "IBM Plex Mono", fontSize: 12, outline: "none",
                        }}
                      />
                    </div>
                    <div className="row" style={{gap: 8, alignItems: "center"}}>
                      <label style={{fontSize: 11.5, color: "var(--text-dim)", width: 80, flexShrink: 0}}>API Secret</label>
                      <input
                        type="password"
                        placeholder="32-character secret"
                        value={editForm.api_secret}
                        onChange={e => setEditForm(f => ({...f, api_secret: e.target.value}))}
                        style={{
                          flex: 1, background: "var(--surface-2)", border: "1px solid var(--border-2)",
                          borderRadius: 6, padding: "7px 12px", color: "var(--text)",
                          fontFamily: "IBM Plex Mono", fontSize: 12, outline: "none",
                        }}
                      />
                    </div>
                    <div className="row" style={{gap: 8, justifyContent: "flex-end"}}>
                      <button className="btn btn-sm btn-ghost" onClick={() => { setEditing(null); setEditForm({ api_key: "", api_secret: "" }); }}>
                        Cancel
                      </button>
                      <button className="btn btn-sm btn-primary"
                        disabled={!editForm.api_key.trim() || !editForm.api_secret.trim()}
                        onClick={() => handleSaveCredentials(b.id)}>
                        Save credentials
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Manual token input — shown after clicking Connect */}
              {connecting === b.id && (
                <div style={{marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--border)"}}>
                  <div style={{fontSize: 12, color: "var(--text-dim)", marginBottom: 8}}>
                    After logging in on Kite, copy the <code style={{color: "var(--green)"}}>request_token</code> from the redirect URL
                    {" "}(it looks like: <code style={{fontSize: 11, color: "var(--text-dim)"}}>https://127.0.0.1/?request_token=<strong>XXXXXX</strong>&…</code>)
                  </div>
                  <div className="row" style={{gap: 8}}>
                    <input
                      type="text"
                      placeholder="Paste request_token here…"
                      value={manualToken}
                      onChange={e => setManualToken(e.target.value)}
                      onKeyDown={e => e.key === "Enter" && handleSubmitToken(b.id)}
                      style={{
                        flex: 1, background: "var(--surface-2)", border: "1px solid var(--border-2)",
                        borderRadius: 6, padding: "7px 12px", color: "var(--text)",
                        fontFamily: "IBM Plex Mono", fontSize: 12, outline: "none",
                      }}
                    />
                    <button className="btn btn-sm btn-primary" onClick={() => handleSubmitToken(b.id)}
                            disabled={!manualToken.trim()}>
                      Verify &amp; Connect
                    </button>
                    <button className="btn btn-sm btn-ghost" onClick={() => { setConnecting(null); setStatus(null); }}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {brokers.length === 0 && (
          <div className="card">
            <div className="card-pad" style={{textAlign: "center", padding: 40, color: "var(--text-dim)"}}>
              <I.link size={24} style={{marginBottom: 12, opacity: 0.4}}/>
              <div>No broker accounts configured yet.</div>
              <div style={{fontSize: 12, marginTop: 6}}>Add accounts via the Streamlit settings page.</div>
            </div>
          </div>
        )}
      </div>

      {/* How it works */}
      <div className="card" style={{marginBottom: 16}}>
        <div className="card-head"><div className="card-title">How to connect Zerodha</div></div>
        <div className="card-pad">
          <div style={{display: "flex", flexDirection: "column", gap: 12}}>
            {[
              { n: "1", text: "Go to developers.kite.trade → My Apps → your app → set Redirect URL to http://localhost:7654/kite-callback" },
              { n: "2", text: "Click \"Connect Kite\" above — it opens the Kite login page in a new tab" },
              { n: "3", text: "Log in with your Zerodha credentials + TOTP" },
              { n: "4", text: "Kite redirects back automatically (if redirect URL is set) — or copy the request_token from the URL and paste it manually" },
              { n: "5", text: "Token is saved and valid until 6:30 AM IST. You'll need to reconnect each morning." },
            ].map(s => (
              <div key={s.n} className="row" style={{gap: 12, alignItems: "flex-start"}}>
                <div style={{
                  width: 22, height: 22, borderRadius: "50%", background: "var(--surface-3)",
                  display: "grid", placeItems: "center", fontSize: 11, fontWeight: 600,
                  color: "var(--green)", flexShrink: 0, fontFamily: "IBM Plex Mono",
                }}>{s.n}</div>
                <div style={{fontSize: 12.5, color: "var(--text-dim)", paddingTop: 2}}>{s.text}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* API health (static for now) */}
      <div className="card">
        <div className="card-head"><div className="card-title">API health</div><span className="card-sub">last 24h</span></div>
        <div className="card-pad">
          {[
            { name: "Zerodha · Kite Connect", uptime: 99.8, lat: "84ms", color: "var(--green)" },
            { name: "Brkout scanner (yfinance)", uptime: 100, lat: "—", color: "var(--green)" },
          ].map((s, i, arr) => (
            <div key={i} style={{padding: "10px 0", borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none"}}>
              <div className="row-between" style={{marginBottom: 5}}>
                <span style={{fontSize: 12.5}}>{s.name}</span>
                <span className="mono" style={{fontSize: 11, color: s.color}}>{s.uptime}%</span>
              </div>
              <div className="row-between mono" style={{fontSize: 10.5, color: "var(--text-dim)"}}>
                <span>p95 latency · {s.lat}</span>
                <div style={{display: "flex", gap: 1.5}}>
                  {[...Array(40)].map((_, j) => (
                    <div key={j} style={{width: 3, height: 12, background: s.color, opacity: 0.7, borderRadius: 1}}/>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

window.PageConnections = PageConnections;
