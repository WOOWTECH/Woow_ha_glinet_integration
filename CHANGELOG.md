# Changelog

## 0.1.0 — 2026-10-22

- 第一版：GL.iNet `/rpc` JSON-RPC API 的 Home Assistant 整合
- sensor：WAN 上/下載速度、連線裝置數、韌體版本、每個裝置的上/下載速度
- device_tracker：每個裝置的連線狀態
- switch：每個 WiFi 頻段開關、每個裝置的封鎖開關
- text：WiFi SSID／密碼直接編輯
- button：重新開機
- services：`add_static_ip`／`remove_static_ip`
- 已知限制：`remove_static_ip` 在目前測過的韌體上無法透過 API 運作，服務會直接回報並附上手動處理方式
