"""The router's own entry in Home Assistant's device registry (the client devices hang under it)."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MANUFACTURER
from .sanitize import as_dict, text


def router_device_info(entry_id: str, info: Any) -> DeviceInfo:
    """DeviceInfo for the router from its system.get_info result."""
    info = as_dict(info)
    board = as_dict(info.get("board_info"))
    mac = text(info.get("mac"))
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        manufacturer=MANUFACTURER,
        model=text(board.get("model")) or text(info.get("vendor")) or "GL.iNet router",
        name=text(board.get("hostname")) or text(info.get("vendor")) or "GL.iNet router",
        sw_version=text(info.get("firmware_version")),
        connections={("mac", mac)} if mac else set(),
    )
