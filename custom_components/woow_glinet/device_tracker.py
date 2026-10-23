"""Device tracker platform: presence for each LAN/WiFi client."""

from __future__ import annotations

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import MODE_ROUTER
from .coordinator import GlinetCoordinator
from .entity import GlinetClientEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: GlinetCoordinator = entry.runtime_data.coordinator

    if coordinator.data.mode != MODE_ROUTER:
        # 非 router 模式下 clients.get_list 看到的是整個共用網段的所有裝置,
        # 不是只有接這台裝置的,追蹤它們的連線狀態沒有意義(而且會跟其他真正
        # 負責那些裝置的 integration 搶著建立同一個裝置)。
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
    def unique_id(self) -> str | None:
        # ScannerEntity would use the bare MAC: scoped to the router, two routers that know the same device each
        # get their own tracker
        return self._attr_unique_id

    @property
    def device_info(self) -> DeviceInfo | None:
        # ScannerEntity returns None for a MAC that is already registered; our own DeviceInfo ties the tracker to the
        # client's device, so its entity id comes from the client's name instead of the (long) unique id
        return self._attr_device_info

    @property
    def hostname(self) -> str | None:
        # without it ScannerEntity renames the client's device to its MAC when the entity is added
        client = self._client_data()
        return (client.get("name") or client.get("alias") or None) if client else None

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
