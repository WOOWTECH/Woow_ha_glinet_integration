# WOOW GL.iNet

Bring a GL.iNet router (firmware 4.x) into Home Assistant: traffic monitoring, WiFi control, device
blocking, static IP leases — all through the router's official `/rpc` JSON-RPC API, not SSH/uci.

## Features

- **WAN traffic**: live upload/download rate for the whole router
- **Per-device traffic**: live upload/download rate for every LAN/WiFi client, auto-discovered as a
  sub-device under the router
- **Presence**: whether each device is currently connected (`device_tracker`)
- **WiFi switches**: enable/disable each band (including guest) independently
- **WiFi SSID/password**: edit directly from the device page, applies immediately
- **Device blocking**: MAC-level block/allow for LAN/WiFi access
- **Static IP**: `add_static_ip` / `remove_static_ip` services for DHCP static leases
- **Reboot**

## Requirements

- A GL.iNet router on firmware 4.x (tested against a GL-SFT1200/Opal)
- Home Assistant needs a reachable path to the router: the default is the router's LAN address (e.g.
  `192.168.8.1`). If HA is on a different segment than the router's LAN side (e.g. behind the router's
  own NAT), configure the integration with whatever address HA can actually reach (typically the
  router's WAN IP), and if needed enable the router's WAN management whitelist for HA's IP over HTTPS.

## Installation

Add as a custom repository in HACS, or manually copy `custom_components/woow_glinet` into HA's
`config/custom_components/` and restart Home Assistant.

## Configuration

Settings → Devices & Services → Add Integration → search "WOOW GL.iNet", then fill in host, username,
password, scheme (http/https) and whether to verify the SSL certificate (routers usually use a
self-signed cert, so this is normally off).

## Services

```yaml
service: woow_glinet.add_static_ip
data:
  device_id: <router device>
  mac: "AA:BB:CC:DD:EE:FF"
  ip: "192.168.8.50"
  name: "My phone"

service: woow_glinet.remove_static_ip
data:
  device_id: <router device>
  mac: "AA:BB:CC:DD:EE:FF"
```

## Known limitations

- **Removing a static IP lease (`lan.remove_static_bind`) does not work over the API on the firmware
  tested so far** (it returns `Invalid params` regardless of the parameters sent). The
  `remove_static_ip` service reports this limitation directly, with the manual SSH + uci command to use
  instead, rather than attempting a call that's known to fail. Adding a static IP is unaffected and
  works normally.
- Per-destination-IP traffic breakdown (which external IP a device talked to, and how much) is not
  implemented — the official API only exposes router-wide and per-device totals. That level of detail
  would require reading connection tracking over SSH, which isn't wired into this integration.
- Only tested against a GL-SFT1200 (Opal). Other firmware 4.x models should share the same object/method
  namespace, but not every method necessarily exists on every model — a `Method not found` error means
  that model/firmware doesn't support it.

## License

MIT
