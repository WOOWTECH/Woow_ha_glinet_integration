"""Diagnostics for the WOOW GL.iNet integration (the "Download diagnostics" button on the device page)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .sanitize import as_dict, dicts

# Passwords, Wi-Fi keys and anything that identifies a person's device or network are left out.
_REDACT_ENTRY = {"password", "username", "host", "unique_id", "title"}
# What the router says about itself is an allow-list: a field a later firmware adds is left out until it is vetted.
_ABOUT = {"vendor", "model", "firmware_version", "board_info"}
_ABOUT_BOARD = {"model", "kernel_version", "openwrt_version"}
_STATUS = {"uptime", "load_average", "mode", "time_sync_status", "qos_enabled", "ipv6_enabled", "netnat_enabled",
           "memory_total", "memory_free", "memory_buff_cache", "flash_total", "flash_free", "flash_app"}


def _allow(data: Any, keys: set[str]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k in keys} if isinstance(data, dict) else {}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: Any) -> dict[str, Any]:
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data
    return {
        "entry": async_redact_data(entry.as_dict(), _REDACT_ENTRY),
        "state": {
            "mode": coordinator.mode,
            "last_update_success": coordinator.last_update_success,
            "auth_failed": coordinator.auth_failed,
            "update_interval_s": coordinator.update_interval.total_seconds() if coordinator.update_interval else None,
            "unsupported_methods": sorted(coordinator.unsupported),
        },
        "counts": {
            "clients": len(data.clients),
            "clients_online": sum(1 for c in data.clients if c.get("online")),
            "clients_blocked": sum(1 for c in data.clients if c.get("blocked")),
            "static_binds": len(data.static_binds),
            "blocklist": len(data.black_mac),
            "wifi_interfaces": sum(len(dicts(b.get("ifaces"))) for b in dicts(data.wifi_bands)),
            "wan_history_samples": len(coordinator.history.wan),
        },
        "device_info": {
            **_allow(as_dict(data.device_info), _ABOUT - {"board_info"}),
            "board_info": _allow(as_dict(data.device_info).get("board_info"), _ABOUT_BOARD),
        },
        "system": {
            "system": _allow(as_dict(data.system).get("system"), _STATUS),
            "network": [{"interface": n.get("interface"), "online": n.get("online"), "up": n.get("up")}
                        for n in dicts(as_dict(data.system).get("network"))],
            "services": [{"name": x.get("name"), "status": x.get("status")}
                         for x in dicts(as_dict(data.system).get("service"))],
        },
        "wifi": [
            {
                "band": band.get("band"),
                "interfaces": [
                    {"enabled": i.get("enabled"), "guest": i.get("guest"), "hidden": i.get("hidden"), "encryption": i.get("encryption")}
                    for i in dicts(band.get("ifaces"))
                ],
            }
            for band in dicts(data.wifi_bands)
        ],
        "clients_sample": [
            {"online": c.get("online"), "blocked": c.get("blocked"), "iface": c.get("iface"), "type": c.get("type"),
             "has_limit": bool(c.get("limit_rx") or c.get("limit_tx"))}
            for c in data.clients[:3]
        ],
    }
