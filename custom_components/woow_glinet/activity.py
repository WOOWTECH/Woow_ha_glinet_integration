"""Activity log: who changed what on a router (the panel, a service call, an entity), shown live in the panel."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
import time
from typing import Any

from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import ACTIVITY_KEEP, DOMAIN

SAVE_DELAY = 30

# One English line per message; the panel shows the same message translated (log_<msg>) with the entry's args.
MESSAGES = {
    "wifi_on": 'WiFi "{ssid}" ({iface}) turned on',
    "wifi_off": 'WiFi "{ssid}" ({iface}) turned off',
    "wifi_ssid": 'WiFi {iface}: name changed to "{ssid}"',
    "wifi_key": 'WiFi "{ssid}" ({iface}): password changed',
    "wifi_failed": "WiFi {iface}: {error}",
    "blocked": "Blocked {name} ({mac})",
    "unblocked": "Unblocked {name} ({mac})",
    "block_failed": "Could not change the block of {mac}: {error}",
    "static_ip_added": "Reserved {ip} for {name} ({mac})",
    "static_ip_failed": "Could not reserve {ip} for {mac}: {error}",
    "client_forgotten": "Forgot the offline device {name} ({mac})",
    "forget_failed": "Could not forget {mac}: {error}",
    "rebooted": "Rebooted {router}",
    "reboot_failed": "Could not reboot {router}: {error}",
}


class _Blank(dict):
    def __missing__(self, key: str) -> str:
        return "?"


def summarize(msg: str, args: dict[str, Any]) -> str:
    return MESSAGES.get(msg, msg).format_map(_Blank(args))


@dataclass
class Origin:
    """Where a change came from: a user in the panel, a service call (agents, scripts), an entity action."""

    channel: str  # "panel" | "service" | "entity"
    context: Context | None = None
    user: str | None = None  # the panel knows its user; the others are looked up from the context


@dataclass
class Activity:
    t: float
    channel: str
    action: str  # wifi, block, static_ip, forget, reboot
    summary: str  # one English line
    ok: bool = True
    user: str | None = None
    entry_id: str | None = None
    router: str = ""
    msg: str = ""  # MESSAGES key; the panel translates it
    args: dict[str, Any] = field(default_factory=dict)


class ActivityLog:
    """Ring buffer of activities, persisted, pushed live to the panel."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.activity")
        self.entries: list[Activity] = []
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self._users: dict[str, str | None] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        names = set(Activity.__dataclass_fields__)
        self.entries = [Activity(**{k: v for k, v in raw.items() if k in names}) for raw in data.get("entries", [])]

    def _data(self) -> dict[str, Any]:
        return {"entries": [asdict(e) for e in self.entries]}

    async def _user_name(self, origin: Origin) -> str | None:
        if origin.user is not None:
            return origin.user
        user_id = origin.context.user_id if origin.context is not None else None
        if not user_id:
            return None
        if user_id not in self._users:
            user = await self.hass.auth.async_get_user(user_id)
            self._users[user_id] = user.name if user is not None else None
        return self._users[user_id]

    async def async_record(self, origin: Origin, entry_id: str, router: str, action: str, msg: str,
                           args: dict[str, Any], ok: bool = True) -> None:
        args = {**args, "router": router}
        self.record(Activity(time.time(), origin.channel, action, summarize(msg, args), ok,
                             await self._user_name(origin), entry_id, router, msg, args))

    @callback
    def record(self, entry: Activity) -> None:
        self.entries.append(entry)
        del self.entries[:-ACTIVITY_KEEP]
        self._store.async_delay_save(self._data, SAVE_DELAY)
        for cb in list(self._listeners):
            cb({"entries": [asdict(entry)]})

    def recent(self, limit: int = 200) -> list[dict[str, Any]]:
        return [asdict(e) for e in reversed(self.entries[-limit:])]

    @callback
    def subscribe(self, cb: Callable[[dict[str, Any]], None]) -> CALLBACK_TYPE:
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb)
