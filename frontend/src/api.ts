// Types and websocket calls shared by the panel views (backend: websocket_api.py, feed.py).

export interface HomeAssistant {
  connection: {
    subscribeMessage<T>(callback: (msg: T) => void, msg: Record<string, unknown>): Promise<() => Promise<void>>;
    addEventListener?(type: "ready" | "disconnected", listener: () => void): void;
    removeEventListener?(type: "ready" | "disconnected", listener: () => void): void;
  };
  callWS<T>(msg: Record<string, unknown>): Promise<T>;
  language: string;
  locale?: { language: string };
}

/** [unix time, rx bytes/s, tx bytes/s]; rx is download, tx is upload. */
export type Sample = [number, number, number];

export interface Client {
  mac: string;
  ip: string;
  name: string;
  alias: string;
  online: boolean;
  blocked: boolean;
  iface: string;
  rx: number;
  tx: number;
  total_rx: number;
  total_tx: number;
  limit_rx: number;
  limit_tx: number;
  since: number | null; // unix time (this host's clock) the client came online
  static_ip: string | null;
}

export interface WifiIface {
  name: string;
  ssid: string;
  enabled: boolean;
  up: boolean | null;
  guest: boolean;
  hidden: boolean;
  encryption: string;
  bssid: string;
}

export interface WifiBand {
  band: string;
  channel: number | string | null;
  hwmode: string;
  htmode: string;
  ifaces: WifiIface[];
}

export interface StaticBind {
  mac: string;
  ip: string;
  name: string;
}

export interface Router {
  entry_id: string;
  title: string;
  host: string;
  available: boolean;
  fetched_at: number;
  mode: string;
  model: string | null;
  hostname: string | null;
  firmware: string | null;
  mac: string | null;
  lan_ip: string | null;
  uptime: number | null;
  load: number[] | null;
  memory: { total: number; free: number; cache: number } | null;
  flash: { total: number; free: number } | null;
  wan: { online: boolean; links: string[]; rx: number; tx: number };
  stations: { wireless: number | null; cable: number | null };
  wifi: WifiBand[];
  clients: Client[];
  static_binds: StaticBind[];
  blocklist: { mode: string; black: string[]; white: string[] };
  auth_failed: boolean;
  features: {
    static_ip_remove: boolean;
    wan_speed: boolean;
    clients: boolean;
    wifi: boolean;
    static_ip: boolean;
    blocklist: boolean;
  };
  history?: { wan: Sample[] };
}

export interface Activity {
  t: number;
  channel: "panel" | "service" | "entity" | string;
  action: string;
  summary: string;
  ok: boolean;
  user: string | null;
  entry_id: string | null;
  router: string;
  msg: string; // a log_<msg> translation key; summary is the English line
  args: Record<string, string | number>;
}

export interface Snapshot {
  routers: Router[];
  activity: Activity[];
  live_interval: number;
}

export type FeedEvent =
  | { kind: "router"; router: Router }
  | { kind: "router_removed"; entry_id: string }
  | { kind: "live"; entry_id: string; t: number; wan: { rx: number; tx: number }; clients: Client[] }
  | { kind: "activity"; entries: Activity[] };

export interface WifiPatch {
  enabled?: boolean;
  ssid?: string;
  key?: string;
}

/** What a rejected websocket call carries (an ActionError's code, or one of Home Assistant's). */
export interface CodedError {
  code?: string;
  message?: string;
}

export class Api {
  constructor(private readonly hass: () => HomeAssistant) {}

  subscribe(callback: (event: FeedEvent) => void): Promise<() => Promise<void>> {
    return this.hass().connection.subscribeMessage<FeedEvent>(callback, { type: "woow_glinet/subscribe" });
  }

  snapshot(): Promise<Snapshot> {
    return this.hass().callWS({ type: "woow_glinet/snapshot" });
  }

  refresh(entryId: string): Promise<void> {
    return this.hass().callWS({ type: "woow_glinet/refresh", entry_id: entryId });
  }

  setWifi(entryId: string, iface: string, patch: WifiPatch): Promise<void> {
    return this.hass().callWS({ type: "woow_glinet/wifi/set", entry_id: entryId, iface, ...patch });
  }

  async wifiKey(entryId: string, iface: string): Promise<string> {
    const res = await this.hass().callWS<{ key: string }>({ type: "woow_glinet/wifi/key", entry_id: entryId, iface });
    return res.key;
  }

  block(entryId: string, mac: string, blocked: boolean): Promise<void> {
    return this.hass().callWS({ type: "woow_glinet/client/block", entry_id: entryId, mac, blocked });
  }

  forget(entryId: string, mac: string): Promise<void> {
    return this.hass().callWS({ type: "woow_glinet/client/forget", entry_id: entryId, mac });
  }

  async clientHistory(entryId: string, mac: string): Promise<Sample[]> {
    const res = await this.hass().callWS<{ series: Sample[] }>({ type: "woow_glinet/client/history", entry_id: entryId, mac });
    return res.series;
  }

  addStaticIp(entryId: string, mac: string, ip: string, name: string): Promise<void> {
    return this.hass().callWS({ type: "woow_glinet/static_ip/add", entry_id: entryId, mac, ip, name });
  }

  reboot(entryId: string): Promise<void> {
    return this.hass().callWS({ type: "woow_glinet/reboot", entry_id: entryId });
  }
}

export function errorText(err: unknown): string {
  if (err && typeof err === "object" && "message" in err) {
    return String((err as { message: unknown }).message);
  }
  return String(err);
}

export function errorCode(err: unknown): string {
  if (err && typeof err === "object" && "code" in err) {
    return String((err as { code: unknown }).code);
  }
  return "";
}

/** Copy that also works over plain http (navigator.clipboard needs a secure context). */
export function copyText(text: string): void {
  if (navigator.clipboard && window.isSecureContext) {
    void navigator.clipboard.writeText(text);
    return;
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}

/** Define a custom element once, so a reloaded bundle does not throw on the second define. */
export function define(name: string, cls: CustomElementConstructor): void {
  if (!customElements.get(name)) {
    customElements.define(name, cls);
  }
}

/** A client's display name: its name, else its alias, else its MAC. */
export function clientName(c: Pick<Client, "name" | "alias" | "mac">): string {
  return c.name || c.alias || c.mac;
}
