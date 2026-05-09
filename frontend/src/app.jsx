// App shell — page router + tweaks
const { useState: useAppState, useEffect: useAppEffect } = React;

function App() {
  const [t, setTweak] = useTweaks(window.TWEAK_DEFAULTS);
  const [dataSource, setDataSource] = useAppState("loading");

  const [active, setActive] = useAppState(() => {
    const hash = (location.hash || "").replace("#", "");
    return ["dashboard", "strategy", "screener", "orders", "journal", "money", "connections"].includes(hash) ? hash : "dashboard";
  });

  useAppEffect(() => { location.hash = active; }, [active]);

  // Fetch live data on mount, re-render when it arrives
  useAppEffect(() => {
    const onLive = () => setDataSource(window._liveDataSource || "mock");
    window.addEventListener("livedata", onLive);
    window.startLiveRefresh();
    return () => window.removeEventListener("livedata", onLive);
  }, []);

  // Apply theme + accent to <body>
  useAppEffect(() => {
    document.body.setAttribute("data-theme", t.theme);
    document.body.setAttribute("data-density", t.density);
    document.body.style.setProperty("--green", t.accent);
    // soft variant
    const m = t.accent.match(/^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i);
    if (m) {
      const [r, g, b] = [m[1], m[2], m[3]].map(x => parseInt(x, 16));
      document.body.style.setProperty("--green-soft", `rgba(${r},${g},${b},0.14)`);
    }
  }, [t.theme, t.accent, t.density]);

  let Page;
  if (active === "dashboard")        Page = PageDashboard;
  else if (active === "strategy")    Page = PageStrategy;
  else if (active === "screener")    Page = PageScreener;
  else if (active === "orders")      Page = PageOrders;
  else if (active === "journal")     Page = PageJournal;
  else if (active === "money")       Page = PageMoney;
  else if (active === "connections") Page = PageConnections;

  return (
    <div className="app">
      <Sidebar active={active} onNav={setActive}/>
      <main className="main">
        <Topbar active={active} dataSource={dataSource}/>
        <Page/>
      </main>
      <TweaksPanel title="Tweaks">
        <TweakSection label="Theme"/>
        <TweakRadio label="Mode" value={t.theme}
          options={["dark", "light"]}
          onChange={v => setTweak("theme", v)}/>
        <TweakColor label="Accent" value={t.accent}
          options={["#22c55e", "#3b82f6", "#a78bfa", "#f59e0b", "#ec4899"]}
          onChange={v => setTweak("accent", v)}/>

        <TweakSection label="Layout"/>
        <TweakRadio label="Density" value={t.density}
          options={["compact", "regular", "comfy"]}
          onChange={v => setTweak("density", v)}/>

        <TweakSection label="Modules"/>
        <TweakToggle label="Today's signals" value={t.showSignals}
          onChange={v => setTweak("showSignals", v)}/>
        <TweakToggle label="Portfolio heat" value={t.showHeat}
          onChange={v => setTweak("showHeat", v)}/>
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("app")).render(<App/>);
