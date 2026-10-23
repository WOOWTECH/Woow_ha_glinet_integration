"""diagnostics.py: the 'Download diagnostics' file is pasted into public issue trackers, so it must carry no secrets.

What the *entry* holds (host, username, password ...) is redacted by name. What the *router says about itself*
(system info, status, Wi-Fi, clients) is an allow-list: a field a later firmware adds is left out until somebody vets it.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from mock_router import MockRouter
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import get_diagnostics_for_config_entry

from custom_components.woow_glinet import diagnostics as diagnostics_module
from custom_components.woow_glinet.activity import Origin
from custom_components.woow_glinet.coordinator import GlinetCoordinator
from custom_components.woow_glinet.diagnostics import async_get_config_entry_diagnostics
from testkit import HOST, HOST2, PASSWORD, ROUTER_MAC, ROUTER_TITLE, WIFI_KEY, RouterWorld, remove_method

from conftest import SetupRouter

MAC_PATTERN = re.compile(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b")
IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
CLIENT_NAMES = ["iPhone-Ann", "MacBook Pro", "Living-room TV", "Hue Bridge", "ESP32-kitchen", "HP LaserJet"]
SSIDS = ["MOCK-8f2", "MOCK-8f2-Guest", "MOCK-8f2-5G", "MOCK-8f2-5G-Guest"]
PRIVATE_HOSTNAME = "Elmo-Private-Router"  # (the mock's own hostname equals its model name, which is harmless)
MARKER = "SECRET-MARKER"


async def diagnostics(hass: HomeAssistant, entry: MockConfigEntry) -> tuple[dict[str, Any], str]:
    data = await async_get_config_entry_diagnostics(hass, entry)
    return data, json.dumps(data, ensure_ascii=False, default=str)


def private_router(router: MockRouter) -> MockRouter:
    """Give the router a hostname that identifies a household (the model stays what it is)."""
    original = router.methods["system.get_info"]

    def get_info(params: dict) -> dict:
        info = original(params)
        info["board_info"] = {**info["board_info"], "hostname": PRIVATE_HOSTNAME}
        return info

    router.methods["system.get_info"] = get_info
    return router


def secrets_for(router: MockRouter) -> list[str]:
    """Everything that must never appear: credentials, keys, identities and addresses of the router and its clients."""
    values = [PASSWORD, WIFI_KEY, "root", HOST, "192.168.8.1", ROUTER_MAC, ROUTER_MAC.lower(), PRIVATE_HOSTNAME, *SSIDS, *CLIENT_NAMES]
    for c in router.clients:
        values += [c["mac"], c["mac"].lower(), c["ip"]]
    for band in router.bands:
        values += [i["bssid"] for i in band["ifaces"]] + [i["name"] for i in band["ifaces"]]
    return values


def with_extras(router: MockRouter) -> MockRouter:
    """A firmware that says more than we know about: every extra field carries a marker that must not come out.

    (Fields the integration itself relies on - `mac`, `name`, `ip` ... - keep their real values, or the router would not load.)
    """
    marked = {"sn": f"{MARKER}-serial", "ddns": f"{MARKER}.glddns.com", "device_ddns": f"{MARKER}-ddns", "country_code": f"{MARKER}-country",
              "wan_ip": f"{MARKER}-203.0.113.5", "hostname": f"{MARKER}-hostname", "ssid": f"{MARKER}-ssid", "passwd": f"{MARKER}-passwd",
              "key": f"{MARKER}-key", "mac_address": f"{MARKER}-mac", "cloud_token": f"{MARKER}-token"}  # fmt: skip
    info, status, clients, wifi = (router.methods[m] for m in ("system.get_info", "system.get_status", "clients.get_list", "wifi.get_config"))

    def get_info(p: dict) -> dict:
        out = info(p)
        return {**out, **marked, "board_info": {**out["board_info"], **marked, "release": {"version": MARKER}}, "hardware_feature": {"sn": MARKER}}

    def get_status(p: dict) -> dict:
        out = status(p)
        return {
            **out, **marked,
            "system": {**out["system"], **marked, "public_ip": f"{MARKER}-public", "lan_netmask": "255.255.255.0"},
            "network": [{**n, **marked, "ip": f"{MARKER}-ip", "gateway": f"{MARKER}-gw"} for n in out["network"]],
            "service": [{**x, "peers": [MARKER], "port": 51820, "server_ip": f"{MARKER}-srv"} for x in out["service"]],
            "wifi": [{**w, **marked} for w in out["wifi"]],
            "client": [{**c, **marked} for c in out["client"]],
        }  # fmt: skip

    def get_list(p: dict) -> dict:
        out = clients(p)
        return {"clients": [{**c, **marked, "dhcp_name": f"{MARKER}-dhcp", "vendor": f"{MARKER}-vendor", "ipv6": [f"{MARKER}-v6"]} for c in out["clients"]]}

    def get_wifi(p: dict) -> dict:
        out = wifi(p)
        return {**out, "res": [{**b, **marked, "ifaces": [{**i, **marked, "radius_secret": f"{MARKER}-radius", "sae_password": f"{MARKER}-sae"} for i in b["ifaces"]]} for b in out["res"]]}

    router.methods.update({"system.get_info": get_info, "system.get_status": get_status, "clients.get_list": get_list, "wifi.get_config": get_wifi})
    return router


# ===================================================================================== what must not be in it
async def test_no_secret_or_identity_in_the_diagnostics(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    router = private_router(world.add(HOST))
    entry = await setup_router(HOST, router=router)
    assert entry.title == ROUTER_TITLE
    _, text = await diagnostics(hass, entry)
    leaked = [value for value in secrets_for(router) if value in text]
    assert leaked == [], f"leaked into the diagnostics: {leaked}"


async def test_no_mac_or_ip_shaped_value_anywhere(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    _, text = await diagnostics(hass, entry)
    assert MAC_PATTERN.findall(text) == []
    assert IPV4_PATTERN.findall(text) == [], "not even the netmask: the LAN range is the one thing about the network that stays out"


async def test_the_password_and_the_username_are_redacted_in_the_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    data, text = await diagnostics(hass, entry)
    assert data["entry"]["data"]["password"] == "**REDACTED**"
    assert data["entry"]["data"]["username"] == "**REDACTED**"
    assert data["entry"]["data"]["host"] == "**REDACTED**"
    assert data["entry"]["unique_id"] == "**REDACTED**" and data["entry"]["title"] == "**REDACTED**"
    assert data["entry"]["data"]["scheme"] == "https" and data["entry"]["data"]["verify_ssl"] is False, "the harmless settings stay: they help debugging"
    assert data["entry"]["domain"] == "woow_glinet"


async def test_a_new_wifi_password_does_not_leak_either(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator) -> None:
    await coordinator.actions.set_wifi("default_radio0", key="brand-new-wifi-secret", ssid="NewName-Secret", origin=Origin("panel", user="x"))
    _, text = await diagnostics(hass, entry)
    assert "brand-new-wifi-secret" not in text and "NewName-Secret" not in text


async def test_static_leases_and_the_blocklist_are_only_counted(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                                router: MockRouter) -> None:
    router.configure(
        black_mac=["AA:BB:CC:00:00:04"],
        static_binds=[{"mac": "AA:BB:CC:00:00:02", "ip": "192.168.8.77", "name": "secret-device-name"}],
    )
    await coordinator.async_refresh()
    data, text = await diagnostics(hass, entry)
    assert data["counts"]["static_binds"] == 1 and data["counts"]["blocklist"] == 1
    assert "192.168.8.77" not in text and "secret-device-name" not in text and "AA:BB:CC:00:00:04" not in text.upper()


# ===================================================================================== the allow-list
async def test_what_the_router_says_about_itself_is_only_the_allowed_fields(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter) -> None:
    data, _ = await diagnostics(hass, entry)
    assert data["device_info"] == {
        "vendor": "GL.iNet", "model": "sft1200", "firmware_version": "4.8.3",
        "board_info": {"model": "GL-MOCK1200", "kernel_version": "5.4.238", "openwrt_version": "OpenWrt 21.02-SNAPSHOT"},
    }  # fmt: skip
    status = data["system"]["system"]
    assert set(status) == {"uptime", "load_average", "mode", "memory_total", "memory_free", "memory_buff_cache", "flash_total", "flash_free", "qos_enabled"}
    assert status["memory_total"] == 121548800 and status["load_average"] == [0.5, 0.6, 0.55] and status["uptime"] > 80000
    assert [n["interface"] for n in data["system"]["network"]] == ["modem_1_1_2", "tethering", "wan6", "wwan", "wan"]
    assert all(set(n) == {"interface", "online", "up"} for n in data["system"]["network"])
    assert data["system"]["network"][-1] == {"interface": "wan", "online": True, "up": True}
    assert data["system"]["services"] == [{"name": "wgserver", "status": 0}, {"name": "ovpnserver", "status": 0}]
    assert set(data["system"]) == {"system", "network", "services"}


async def test_wifi_is_reduced_to_flags(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    data, _ = await diagnostics(hass, entry)
    assert [b["band"] for b in data["wifi"]] == ["2G", "5G"]
    first = data["wifi"][0]
    assert set(first) == {"band", "interfaces"}
    assert first["interfaces"] == [
        {"enabled": True, "guest": False, "hidden": False, "encryption": "psk2"},
        {"enabled": False, "guest": True, "hidden": False, "encryption": "psk2"},
    ]  # fmt: skip


async def test_the_client_sample_is_reduced_to_flags(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    data, _ = await diagnostics(hass, entry)
    assert len(data["clients_sample"]) == 3, "a sample, not the whole list"
    for sample in data["clients_sample"]:
        assert set(sample) == {"online", "blocked", "iface", "type", "has_limit"}
    assert data["clients_sample"][0] == {"online": True, "blocked": False, "iface": "cable", "type": 2, "has_limit": False}


async def test_has_limit_reports_a_speed_limit_without_its_value(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                                  router: MockRouter) -> None:
    router.clients[0]["limit_rx"] = 5000
    await coordinator.async_refresh()
    data, text = await diagnostics(hass, entry)
    assert data["clients_sample"][0]["has_limit"] is True and "5000" not in text


async def test_extra_fields_a_firmware_adds_never_come_out(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    """The point of an allow-list: serial numbers, DDNS names, WAN addresses ... nobody thought of, nobody leaks."""
    router = with_extras(private_router(world.add(HOST)))
    entry = await setup_router(HOST, router=router)
    assert MARKER in json.dumps(entry.runtime_data.coordinator.data.device_info), "(the integration did receive the extras)"

    data, text = await diagnostics(hass, entry)

    assert MARKER not in text, f"an unvetted field leaked: {re.findall(rf'.{{30}}{MARKER}.{{20}}', text)[:3]}"
    assert [v for v in secrets_for(router) if v in text] == []
    assert set(data["device_info"]) == {"vendor", "model", "firmware_version", "board_info"}
    assert set(data["device_info"]["board_info"]) == {"model", "kernel_version", "openwrt_version"}
    assert set(data["system"]["system"]) <= diagnostics_module._STATUS
    assert all(set(n) == {"interface", "online", "up"} for n in data["system"]["network"])
    assert all(set(x) == {"name", "status"} for x in data["system"]["services"])
    assert all(set(i) == {"enabled", "guest", "hidden", "encryption"} for b in data["wifi"] for i in b["interfaces"])
    assert all(set(c) == {"online", "blocked", "iface", "type", "has_limit"} for c in data["clients_sample"])


@pytest.mark.parametrize(
    ("constant", "added", "leaks"),
    [
        ("_ABOUT", "mac", ROUTER_MAC),
        ("_ABOUT_BOARD", "hostname", PRIVATE_HOSTNAME),
        ("_STATUS", "lan_ip", "192.168.8.1"),
        ("_STATUS", "lan_netmask", "255.255.255.0"),
    ],
    ids=["info-mac", "board-hostname", "status-lan-ip", "status-netmask"],
)
async def test_the_checks_would_notice_a_sensitive_key_added_to_the_allow_list(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld,
                                                                               monkeypatch: pytest.MonkeyPatch, constant: str, added: str,
                                                                               leaks: str) -> None:
    """Prove the leak checks are not vacuous: vet a sensitive field in by mistake and they must find it."""
    router = private_router(world.add(HOST))
    entry = await setup_router(HOST, router=router)
    monkeypatch.setattr(diagnostics_module, constant, getattr(diagnostics_module, constant) | {added})
    _, text = await diagnostics(hass, entry)
    assert leaks in text, f"adding {added!r} to {constant} did not show up: the test would not catch that mistake"


# ===================================================================================== what is in it
async def test_the_diagnostics_content(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    data, _ = await diagnostics(hass, entry)
    assert set(data) == {"entry", "state", "counts", "device_info", "system", "wifi", "clients_sample"}
    assert data["state"] == {
        "mode": "router", "last_update_success": True, "auth_failed": False, "update_interval_s": 30.0, "unsupported_methods": [],
    }  # fmt: skip
    counts = data["counts"]
    assert (counts["clients"], counts["clients_online"], counts["clients_blocked"], counts["wifi_interfaces"]) == (6, 4, 0, 4)
    assert counts["static_binds"] == 0 and counts["blocklist"] == 0 and counts["wan_history_samples"] >= 1


async def test_the_diagnostics_are_json_serialisable(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    from homeassistant.helpers.json import json_bytes

    data, _ = await diagnostics(hass, entry)
    json_bytes(data)


async def test_unsupported_methods_are_listed(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    router = world.add(HOST2, mac="94:83:C4:00:00:09")
    remove_method(router, "wifi.get_config", "clients.get_wan_speed")
    entry = await setup_router(HOST2, router=router)
    data, _ = await diagnostics(hass, entry)
    assert data["state"]["unsupported_methods"] == ["clients.get_wan_speed", "wifi.get_config"], "sorted"
    assert data["counts"]["wifi_interfaces"] == 0 and data["wifi"] == []


async def test_a_router_without_system_info_or_status(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    router = world.add(HOST2, mac="94:83:C4:00:00:09")
    remove_method(router, "system.get_info", "system.get_status")
    entry = await setup_router(HOST2, router=router)
    data, _ = await diagnostics(hass, entry)
    assert data["device_info"] == {"board_info": {}}
    assert data["system"] == {"system": {}, "network": [], "services": []}


async def test_the_diagnostics_of_a_failing_router(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator, world: RouterWorld) -> None:
    world.disconnect(HOST)
    await coordinator.async_refresh()
    data, text = await diagnostics(hass, entry)
    assert data["state"]["last_update_success"] is False
    assert PASSWORD not in text


async def test_the_diagnostics_after_the_password_was_rejected(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                               router: MockRouter) -> None:
    router.configure(password="changed")
    await coordinator.async_refresh()
    data, _ = await diagnostics(hass, entry)
    assert data["state"]["auth_failed"] is True


async def test_the_diagnostics_in_ap_mode(hass: HomeAssistant, setup_router: SetupRouter) -> None:
    entry = await setup_router(HOST2, mode="ap", clients=9, mac="94:83:C4:00:00:09")
    data, text = await diagnostics(hass, entry)
    assert data["state"]["mode"] == "ap" and data["counts"]["clients"] == 9
    assert MAC_PATTERN.findall(text) == []


async def test_a_router_with_no_clients(hass: HomeAssistant, setup_router: SetupRouter) -> None:
    entry = await setup_router(HOST2, clients=0, mac="94:83:C4:00:00:09")
    data, _ = await diagnostics(hass, entry)
    assert data["counts"]["clients"] == 0 and data["clients_sample"] == []


async def test_home_assistant_finds_and_serves_the_diagnostics(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld,
                                                              hass_client: Any) -> None:
    """The real path behind the 'Download diagnostics' button (HA discovers diagnostics.py by itself)."""
    router = with_extras(private_router(world.add(HOST)))
    entry = await setup_router(HOST, router=router)
    served = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    text = json.dumps(served, ensure_ascii=False)
    assert served["counts"]["clients"] == 6
    assert [v for v in secrets_for(router) if v in text] == [] and MARKER not in text


# ===================================================================================== odd routers
ODD = [
    pytest.param("network", None, id="network-null"),
    pytest.param("network", 5, id="network-number"),
    pytest.param("service", None, id="service-null"),
    pytest.param("service", 7, id="service-number"),
    pytest.param("network", [None, 3, "x", {"interface": "wan", "online": True}], id="network-junk-items"),
    pytest.param("service", [None, "x", {"name": "wg", "status": 1}], id="service-junk-items"),
    pytest.param("network", {}, id="network-lua-empty"),
    pytest.param("service", {}, id="service-lua-empty"),
    pytest.param("network", "text", id="network-string"),
]


@pytest.mark.parametrize(("key", "value"), ODD)
async def test_diagnostics_still_work_when_the_status_is_odd(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                             router: MockRouter, key: str, value: Any) -> None:
    """The file is asked for exactly when something is odd about the router."""
    original = router.methods["system.get_status"]
    router.methods["system.get_status"] = lambda params: {**original(params), key: value}
    await coordinator.async_refresh()
    data, _ = await diagnostics(hass, entry)
    assert set(data) >= {"state", "counts", "system"}


IFACES = [
    pytest.param(None, id="null"),
    pytest.param(5, id="number"),
    pytest.param({}, id="lua-empty"),
    pytest.param([None, "x", {"enabled": True, "ssid": "S"}], id="junk-items"),
]


@pytest.mark.parametrize("ifaces", IFACES)
async def test_diagnostics_still_work_when_a_band_has_odd_interfaces(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                                      ifaces: Any) -> None:
    coordinator.data.wifi_bands = [{"band": "2G", "ifaces": ifaces}]
    data, text = await diagnostics(hass, entry)
    assert data["wifi"][0]["band"] == "2G"
    assert '"S"' not in text
