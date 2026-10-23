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
- **管理面板**：側邊欄「WOOW GL.iNet」專屬頁面（跟 WOOW 串口、WOOW CAN 同一套做法），見下一節

## 管理面板

安裝後側邊欄會多一個「**WOOW GL.iNet**」（只有管理員看得到），所有功能都能在這一頁完成，手機版面也能用，
隨 Home Assistant 的語言顯示繁體中文或英文、跟著淺色／深色主題：

| 分頁 | 內容 |
|---|---|
| **總覽** | 路由器狀態（型號、韌體、運行時間、負載、記憶體、儲存空間、網際網路連線）、**即時流量圖**（下載／上傳，5 分鐘／30 分鐘／全部，滑過去看數值）、目前最忙碌的裝置、重新整理、重新開機 |
| **裝置** | 路由器認得的每個裝置：在線／離線、IP、MAC、有線或 WiFi、**即時上傳下載速度**、累計流量、連線多久；可搜尋、篩選、排序；每台可**封鎖／解除封鎖**、**設定固定 IP**、移除離線裝置的記錄（可一次清除全部離線裝置）、展開看最近的流量圖 |
| **WiFi** | 每個介面（主要／訪客、2.4／5 GHz）：開關、改名稱（SSID）、改密碼；密碼不會預先載入，按「顯示目前密碼」才向路由器讀 |
| **存取控制** | MAC 封鎖清單（可用 MAC 位址直接封鎖，也能從已知裝置挑）、固定 IP 清單與新增 |
| **活動** | 誰改了什麼：面板、服務呼叫（腳本、自動化、AI 代理）或實體，哪個使用者、成功或失敗，即時更新，重啟後還在 |

- **即時**：面板開著的時候，流量每 5 秒更新一次（只在有人開著面板時才多問路由器，實體仍是每 30 秒）；其他資料
  一有變動就推送，不用手動重新整理。
- **自動判斷模式**：路由器不是 router 模式（AP、中繼…）時，面板只留總覽、WiFi、活動，並說明原因——因為
  那時候路由器是橋接在別的網路上，裝置清單是整個網段、封鎖和固定 IP 都沒有意義。
- **多台路由器**：有多台時面板上方會多一個選單切換。
- **安全**：面板和它的 WebSocket 指令只有管理員能用；修改主要 WiFi（會踢掉所有連線裝置）、封鎖裝置、重新開機
  都會先問一次。
- 實體、服務和面板走同一套寫入程式：同樣的檢查（MAC／IP 格式、IP 在不在 LAN 網段、有沒有重複綁定、WiFi 名稱
  和密碼長度），同樣記進活動紀錄。

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

- **WiFi 密碼實體的狀態是明碼**：`text` 實體「WiFi … 密碼」的狀態就是目前的 WiFi 密碼，能看到實體狀態的
  Home Assistant 使用者都看得到，也會進歷史資料庫。不需要的話，到「設定 → 裝置與服務 → 實體」把這些
  「…密碼」實體停用即可（面板的 WiFi 分頁不依賴它們）。
- WiFi 的設定套用要約 8～9 秒（路由器重新載入無線網路），面板會顯示處理中。
- 「重新開機」的指令已經接好，但還沒有在實機上按過（會讓整個網路中斷），其餘寫入都在實機測過。
- **固定 IP 的移除（`lan.remove_static_bind`）在目前測過的韌體版本上透過 API 無法正常運作**（不管傳
  什麼參數都回 `Invalid params`）。`remove_static_ip` 服務會直接回報這個限制並附上手動用 SSH + uci
  處理的指令，不會嘗試一定會失敗的呼叫。新增固定 IP 不受影響，正常可用。
- 「這個裝置連到哪個外部 IP、各花多少流量」這種更細的流量分析沒有做——官方 API 只到「整台路由器」跟
  「每個裝置」兩個層級，更細的要另外走 SSH 讀 Linux 的 connection tracking，目前沒有做成 HA 功能。
- 只在 GL-SFT1200（Opal）上實測過；其他韌體 4.x 機型的 object/method 清單理論上共通，但未必每個方法
  都存在，遇到 `Method not found` 是正常的（代表這個機型/韌體沒有這個功能）。

## 開發

面板是 Lit + TypeScript，原始碼在 `frontend/`，建置好的單一檔案放在
`custom_components/woow_glinet/frontend/woow-glinet-panel.js`（已提交，安裝時不需要建置）：

```sh
cd frontend
npm ci
npm run build      # 輸出到 custom_components/woow_glinet/frontend/
npm run typecheck
```

## 授權

MIT
