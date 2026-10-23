// Panel strings. Follows the Home Assistant user's language: Chinese (any zh-*) or English.

const en = {
  title: "WOOW GL.iNet",
  tab_overview: "Overview",
  tab_clients: "Devices",
  tab_wifi: "Wi-Fi",
  tab_access: "Access",
  tab_activity: "Activity",
  loading: "Loading…",
  no_routers: "No router yet. Add one under Settings › Devices & services › WOOW GL.iNet.",
  error: "Error: {msg}",
  cancel: "Cancel",
  confirm: "Confirm",
  save: "Save",
  saving: "Saving…",
  add: "Add",
  refresh: "Refresh",
  copy: "Copy",
  copied: "Copied",
  show: "Show",
  hide: "Hide",
  just_now: "just now",
  s_ago: "{n} s ago",
  m_ago: "{n} min ago",
  h_ago: "{n} h ago",
  d_ago: "{n} d ago",
  updated: "Updated {x}",
  router_pick: "Router",

  // overview
  unreachable: "The router does not answer. Showing what was last read.",
  mode_router: "Router mode",
  mode_ap: "Access point mode",
  mode_wds: "WDS mode",
  mode_relay: "Repeater mode",
  mode_mesh: "Mesh mode",
  mode_passthrough: "Pass-through mode",
  mode_other: "{mode} mode",
  mode_note:
    "In this mode the router is bridged onto another network: it has no NAT or DHCP of its own, so the device list, blocking, fixed IPs and internet traffic are not available here. Wi-Fi and system controls still work.",
  fact_model: "Model",
  fact_firmware: "Firmware",
  fact_address: "Address",
  fact_lan: "LAN address",
  fact_uptime: "Uptime",
  fact_load: "Load (1 / 5 / 15 min)",
  fact_memory: "Memory",
  fact_storage: "Storage",
  fact_internet: "Internet",
  fact_devices: "Devices",
  wan_online: "Connected",
  wan_offline: "No uplink",
  link_wan: "WAN port",
  link_wwan: "Wi-Fi uplink",
  link_tethering: "USB tethering",
  link_modem: "Cellular",
  devices_online: "{n} online",
  devices_split: "{wired} wired · {wireless} Wi-Fi",
  used_of: "{used} of {total}",
  traffic_title: "Internet traffic",
  download: "Download",
  upload: "Upload",
  peak: "peak {x}",
  range_5m: "5 min",
  range_30m: "30 min",
  range_all: "All",
  chart_empty: "Collecting samples…",
  busiest_title: "Busiest devices",
  busiest_empty: "Nothing is moving right now.",
  reboot: "Reboot",
  reboot_title: "Reboot {router}?",
  reboot_text: "The network goes down for 1–2 minutes and every device has to reconnect.",
  rebooting: "Reboot command sent. The router is back in about 1–2 minutes.",

  // devices
  search_ph: "Search name, IP or MAC",
  f_all: "All",
  f_online: "Online",
  f_offline: "Offline",
  f_blocked: "Blocked",
  sort_speed: "Sort: speed",
  sort_total: "Sort: total traffic",
  sort_name: "Sort: name",
  sort_ip: "Sort: IP address",
  unnamed: "Unnamed device",
  iface_cable: "Wired",
  chip_blocked: "Blocked",
  chip_static: "Fixed {ip}",
  chip_limit: "Speed limited",
  online_for: "online {x}",
  offline: "offline",
  total_line: "Total ↓ {rx}  ↑ {tx}",
  act_block: "Block",
  act_unblock: "Unblock",
  act_static: "Fixed IP…",
  act_forget: "Forget",
  act_details: "Details",
  act_copy_mac: "Copy MAC",
  block_title: "Block {name}?",
  block_text: "Until you unblock it, this device (by MAC address) can no longer connect to this router.",
  unblocked_toast: "{name} is unblocked",
  blocked_toast: "{name} is blocked",
  forget_title: "Forget {name}?",
  forget_text: "Removes it from the router's own device list. It shows up again when it reconnects.",
  forget_all: "Forget offline devices ({n})",
  forget_all_title: "Forget {n} offline devices?",
  forget_all_text:
    "Removes them from the router's own device list, with their names and traffic counters. They show up again when they reconnect.",
  forgot_n: "Forgot {n} devices",
  clients_empty: "No device matches.",
  clients_none: "The router lists no device yet.",
  history_title: "Speed over the last minutes",
  history_empty: "Not enough samples yet.",
  static_title: "Fixed IP for {name}",
  static_hint:
    "The router will always give this device this address (a DHCP reservation). This router's API cannot remove it again from here.",
  ip_address: "IP address",
  device_name: "Name",
  static_saved: "Fixed IP {ip} is set",
  already_static: "Already has a fixed IP ({ip})",

  // Wi-Fi
  band_2g: "2.4 GHz",
  band_5g: "5 GHz",
  guest: "Guest",
  hidden: "Hidden",
  on_air: "Broadcasting",
  radio_off: "Off",
  enabled: "Enabled",
  ssid: "Network name (SSID)",
  password: "Password",
  password_ph: "New password (leave empty to keep)",
  show_password: "Show current password",
  wifi_warn: "Devices on this network are disconnected and must reconnect.",
  wifi_confirm_title: "Change the Wi-Fi “{ssid}”?",
  wifi_saved: "Saved",
  wifi_on_toast: "“{ssid}” is on",
  wifi_off_toast: "“{ssid}” is off",
  wifi_enc: "Encryption",
  wifi_channel: "Channel",
  channel_auto: "auto",
  wifi_empty: "The router reports no Wi-Fi interface.",

  // access
  blocked_title: "Blocked devices",
  blocked_empty: "No device is blocked.",
  unknown_device: "Unknown device",
  block_by_mac: "Block by MAC address",
  mac_ph: "AA:BB:CC:DD:EE:FF",
  pick_client: "Pick a known device…",
  mode_not_black:
    "The router is in allow-list mode, where the list means the opposite (only listed devices may connect). Blocking is switched off here to avoid mistakes.",
  allowed_title: "Allowed devices",
  static_list_title: "Fixed IP addresses",
  static_empty: "No fixed IP yet.",
  static_add_title: "Add a fixed IP",
  static_remove_why: "Why can't I remove one?",
  static_remove_text:
    "On this firmware the router's remove call (lan.remove_static_bind) always answers “Invalid params”, so it cannot be done through the API. To remove one, log in to the router over SSH, find its number with `uci show dhcp`, then run `uci delete dhcp.@host[N]`, `uci commit dhcp` and `/etc/init.d/dnsmasq restart`.",

  // activity
  activity_hint:
    "What changed on the router and who did it: this panel, a service call (scripts, automations, AI agents) or an entity.",
  activity_empty: "Nothing yet.",
  all_channels: "All sources",
  channel_panel: "Panel",
  channel_service: "Service",
  channel_entity: "Entity",
  log_wifi_on: "Wi-Fi “{ssid}” ({iface}) turned on",
  log_wifi_off: "Wi-Fi “{ssid}” ({iface}) turned off",
  log_wifi_ssid: "Wi-Fi {iface}: renamed to “{ssid}”",
  log_wifi_key: "Wi-Fi “{ssid}” ({iface}): password changed",
  log_wifi_failed: "Wi-Fi {iface}: {error}",
  log_blocked: "Blocked {name} ({mac})",
  log_unblocked: "Unblocked {name} ({mac})",
  log_block_failed: "Could not change the block of {mac}: {error}",
  log_static_ip_added: "Reserved {ip} for {name} ({mac})",
  log_static_ip_failed: "Could not reserve {ip} for {mac}: {error}",
  log_client_forgotten: "Forgot the offline device {name} ({mac})",
  log_forget_failed: "Could not forget {mac}: {error}",
  log_rebooted: "Rebooted {router}",
  log_reboot_failed: "Could not reboot {router}: {error}",

  // errors (ActionError codes)
  err_invalid_mac: "That is not a valid MAC address.",
  err_invalid_ip: "That is not a valid IPv4 address.",
  err_bad_ssid: "The network name must be 1–32 bytes (a Chinese character takes 3).",
  err_bad_key: "The Wi-Fi password must be 8–63 characters.",
  err_bad_name: "The name cannot be empty.",
  err_no_such_wifi: "The router has no such Wi-Fi interface.",
  err_not_router_mode: "Only available in router mode.",
  err_not_blacklist_mode: "The router is in allow-list mode, so blocking would mean the opposite.",
  err_ip_outside_lan:
    "That address cannot be used: it must be inside the router's LAN range and not the network, broadcast or router address.",
  err_mac_already_bound:
    "That device already has a fixed IP, and this router's API cannot remove the old one, so it is not added twice.",
  err_ip_already_bound: "That address is already given to another device.",
  err_client_online: "Only offline devices can be forgotten.",
  err_api_error: "The router reported an error",
  err_not_loaded: "That router is not loaded.",
  err_failed: "The change failed",
};

export type Key = keyof typeof en;

const zh: Record<Key, string> = {
  title: "WOOW GL.iNet",
  tab_overview: "總覽",
  tab_clients: "裝置",
  tab_wifi: "WiFi",
  tab_access: "存取控制",
  tab_activity: "活動",
  loading: "載入中…",
  no_routers: "還沒有路由器。到「設定 › 裝置與服務 › WOOW GL.iNet」新增。",
  error: "錯誤：{msg}",
  cancel: "取消",
  confirm: "確定",
  save: "儲存",
  saving: "儲存中…",
  add: "新增",
  refresh: "重新整理",
  copy: "複製",
  copied: "已複製",
  show: "顯示",
  hide: "隱藏",
  just_now: "剛剛",
  s_ago: "{n} 秒前",
  m_ago: "{n} 分鐘前",
  h_ago: "{n} 小時前",
  d_ago: "{n} 天前",
  updated: "{x}更新",
  router_pick: "路由器",

  unreachable: "路由器沒有回應，顯示的是最後一次讀到的資料。",
  mode_router: "路由器模式",
  mode_ap: "AP 模式",
  mode_wds: "WDS 模式",
  mode_relay: "中繼模式",
  mode_mesh: "Mesh 模式",
  mode_passthrough: "透傳模式",
  mode_other: "{mode} 模式",
  mode_note:
    "這個模式下路由器是橋接在別的網路上：沒有自己的 NAT 和 DHCP，所以裝置清單、封鎖、固定 IP 和網際網路流量在這裡都不適用。WiFi 和系統控制還是可以用。",
  fact_model: "型號",
  fact_firmware: "韌體",
  fact_address: "連線位址",
  fact_lan: "LAN 位址",
  fact_uptime: "已運行",
  fact_load: "負載（1／5／15 分鐘）",
  fact_memory: "記憶體",
  fact_storage: "儲存空間",
  fact_internet: "網際網路",
  fact_devices: "裝置",
  wan_online: "已連線",
  wan_offline: "沒有上行連線",
  link_wan: "WAN 孔",
  link_wwan: "WiFi 上行",
  link_tethering: "USB 網路共享",
  link_modem: "行動網路",
  devices_online: "{n} 台在線",
  devices_split: "{wired} 有線 · {wireless} 無線",
  used_of: "{used}／{total}",
  traffic_title: "網際網路流量",
  download: "下載",
  upload: "上傳",
  peak: "尖峰 {x}",
  range_5m: "5 分鐘",
  range_30m: "30 分鐘",
  range_all: "全部",
  chart_empty: "收集資料中…",
  busiest_title: "最忙碌的裝置",
  busiest_empty: "目前沒有流量。",
  reboot: "重新開機",
  reboot_title: "要重新開機「{router}」嗎？",
  reboot_text: "網路會中斷約 1～2 分鐘，所有裝置都要重新連線。",
  rebooting: "已送出重新開機指令，約 1～2 分鐘後恢復。",

  search_ph: "搜尋名稱、IP 或 MAC",
  f_all: "全部",
  f_online: "在線",
  f_offline: "離線",
  f_blocked: "已封鎖",
  sort_speed: "排序：目前流量",
  sort_total: "排序：累計流量",
  sort_name: "排序：名稱",
  sort_ip: "排序：IP 位址",
  unnamed: "未命名裝置",
  iface_cable: "有線",
  chip_blocked: "已封鎖",
  chip_static: "固定 {ip}",
  chip_limit: "已限速",
  online_for: "在線 {x}",
  offline: "離線",
  total_line: "累計 ↓ {rx}  ↑ {tx}",
  act_block: "封鎖",
  act_unblock: "解除封鎖",
  act_static: "固定 IP…",
  act_forget: "移除記錄",
  act_details: "詳細",
  act_copy_mac: "複製 MAC",
  block_title: "要封鎖「{name}」嗎？",
  block_text: "解除封鎖之前，這台裝置（依 MAC 位址）沒辦法再連上這台路由器。",
  unblocked_toast: "已解除封鎖 {name}",
  blocked_toast: "已封鎖 {name}",
  forget_title: "要移除「{name}」的記錄嗎？",
  forget_text: "會從路由器自己的裝置清單拿掉，它下次連線時又會出現。",
  forget_all: "清除離線裝置（{n}）",
  forget_all_title: "要清除 {n} 台離線裝置嗎？",
  forget_all_text: "會從路由器自己的裝置清單拿掉（連同名稱和流量計數），它們下次連線時又會出現。",
  forgot_n: "已清除 {n} 台",
  clients_empty: "沒有符合的裝置。",
  clients_none: "路由器上還沒有任何裝置記錄。",
  history_title: "最近的流量",
  history_empty: "資料還不夠。",
  static_title: "為「{name}」設定固定 IP",
  static_hint: "路由器之後都會把這個位址給這台裝置（DHCP 固定租約）。注意：這台路由器的 API 沒辦法從這裡再移除它。",
  ip_address: "IP 位址",
  device_name: "名稱",
  static_saved: "已設定固定 IP {ip}",
  already_static: "已經有固定 IP（{ip}）",

  band_2g: "2.4 GHz",
  band_5g: "5 GHz",
  guest: "訪客",
  hidden: "隱藏",
  on_air: "廣播中",
  radio_off: "關閉",
  enabled: "啟用",
  ssid: "網路名稱（SSID）",
  password: "密碼",
  password_ph: "新密碼（不改就留空）",
  show_password: "顯示目前密碼",
  wifi_warn: "這個網路上的裝置會被中斷，要重新連線。",
  wifi_confirm_title: "要修改 WiFi「{ssid}」嗎？",
  wifi_saved: "已儲存",
  wifi_on_toast: "「{ssid}」已開啟",
  wifi_off_toast: "「{ssid}」已關閉",
  wifi_enc: "加密",
  wifi_channel: "頻道",
  channel_auto: "自動",
  wifi_empty: "路由器沒有回報任何 WiFi 介面。",

  blocked_title: "已封鎖的裝置",
  blocked_empty: "沒有封鎖任何裝置。",
  unknown_device: "不明裝置",
  block_by_mac: "用 MAC 位址封鎖",
  mac_ph: "AA:BB:CC:DD:EE:FF",
  pick_client: "選一台已知的裝置…",
  mode_not_black: "路由器目前是白名單模式（只有清單內的裝置能連線），封鎖的意義剛好相反，這裡先停用以免誤操作。",
  allowed_title: "允許的裝置",
  static_list_title: "固定 IP",
  static_empty: "還沒有固定 IP。",
  static_add_title: "新增固定 IP",
  static_remove_why: "為什麼不能移除？",
  static_remove_text:
    "這個韌體上，路由器的移除指令（lan.remove_static_bind）不管怎麼傳都回「Invalid params」，所以沒辦法透過 API 做。要移除請用 SSH 登入路由器，先用 `uci show dhcp` 找出它的編號，再執行 `uci delete dhcp.@host[N]`、`uci commit dhcp` 和 `/etc/init.d/dnsmasq restart`。",

  activity_hint: "路由器上改了什麼、是誰改的：這個面板、服務呼叫（腳本、自動化、AI 代理）或實體。",
  activity_empty: "目前沒有紀錄。",
  all_channels: "全部來源",
  channel_panel: "面板",
  channel_service: "服務",
  channel_entity: "實體",
  log_wifi_on: "WiFi「{ssid}」（{iface}）已開啟",
  log_wifi_off: "WiFi「{ssid}」（{iface}）已關閉",
  log_wifi_ssid: "WiFi {iface}：名稱改為「{ssid}」",
  log_wifi_key: "WiFi「{ssid}」（{iface}）：密碼已更改",
  log_wifi_failed: "WiFi {iface}：{error}",
  log_blocked: "已封鎖 {name}（{mac}）",
  log_unblocked: "已解除封鎖 {name}（{mac}）",
  log_block_failed: "沒能改變 {mac} 的封鎖：{error}",
  log_static_ip_added: "已為 {name}（{mac}）固定 {ip}",
  log_static_ip_failed: "沒能為 {mac} 固定 {ip}：{error}",
  log_client_forgotten: "已移除離線裝置 {name}（{mac}）的記錄",
  log_forget_failed: "沒能移除 {mac} 的記錄：{error}",
  log_rebooted: "已重新開機 {router}",
  log_reboot_failed: "沒能重新開機 {router}：{error}",

  err_invalid_mac: "這不是有效的 MAC 位址。",
  err_invalid_ip: "這不是有效的 IPv4 位址。",
  err_bad_ssid: "網路名稱要 1～32 個位元組（一個中文字佔 3 個）。",
  err_bad_key: "WiFi 密碼要 8～63 個字元。",
  err_bad_name: "名稱不能是空的。",
  err_no_such_wifi: "路由器沒有這個 WiFi 介面。",
  err_not_router_mode: "只有路由器模式才能用。",
  err_not_blacklist_mode: "路由器目前是白名單模式，封鎖的意義會剛好相反。",
  err_ip_outside_lan: "這個位址不能用：要在路由器的 LAN 網段內，而且不是網段位址、廣播位址或路由器自己。",
  err_mac_already_bound: "這台裝置已經有固定 IP，而這台路由器的 API 沒辦法移除舊的，所以不重複新增。",
  err_ip_already_bound: "這個位址已經給了另一台裝置。",
  err_client_online: "只能移除離線裝置的記錄。",
  err_api_error: "路由器回報錯誤",
  err_not_loaded: "這台路由器沒有載入。",
  err_failed: "沒能完成修改",
};

export type Translate = (key: Key, vars?: Record<string, string | number>) => string;

export function makeTranslate(language: string): Translate {
  const dict: Record<Key, string> = language.toLowerCase().startsWith("zh") ? zh : en;
  return (key, vars) => {
    let text = dict[key] ?? en[key] ?? key;
    if (vars) {
      for (const [name, value] of Object.entries(vars)) {
        text = text.split(`{${name}}`).join(String(value));
      }
    }
    return text;
  };
}

export function isKey(key: string): key is Key {
  return key in en;
}

/** A rejected call in the user's language: the ActionError code's text, plus the router's own words for api_error. */
export function explain(err: unknown, t: Translate): string {
  const code = err && typeof err === "object" && "code" in err ? String((err as { code: unknown }).code) : "";
  const message = err && typeof err === "object" && "message" in err ? String((err as { message: unknown }).message) : String(err);
  const key = `err_${code}`;
  if (!isKey(key)) return t("error", { msg: message });
  return code === "api_error" || code === "failed" ? `${t(key)}: ${message}` : t(key);
}

export function ago(time: number, t: Translate): string {
  const seconds = Math.max(0, Date.now() / 1000 - time);
  if (seconds < 5) return t("just_now");
  if (seconds < 60) return t("s_ago", { n: Math.floor(seconds) });
  if (seconds < 3600) return t("m_ago", { n: Math.floor(seconds / 60) });
  if (seconds < 86400) return t("h_ago", { n: Math.floor(seconds / 3600) });
  return t("d_ago", { n: Math.floor(seconds / 86400) });
}

export function clock(time: number, withSeconds = true): string {
  const d = new Date(time * 1000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return withSeconds ? `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}` : `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const UNITS = ["B", "kB", "MB", "GB", "TB"];

/** Decimal prefixes, like Home Assistant's data-rate units: 1 kB = 1000 B. */
export function formatBytes(bytes: number): string {
  let value = Math.max(0, bytes);
  let unit = 0;
  while (value >= 1000 && unit < UNITS.length - 1) {
    value /= 1000;
    unit += 1;
  }
  const digits = unit === 0 || value >= 100 ? 0 : value >= 10 ? 1 : 2;
  return `${value.toFixed(digits)} ${UNITS[unit]}`;
}

export function formatRate(bytesPerSecond: number): string {
  return `${formatBytes(bytesPerSecond)}/s`;
}

/** 90061 -> "1d 1h", 3700 -> "1h 1m", 125 -> "2m". */
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d) return `${d}d ${h}h`;
  if (h) return `${h}h ${m}m`;
  return `${Math.max(m, 0)}m`;
}
