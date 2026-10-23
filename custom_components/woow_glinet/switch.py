"""Switch platform for the WOOW GL.iNet integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .activity import Origin
from .const import MODE_ROUTER
from .coordinator import GlinetCoordinator
from .entity import GlinetClientEntity, GlinetEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: GlinetCoordinator = entry.runtime_data.coordinator

    wifi_entities = [
        GlinetWifiSwitch(coordinator, iface["name"], iface.get("ssid") or iface["name"])
        for band in coordinator.data.wifi_bands
        for iface in band.get("ifaces", [])
    ]
    async_add_entities(wifi_entities)

    if coordinator.data.mode != MODE_ROUTER:
        # 非 router 模式下 clients.get_list 看到的是整個共用網段,不是只有這台
        # 裝置自己的客戶端,「封鎖」開關在這種情況下語意不明(不確定封鎖得到的是
        # 不是真的接在這台裝置上的裝置),不建這些 entity。
        return

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
        await self.coordinator.actions.set_wifi(
            self._iface_name, enabled=enabled, origin=Origin("entity", self._context)
        )

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
        await self.coordinator.actions.set_blocked(
            self._mac, blocked, origin=Origin("entity", self._context)
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)
