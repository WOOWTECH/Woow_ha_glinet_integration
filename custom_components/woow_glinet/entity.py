"""Shared base entity for the WOOW GL.iNet integration."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GlinetCoordinator
from .device import router_device_info


class GlinetEntity(CoordinatorEntity[GlinetCoordinator]):
    """Base entity tied to the router device itself."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GlinetCoordinator, unique_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id

        self._attr_device_info = router_device_info(coordinator.config_entry.entry_id, coordinator.device_info)


class GlinetClientEntity(CoordinatorEntity[GlinetCoordinator]):
    """Base entity for one LAN/WiFi client device, grouped under the router."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GlinetCoordinator, mac: str, unique_id: str) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"client_{mac}")},
            connections={("mac", mac)},
            via_device_id=coordinator.router_device_id,
            name=self._client_name(),
        )

    def _client_data(self) -> dict | None:
        for client in self.coordinator.data.clients:
            if client.get("mac") == self._mac:
                return client
        return None

    def _client_name(self) -> str:
        client = self._client_data()
        if client:
            return client.get("name") or client.get("alias") or self._mac
        return self._mac


class GlinetWifiEntity(GlinetEntity):
    """Base for the entities of one Wi-Fi interface: named after its SSID, kept current when it is renamed."""

    def __init__(self, coordinator: GlinetCoordinator, unique_id: str, iface_name: str) -> None:
        super().__init__(coordinator, unique_id)
        self._iface_name = iface_name
        self._attr_translation_placeholders = {"ssid": self._ssid()}

    def _iface(self) -> dict | None:
        for band in self.coordinator.data.wifi_bands:
            for iface in band.get("ifaces", []):
                if iface.get("name") == self._iface_name:
                    return iface
        return None

    def _ssid(self) -> str:
        return (self._iface() or {}).get("ssid") or self._iface_name

    @callback
    def _handle_coordinator_update(self) -> None:
        placeholders = {"ssid": self._ssid()}
        if placeholders != self._attr_translation_placeholders:
            self._attr_translation_placeholders = placeholders
            # Home Assistant computes the translated name once and caches it (functools-style, in the instance
            # dict): drop that so the renamed SSID shows up in the name at the next state write.
            self.__dict__.pop("name", None)
        super()._handle_coordinator_update()
