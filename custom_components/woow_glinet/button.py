"""Button platform for the WOOW GL.iNet integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import GlinetApiError
from .coordinator import GlinetCoordinator
from .entity import GlinetEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: GlinetCoordinator = entry.runtime_data.coordinator
    async_add_entities([GlinetRebootButton(coordinator)])


class GlinetRebootButton(GlinetEntity, ButtonEntity):
    """重新開機路由器。"""

    _attr_name = "重新開機"
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, coordinator: GlinetCoordinator) -> None:
        super().__init__(coordinator, f"{coordinator.config_entry.entry_id}_reboot")

    async def async_press(self) -> None:
        try:
            await self.coordinator.client.call("system", "reboot")
        except GlinetApiError as err:
            raise HomeAssistantError(f"重新開機失敗：{err}") from err
