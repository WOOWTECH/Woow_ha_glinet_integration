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

from .coordinator import GlinetCoordinator
from .entity import GlinetClientEntity, GlinetEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up router-level sensors, then track clients as they appear."""
    coordinator: GlinetCoordinator = entry.runtime_data.coordinator

    async_add_entities(
        [
            GlinetWanSpeedSensor(coordinator, "speed_rx", "WAN 下載速度"),
            GlinetWanSpeedSensor(coordinator, "speed_tx", "WAN 上傳速度"),
            GlinetConnectedClientsSensor(coordinator),
            GlinetFirmwareSensor(coordinator),
        ]
    )

    known_macs: set[str] = set()

    @callback
    def _async_add_new_clients() -> None:
        new_entities: list[SensorEntity] = []
        for client in coordinator.data.clients:
            mac = client.get("mac")
            if not mac or mac in known_macs:
                continue
            known_macs.add(mac)
            new_entities.append(GlinetClientSpeedSensor(coordinator, mac, "rx", "下載速度"))
            new_entities.append(GlinetClientSpeedSensor(coordinator, mac, "tx", "上傳速度"))
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_clients))
    _async_add_new_clients()


class GlinetWanSpeedSensor(GlinetEntity, SensorEntity):
    """外網(WAN)即時流量。"""

    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND

    def __init__(self, coordinator: GlinetCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator, f"{coordinator.config_entry.entry_id}_wan_{key}")
        self._key = key
        self._attr_name = name

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.wan_speed.get(self._key)
        return float(value) if value is not None else None


class GlinetConnectedClientsSensor(GlinetEntity, SensorEntity):
    """目前在線的區網裝置數。"""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "連線裝置數"

    def __init__(self, coordinator: GlinetCoordinator) -> None:
        super().__init__(coordinator, f"{coordinator.config_entry.entry_id}_connected_clients")

    @property
    def native_value(self) -> int:
        return sum(1 for c in self.coordinator.data.clients if c.get("online"))


class GlinetFirmwareSensor(GlinetEntity, SensorEntity):
    """韌體版本(診斷用)。"""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "韌體版本"

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

    def __init__(self, coordinator: GlinetCoordinator, mac: str, key: str, name: str) -> None:
        super().__init__(coordinator, mac, f"{coordinator.config_entry.entry_id}_{mac}_{key}")
        self._key = key
        self._attr_name = name

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
