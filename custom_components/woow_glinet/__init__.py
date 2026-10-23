"""The WOOW GL.iNet integration: GL.iNet routers as entities, plus a sidebar panel to watch and control them."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv, device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from . import panel, websocket_api
from .activity import ActivityLog
from .api import GlinetClient
from .const import CONF_SCHEME, CONF_VERIFY_SSL, DOMAIN
from .coordinator import GlinetCoordinator
from .feed import PanelFeed
from .services import async_register_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_BARE_MAC = re.compile(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.DEVICE_TRACKER,
    Platform.BUTTON,
    Platform.TEXT,
]


@dataclass
class GlinetRuntimeData:
    """Data stored on the config entry while it's loaded."""

    client: GlinetClient
    coordinator: GlinetCoordinator


type GlinetConfigEntry = ConfigEntry[GlinetRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """The activity log, the panel's live feed and its websocket commands (shared by all routers)."""
    activity = ActivityLog(hass)
    await activity.async_load()
    data = hass.data.setdefault(DOMAIN, {})
    data["activity"] = activity
    data["feed"] = PanelFeed(hass, activity)
    websocket_api.async_register(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GlinetConfigEntry) -> bool:
    """Set up one GL.iNet router from a config entry."""
    session = aiohttp_client.async_get_clientsession(
        hass, verify_ssl=entry.data[CONF_VERIFY_SSL]
    )
    client = GlinetClient(
        session,
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        scheme=entry.data[CONF_SCHEME],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
    )

    coordinator = GlinetCoordinator(hass, entry, client, entry.data[CONF_HOST])
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = GlinetRuntimeData(client=client, coordinator=coordinator)

    await _async_scope_tracker_unique_ids(hass, entry)

    feed: PanelFeed = hass.data[DOMAIN]["feed"]
    entry.async_on_unload(coordinator.async_add_listener(lambda: feed.router_updated(coordinator)))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_register_services(hass)
    await panel.async_register_panel(hass)

    return True


async def _async_scope_tracker_unique_ids(hass: HomeAssistant, entry: GlinetConfigEntry) -> None:
    """Device trackers used to be registered under the bare MAC (Home Assistant's ScannerEntity derives its unique id
    from it), so a second router that knows the same device got no tracker of its own: scope them to the router."""

    @callback
    def migrate(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
        if entity_entry.domain == "device_tracker" and _BARE_MAC.match(entity_entry.unique_id or ""):
            return {"new_unique_id": f"{entry.entry_id}_{entity_entry.unique_id}_tracker"}
        return None

    await er.async_migrate_entries(hass, entry.entry_id, migrate)


async def async_unload_entry(hass: HomeAssistant, entry: GlinetConfigEntry) -> bool:
    """Unload one config entry; the panel goes with the last router."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN]["feed"].router_removed(entry.entry_id)
        others = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id and e.state is ConfigEntryState.LOADED
        ]
        if not others:
            panel.async_remove_panel(hass)
    return unloaded


def async_get_coordinator_for_device(
    hass: HomeAssistant, device_id: str
) -> GlinetCoordinator | None:
    """The coordinator of the loaded router that owns a given device registry entry (None if there is none)."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return None
    entry = hass.config_entries.async_get_entry(device.config_entry_id)
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        return None
    return entry.runtime_data.coordinator
