"""coordinator.py: polling one router - tolerance of firmware differences, mode changes, auth, devices."""

from __future__ import annotations

import logging
import math
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from mock_router import MockRouter
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.woow_glinet.api import GlinetApiError
from custom_components.woow_glinet.const import DOMAIN, UPDATE_INTERVAL
from custom_components.woow_glinet.coordinator import GlinetCoordinator, GlinetData
from testkit import HOST, HOST2, ROUTER_MAC, RouterWorld, override, remove_method

OPTIONAL_METHODS = [
    "wifi.get_config",
    "lan.get_static_bind_list",
    "black_white_list.get_config",
    "clients.get_wan_speed",
    "clients.get_list",
    "system.get_status",
    "netmode.get_mode",
]

# What the data looks like when that one method is missing
DEFAULTS = {
    "wifi.get_config": lambda d: d.wifi_bands == [],
    "lan.get_static_bind_list": lambda d: d.static_binds == [],
    "black_white_list.get_config": lambda d: (d.blacklist_mode, d.black_mac, d.white_mac) == ("black", [], []),
    "clients.get_wan_speed": lambda d: d.wan_speed == {},
    "clients.get_list": lambda d: d.clients == [],
    "system.get_status": lambda d: d.system == {},
    "netmode.get_mode": lambda d: d.mode == "router",
}


async def lacking(setup_router: Any, world: RouterWorld, *methods: str, host: str = HOST, **kwargs: Any) -> MockConfigEntry:
    router = world.add(host, **kwargs)
    remove_method(router, *methods)
    return await setup_router(host, router=router)


# ===================================================================================== a normal poll
async def test_a_poll_fills_in_everything(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    data = coordinator.data
    assert isinstance(data, GlinetData)
    assert data.mode == "router" and coordinator.mode == "router"
    assert len(data.clients) == 6 and data.clients[0]["mac"] == "AA:BB:CC:00:00:00"
    assert [b["band"] for b in data.wifi_bands] == ["2G", "5G"]
    assert data.static_binds == [] and data.black_mac == [] and data.white_mac == [] and data.blacklist_mode == "black"
    assert data.wan_speed == {"speed_rx": 12000, "speed_tx": 1200}
    assert data.device_info["firmware_version"] == "4.8.3"
    assert data.system["system"]["lan_ip"] == "192.168.8.1"
    assert coordinator.unsupported == set()
    assert coordinator.auth_failed is False


async def test_the_poll_interval_is_30_seconds(coordinator: GlinetCoordinator) -> None:
    assert UPDATE_INTERVAL == timedelta(seconds=30) == coordinator.update_interval
    assert coordinator.name == f"{DOMAIN}_{HOST}"


async def test_each_refresh_asks_each_endpoint_once_and_system_info_only_once(coordinator: GlinetCoordinator, world: RouterWorld) -> None:
    await coordinator.async_refresh()
    await coordinator.async_refresh()
    for method in OPTIONAL_METHODS:
        assert world.count(method) == 3, f"{method}: setup + 2 refreshes"
    assert world.count("system.get_info") == 1, "the device info does not change: asked once"
    assert world.count("login") == 1


async def test_blocklist_and_static_binds_arrive_in_the_data(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    router.configure(black_mac=["AA:BB:CC:00:00:01"], static_binds=[{"mac": "AA:BB:CC:00:00:02", "ip": "192.168.8.40", "name": "tv"}])
    router.white_mac = ["AA:BB:CC:00:00:03"]
    await coordinator.async_refresh()
    assert coordinator.data.black_mac == ["AA:BB:CC:00:00:01"]
    assert coordinator.data.white_mac == ["AA:BB:CC:00:00:03"]
    assert coordinator.data.static_binds == [{"mac": "AA:BB:CC:00:00:02", "ip": "192.168.8.40", "name": "tv"}]


# ===================================================================================== firmware without some methods
@pytest.mark.parametrize("method", OPTIONAL_METHODS)
async def test_a_firmware_without_one_method_still_loads(setup_router: Any, world: RouterWorld, method: str) -> None:
    entry = await lacking(setup_router, world, method)
    coordinator = entry.runtime_data.coordinator

    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.unsupported == {method}, "remembered, so the matching feature can be switched off"
    assert DEFAULTS[method](coordinator.data), f"default data for {method}"
    assert coordinator.last_update_success is True


# What a normal poll of a router that has a static lease and one blocked device returns, piece by piece
NORMAL = {
    "wifi.get_config": lambda d: len(d.wifi_bands) == 2,
    "lan.get_static_bind_list": lambda d: len(d.static_binds) == 1,
    "black_white_list.get_config": lambda d: d.black_mac == ["AA:BB:CC:00:00:01"],
    "clients.get_wan_speed": lambda d: d.wan_speed.get("speed_rx") == 12000,
    "clients.get_list": lambda d: len(d.clients) == 6,
    "system.get_status": lambda d: d.system.get("system", {}).get("lan_ip") == "192.168.8.1",
    "netmode.get_mode": lambda d: d.mode == "ap",  # (the default, when the method is missing, would be "router")
}


@pytest.mark.parametrize("method", OPTIONAL_METHODS)
async def test_the_other_data_is_unaffected_by_a_missing_method(setup_router: Any, world: RouterWorld, method: str) -> None:
    entry = await lacking(
        setup_router, world, method,
        mode="ap", black_mac=["AA:BB:CC:00:00:01"], static_binds=[{"mac": "AA:BB:CC:00:00:02", "ip": "192.168.8.40", "name": "tv"}],
    )  # fmt: skip
    data = entry.runtime_data.coordinator.data
    assert not NORMAL[method](data), "the missing method's own data is the default"
    assert all(check(data) for other, check in NORMAL.items() if other != method), "everything else is as usual"


async def test_a_firmware_with_none_of_the_optional_methods(setup_router: Any, world: RouterWorld) -> None:
    entry = await lacking(setup_router, world, *OPTIONAL_METHODS)
    coordinator = entry.runtime_data.coordinator
    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.unsupported == set(OPTIONAL_METHODS)
    assert all(check(coordinator.data) for check in DEFAULTS.values())
    assert coordinator.mode == "router"


async def test_a_firmware_without_system_info_still_loads(setup_router: Any, world: RouterWorld) -> None:
    entry = await lacking(setup_router, world, "system.get_info")
    coordinator = entry.runtime_data.coordinator
    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.device_info == {}
    assert "system.get_info" in coordinator.unsupported


async def test_a_missing_method_is_logged_once_not_every_poll(setup_router: Any, world: RouterWorld, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="custom_components.woow_glinet.coordinator")
    entry = await lacking(setup_router, world, "wifi.get_config")
    coordinator = entry.runtime_data.coordinator
    for _ in range(3):
        await coordinator.async_refresh()
    notices = [r for r in caplog.records if "wifi.get_config" in r.getMessage()]
    assert len(notices) == 1


async def test_a_method_that_appears_later_is_no_longer_unsupported(setup_router: Any, world: RouterWorld) -> None:
    router = world.add(HOST)
    original = router.methods["wifi.get_config"]
    remove_method(router, "wifi.get_config")
    entry = await setup_router(HOST, router=router)
    coordinator = entry.runtime_data.coordinator
    assert coordinator.unsupported == {"wifi.get_config"} and coordinator.data.wifi_bands == []

    router.methods["wifi.get_config"] = original  # a firmware update
    await coordinator.async_refresh()
    assert coordinator.unsupported == set()
    assert len(coordinator.data.wifi_bands) == 2


async def test_no_client_entities_when_the_client_list_is_missing(hass: HomeAssistant, setup_router: Any, world: RouterWorld) -> None:
    entry = await lacking(setup_router, world, "clients.get_list")
    assert entry.state is ConfigEntryState.LOADED
    unique_ids = [e.unique_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)]
    per_client = [u for u in unique_ids if u.endswith(("_rx", "_tx", "_blocked", "_tracker")) and "wan_speed" not in u]
    assert per_client == [] and not any(":" in u for u in unique_ids)
    assert any(u.endswith("_wifi_default_radio0") for u in unique_ids), "the router-level entities are all still there"


# ===================================================================================== Lua's [] for {}
LUA_EMPTY = [[], None]  # an empty Lua table is serialised as [], and some methods answer null


@pytest.mark.parametrize("empty", LUA_EMPTY, ids=["empty-list", "null"])
@pytest.mark.parametrize("method", OPTIONAL_METHODS)
async def test_an_empty_lua_table_where_a_dict_is_expected(setup_router: Any, world: RouterWorld, method: str, empty: Any) -> None:
    router = world.add(HOST)
    override(router, method, lambda p, empty=empty: empty)
    entry = await setup_router(HOST, router=router)
    coordinator = entry.runtime_data.coordinator

    assert entry.state is ConfigEntryState.LOADED
    assert DEFAULTS[method](coordinator.data), f"{method} -> {empty!r} must give the default"
    assert coordinator.unsupported == set(), "the method exists: it just had nothing to say"


async def test_system_info_as_an_empty_list(setup_router: Any, world: RouterWorld) -> None:
    router = world.add(HOST)
    override(router, "system.get_info", lambda p: [])
    entry = await setup_router(HOST, router=router)
    assert entry.state is ConfigEntryState.LOADED and entry.runtime_data.coordinator.device_info == {}


@pytest.mark.parametrize("clients", [{}, {"a": 1}, None, "no", 5, []], ids=["empty-object", "object", "null", "string", "number", "empty-list"])
async def test_a_clients_field_that_is_not_a_list(setup_router: Any, world: RouterWorld, clients: Any) -> None:
    router = world.add(HOST)
    override(router, "clients.get_list", lambda p, clients=clients: {"clients": clients})
    entry = await setup_router(HOST, router=router)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.coordinator.data.clients == []


async def test_a_response_without_the_clients_key(setup_router: Any, world: RouterWorld) -> None:
    router = world.add(HOST)
    override(router, "clients.get_list", lambda p: {})
    entry = await setup_router(HOST, router=router)
    assert entry.runtime_data.coordinator.data.clients == []


async def test_no_blocklist_keys_when_the_lists_are_empty(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    """The real firmware omits black_mac / white_mac when empty."""
    assert "black_mac" not in router.methods["black_white_list.get_config"]({})
    assert coordinator.data.black_mac == [] and coordinator.data.white_mac == []


# ===================================================================================== network mode changes
async def test_mode_change_schedules_exactly_one_reload(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                        router: MockRouter) -> None:
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        assert coordinator.mode == "router"
        await coordinator.async_refresh()
        reload.assert_not_called()

        router.configure(mode="ap")
        for _ in range(4):
            await coordinator.async_refresh()

    reload.assert_called_once_with(entry.entry_id)
    assert coordinator.mode == "ap" and coordinator.data.mode == "ap"


@pytest.mark.parametrize("new_mode", ["ap", "repeater", "wds", "relay", "mesh", "passthrough"])
async def test_any_other_mode_triggers_the_reload(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                  router: MockRouter, new_mode: str) -> None:
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        router.configure(mode=new_mode)
        await coordinator.async_refresh()
    reload.assert_called_once_with(entry.entry_id)


async def test_mode_change_back_to_the_original_mode_before_the_reload_runs(hass: HomeAssistant, entry: MockConfigEntry,
                                                                           coordinator: GlinetCoordinator, router: MockRouter) -> None:
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        router.configure(mode="ap")
        await coordinator.async_refresh()
        router.configure(mode="router")
        await coordinator.async_refresh()
        router.configure(mode="ap")
        await coordinator.async_refresh()
    assert reload.call_count == 1, "one reload per coordinator lifetime, however much the router flaps"


async def test_a_mode_change_really_reloads_the_entry_and_the_entities_follow(hass: HomeAssistant, entry: MockConfigEntry,
                                                                              coordinator: GlinetCoordinator, router: MockRouter) -> None:
    assert hass.states.async_entity_ids("device_tracker")
    router.configure(mode="ap")

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    new = entry.runtime_data.coordinator
    assert new is not coordinator, "the coordinator was rebuilt"
    assert new.mode == "ap"
    # per-client entities only exist in router mode: Home Assistant keeps the old registry entries as "restored"
    # placeholders, but nothing provides them any more
    trackers = hass.states.async_all("device_tracker")
    assert trackers and all(s.state == "unavailable" and s.attributes.get("restored") for s in trackers)
    assert all(s.state == "unavailable" for s in hass.states.async_all("sensor") if "rx" in s.entity_id or "xia_zai" in s.entity_id)


async def test_the_first_poll_defines_the_mode_the_entities_are_built_for(setup_router: Any) -> None:
    entry = await setup_router(HOST2, mode="ap", mac="94:83:C4:00:00:09")
    assert entry.runtime_data.coordinator._setup_mode == "ap"
    assert entry.runtime_data.coordinator._reload_scheduled is False


# ===================================================================================== credentials
async def test_wrong_password_at_setup_starts_reauthentication(hass: HomeAssistant, setup_router: Any, world: RouterWorld) -> None:
    router = world.add(HOST, password="not-what-the-entry-has")
    entry = await setup_router(HOST, router=router, expect=ConfigEntryState.SETUP_ERROR)
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [(f["context"]["source"], f["context"]["entry_id"]) for f in flows] == [("reauth", entry.entry_id)]


async def test_update_with_rejected_credentials_raises_auth_failed_and_sets_the_flag(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    router.configure(password="changed")
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
    assert coordinator.auth_failed is True


async def test_refresh_with_rejected_credentials(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                 router: MockRouter) -> None:
    router.configure(password="changed")
    await coordinator.async_refresh()
    assert coordinator.auth_failed is True
    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f["context"]["source"] for f in flows] == ["reauth"]


async def test_auth_failed_clears_when_the_router_accepts_the_credentials_again(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    router.configure(password="changed")
    await coordinator.async_refresh()
    assert coordinator.auth_failed is True
    router.configure(password="mockpass")
    await coordinator.async_refresh()
    assert coordinator.auth_failed is False and coordinator.last_update_success is True


async def test_status_that_the_router_refuses_to_give_is_not_fatal(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    """system.get_status is only for the panel: a -1/-32000 on it must not take the entities down."""
    router.configure(error_methods={"system.get_status": (-1, "Access denied")})
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert coordinator.data.system == {}
    assert coordinator.auth_failed is False


async def test_a_failing_system_status_does_not_break_the_other_data(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    router.configure(error_methods={"system.get_status": (-5, "Boom")})
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert len(coordinator.data.clients) == 6 and coordinator.data.system == {}


async def test_a_failing_system_info_is_retried_on_the_next_poll(setup_router: Any, world: RouterWorld) -> None:
    router = world.add(HOST)
    router.configure(error_methods={"system.get_info": (-5, "Boom")})
    entry = await setup_router(HOST, router=router)
    coordinator = entry.runtime_data.coordinator
    assert coordinator.device_info == {}
    router.configure(error_methods={})
    await coordinator.async_refresh()
    assert coordinator.device_info["mac"] == ROUTER_MAC


# ===================================================================================== unreachable router
async def test_unreachable_router_at_setup_is_retried(hass: HomeAssistant, setup_router: Any, world: RouterWorld) -> None:
    world.add(HOST)
    world.disconnect(HOST)
    entry = await setup_router(HOST, expect=ConfigEntryState.SETUP_RETRY)
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN) == [], "no reauth: nothing is wrong with the password"
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unreachable_router_gives_update_failed(coordinator: GlinetCoordinator, world: RouterWorld) -> None:
    world.disconnect(HOST)
    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_update_data()
    assert isinstance(err.value.__cause__, GlinetApiError)
    assert coordinator.auth_failed is False


async def test_the_entities_recover_when_the_router_comes_back(hass: HomeAssistant, coordinator: GlinetCoordinator, world: RouterWorld) -> None:
    world.disconnect(HOST)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    assert all(s.state == "unavailable" for s in hass.states.async_all("sensor"))

    world.reconnect(HOST)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert not any(s.state == "unavailable" for s in hass.states.async_all("sensor"))


@pytest.mark.parametrize(
    "inject",
    [
        {"exc": TimeoutError()},
        {"raw": b"<html>502 Bad Gateway</html>"},
        {"raw": b'{"error": {"code": -5, "message": "internal error"}}'},
        {"raw": b"[]", "status": 500},
    ],
    ids=["timeout", "html", "rpc-error", "http-500"],
)
async def test_every_kind_of_trouble_is_an_update_failed(coordinator: GlinetCoordinator, world: RouterWorld, inject: dict) -> None:
    world.inject("clients.get_list", times=None, **inject)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False


async def test_a_router_that_reboots_during_a_poll(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    router.configure(dark_for=60)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    router.configure(dark_for=0)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True


# ===================================================================================== clock skew
async def test_clock_skew_is_this_hosts_clock_minus_the_routers(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    import time

    for offset in (3600, -90, 0):
        # the router's clock is `offset` seconds behind this host's
        set_timestamp(router, lambda offset=offset: int(time.time()) - offset)
        await coordinator.async_refresh()
        assert coordinator.clock_skew == pytest.approx(offset, abs=2.0)


def set_timestamp(router: MockRouter, fn: Any) -> None:
    original = router.methods["system.get_status"]
    if not hasattr(router, "_original_status"):
        router._original_status = original  # type: ignore[attr-defined]
    base = router._original_status  # type: ignore[attr-defined]

    def patched(params: dict) -> dict:
        out = base(params)
        out["system"] = {**out["system"], "timestamp": fn()}
        return out

    router.methods["system.get_status"] = patched


async def test_clock_skew_when_the_router_reports_no_time(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    set_timestamp(router, lambda: None)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert coordinator.clock_skew == pytest.approx(0, abs=2.0), "no timestamp: the old value stays"


async def test_clock_skew_accepts_a_numeric_string(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    import time

    set_timestamp(router, lambda: str(int(time.time()) - 500))
    await coordinator.async_refresh()
    assert coordinator.clock_skew == pytest.approx(500, abs=2.0)


@pytest.mark.parametrize(
    "timestamp",
    ["garbage", "", [1], {"a": 1}, float("inf"), float("-inf"), float("nan"), "NaN", "inf", True and "1e999"],
    ids=["garbage", "empty-string", "list", "object", "infinity", "minus-infinity", "nan", "nan-text", "inf-text", "overflow-text"],
)
async def test_a_timestamp_that_is_not_a_usable_time_is_ignored(coordinator: GlinetCoordinator, router: MockRouter, timestamp: Any) -> None:
    """The clock is only used to show 'online since' in this host's time: junk must neither fail the poll nor poison the skew."""
    import time

    set_timestamp(router, lambda: int(time.time()) - 120)
    await coordinator.async_refresh()
    assert coordinator.clock_skew == pytest.approx(120, abs=2.0)

    set_timestamp(router, lambda: timestamp)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.clock_skew == pytest.approx(120, abs=2.0), "the last good value stays"
    assert math.isfinite(coordinator.clock_skew)


@pytest.mark.parametrize("odd", [[], "text", 5, None, 1.5, True], ids=["lua-empty-table", "string", "int", "null", "float", "bool"])
async def test_an_inner_status_that_is_not_an_object_does_not_take_the_entities_down(coordinator: GlinetCoordinator, router: MockRouter,
                                                                                    odd: Any) -> None:
    """system.get_status is 'only for the panel'; a Lua-style `system: []` (or junk) must not make every entity unavailable."""
    original = router.methods["system.get_status"]
    router.methods["system.get_status"] = lambda params: {**original(params), "system": odd}

    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data.system["system"] == {}, "replaced by an empty object, the rest of the status is kept"
    assert coordinator.data.system["network"], "(the other parts of the status stay)"
    assert len(coordinator.data.clients) == 6


async def test_a_status_without_the_inner_system_key_is_left_alone(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    original = router.methods["system.get_status"]
    router.methods["system.get_status"] = lambda params: {k: v for k, v in original(params).items() if k != "system"}
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True and "system" not in coordinator.data.system
    assert "network" in coordinator.data.system


async def test_an_empty_status_is_an_empty_dict(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    router.methods["system.get_status"] = lambda params: []
    await coordinator.async_refresh()
    assert coordinator.data.system == {} and coordinator.last_update_success is True


async def test_no_clock_skew_without_a_status(setup_router: Any, world: RouterWorld) -> None:
    entry = await lacking(setup_router, world, "system.get_status")
    assert entry.runtime_data.coordinator.clock_skew == 0.0


# ===================================================================================== devices in the registry
async def test_the_router_device_is_created_before_the_client_devices(hass: HomeAssistant, setup_router: Any, world: RouterWorld) -> None:
    world.add(HOST)
    calls: list[dict[str, Any]] = []
    original = dr.DeviceRegistry.async_get_or_create

    def spy(self: dr.DeviceRegistry, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return original(self, **kwargs)

    with patch.object(dr.DeviceRegistry, "async_get_or_create", spy):
        entry = await setup_router(HOST)

    assert calls[0]["identifiers"] == {(DOMAIN, entry.entry_id)}, "the router is registered first"
    assert calls[0]["manufacturer"] == "GL.iNet" and calls[0]["model"] == "GL-MOCK1200" and calls[0]["name"] == "GL-MOCK1200"
    assert calls[0]["sw_version"] == "4.8.3" and calls[0]["connections"] == {("mac", ROUTER_MAC)}
    client_calls = [c for c in calls[1:] if any(i[1].startswith("client_") for i in c.get("identifiers", ()))]
    assert len(client_calls) >= 6
    router_id = entry.runtime_data.coordinator.router_device_id
    assert router_id is not None
    for call in client_calls[:6]:
        assert call["via_device_id"] == router_id, "attached to the router from the start (no deprecated via_device)"
        assert "via_device" not in call


async def test_client_devices_hang_under_the_router(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator) -> None:
    registry = dr.async_get(hass)
    router_device = registry.async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
    assert router_device is not None and coordinator.router_device_id == router_device.id
    assert router_device.via_device_id is None

    clients = [d for d in registry.devices if d.id != router_device.id]
    assert len(clients) == 6
    assert {d.via_device_id for d in clients} == {router_device.id}
    assert {next(iter(d.identifiers)) for d in clients} == {(DOMAIN, f"client_AA:BB:CC:00:00:0{i}") for i in range(6)}
    assert {next(iter(d.connections)) for d in clients} == {("mac", f"aa:bb:cc:00:00:0{i}") for i in range(6)}


async def test_the_tracker_gives_home_assistant_the_clients_name(coordinator: GlinetCoordinator) -> None:
    """Without a hostname, ScannerEntity re-registers the client's device named by its MAC when the tracker is added."""
    from custom_components.woow_glinet.device_tracker import GlinetClientTracker

    assert GlinetClientTracker(coordinator, "AA:BB:CC:00:00:00").hostname == "iPhone-Ann"
    assert GlinetClientTracker(coordinator, "AA:BB:CC:00:00:01").hostname == "MacBook Pro"


@pytest.mark.parametrize(
    ("name", "alias", "expected"),
    [("Name", "Alias", "Name"), ("", "Alias", "Alias"), (None, "Alias", "Alias"), ("", "", None), (None, None, None)],
)
async def test_the_tracker_hostname_falls_back_to_the_alias_and_then_to_nothing(coordinator: GlinetCoordinator, router: MockRouter,
                                                                              name: Any, alias: Any, expected: Any) -> None:
    from custom_components.woow_glinet.device_tracker import GlinetClientTracker

    router.clients[3]["name"], router.clients[3]["alias"] = name, alias
    await coordinator.async_refresh()
    assert GlinetClientTracker(coordinator, "AA:BB:CC:00:00:03").hostname == expected, "None: Home Assistant then uses the MAC"


async def test_the_tracker_of_a_client_the_router_forgot_has_no_hostname(coordinator: GlinetCoordinator) -> None:
    from custom_components.woow_glinet.device_tracker import GlinetClientTracker

    assert GlinetClientTracker(coordinator, "DE:AD:BE:EF:00:09").hostname is None


async def test_client_devices_are_named_after_the_clients_as_soon_as_the_entry_is_loaded(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Right after setup, not after the next poll: the tracker platform used to rename every client device to its MAC
    (and the outcome depended on which platform finished last)."""
    registry = dr.async_get(hass)
    names = {
        mac: registry.async_get_device_by_identifier((DOMAIN, f"client_{mac}"), entry.entry_id).name
        for mac in (f"AA:BB:CC:00:00:0{i}" for i in range(6))
    }
    assert names == {
        "AA:BB:CC:00:00:00": "iPhone-Ann", "AA:BB:CC:00:00:01": "MacBook Pro", "AA:BB:CC:00:00:02": "Living-room TV",
        "AA:BB:CC:00:00:03": "Hue Bridge", "AA:BB:CC:00:00:04": "ESP32-kitchen", "AA:BB:CC:00:00:05": "HP LaserJet",
    }  # fmt: skip


async def test_client_devices_keep_their_names_across_a_reload(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    registry = dr.async_get(hass)
    assert registry.async_get_device_by_identifier((DOMAIN, "client_AA:BB:CC:00:00:00"), entry.entry_id).name == "iPhone-Ann"


async def test_client_device_names_follow_the_router(hass: HomeAssistant, coordinator: GlinetCoordinator, router: MockRouter) -> None:
    registry = dr.async_get(hass)
    router.configure(client_names=["Renamed phone"])
    await coordinator.async_refresh()
    device = registry.async_get_device_by_identifier((DOMAIN, "client_AA:BB:CC:00:00:00"), coordinator.config_entry.entry_id)
    assert device is not None and device.name == "Renamed phone"


@pytest.mark.parametrize(
    ("name", "alias", "expected"),
    [("Name", "Alias", "Name"), ("", "Alias", "Alias"), (None, "Alias", "Alias"), ("", "", "AA:BB:CC:00:00:03"), (None, None, "AA:BB:CC:00:00:03")],
)
async def test_client_device_name_falls_back_to_alias_then_mac(hass: HomeAssistant, coordinator: GlinetCoordinator, router: MockRouter,
                                                              name: Any, alias: Any, expected: str) -> None:
    router.clients[3]["name"], router.clients[3]["alias"] = name, alias
    await coordinator.async_refresh()
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, "client_AA:BB:CC:00:00:03"), coordinator.config_entry.entry_id)
    assert device is not None and device.name == expected


async def test_refreshing_does_not_multiply_devices(hass: HomeAssistant, coordinator: GlinetCoordinator) -> None:
    before = len(list(dr.async_get(hass).devices))
    for _ in range(3):
        await coordinator.async_refresh()
    assert len(list(dr.async_get(hass).devices)) == before


async def test_a_client_without_a_mac_gets_no_device(hass: HomeAssistant, coordinator: GlinetCoordinator, router: MockRouter) -> None:
    before = len(list(dr.async_get(hass).devices))
    router.clients.append({**router.clients[0], "mac": "", "name": "ghost"})
    await coordinator.async_refresh()
    assert len(list(dr.async_get(hass).devices)) == before


async def test_new_clients_get_devices_under_the_router(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                       router: MockRouter) -> None:
    from testkit import add_clients

    add_clients(router, 8)
    await coordinator.async_refresh()
    registry = dr.async_get(hass)
    device = registry.async_get_device_by_identifier((DOMAIN, "client_AA:BB:CC:00:00:07"), entry.entry_id)
    assert device is not None and device.via_device_id == coordinator.router_device_id


async def test_no_client_devices_and_no_history_outside_router_mode(hass: HomeAssistant, setup_router: Any) -> None:
    """In AP/repeater mode the client list is the whole shared segment: it must not become 'ghost' devices."""
    entry = await setup_router(HOST2, mode="ap", mac="94:83:C4:00:00:09", clients=12)
    coordinator = entry.runtime_data.coordinator
    registry = dr.async_get(hass)

    assert len(coordinator.data.clients) == 12, "the data still has the list (the panel is told the mode)"
    assert [d.name for d in registry.devices] == ["GL-MOCK1200"], "only the router itself"
    assert coordinator.router_device_id is None
    assert len(coordinator.history.wan) == 0 and coordinator.history.clients == {}


# ===================================================================================== the live poll
async def test_live_poll_returns_just_the_traffic(coordinator: GlinetCoordinator, world: RouterWorld) -> None:
    before = (world.count("wifi.get_config"), world.count("system.get_status"))
    wan, clients = await coordinator.async_live_poll()
    assert wan == {"speed_rx": 12000, "speed_tx": 1200}
    assert len(clients) == 6
    assert (world.count("wifi.get_config"), world.count("system.get_status")) == before, "only the two traffic calls"


async def test_live_poll_adds_to_the_history(coordinator: GlinetCoordinator) -> None:
    before = len(coordinator.history.wan)
    await coordinator.async_live_poll()
    assert len(coordinator.history.wan) == before + 1


async def test_live_poll_with_a_client_field_that_is_not_a_list(setup_router: Any, world: RouterWorld) -> None:
    router = world.add(HOST)
    entry = await setup_router(HOST, router=router)
    override(router, "clients.get_list", lambda p: {"clients": {"oops": 1}})
    wan, clients = await entry.runtime_data.coordinator.async_live_poll()
    assert clients == [] and "speed_rx" in wan


async def test_live_poll_on_a_firmware_without_the_methods(setup_router: Any, world: RouterWorld) -> None:
    entry = await lacking(setup_router, world, "clients.get_wan_speed", "clients.get_list")
    assert await entry.runtime_data.coordinator.async_live_poll() == ({}, [])


async def test_live_poll_that_meets_a_changed_password(hass: HomeAssistant, coordinator: GlinetCoordinator, router: MockRouter) -> None:
    from custom_components.woow_glinet.api import GlinetInvalidAuth

    router.configure(password="changed")
    with pytest.raises(GlinetInvalidAuth):
        await coordinator.async_live_poll()
    assert coordinator.auth_failed is True
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f["context"]["source"] for f in flows] == ["reauth"]


async def test_two_sources_of_auth_failure_start_one_reauth_flow(hass: HomeAssistant, coordinator: GlinetCoordinator, router: MockRouter) -> None:
    from custom_components.woow_glinet.api import GlinetInvalidAuth

    router.configure(password="changed")
    await coordinator.async_refresh()  # the regular poll notices
    with pytest.raises(GlinetInvalidAuth):
        await coordinator.async_live_poll()  # and so does the panel's
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1


async def test_live_poll_transport_error_is_not_swallowed(coordinator: GlinetCoordinator, world: RouterWorld) -> None:
    world.disconnect(HOST)
    with pytest.raises(GlinetApiError):
        await coordinator.async_live_poll()


# ===================================================================================== two routers
async def test_two_routers_have_separate_coordinators_and_devices(hass: HomeAssistant, setup_router: Any, world: RouterWorld) -> None:
    one = await setup_router(HOST)
    two = await setup_router(HOST2, mac="94:83:C4:00:00:02", clients=3)
    c1, c2 = one.runtime_data.coordinator, two.runtime_data.coordinator
    assert c1 is not c2 and c1.router_device_id != c2.router_device_id
    assert len(c1.data.clients) == 6 and len(c2.data.clients) == 3
    registry = dr.async_get(hass)
    assert {d.via_device_id for d in registry.devices if d.id not in (c1.router_device_id, c2.router_device_id) and d.config_entry_id == one.entry_id} == {c1.router_device_id}
    assert c1.name != c2.name


async def test_credentials_rejected_in_the_middle_of_a_poll(coordinator: GlinetCoordinator, router: MockRouter, world: RouterWorld) -> None:
    """The password changes after the main data was read but before the optional status call: still an auth failure."""
    world.inject("system.get_status", before=lambda: router.configure(password="changed-mid-poll"))
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
    assert coordinator.auth_failed is True


# ===================================================================================== junk inside the lists
GOOD_CLIENT = {"mac": "AA:BB:CC:00:00:70", "ip": "192.168.8.70", "name": "Kept", "alias": "Kept", "online": True, "blocked": False, "iface": "cable",
               "rx": 1, "tx": 1, "total_rx": "5", "total_tx": "5", "limit_rx": 0, "limit_tx": 0, "online_time": 1000}  # fmt: skip
JUNK = [None, "text", 5, 1.5, True, [1, 2], []]
NOT_STRINGS = [None, 5, 1.5, True, [1, 2], [], {"a": 1}]  # (a MAC list keeps strings, whatever they say)


async def test_junk_items_in_the_client_list_are_dropped(setup_router: Any, world: RouterWorld) -> None:
    router = world.add(HOST)
    override(router, "clients.get_list", lambda p: {"clients": [*JUNK, GOOD_CLIENT]})
    entry = await setup_router(HOST, router=router)
    assert entry.runtime_data.coordinator.data.clients == [GOOD_CLIENT]


async def test_junk_items_in_the_wifi_list_are_dropped(setup_router: Any, world: RouterWorld) -> None:
    router = world.add(HOST)
    band = {"band": "2G", "channel": 1, "hwmode": "11g", "htmode": "auto", "ifaces": [
        {"name": "default_radio0", "ssid": "Only", "enabled": True, "encryption": "psk2", "guest": False, "hidden": False, "key": "mock-wifi-key", "bssid": "D2:00:00:00:00:01"}]}  # fmt: skip
    override(router, "wifi.get_config", lambda p: {"res": [*JUNK, band]})
    entry = await setup_router(HOST, router=router)
    assert entry.runtime_data.coordinator.data.wifi_bands == [band]


async def test_junk_items_in_the_static_leases_and_the_blocklists_are_dropped(setup_router: Any, world: RouterWorld) -> None:
    router = world.add(HOST)
    bind = {"mac": "AA:BB:CC:00:00:02", "ip": "192.168.8.40", "name": "tv"}
    override(router, "lan.get_static_bind_list", lambda p: {"static_bind_list": [*JUNK, bind]})
    override(router, "black_white_list.get_config", lambda p: {"mode": "black", "black_mac": [*NOT_STRINGS, "AA:BB:CC:00:00:01"], "white_mac": [5, None, "AA:BB:CC:00:00:03"]})
    entry = await setup_router(HOST, router=router)
    data = entry.runtime_data.coordinator.data
    assert data.static_binds == [bind]
    assert (data.black_mac, data.white_mac) == (["AA:BB:CC:00:00:01"], ["AA:BB:CC:00:00:03"])
    assert data.blacklist_mode == "black"


@pytest.mark.parametrize("shape", [{}, "text", 5, None], ids=["empty-object", "string", "number", "null"])
async def test_lists_that_are_not_lists_become_empty(setup_router: Any, world: RouterWorld, shape: Any) -> None:
    """Lua's empty table is [] (or {}); anything else where a list belongs is ignored too."""
    router = world.add(HOST)
    override(router, "wifi.get_config", lambda p: {"res": shape})
    override(router, "lan.get_static_bind_list", lambda p: {"static_bind_list": shape})
    override(router, "black_white_list.get_config", lambda p: {"mode": "black", "black_mac": shape, "white_mac": shape})
    entry = await setup_router(HOST, router=router)
    data = entry.runtime_data.coordinator.data
    assert (data.wifi_bands, data.static_binds, data.black_mac, data.white_mac) == ([], [], [], [])


async def test_the_live_poll_drops_junk_clients_too(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    override(router, "clients.get_list", lambda p: {"clients": [*JUNK, GOOD_CLIENT]})
    wan, clients = await coordinator.async_live_poll()
    assert clients == [GOOD_CLIENT] and "speed_rx" in wan


# ===================================================================================== Lua's [] for board_info
@pytest.mark.parametrize("board_info", [[], None], ids=["lua-empty-table", "null"])
async def test_a_system_info_without_a_usable_board_info_still_loads(setup_router: Any, world: RouterWorld, board_info: Any) -> None:
    router = world.add(HOST)
    override(router, "system.get_info", lambda p: {"vendor": "GL.iNet", "model": "sft1200", "mac": ROUTER_MAC, "firmware_version": "4.8.3", "board_info": board_info})
    entry = await setup_router(HOST, router=router)  # expects LOADED
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize("mac", [5, ["AA"], True], ids=["number", "list", "bool"])
async def test_a_client_with_a_non_text_mac_does_not_stop_the_router_loading(setup_router: Any, world: RouterWorld, mac: Any) -> None:
    router = world.add(HOST)
    override(router, "clients.get_list", lambda p: {"clients": [{"mac": mac, "name": "odd", "online": True}, GOOD_CLIENT]})
    entry = await setup_router(HOST, router=router)  # expects LOADED
    assert entry.state is ConfigEntryState.LOADED
