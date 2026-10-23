"""What the panel sees: a snapshot of every router, then a live feed (router updates, traffic, activity)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .activity import ActivityLog
from .api import GlinetApiError
from .const import DOMAIN, LIVE_INTERVAL, MODE_ROUTER

if TYPE_CHECKING:
    from .coordinator import GlinetCoordinator

_LOGGER = logging.getLogger(__name__)


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _static_by_mac(binds: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(b.get("mac", "")).upper(): b for b in binds}


def client_record(client: dict[str, Any], statics: dict[str, dict[str, Any]], skew: float) -> dict[str, Any]:
    """One client as the panel wants it (numbers as numbers, "online since" in this host's clock)."""
    mac = str(client.get("mac", ""))
    online = bool(client.get("online"))
    since = client.get("online_time")
    return {
        "mac": mac,
        "ip": client.get("ip") or "",
        "name": client.get("name") or "",
        "alias": client.get("alias") or "",
        "online": online,
        "blocked": bool(client.get("blocked")),
        "iface": client.get("iface") or "",
        "rx": _int(client.get("rx")),
        "tx": _int(client.get("tx")),
        "total_rx": _int(client.get("total_rx")),
        "total_tx": _int(client.get("total_tx")),
        "limit_rx": _int(client.get("limit_rx")),
        "limit_tx": _int(client.get("limit_tx")),
        "since": float(since) + skew if online and since else None,
        "static_ip": (statics.get(mac.upper()) or {}).get("ip"),
    }


def router_snapshot(coordinator: GlinetCoordinator, with_history: bool = False) -> dict[str, Any]:
    """Everything the panel shows about one router. Wi-Fi passwords are left out (fetched on demand)."""
    entry = coordinator.config_entry
    data = coordinator.data
    info = data.device_info or {}
    board = info.get("board_info", {})
    status = data.system or {}
    system = status.get("system", {})
    wifi_up = {w.get("name"): bool(w.get("up")) for w in status.get("wifi", [])}
    online_links = [n.get("interface") for n in status.get("network", []) if n.get("online")]
    stations = (status.get("client") or [{}])[0]
    statics = _static_by_mac(data.static_binds)
    snapshot: dict[str, Any] = {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "host": entry.data.get(CONF_HOST),
        "available": coordinator.last_update_success,
        "fetched_at": time.time(),
        "mode": data.mode,
        "model": board.get("model") or info.get("model") or info.get("vendor"),
        "hostname": board.get("hostname"),
        "firmware": info.get("firmware_version"),
        "mac": info.get("mac"),
        "lan_ip": system.get("lan_ip"),
        "uptime": system.get("uptime"),
        "load": system.get("load_average"),
        "memory": {
            "total": system.get("memory_total"),
            "free": system.get("memory_free"),
            "cache": system.get("memory_buff_cache"),
        } if "memory_total" in system else None,
        "flash": {"total": system.get("flash_total"), "free": system.get("flash_free")} if "flash_total" in system else None,
        "wan": {
            "online": bool(online_links),
            "links": online_links,
            "rx": _int(data.wan_speed.get("speed_rx")),
            "tx": _int(data.wan_speed.get("speed_tx")),
        },
        "stations": {"wireless": stations.get("wireless_total"), "cable": stations.get("cable_total")},
        "wifi": [
            {
                "band": band.get("band"),
                "channel": band.get("channel"),
                "hwmode": band.get("hwmode"),
                "htmode": band.get("htmode"),
                "ifaces": [
                    {
                        "name": iface.get("name"),
                        "ssid": iface.get("ssid"),
                        "enabled": bool(iface.get("enabled")),
                        "up": wifi_up.get(iface.get("name")),
                        "guest": bool(iface.get("guest")),
                        "hidden": bool(iface.get("hidden")),
                        "encryption": iface.get("encryption"),
                        "bssid": iface.get("bssid"),
                    }
                    for iface in band.get("ifaces", [])
                ],
            }
            for band in data.wifi_bands
        ],
        "clients": [client_record(c, statics, coordinator.clock_skew) for c in data.clients if c.get("mac")],
        "static_binds": [{"mac": b.get("mac"), "ip": b.get("ip"), "name": b.get("name")} for b in data.static_binds],
        "blocklist": {"mode": data.blacklist_mode, "black": data.black_mac, "white": data.white_mac},
        # lan.remove_static_bind is broken on the firmware this was written against (always "Invalid params").
        "features": {"static_ip_remove": False},
    }
    if with_history:
        snapshot["history"] = {"wan": coordinator.history.wan_series()}
    return snapshot


class PanelFeed:
    """Fans router updates, fast traffic samples and activity out to the panels that are open."""

    def __init__(self, hass: HomeAssistant, activity: ActivityLog) -> None:
        self.hass = hass
        self.activity = activity
        self._subs: list[Callable[[dict[str, Any]], None]] = []
        self._stop_live: CALLBACK_TYPE | None = None
        self._stop_activity: CALLBACK_TYPE | None = None
        self._busy: set[str] = set()

    def coordinators(self) -> list[GlinetCoordinator]:
        return [
            entry.runtime_data.coordinator
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.state is ConfigEntryState.LOADED and entry.runtime_data.coordinator.data is not None
        ]

    def snapshot(self) -> dict[str, Any]:
        return {
            "routers": [router_snapshot(c, with_history=True) for c in self.coordinators()],
            "activity": self.activity.recent(),
            "live_interval": LIVE_INTERVAL,
        }

    @callback
    def subscribe(self, cb: Callable[[dict[str, Any]], None]) -> CALLBACK_TYPE:
        self._subs.append(cb)
        if len(self._subs) == 1:  # the first panel switches the fast traffic poll on
            self._stop_live = async_track_time_interval(
                self.hass, self._tick, timedelta(seconds=LIVE_INTERVAL), cancel_on_shutdown=True
            )
            self._stop_activity = self.activity.subscribe(lambda payload: self._push("activity", payload))

        @callback
        def unsubscribe() -> None:
            if cb in self._subs:
                self._subs.remove(cb)
            if not self._subs:
                if self._stop_live is not None:
                    self._stop_live()
                    self._stop_live = None
                if self._stop_activity is not None:
                    self._stop_activity()
                    self._stop_activity = None

        return unsubscribe

    @callback
    def _push(self, kind: str, payload: dict[str, Any]) -> None:
        event = {"kind": kind, **payload}
        for cb in list(self._subs):
            cb(event)

    @callback
    def router_updated(self, coordinator: GlinetCoordinator) -> None:
        if self._subs and coordinator.data is not None:
            self._push("router", {"router": router_snapshot(coordinator)})

    @callback
    def router_removed(self, entry_id: str) -> None:
        self._push("router_removed", {"entry_id": entry_id})

    async def _tick(self, _now: Any) -> None:
        routers = [c for c in self.coordinators() if c.data.mode == MODE_ROUTER]
        await asyncio.gather(*(self._live(c) for c in routers))

    async def _live(self, coordinator: GlinetCoordinator) -> None:
        entry_id = coordinator.config_entry.entry_id
        if entry_id in self._busy:  # the router is slow: do not pile polls up
            return
        self._busy.add(entry_id)
        try:
            wan, clients = await coordinator.async_live_poll()
        except GlinetApiError as err:
            _LOGGER.debug("live traffic poll of %s failed: %s", coordinator.config_entry.title, err)
            return
        finally:
            self._busy.discard(entry_id)
        statics = _static_by_mac(coordinator.data.static_binds)
        self._push("live", {
            "entry_id": entry_id,
            "t": time.time(),
            "wan": {"rx": _int(wan.get("speed_rx")), "tx": _int(wan.get("speed_tx"))},
            "clients": [client_record(c, statics, coordinator.clock_skew) for c in clients if c.get("mac")],
        })
