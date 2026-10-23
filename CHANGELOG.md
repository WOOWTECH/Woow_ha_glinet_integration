# Changelog

## 0.3.0 — 2026-10-23

- 新增側邊欄管理面板「WOOW GL.iNet」（總覽、裝置、WiFi、存取控制、活動），做法同 WOOW 串口／WOOW CAN：
  Lit + TypeScript 單一檔案、WebSocket 指令僅管理員、中英文、手機版面、淺色／深色主題
  - 總覽：路由器狀態、即時流量圖、最忙碌的裝置、重新整理、重新開機
  - 裝置：搜尋／篩選／排序、每台的即時速度與累計流量、封鎖、固定 IP、移除離線記錄、流量小圖
  - WiFi：開關、SSID、密碼（密碼按了才讀）；存取控制：封鎖清單、固定 IP 清單
  - 活動：面板、服務、實體做的修改（誰、成功或失敗），持久化、即時推送
  - 面板開著時流量每 5 秒更新；路由器不是 router 模式時自動只留總覽／WiFi／活動
- 新增 WOOW 品牌圖示（`brand/`），整合頁不再顯示「icon not available」
- 所有寫入（WiFi、封鎖、固定 IP、移除離線記錄、重新開機）統一走 `actions.py`：實體、服務、面板行為一致，
  同樣的檢查、同樣記進活動紀錄
- `add_static_ip` 現在會先檢查：MAC／IP 格式、IP 要在路由器的 LAN 網段內（且不是網段／廣播／路由器自己）、
  MAC 或 IP 不能已經被綁定（這台路由器的 API 沒辦法移除舊綁定，所以不重複新增）
- WiFi 名稱依位元組數檢查（上限 32，一個中文字佔 3）、密碼 8～63 字元
- 協調器多讀 `system.get_status`（運行時間、負載、記憶體、儲存空間、網際網路連線，面板用）
- API client 登入加鎖，多處同時呼叫時不會重複登入
- manifest 新增 `dependencies`：`frontend`、`http`、`panel_custom`、`websocket_api`
- 已知：WiFi 密碼文字實體的狀態是明碼（見 README「已知限制」）

## 0.2.0 — 2026-10-23

- 新增上網模式偵測（`netmode.get_mode`）：router 模式才會建立 WAN 流量 sensor、每個裝置的
  流量/封鎖/連線狀態 entity、固定 IP 服務；其他模式（AP 等）下，`clients.get_list` 看到的是
  整個共用網段的所有裝置而不是只有接這台裝置的，所以會跳過這些 entity，避免建出跟這台裝置
  無關的幽靈裝置
- 新增「模式」診斷 sensor，直接顯示目前的上網模式字串
- `add_static_ip`/`remove_static_ip` 服務在非 router 模式下會直接回報並拒絕執行

## 0.1.0 — 2026-10-22

- 第一版：GL.iNet `/rpc` JSON-RPC API 的 Home Assistant 整合
- sensor：WAN 上/下載速度、連線裝置數、韌體版本、每個裝置的上/下載速度
- device_tracker：每個裝置的連線狀態
- switch：每個 WiFi 頻段開關、每個裝置的封鎖開關
- text：WiFi SSID／密碼直接編輯
- button：重新開機
- services：`add_static_ip`／`remove_static_ip`
- 已知限制：`remove_static_ip` 在目前測過的韌體上無法透過 API 運作，服務會直接回報並附上手動處理方式
