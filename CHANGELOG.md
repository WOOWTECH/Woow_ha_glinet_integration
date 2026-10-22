# Changelog

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
