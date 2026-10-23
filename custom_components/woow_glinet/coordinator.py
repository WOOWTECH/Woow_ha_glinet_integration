"""DataUpdateCoordinator polling one GL.iNet router."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .actions import GlinetActions
from .api import GlinetApiError, GlinetClient
from .const import DOMAIN, MODE_ROUTER, UPDATE_INTERVAL
from .history import TrafficHistory

_LOGGER = logging.getLogger(__name__)


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

    async def _async_fetch_device_info(self) -> None:
        if self.device_info:
            return
        try:
            self.device_info = await self.client.call("system", "get_info") or {}
        except GlinetApiError as err:
            _LOGGER.debug("讀取 system.get_info 失敗（不影響其他感測器）：%s", err)

    async def _async_fetch_mode(self) -> None:
        """只在第一次抓,之後快cache——模式是使用者刻意切的,很少變,
        整合期間重新偵測沒有意義;真的切了模式要重新載入這個整合才會生效。"""
        try:
            result = await self.client.call("netmode", "get_mode")
            self.mode = (result or {}).get("mode", MODE_ROUTER)
        except GlinetApiError as err:
            _LOGGER.debug("讀取 netmode.get_mode 失敗，當作 router 模式：%s", err)

    async def _async_update_data(self) -> GlinetData:
        await self._async_fetch_device_info()
        if self.data is None:
            await self._async_fetch_mode()

        try:
            wan_speed = await self.client.call("clients", "get_wan_speed")
            clients_res = await self.client.call("clients", "get_list")
            wifi_res = await self.client.call("wifi", "get_config")
            static_res = await self.client.call("lan", "get_static_bind_list")
            bwl_res = await self.client.call("black_white_list", "get_config")
        except GlinetApiError as err:
            raise UpdateFailed(f"跟路由器溝通失敗：{err}") from err

        # 只給面板用（運行時間、負載、記憶體、WAN 連線狀態），讀不到不影響其他功能。
        try:
            system = await self.client.call("system", "get_status") or {}
        except GlinetApiError as err:
            _LOGGER.debug("讀取 system.get_status 失敗（不影響其他感測器）：%s", err)
            system = {}
        if (router_time := system.get("system", {}).get("timestamp")) is not None:
            self.clock_skew = time.time() - float(router_time)

        clients = (clients_res or {}).get("clients", [])
        if self.mode == MODE_ROUTER:
            # 非 router 模式下 clients.get_list 看到的是整個共用網段的所有裝置
            # (不是只有接這台裝置的),不要幫這些裝置建 HA device,會灌一堆跟這台
            # 裝置無關的「幽靈裝置」進裝置登錄表。
            self._async_sync_client_devices(clients)
            self.history.add(time.time(), wan_speed or {}, clients)

        return GlinetData(
            wan_speed=wan_speed or {},
            clients=clients,
            wifi_bands=(wifi_res or {}).get("res", []),
            static_binds=(static_res or {}).get("static_bind_list", []),
            blacklist_mode=(bwl_res or {}).get("mode", "black"),
            black_mac=list((bwl_res or {}).get("black_mac", [])),
            white_mac=list((bwl_res or {}).get("white_mac", [])),
            device_info=self.device_info,
            mode=self.mode,
            system=system,
        )

    async def async_live_poll(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Just the traffic numbers, for the panel while a browser has it open (entities keep their own pace)."""
        wan_speed = await self.client.call("clients", "get_wan_speed") or {}
        clients = ((await self.client.call("clients", "get_list")) or {}).get("clients", [])
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
        router_device_id: str | None = None
        if self.config_entry is not None:
            router_device = registry.async_get_device(
                identifiers={(DOMAIN, self.config_entry.entry_id)}
            )
            router_device_id = router_device.id if router_device else None

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
                via_device_id=router_device_id,
            )
