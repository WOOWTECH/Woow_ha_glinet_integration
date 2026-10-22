"""Device tracker platform: presence for each LAN/WiFi client."""

from __future__ import annotations

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import GlinetCoordinator
from .entity import GlinetClientEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: GlinetCoordinator = entry.runtime_data.coordinator

    known_macs: set[str] = set()

    @callback
    def _async_add_new_clients() -> None:
        new_entities = []
        for client in coordinator.data.clients:
            mac = client.get("mac")
            if not mac or mac in known_macs:
                continue
            known_macs.add(mac)
            new_entities.append(GlinetClientTracker(coordinator, mac))
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_clients))
    _async_add_new_clients()


class GlinetClientTracker(GlinetClientEntity, ScannerEntity):
    """某個裝置目前有沒有連在這台路由器上。"""

    _attr_name = None

    def __init__(self, coordinator: GlinetCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac, f"{coordinator.config_entry.entry_id}_{mac}_tracker")

    @property
    def source_type(self) -> SourceType:
        return SourceType.ROUTER

    @property
    def is_connected(self) -> bool:
        client = self._client_data()
        return bool(client.get("online")) if client else False

    @property
    def ip_address(self) -> str | None:
        client = self._client_data()
        return client.get("ip") if client else None

    @property
    def mac_address(self) -> str:
        return self._mac
