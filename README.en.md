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
- **Admin panel**: a dedicated "WOOW GL.iNet" sidebar page, built the same way as WOOW Serial and WOOW CAN
  (see the next section)

## Admin panel

A **WOOW GL.iNet** entry appears in the sidebar (administrators only). Everything the integration can do
is available from that one page, which also works on a phone, follows Home Assistant's language
(Traditional Chinese or English) and its light/dark theme:

| Tab | What it has |
|---|---|
| **Overview** | Router status (model, firmware, uptime, load, memory, storage, internet link), a **live traffic chart** (download / upload; 5 min / 30 min / all; hover for values), the busiest devices right now, refresh and reboot |
| **Devices** | Every device the router knows: online/offline, IP, MAC, wired or Wi-Fi, **live up/down speed**, total traffic, time online; search, filter and sort; per device **block / unblock**, **fixed IP**, forget an offline device (or all offline ones at once), and an expandable recent-speed chart |
| **Wi-Fi** | Each interface (main / guest, 2.4 / 5 GHz): on/off switch, rename (SSID), change the password. The password is not preloaded: "Show current password" asks the router when you press it |
| **Access** | The MAC blocklist (block by MAC address or pick a known device) and the fixed-IP list with an add form |
| **Activity** | Who changed what: the panel, a service call (scripts, automations, AI agents) or an entity, which user, success or failure; live, and kept across restarts |

- **Live**: while the panel is open, traffic refreshes every 5 s (the router is only asked more often while
  someone is looking; entities keep their 30 s); everything else is pushed as it changes.
- **Mode aware**: when the router is not in router mode (AP, repeater ...) the panel keeps only Overview,
  Wi-Fi and Activity and says why: the router is then bridged onto another network, so the device list is the
  whole segment and blocking / fixed IPs make no sense.
- **Several routers**: a selector appears at the top.
- **Safety**: the panel and its websocket commands are for administrators only; changing a main Wi-Fi
  network (it disconnects everything on it), blocking a device and rebooting all ask first.
- **When the login breaks**: if the router password is changed the integration asks for re-authentication (it does not
  keep trying a wrong password until the router locks you out); if the router gets a new address or protocol use the
  integration's "Reconfigure" instead of deleting and re-adding it. A pasted browser address is fine in the host field.
- **Follows the router's mode**: switch the router to AP (or back) in its own UI and the integration notices on the
  next poll and reloads.
- **Missing firmware features do not stop the integration**: a feature the router answers "Method not found" to
  (a model without a blocklist, say) is simply switched off, and the panel hides the matching tab or section.
- **Download diagnostics** on the device page, with passwords, Wi-Fi keys, MACs, IPs and names redacted.
- Entities, services and the panel share one write path: the same checks (MAC / IP format, IP inside the
  LAN range, duplicate reservations, Wi-Fi name and password length) and the same activity log.

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

- **The Wi-Fi password entities do not show the password by default**: the `text` entities "Wi-Fi … password" are
  disabled by default and their state is "unknown" (write-only). An entity state is readable by every Home Assistant
  user who can see states and is stored in the history database. To show the passwords on a dashboard (a guest
  network QR card, say) turn on "Show Wi-Fi passwords as entity states" in the integration's options. The panel does
  not need it: an administrator presses "Show current password" and the password is read from the router then.
  When upgrading from 0.3.x, the old password states are still in the history database; `recorder.purge_entities`
  removes them.
- Every known device gets 4 entities (upload / download speed, presence, block switch) plus a device, including the
  offline ones the router remembers; a site with hundreds of devices gets a long entity list. Disable what you do not
  need under Settings → Devices & services → Entities (turn off "Enable newly added entities" in the integration's
  System options to keep newly discovered devices quiet). After the router is switched to AP mode the per-device entities stay in the
  registry as unavailable placeholders until you delete them.
- Applying a Wi-Fi change takes about 8–9 s (the router reloads its wireless networks); the panel shows it
  is working.
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

## Testing

- `pytest -q tests`: the backend suite (login handshake, error handling, the config flow including re-authentication,
  reconfigure and options, websocket permissions, panel registration, entities, diagnostics, translation checks).
- `cd frontend && npm test`: the panel's formatting helpers, and the contract between the panel's strings and the
  backend's error codes and activity messages.
- `cd frontend && npm run e2e`: browser tests of the panel against a fake Home Assistant (AP mode, several routers,
  allow-list mode, hundreds of devices, very long or hostile names, missing firmware features, a rejected login,
  recovery after a lost connection, an accessibility scan); see `frontend/e2e/README.md`.
- `tools/mock_router.py`: an in-memory GL.iNet router (same login handshake and response shapes, including what is
  broken on the real firmware) that you can steer while it runs (latency, hanging, garbage replies, missing methods,
  a changed password, reboots, hundreds of devices ...). Run
  `uv run --python 3.13 --with passlib python tools/mock_router.py --port 8780 --clients 60`, then add the
  integration with host `<this machine>:8780`, scheme http, user root, password mockpass.

## Development

The panel is Lit + TypeScript; the source is in `frontend/` and the built single file is committed as
`custom_components/woow_glinet/frontend/woow-glinet-panel.js` (no build is needed to install):

```sh
cd frontend
npm ci
npm run build      # writes to custom_components/woow_glinet/frontend/
npm run typecheck
```

## License

MIT
