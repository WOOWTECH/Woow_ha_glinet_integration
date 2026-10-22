"""Switch platform for the WOOW GL.iNet integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import GlinetApiError
from .const import BLACKLIST_MODE, OPERATE_ADD
from .coordinator import GlinetCoordinator
from .entity import GlinetClientEntity, GlinetEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: GlinetCoordinator = entry.runtime_data.coordinator

    wifi_entities = [
        GlinetWifiSwitch(coordinator, iface["name"], iface.get("ssid") or iface["name"])
        for band in coordinator.data.wifi_bands
        for iface in band.get("ifaces", [])
    ]
    async_add_entities(wifi_entities)

    known_macs: set[str] = set()

    @callback
    def _async_add_new_clients() -> None:
        new_entities = []
        for client in coordinator.data.clients:
            mac = client.get("mac")
            if not mac or mac in known_macs:
                continue
            known_macs.add(mac)
            new_entities.append(GlinetClientBlockSwitch(coordinator, mac))
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_clients))
    _async_add_new_clients()


class GlinetWifiSwitch(GlinetEntity, SwitchEntity):
    """開/關一個 WiFi 介面(主頻或 guest)。"""

    def __init__(self, coordinator: GlinetCoordinator, iface_name: str, name: str) -> None:
        super().__init__(coordinator, f"{coordinator.config_entry.entry_id}_wifi_{iface_name}")
        self._iface_name = iface_name
        self._attr_name = f"WiFi {name}"

    def _iface(self) -> dict | None:
        for band in self.coordinator.data.wifi_bands:
            for iface in band.get("ifaces", []):
                if iface.get("name") == self._iface_name:
                    return iface
        return None

    @property
    def available(self) -> bool:
        return super().available and self._iface() is not None

    @property
    def is_on(self) -> bool | None:
        iface = self._iface()
        return bool(iface["enabled"]) if iface else None

    async def _async_set(self, enabled: bool) -> None:
        try:
            await self.coordinator.client.call(
                "wifi", "set_config", {"enabled": enabled, "iface_name": self._iface_name}
            )
        except GlinetApiError as err:
            raise HomeAssistantError(f"切換 WiFi 失敗：{err}") from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)


class GlinetClientBlockSwitch(GlinetClientEntity, SwitchEntity):
    """封鎖/允許某個裝置連上 LAN/WiFi(MAC 黑名單)。"""

    _attr_name = "封鎖"
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: GlinetCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac, f"{coordinator.config_entry.entry_id}_{mac}_blocked")

    @property
    def available(self) -> bool:
        return super().available and self._client_data() is not None

    @property
    def is_on(self) -> bool | None:
        client = self._client_data()
        return bool(client.get("blocked")) if client else None

    async def _async_set(self, blocked: bool) -> None:
        mode = self.coordinator.data.blacklist_mode
        if mode != BLACKLIST_MODE:
            # 在 whitelist 模式下「加進清單」是放行而不是封鎖，語意會反過來，
            # 這個開關只在黑名單模式下有意義，白名單模式下直接拒絕動作比默默做錯更安全。
            raise HomeAssistantError(
                f"路由器目前是「{mode}」模式,不是黑名單模式,這個開關的語意會反過來,先不執行。"
            )
        try:
            if blocked:
                await self.coordinator.client.call(
                    "black_white_list",
                    "set_single_mac",
                    {"mode": mode, "operate": OPERATE_ADD, "mac": self._mac},
                )
            else:
                # 實測過 set_single_mac 的 operate="remove"/"delete" 都不會真的生效
                # （呼叫成功但清單沒變），解除封鎖要整批重寫清單：讀現有黑名單、
                # 濾掉這個 mac、用 set_config 送回去才會真的拿掉。
                current = await self.coordinator.client.call("black_white_list", "get_config")
                mac_list = [
                    m for m in (current or {}).get("black_mac", []) if m.upper() != self._mac.upper()
                ]
                await self.coordinator.client.call(
                    "black_white_list", "set_config", {"mode": mode, "mac": mac_list}
                )
        except GlinetApiError as err:
            raise HomeAssistantError(f"設定裝置封鎖失敗：{err}") from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)
