// Sidebar + topbar layout shell
const { useState } = React;

const NAV = [
  { id: "dashboard",   label: "Dashboard",        icon: "dashboard" },
  { id: "strategy",    label: "Strategy",         icon: "strategy", badge: "1" },
  { id: "screener",    label: "Screener",         icon: "screener", badge: "12" },
  { id: "orders",      label: "Orders",           icon: "orders",   badge: "4" },
  { id: "journal",     label: "Journal",          icon: "journal" },
  { id: "money",       label: "Money mgmt",       icon: "money" },
  { id: "connections", label: "Brokers",          icon: "link" },
];

function Sidebar({ active, onNav }) {
  return (
    <aside className="sidebar" data-screen-label="Sidebar">
      <div className="sb-brand">
        <div className="sb-brand-mark">B</div>
        <div>
          <div className="sb-brand-name">Brkout</div>
          <div className="sb-brand-sub">v0.4 · alpha</div>
        </div>
      </div>

      <div className="sb-section">Trade</div>
      <div className="sb-nav">
        {NAV.slice(0, 4).map(n => {
          const Icon = I[n.icon];
          return (
            <a key={n.id} className={"sb-link " + (active === n.id ? "active" : "")} onClick={() => onNav(n.id)}>
              <Icon/>
              <span>{n.label}</span>
              {n.badge && <span className="badge">{n.badge}</span>}
            </a>
          );
        })}
      </div>

      <div className="sb-section">Analyze</div>
      <div className="sb-nav">
        {NAV.slice(4, 6).map(n => {
          const Icon = I[n.icon];
          return (
            <a key={n.id} className={"sb-link " + (active === n.id ? "active" : "")} onClick={() => onNav(n.id)}>
              <Icon/>
              <span>{n.label}</span>
              {n.badge && <span className="badge">{n.badge}</span>}
            </a>
          );
        })}
      </div>

      <div className="sb-section">Setup</div>
      <div className="sb-nav">
        {NAV.slice(6).map(n => {
          const Icon = I[n.icon];
          return (
            <a key={n.id} className={"sb-link " + (active === n.id ? "active" : "")} onClick={() => onNav(n.id)}>
              <Icon/>
              <span>{n.label}</span>
              {n.badge && <span className="badge">{n.badge}</span>}
            </a>
          );
        })}
      </div>

      <div className="sb-foot">
        <div className="sb-avatar">RP</div>
        <div className="sb-foot-meta">
          <div className="sb-foot-name">Ravi Patel</div>
          <div className="sb-foot-sub">5 brokers · 2 live</div>
        </div>
        <div className="sb-foot-dot" title="Live"/>
      </div>
    </aside>
  );
}

function Topbar({ active, dataSource }) {
  const titleMap = {
    dashboard: "Dashboard",
    strategy: "Strategy · IPO Breakout",
    screener: "Screener",
    orders: "Order Manager",
    journal: "Trade Journal",
    money: "Money Management",
    connections: "Broker Connections",
  };
  const crumbMap = {
    dashboard: "Home",
    strategy: "Strategies / IPO Breakout",
    screener: "Live universe / NSE & BSE",
    orders: "Open + pending",
    journal: "Closed trades + analytics",
    money: "Capital · Risk · Heat",
    connections: "API integrations",
  };
  return (
    <div className="topbar">
      <div>
        <div className="topbar-title">{titleMap[active]}</div>
        <div className="topbar-crumb">{crumbMap[active]}</div>
      </div>
      <div className="topbar-actions">
        <span className="market-pill"><span className="dot"/>NSE LIVE · 14:42 IST</span>
        <span className="market-pill" style={{borderColor: "var(--border)"}}>NIFTY 23,418.40 <span className="up" style={{marginLeft:6}}>+0.41%</span></span>
        {dataSource === "live"
          ? <span className="pill green dot" style={{fontSize:11}}>↻ Live</span>
          : dataSource === "mock"
          ? <span className="pill amber" style={{fontSize:11}}>⚠ Mock data</span>
          : <span className="pill" style={{fontSize:11, color:"var(--text-dim)"}}>⟳ Loading…</span>
        }
        <button className="btn btn-ghost"><I.search size={14}/> Search <span className="kbd" style={{marginLeft:4}}>⌘K</span></button>
        <button className="btn btn-ghost" title="Notifications"><I.bell size={14}/></button>
        <button className="btn btn-ghost" title="Settings"><I.settings size={14}/></button>
      </div>
    </div>
  );
}

window.Sidebar = Sidebar;
window.Topbar = Topbar;
