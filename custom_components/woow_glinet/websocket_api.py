"""Websocket commands behind the panel (admin only)."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .actions import ActionError
from .activity import Origin
from .const import DOMAIN
from .coordinator import GlinetCoordinator
from .feed import PanelFeed

_COMMANDS: list[Any] = []


def _command(func: Any) -> Any:
    _COMMANDS.append(func)
    return func


@callback
def async_register(hass: HomeAssistant) -> None:
    for handler in _COMMANDS:
        websocket_api.async_register_command(hass, handler)


def _feed(hass: HomeAssistant) -> PanelFeed:
    return hass.data[DOMAIN]["feed"]


def _coordinator(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> GlinetCoordinator | None:
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        connection.send_error(msg["id"], "not_loaded", "That router is not loaded")
        return None
    return entry.runtime_data.coordinator


def _origin(connection: websocket_api.ActiveConnection) -> Origin:
    return Origin("panel", user=connection.user.name if connection.user is not None else None)


async def _answer(connection: websocket_api.ActiveConnection, msg: dict, work: Awaitable[Any]) -> None:
    try:
        result = await work
    except ActionError as err:  # the panel shows these in the user's language, keyed by code
        connection.send_error(msg["id"], err.code, str(err))
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "failed", str(err))
    else:
        connection.send_result(msg["id"], result)


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "woow_glinet/snapshot"})
@callback
def ws_snapshot(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    connection.send_result(msg["id"], _feed(hass).snapshot())


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "woow_glinet/subscribe"})
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Live feed: {"kind": "router" | "router_removed" | "live" | "activity", ...}."""

    @callback
    def forward(event: dict[str, Any]) -> None:
        connection.send_message(websocket_api.event_message(msg["id"], event))

    connection.subscriptions[msg["id"]] = _feed(hass).subscribe(forward)
    connection.send_result(msg["id"])


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "woow_glinet/refresh", vol.Required("entry_id"): str})
@websocket_api.async_response
async def ws_refresh(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is not None:
        await coordinator.async_refresh()
        connection.send_result(msg["id"])


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_glinet/wifi/set",
    vol.Required("entry_id"): str,
    vol.Required("iface"): str,
    vol.Optional("enabled"): bool,
    vol.Optional("ssid"): str,
    vol.Optional("key"): str,
})
@websocket_api.async_response
async def ws_wifi_set(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is not None:
        await _answer(connection, msg, coordinator.actions.set_wifi(
            msg["iface"], enabled=msg.get("enabled"), ssid=msg.get("ssid"), key=msg.get("key"),
            origin=_origin(connection)))


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_glinet/wifi/key",
    vol.Required("entry_id"): str,
    vol.Required("iface"): str,
})
@callback
def ws_wifi_key(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """The Wi-Fi password, only when someone asks for it (the snapshot never carries it)."""
    if (coordinator := _coordinator(hass, connection, msg)) is None:
        return
    for band in coordinator.data.wifi_bands:
        for iface in band.get("ifaces", []):
            if iface.get("name") == msg["iface"]:
                connection.send_result(msg["id"], {"key": iface.get("key") or ""})
                return
    connection.send_error(msg["id"], "no_such_wifi", "No such Wi-Fi interface")


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_glinet/client/block",
    vol.Required("entry_id"): str,
    vol.Required("mac"): str,
    vol.Required("blocked"): bool,
})
@websocket_api.async_response
async def ws_client_block(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is not None:
        await _answer(connection, msg, coordinator.actions.set_blocked(
            msg["mac"], msg["blocked"], origin=_origin(connection)))


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_glinet/client/forget",
    vol.Required("entry_id"): str,
    vol.Required("mac"): str,
})
@websocket_api.async_response
async def ws_client_forget(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is not None:
        await _answer(connection, msg, coordinator.actions.forget_client(msg["mac"], origin=_origin(connection)))


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_glinet/client/history",
    vol.Required("entry_id"): str,
    vol.Required("mac"): str,
})
@callback
def ws_client_history(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is not None:
        connection.send_result(msg["id"], {"series": coordinator.history.client_series(msg["mac"])})


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "woow_glinet/static_ip/add",
    vol.Required("entry_id"): str,
    vol.Required("mac"): str,
    vol.Required("ip"): str,
    vol.Required("name"): str,
})
@websocket_api.async_response
async def ws_static_ip_add(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is not None:
        await _answer(connection, msg, coordinator.actions.add_static_ip(
            msg["mac"], msg["ip"], msg["name"], origin=_origin(connection)))


@_command
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "woow_glinet/reboot", vol.Required("entry_id"): str})
@websocket_api.async_response
async def ws_reboot(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (coordinator := _coordinator(hass, connection, msg)) is not None:
        await _answer(connection, msg, coordinator.actions.reboot(origin=_origin(connection)))
