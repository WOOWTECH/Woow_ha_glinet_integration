"""Shared base entity for the WOOW GL.iNet integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import GlinetCoordinator


class GlinetEntity(CoordinatorEntity[GlinetCoordinator]):
    """Base entity tied to the router device itself."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GlinetCoordinator, unique_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id

        info = coordinator.device_info
        board = info.get("board_info", {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=board.get("model") or info.get("vendor") or "GL.iNet router",
            name=board.get("hostname") or info.get("vendor") or "GL.iNet router",
            sw_version=info.get("firmware_version"),
            connections={("mac", info["mac"])} if info.get("mac") else set(),
        )


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
            via_device=(DOMAIN, coordinator.config_entry.entry_id),
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
