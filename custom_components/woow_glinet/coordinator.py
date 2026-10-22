"""DataUpdateCoordinator polling one GL.iNet router."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GlinetApiError, GlinetClient
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class GlinetData:
    """One poll's worth of router state."""

    wan_speed: dict[str, Any] = field(default_factory=dict)
    clients: list[dict[str, Any]] = field(default_factory=list)
    wifi_bands: list[dict[str, Any]] = field(default_factory=list)
    static_binds: list[dict[str, Any]] = field(default_factory=list)
    blacklist_mode: str = "black"
    device_info: dict[str, Any] = field(default_factory=dict)


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

    async def _async_fetch_device_info(self) -> None:
        if self.device_info:
            return
        try:
            self.device_info = await self.client.call("system", "get_info") or {}
        except GlinetApiError as err:
            _LOGGER.debug("讀取 system.get_info 失敗（不影響其他感測器）：%s", err)

    async def _async_update_data(self) -> GlinetData:
        await self._async_fetch_device_info()

        try:
            wan_speed = await self.client.call("clients", "get_wan_speed")
            clients_res = await self.client.call("clients", "get_list")
            wifi_res = await self.client.call("wifi", "get_config")
            static_res = await self.client.call("lan", "get_static_bind_list")
            bwl_res = await self.client.call("black_white_list", "get_config")
        except GlinetApiError as err:
            raise UpdateFailed(f"跟路由器溝通失敗：{err}") from err

        clients = (clients_res or {}).get("clients", [])
        self._async_sync_client_devices(clients)

        return GlinetData(
            wan_speed=wan_speed or {},
            clients=clients,
            wifi_bands=(wifi_res or {}).get("res", []),
            static_binds=(static_res or {}).get("static_bind_list", []),
            blacklist_mode=(bwl_res or {}).get("mode", "black"),
            device_info=self.device_info,
        )

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
