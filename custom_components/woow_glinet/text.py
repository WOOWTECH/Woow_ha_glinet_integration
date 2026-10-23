"""Text platform: edit WiFi SSID / password directly from the device page."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .activity import Origin
from .coordinator import GlinetCoordinator
from .entity import GlinetEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: GlinetCoordinator = entry.runtime_data.coordinator

    entities: list[TextEntity] = []
    for band in coordinator.data.wifi_bands:
        for iface in band.get("ifaces", []):
            name = iface["name"]
            label = iface.get("ssid") or name
            entities.append(GlinetWifiSsidText(coordinator, name, label))
            entities.append(GlinetWifiKeyText(coordinator, name, label))
    async_add_entities(entities)


class _GlinetWifiFieldText(GlinetEntity, TextEntity):
    _field: str

    def __init__(self, coordinator: GlinetCoordinator, iface_name: str, label: str, suffix: str) -> None:
        super().__init__(
            coordinator, f"{coordinator.config_entry.entry_id}_wifi_{iface_name}_{self._field}"
        )
        self._iface_name = iface_name
        self._attr_name = f"WiFi {label} {suffix}"

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
    def native_value(self) -> str | None:
        iface = self._iface()
        return iface.get(self._field) if iface else None

    async def async_set_value(self, value: str) -> None:
        await self.coordinator.actions.set_wifi(
            self._iface_name, origin=Origin("entity", self._context), **{self._field: value}
        )


class GlinetWifiSsidText(_GlinetWifiFieldText):
    """WiFi SSID(名稱)。"""

    _field = "ssid"
    _attr_native_min = 1
    _attr_native_max = 32

    def __init__(self, coordinator: GlinetCoordinator, iface_name: str, label: str) -> None:
        super().__init__(coordinator, iface_name, label, "SSID")


class GlinetWifiKeyText(_GlinetWifiFieldText):
    """WiFi 密碼。"""

    _field = "key"
    _attr_mode = TextMode.PASSWORD
    _attr_native_min = 8
    _attr_native_max = 63

    def __init__(self, coordinator: GlinetCoordinator, iface_name: str, label: str) -> None:
        super().__init__(coordinator, iface_name, label, "密碼")
