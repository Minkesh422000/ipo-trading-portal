// Inline icons — minimal stroke icons (16x16 viewBox by default)
const Ico = ({ d, size = 16, fill = "none", stroke = "currentColor", sw = 1.5, children }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill={fill} stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" className="ico">
    {d ? <path d={d}/> : children}
  </svg>
);

const I = {
  dashboard: (p) => <Ico {...p}><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></Ico>,
  strategy:  (p) => <Ico {...p}><path d="M3 17l5-5 4 4 8-9"/><path d="M14 7h6v6"/></Ico>,
  screener:  (p) => <Ico {...p}><circle cx="11" cy="11" r="6"/><path d="m20 20-3.5-3.5"/></Ico>,
  orders:    (p) => <Ico {...p}><path d="M3 7h18M3 12h18M3 17h12"/></Ico>,
  journal:   (p) => <Ico {...p}><path d="M5 4h11a3 3 0 0 1 3 3v13a1 1 0 0 1-1 1H8a3 3 0 0 1-3-3V4z"/><path d="M9 8h6M9 12h6M9 16h4"/></Ico>,
  money:     (p) => <Ico {...p}><circle cx="12" cy="12" r="9"/><path d="M14.5 9.5C14 8 12.8 7.5 12 7.5S9.5 8 9.5 9.8c0 3 5 1.7 5 4.4 0 1.8-1.5 2.3-2.5 2.3s-2.3-.5-2.7-2"/><path d="M12 6v12"/></Ico>,
  link:      (p) => <Ico {...p}><path d="M10 13a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1.5 1.5"/><path d="M14 11a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1.5-1.5"/></Ico>,
  bell:      (p) => <Ico {...p}><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10 21a2 2 0 0 0 4 0"/></Ico>,
  search:    (p) => <Ico {...p}><circle cx="11" cy="11" r="6"/><path d="m20 20-3.5-3.5"/></Ico>,
  plus:      (p) => <Ico {...p}><path d="M12 5v14M5 12h14"/></Ico>,
  arrowUp:   (p) => <Ico {...p}><path d="M12 19V5M5 12l7-7 7 7"/></Ico>,
  arrowDown: (p) => <Ico {...p}><path d="M12 5v14M5 12l7 7 7-7"/></Ico>,
  filter:    (p) => <Ico {...p}><path d="M4 4h16l-6 8v6l-4 2v-8z"/></Ico>,
  sliders:   (p) => <Ico {...p}><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M18 18h2"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="16" cy="18" r="2" fill="currentColor"/></Ico>,
  download:  (p) => <Ico {...p}><path d="M12 4v12m-5-5 5 5 5-5"/><path d="M5 20h14"/></Ico>,
  settings:  (p) => <Ico {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.7l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.7-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.7.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.7 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.7l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.7.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.7-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.7V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/></Ico>,
  trash:     (p) => <Ico {...p}><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M6 6l1 14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-14"/></Ico>,
  edit:      (p) => <Ico {...p}><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4z"/></Ico>,
  bolt:      (p) => <Ico {...p}><path d="M13 2 4 14h7l-1 8 9-12h-7z"/></Ico>,
  shield:    (p) => <Ico {...p}><path d="M12 2 4 5v6c0 5 3.5 9 8 11 4.5-2 8-6 8-11V5z"/></Ico>,
  target:    (p) => <Ico {...p}><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/></Ico>,
  refresh:   (p) => <Ico {...p}><path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/></Ico>,
  clock:     (p) => <Ico {...p}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></Ico>,
  check:     (p) => <Ico {...p}><path d="M5 13l4 4L19 7"/></Ico>,
  x:         (p) => <Ico {...p}><path d="M6 6l12 12M18 6 6 18"/></Ico>,
  chev:      (p) => <Ico {...p}><path d="m9 6 6 6-6 6"/></Ico>,
  external:  (p) => <Ico {...p}><path d="M14 4h6v6"/><path d="M20 4 10 14"/><path d="M20 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h5"/></Ico>,
  dot:       (p) => <Ico {...p}><circle cx="12" cy="12" r="3" fill="currentColor"/></Ico>,
  candle:    (p) => <Ico {...p}><path d="M6 4v4M6 16v4M18 6v4M18 14v6"/><rect x="4" y="8" width="4" height="8"/><rect x="16" y="10" width="4" height="4"/></Ico>,
  flag:      (p) => <Ico {...p}><path d="M4 21V4M4 4h13l-2 4 2 4H4"/></Ico>,
  history:   (p) => <Ico {...p}><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/><path d="M12 7v5l3 2"/></Ico>,
};

window.I = I;
window.Ico = Ico;
