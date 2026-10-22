# WOOW GL.iNet（WOOW GL.iNet 路由器）

把 GL.iNet 路由器（韌體 4.x）接進 Home Assistant：流量監控、WiFi 控制、裝置封鎖、固定 IP，全部走官方
`/rpc` JSON-RPC API，不是 SSH/uci。

## 功能

- **WAN 流量**：整台路由器對外的即時上傳/下載速率
- **每個裝置的流量**：區網/WiFi 上每個裝置各自的即時上傳/下載速率，裝置自動被發現、自動多一個對應的
  HA 裝置（掛在路由器底下）
- **連線狀態**：每個裝置目前有沒有連著（`device_tracker`）
- **WiFi 開關**：每個頻段（含 guest）獨立開關
- **WiFi SSID／密碼**：在裝置頁面直接編輯文字欄位，即時生效
- **裝置封鎖**：MAC 層級封鎖/允許某個裝置連上 LAN/WiFi
- **固定 IP**：`add_static_ip`／`remove_static_ip` 服務，設定 DHCP 靜態租約
- **重新開機**

## 需求

- GL.iNet 路由器，韌體 4.x（本整合已在 GL-SFT1200/Opal 上實測）
- Home Assistant 要能連到路由器：預設是路由器的 LAN 位址（例如 `192.168.8.1`）。如果 HA 跟路由器不在
  同一個網段（例如路由器自己的 NAT 把 LAN 側隔開），要讓 HA 連得到路由器某個可達的位址（通常是它的
  WAN IP），必要時到路由器後台開「WAN 端管理白名單」，只放 HA 的 IP，開 HTTPS

## 安裝

透過 HACS 加自訂儲存庫，或手動把 `custom_components/woow_glinet` 整個資料夾複製到 HA 的
`config/custom_components/` 下，重啟 Home Assistant。

## 設定

設定 → 裝置與服務 → 新增整合 → 搜尋「WOOW GL.iNet」，填：

| 欄位 | 說明 |
|---|---|
| 位址 | 路由器的 IP 或網域 |
| 帳號 | 通常是 `root` |
| 密碼 | 路由器後台密碼 |
| 通訊協定 | `http` 或 `https` |
| 驗證 SSL 憑證 | 路由器通常是自簽憑證，一般關掉 |

## 服務

```yaml
service: woow_glinet.add_static_ip
data:
  device_id: <路由器裝置>
  mac: "AA:BB:CC:DD:EE:FF"
  ip: "192.168.8.50"
  name: "我的手機"

service: woow_glinet.remove_static_ip
data:
  device_id: <路由器裝置>
  mac: "AA:BB:CC:DD:EE:FF"
```

## 已知限制

- **固定 IP 的移除（`lan.remove_static_bind`）在目前測過的韌體版本上透過 API 無法正常運作**（不管傳
  什麼參數都回 `Invalid params`）。`remove_static_ip` 服務會直接回報這個限制並附上手動用 SSH + uci
  處理的指令，不會嘗試一定會失敗的呼叫。新增固定 IP 不受影響，正常可用。
- 「這個裝置連到哪個外部 IP、各花多少流量」這種更細的流量分析沒有做——官方 API 只到「整台路由器」跟
  「每個裝置」兩個層級，更細的要另外走 SSH 讀 Linux 的 connection tracking，目前沒有做成 HA 功能。
- 只在 GL-SFT1200（Opal）上實測過；其他韌體 4.x 機型的 object/method 清單理論上共通，但未必每個方法
  都存在，遇到 `Method not found` 是正常的（代表這個機型/韌體沒有這個功能）。

## 授權

MIT
