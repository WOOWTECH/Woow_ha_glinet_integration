// Fake backend data for the panel harness: situations the one real router cannot produce.
const NOW = () => Date.now() / 1000;
const NAMES = ["iPhone-Ann", "MacBook Pro", "Living-room TV", "Hue Bridge", "ESP32-sensor-kitchen", "HP LaserJet", "", "Galaxy-S24", "Nest Thermostat",
  "A-very-long-device-name-that-should-be-truncated-with-an-ellipsis-in-the-card", "Switch-Lite", "Echo Dot", "Roborock", "iPad", "Pixel-8", "NAS", "Camera-front", "Camera-garden", "Sonos", "Fridge", "Desktop-PC", "Laptop-Bob", "Kindle", "Watch"];

export function client(i, over = {}) {
  const online = i % 5 !== 3;
  const mac = `AA:BB:CC:00:${String(Math.floor(i / 256)).padStart(2, "0")}:${i.toString(16).toUpperCase().padStart(2, "0")}`;
  return {
    mac, ip: `192.168.8.${100 + i}`, name: NAMES[i % NAMES.length], alias: "", online, blocked: i % 11 === 7,
    iface: i % 3 === 0 ? "cable" : i % 3 === 1 ? "2.4G" : "5G",
    rx: online ? Math.round(Math.abs(Math.sin(i)) * 900000) : 0, tx: online ? Math.round(Math.abs(Math.cos(i)) * 120000) : 0,
    total_rx: 5e9 * (i + 1) / 7, total_tx: 4e8 * (i + 1) / 5, limit_rx: i === 2 ? 2000 : 0, limit_tx: i === 2 ? 500 : 0,
    since: online ? NOW() - 3600 * (i + 1) : null, static_ip: i % 4 === 0 ? `192.168.8.${100 + i}` : null, ...over,
  };
}

export function wanHistory(n = 300, step = 5) {
  const t0 = NOW() - n * step;
  return Array.from({ length: n }, (_, i) => [t0 + i * step, Math.round(2e5 + 1.5e5 * Math.sin(i / 9) + (i % 37 === 0 ? 2e6 : 0)), Math.round(4e4 + 3e4 * Math.cos(i / 7))]);
}

export function router(over = {}) {
  const clients = Array.from({ length: 24 }, (_, i) => client(i));
  return {
    entry_id: "r1", title: "GL-SFT1200", host: "192.0.2.45", available: true, fetched_at: NOW(), mode: "router", model: "GL-SFT1200", hostname: "GL-SFT1200",
    firmware: "4.8.3", mac: "94:83:C4:00:00:01", lan_ip: "192.168.8.1", uptime: 400000, load: [0.42, 0.51, 0.47],
    memory: { total: 121548800, free: 21835776, cache: 6815744 }, flash: { total: 134217728, free: 85434368 },
    wan: { online: true, links: ["wan"], rx: 412000, tx: 61000 }, stations: { wireless: 14, cable: 6 },
    wifi: [
      { band: "2G", channel: 6, hwmode: "11g/n", htmode: "HT20", ifaces: [
        { name: "default_radio0", ssid: "WOOW-Home", enabled: true, up: true, guest: false, hidden: false, encryption: "psk2", bssid: "D2:00:00:00:00:01" },
        { name: "guest2g", ssid: "WOOW-Home-Guest", enabled: false, up: false, guest: true, hidden: false, encryption: "psk2", bssid: "6E:B3:91:76:E1:B3" }] },
      { band: "5G", channel: 0, hwmode: "11a/n/ac", htmode: "80", ifaces: [
        { name: "default_radio1", ssid: "WOOW-Home-5G", enabled: true, up: true, guest: false, hidden: true, encryption: "sae-mixed", bssid: "7A:01:63:FD:7C:9E" }] },
    ],
    clients, static_binds: clients.filter((c) => c.static_ip).slice(0, 4).map((c) => ({ mac: c.mac, ip: c.ip, name: c.name || "unnamed" })),
    blocklist: { mode: "black", black: [clients[7].mac, clients[18].mac, "DE:AD:BE:EF:00:01"], white: [] },
    auth_failed: false, features: { static_ip_remove: false, wan_speed: true, clients: true, wifi: true, static_ip: true, blocklist: true }, history: { wan: wanHistory() }, ...over,
  };
}

const activity = () => [
  { t: NOW() - 30, channel: "panel", action: "block", summary: "Blocked Galaxy-S24 (AA:BB:CC:00:00:07)", ok: true, user: "Ann", entry_id: "r1", router: "GL-SFT1200", msg: "blocked", args: { name: "Galaxy-S24", mac: "AA:BB:CC:00:00:07" } },
  { t: NOW() - 400, channel: "service", action: "static_ip", summary: "Reserved", ok: true, user: "AI agent", entry_id: "r1", router: "GL-SFT1200", msg: "static_ip_added", args: { name: "NAS", mac: "AA:BB:CC:00:00:0F", ip: "192.168.8.115" } },
  { t: NOW() - 900, channel: "entity", action: "wifi", summary: "x", ok: true, user: null, entry_id: "r1", router: "GL-SFT1200", msg: "wifi_off", args: { ssid: "WOOW-Home-Guest", iface: "guest2g" } },
  { t: NOW() - 5000, channel: "panel", action: "static_ip", summary: "x", ok: false, user: "Ann", entry_id: "r1", router: "GL-SFT1200", msg: "static_ip_failed", args: { mac: "AA:BB:CC:00:00:01", ip: "10.1.1.1", error: "中文訊息", code: "ip_outside_lan" } },
  { t: NOW() - 9000, channel: "panel", action: "reboot", summary: "Rebooted GL-SFT1200", ok: true, user: "Ann", entry_id: "r1", router: "GL-SFT1200", msg: "rebooted", args: {} },
];

const LONG = "x".repeat(300);
const longnames = () => {
  const r = router({ title: "GL-ROUTER-" + "y".repeat(80) });
  r.clients = r.clients.map((c, i) => ({ ...c, name: i % 3 === 0 ? LONG : i % 3 === 1 ? "https://" + "z".repeat(120) + ".example.com/path" : c.name, alias: "" }));
  r.wifi[0].ifaces[0].ssid = "W".repeat(32);
  r.blocklist.black = [r.clients[0].mac, r.clients[1].mac];
  r.static_binds = r.clients.slice(0, 3).map((c) => ({ mac: c.mac, ip: c.ip, name: LONG }));
  return { snapshot: { routers: [r], activity: [{ t: Date.now() / 1000 - 5, channel: "panel", action: "block", summary: "x", ok: true, user: "u".repeat(60), entry_id: "r1", router: r.title, msg: "blocked", args: { name: LONG, mac: r.clients[0].mac } }], live_interval: 5 } };
};
export const scenarios = {
  authfailed: () => ({ snapshot: { routers: [router({ auth_failed: true, available: false })], activity: [], live_interval: 5 } }),
  nofeatures: () => ({ snapshot: { routers: [router({ features: { static_ip_remove: false, wan_speed: false, clients: true, wifi: true, static_ip: false, blocklist: true } })], activity: [], live_interval: 5 } }),
  nowifi: () => ({ snapshot: { routers: [router({ features: { static_ip_remove: false, wan_speed: true, clients: false, wifi: false, static_ip: false, blocklist: false }, clients: [], wifi: [] })], activity: [], live_interval: 5 } }),
  longnames,
  many: () => ({ snapshot: { routers: [router()], activity: activity(), live_interval: 5 } }),
  ap: () => ({ snapshot: { routers: [router({ mode: "ap", wan: { online: true, links: ["wwan"], rx: 0, tx: 0 }, clients: [], history: { wan: [] } })], activity: activity(), live_interval: 5 } }),
  multi: () => ({ snapshot: { routers: [router(), router({ entry_id: "r2", title: "GL-SFT1200 (office)", host: "192.0.2.46", available: false, clients: [client(1), client(2)], blocklist: { mode: "black", black: [], white: [] }, static_binds: [] })], activity: activity(), live_interval: 5 } }),
  white: () => ({ snapshot: { routers: [router({ blocklist: { mode: "white", black: [], white: ["AA:BB:CC:00:00:01", "AA:BB:CC:00:00:02"] } })], activity: activity(), live_interval: 5 } }),
  empty: () => ({ snapshot: { routers: [], activity: [], live_interval: 5 } }),
  error: () => ({ error: true }),
  fresh: () => ({ snapshot: { routers: [router({ clients: [], static_binds: [], blocklist: { mode: "black", black: [], white: [] }, history: { wan: [] } })], activity: [], live_interval: 5 } }),
};
