"""Sensor platform for the WOOW GL.iNet integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfDataRate
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import MODE_ROUTER
from .coordinator import GlinetCoordinator
from .entity import GlinetClientEntity, GlinetEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up router-level sensors, then track clients as they appear.

    `clients.get_list` only scopes to "devices actually connected to this
    device" when it's in router mode. In every other mode (ap/repeater/
    relay/wds/mesh/passthrough) it's bridged onto a shared network segment
    and the call returns *every* device on that whole segment, not just
    this device's own - so per-client entities are skipped there to avoid
    flooding HA with devices unrelated to this GL.iNet unit. Likewise WAN
    speed is always 0 outside router mode (there's no NAT/WAN to measure).
    """
    coordinator: GlinetCoordinator = entry.runtime_data.coordinator
    is_router = coordinator.data.mode == MODE_ROUTER

    entities: list[SensorEntity] = [GlinetModeSensor(coordinator), GlinetFirmwareSensor(coordinator)]
    if is_router:
        entities += [
            GlinetWanSpeedSensor(coordinator, "speed_rx"),
            GlinetWanSpeedSensor(coordinator, "speed_tx"),
            GlinetConnectedClientsSensor(coordinator),
        ]
    async_add_entities(entities)

    if not is_router:
        return

    known_macs: set[str] = set()

    @callback
    def _async_add_new_clients() -> None:
        new_entities: list[SensorEntity] = []
        for client in coordinator.data.clients:
            mac = client.get("mac")
            if not mac or mac in known_macs:
                continue
            known_macs.add(mac)
            new_entities.append(GlinetClientSpeedSensor(coordinator, mac, "rx"))
            new_entities.append(GlinetClientSpeedSensor(coordinator, mac, "tx"))
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_clients))
    _async_add_new_clients()


class GlinetModeSensor(GlinetEntity, SensorEntity):
    """目前的上網模式(router/ap/repeater/...)，決定哪些其他 entity 會出現。"""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "mode"

    def __init__(self, coordinator: GlinetCoordinator) -> None:
        super().__init__(coordinator, f"{coordinator.config_entry.entry_id}_mode")

    @property
    def native_value(self) -> str:
        return self.coordinator.data.mode


class GlinetWanSpeedSensor(GlinetEntity, SensorEntity):
    """外網(WAN)即時流量。"""

    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND

    def __init__(self, coordinator: GlinetCoordinator, key: str) -> None:
        super().__init__(coordinator, f"{coordinator.config_entry.entry_id}_wan_{key}")
        self._key = key
        self._attr_translation_key = {"speed_rx": "wan_download", "speed_tx": "wan_upload"}[key]

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.wan_speed.get(self._key)
        return float(value) if value is not None else None


class GlinetConnectedClientsSensor(GlinetEntity, SensorEntity):
    """目前在線的區網裝置數。"""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "connected_clients"

    def __init__(self, coordinator: GlinetCoordinator) -> None:
        super().__init__(coordinator, f"{coordinator.config_entry.entry_id}_connected_clients")

    @property
    def native_value(self) -> int:
        return sum(1 for c in self.coordinator.data.clients if c.get("online"))


class GlinetFirmwareSensor(GlinetEntity, SensorEntity):
    """韌體版本(診斷用)。"""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "firmware"

    def __init__(self, coordinator: GlinetCoordinator) -> None:
        super().__init__(coordinator, f"{coordinator.config_entry.entry_id}_firmware_version")

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.device_info.get("firmware_version")


class GlinetClientSpeedSensor(GlinetClientEntity, SensorEntity):
    """單一區網/WiFi 裝置的即時流量。"""

    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND

    def __init__(self, coordinator: GlinetCoordinator, mac: str, key: str) -> None:
        super().__init__(coordinator, mac, f"{coordinator.config_entry.entry_id}_{mac}_{key}")
        self._key = key
        self._attr_translation_key = {"rx": "client_download", "tx": "client_upload"}[key]

    @property
    def available(self) -> bool:
        return super().available and self._client_data() is not None

    @property
    def native_value(self) -> float | None:
        client = self._client_data()
        if client is None:
            return None
        value = client.get(self._key)
        return float(value) if value is not None else None
