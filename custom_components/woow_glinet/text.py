"""Text platform: edit WiFi SSID / password directly from the device page."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .activity import Origin
from .const import OPTION_EXPOSE_WIFI_PASSWORDS
from .coordinator import GlinetCoordinator
from .entity import GlinetWifiEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: GlinetCoordinator = entry.runtime_data.coordinator

    entities: list[TextEntity] = []
    for band in coordinator.data.wifi_bands:
        for iface in band.get("ifaces", []):
            name = iface["name"]
            entities.append(GlinetWifiSsidText(coordinator, name))
            entities.append(GlinetWifiKeyText(coordinator, name))
    async_add_entities(entities)


class _GlinetWifiFieldText(GlinetWifiEntity, TextEntity):
    _field: str

    def __init__(self, coordinator: GlinetCoordinator, iface_name: str) -> None:
        super().__init__(
            coordinator, f"{coordinator.config_entry.entry_id}_wifi_{iface_name}_{self._field}", iface_name
        )

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
    _attr_translation_key = "wifi_ssid"
    _attr_native_min = 1
    _attr_native_max = 32


class GlinetWifiKeyText(_GlinetWifiFieldText):
    """WiFi 密碼。"""

    _field = "key"
    _attr_translation_key = "wifi_key"
    _attr_mode = TextMode.PASSWORD
    _attr_native_min = 8
    _attr_native_max = 63
    # a password in an entity state is readable by every user who can see states, and ends up in the history
    # database: new installs start with these entities disabled, and they are write-only unless the option is on
    _attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.config_entry.options.get(OPTION_EXPOSE_WIFI_PASSWORDS, False):
            return None
        value = super().native_value
        # an open network has no key (empty, or shorter than a text entity may hold): nothing to show
        return value if isinstance(value, str) and len(value) >= self._attr_native_min else None

