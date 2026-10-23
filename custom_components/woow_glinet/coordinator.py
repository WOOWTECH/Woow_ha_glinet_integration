"""DataUpdateCoordinator polling one GL.iNet router."""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .actions import GlinetActions
from .api import METHOD_NOT_FOUND, GlinetApiError, GlinetClient, GlinetInvalidAuth
from .const import DOMAIN, MODE_ROUTER, UPDATE_INTERVAL
from .device import router_device_info
from .history import TrafficHistory
from .sanitize import dicts, strings

_LOGGER = logging.getLogger(__name__)


def _wifi_bands(res: Any) -> list[dict[str, Any]]:
    """The bands, each with only the interfaces that are objects with a name (the platforms rely on it)."""
    return [
        {**band, "ifaces": [i for i in dicts(band.get("ifaces")) if isinstance(i.get("name"), str) and i["name"]]}
        for band in dicts(res)
    ]


def _with_mac(value: Any) -> list[dict[str, Any]]:
    """The client records that are objects with a MAC address in text form (everything keys off it)."""
    return [c for c in dicts(value) if isinstance(c.get("mac"), str) and c["mac"]]


@dataclass
class GlinetData:
    """One poll's worth of router state."""

    wan_speed: dict[str, Any] = field(default_factory=dict)
    clients: list[dict[str, Any]] = field(default_factory=list)
    wifi_bands: list[dict[str, Any]] = field(default_factory=list)
    static_binds: list[dict[str, Any]] = field(default_factory=list)
    blacklist_mode: str = "black"
    black_mac: list[str] = field(default_factory=list)
    white_mac: list[str] = field(default_factory=list)
    device_info: dict[str, Any] = field(default_factory=dict)
    mode: str = MODE_ROUTER
    system: dict[str, Any] = field(default_factory=dict)  # system.get_status: uptime, load, memory, WAN link ...


class GlinetCoordinator(DataUpdateCoordinator[GlinetData]):
    """Polls clients/wan-speed/wifi/static-binds/blacklist on one interval."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: GlinetClient, host: str
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{host}",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.device_info: dict[str, Any] = {}
        self.mode: str = MODE_ROUTER
        self.actions = GlinetActions(self)
        self.history = TrafficHistory()
        self.clock_skew = 0.0  # this host's clock minus the router's, to show "online since" in our time
        # "object.method" names this firmware does not have; the feature behind each one is switched off
        # instead of the whole integration failing (models and firmware versions differ).
        self.unsupported: set[str] = set()
        self.auth_failed = False  # the router rejected the credentials: stop polling until they are fixed
        self._setup_mode: str | None = None  # the mode the entities were built for
        self._reload_scheduled = False
        self.router_device_id: str | None = None  # the router's device registry id; client devices hang under it

    async def _fetch(self, obj: str, method: str, default: Any) -> Any:
        """One router call; a method the firmware does not have gives `default` (once logged), other errors raise."""
        key = f"{obj}.{method}"
        try:
            result = await self.client.call(obj, method)
        except GlinetApiError as err:
            if err.code == METHOD_NOT_FOUND:
                if key not in self.unsupported:
                    self.unsupported.add(key)
                    _LOGGER.info("這台路由器的韌體沒有 %s，用到它的功能先停用", key)
                return default
            raise
        self.unsupported.discard(key)
        if result is None or (isinstance(default, dict) and not isinstance(result, dict)):
            # Lua serialises an empty table as [], so "nothing" can arrive as a list
            return default
        return result

    def _credentials_rejected(self) -> None:
        """Stop polling and ask for new credentials, instead of hammering the router with a wrong password."""
        self.auth_failed = True
        if self.config_entry is not None:
            self.config_entry.async_start_reauth(self.hass)

    async def _async_fetch_device_info(self) -> None:
        if self.device_info:
            return
        try:
            self.device_info = await self._fetch("system", "get_info", {})
        except GlinetApiError as err:
            if isinstance(err, GlinetInvalidAuth):
                raise
            _LOGGER.debug("讀取 system.get_info 失敗（不影響其他感測器）：%s", err)

    async def _async_check_mode(self) -> None:
        """Read the network mode on every poll: a switch to AP / repeater / ... in the router's own UI reloads the entry,
        so the entities follow (per-device entities only make sense in router mode)."""
        result = await self._fetch("netmode", "get_mode", {})
        self.mode = result.get("mode", MODE_ROUTER)
        if self._setup_mode is None:
            self._setup_mode = self.mode
        elif self.mode != self._setup_mode and not self._reload_scheduled and self.config_entry is not None:
            _LOGGER.info("路由器的上網模式從 %s 變成 %s，重新載入整合", self._setup_mode, self.mode)
            self._reload_scheduled = True
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

    async def _async_update_data(self) -> GlinetData:
        try:
            data = await self._async_poll()
        except GlinetInvalidAuth as err:
            self.auth_failed = True  # Home Assistant starts the re-authentication flow and stops polling
            raise ConfigEntryAuthFailed(f"路由器拒絕了帳號或密碼：{err}") from err
        except GlinetApiError as err:
            raise UpdateFailed(f"跟路由器溝通失敗：{err}") from err
        self.auth_failed = False
        return data

    async def _async_poll(self) -> GlinetData:
        await self._async_fetch_device_info()
        await self._async_check_mode()

        wan_speed = await self._fetch("clients", "get_wan_speed", {})
        clients_res = await self._fetch("clients", "get_list", {})
        wifi_res = await self._fetch("wifi", "get_config", {})
        static_res = await self._fetch("lan", "get_static_bind_list", {})
        bwl_res = await self._fetch("black_white_list", "get_config", {})
        # 只給面板用（運行時間、負載、記憶體、WAN 連線狀態），讀不到不影響其他功能。
        try:
            system = await self._fetch("system", "get_status", {})
        except GlinetInvalidAuth:
            raise
        except GlinetApiError as err:
            _LOGGER.debug("讀取 system.get_status 失敗（不影響其他感測器）：%s", err)
            system = {}
        if "system" in system and not isinstance(system["system"], dict):  # Lua serialises an empty table as []
            system = {**system, "system": {}}
        try:
            skew = time.time() - float(system["system"]["timestamp"])
            if math.isfinite(skew):
                self.clock_skew = skew
        except (KeyError, TypeError, ValueError):
            pass  # no usable clock: "online since" falls back to the last skew

        clients = _with_mac(clients_res.get("clients"))
        if self.mode == MODE_ROUTER:
            # 非 router 模式下 clients.get_list 看到的是整個共用網段的所有裝置
            # (不是只有接這台裝置的),不要幫這些裝置建 HA device,會灌一堆跟這台
            # 裝置無關的「幽靈裝置」進裝置登錄表。
            self._async_sync_client_devices(clients)
            self.history.add(time.time(), wan_speed, clients)

        return GlinetData(
            wan_speed=wan_speed,
            clients=clients,
            wifi_bands=_wifi_bands(wifi_res.get("res")),
            static_binds=dicts(static_res.get("static_bind_list")),
            blacklist_mode=bwl_res.get("mode", "black"),
            black_mac=strings(bwl_res.get("black_mac")),
            white_mac=strings(bwl_res.get("white_mac")),
            device_info=self.device_info,
            mode=self.mode,
            system=system,
        )

    async def async_live_poll(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Just the traffic numbers, for the panel while a browser has it open (entities keep their own pace)."""
        try:
            wan_speed = await self._fetch("clients", "get_wan_speed", {})
            clients = _with_mac((await self._fetch("clients", "get_list", {})).get("clients"))
        except GlinetInvalidAuth:
            self._credentials_rejected()
            raise
        self.history.add(time.time(), wan_speed, clients)
        return wan_speed, clients

    def _async_sync_client_devices(self, clients: list[dict[str, Any]]) -> None:
        """Keep each client sub-device's registered name up to date.

        Done explicitly (rather than relying only on each entity's own
        DeviceInfo) because on first creation the device ended up named
        after the raw MAC instead of the client's alias - entities race
        to register the same device via a deprecated `via_device` path,
        and whichever wins isn't guaranteed to carry the friendliest name.
        This call is idempotent and authoritative, and self-heals if the
        router-side device name changes later.
        """
        registry = dr.async_get(self.hass)
        entry = self.config_entry
        if self.router_device_id is None:
            # create the router's own device first, so the clients can be attached to it from the start
            self.router_device_id = registry.async_get_or_create(
                config_entry_id=entry.entry_id, **router_device_info(entry.entry_id, self.device_info)
            ).id

        for client in clients:
            mac = client.get("mac")
            if not mac:
                continue
            name = client.get("name") or client.get("alias") or mac
            registry.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                identifiers={(DOMAIN, f"client_{mac}")},
                connections={(dr.CONNECTION_NETWORK_MAC, mac)},
                name=name,
                via_device_id=self.router_device_id,
            )
