"""sensor / switch / device_tracker / text / button: what a router turns into in Home Assistant, and what the entities do."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from mock_router import MockRouter
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser

from custom_components.woow_glinet.const import DOMAIN, OPTION_EXPOSE_WIFI_PASSWORDS
from custom_components.woow_glinet.coordinator import GlinetCoordinator
from testkit import HOST, HOST2, WIFI_KEY, RouterWorld, add_clients, iface

from conftest import SetupRouter

IFACES = ["default_radio0", "guest2g", "default_radio1", "guest5g"]
MACS = [f"AA:BB:CC:00:00:0{i}" for i in range(6)]
ONLINE = [MACS[0], MACS[1], MACS[3], MACS[4]]


def entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str:
    found = er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)
    assert found is not None, f"no {domain} entity with unique id {unique_id}"
    return found


def state_of(hass: HomeAssistant, domain: str, unique_id: str) -> Any:
    state = hass.states.get(entity_id(hass, domain, unique_id))
    assert state is not None
    return state


def tracker_uid(entry: MockConfigEntry, mac: str) -> str:
    """A device tracker is registered per router: the router's entry id, the client's MAC."""
    return f"{entry.entry_id}_{mac}_tracker"


def registry_entries(hass: HomeAssistant, entry: MockConfigEntry) -> list[er.RegistryEntry]:
    return er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)


def expected_unique_ids(entry: MockConfigEntry, ifaces: list[str], macs: list[str], router_mode: bool = True) -> set[tuple[str, str]]:
    """The identity of every entity of a router: change one and users lose their entity history and customisations."""
    e = entry.entry_id
    ids = {("sensor", f"{e}_mode"), ("sensor", f"{e}_firmware_version"), ("button", f"{e}_reboot")}
    for name in ifaces:
        ids |= {("switch", f"{e}_wifi_{name}"), ("text", f"{e}_wifi_{name}_ssid"), ("text", f"{e}_wifi_{name}_key")}
    if router_mode:
        ids |= {("sensor", f"{e}_wan_speed_rx"), ("sensor", f"{e}_wan_speed_tx"), ("sensor", f"{e}_connected_clients")}
        for mac in macs:
            ids |= {
                ("sensor", f"{e}_{mac}_rx"), ("sensor", f"{e}_{mac}_tx"), ("switch", f"{e}_{mac}_blocked"),
                ("device_tracker", f"{e}_{mac}_tracker"),
            }  # fmt: skip
    return ids


# ===================================================================================== what is created
async def test_router_mode_creates_every_expected_entity(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    actual = {(e.domain, e.unique_id) for e in registry_entries(hass, entry)}
    assert actual == expected_unique_ids(entry, IFACES, MACS)
    assert len(actual) == 3 + 3 + 4 * 3 + 6 * 4, "3 router sensors + reboot-level, 3 WAN/client-count entities, 12 Wi-Fi entities, 24 per-client"


async def test_the_unique_ids_are_exactly_these(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Pinned on purpose, written out by hand. A changed unique id orphans the entity a user has automations, dashboards and history on."""
    e = entry.entry_id
    live = {(x.domain, x.unique_id) for x in registry_entries(hass, entry)}

    def of(domain: str) -> set[str]:
        return {u for d, u in live if d == domain}

    assert of("sensor") == (
        {f"{e}_mode", f"{e}_firmware_version", f"{e}_wan_speed_rx", f"{e}_wan_speed_tx", f"{e}_connected_clients"}
        | {f"{e}_{mac}_{d}" for mac in MACS for d in ("rx", "tx")}
    )
    assert of("switch") == {f"{e}_wifi_{n}" for n in IFACES} | {f"{e}_{mac}_blocked" for mac in MACS}
    assert of("text") == {f"{e}_wifi_{n}_{field}" for n in IFACES for field in ("ssid", "key")}
    assert of("button") == {f"{e}_reboot"}
    assert of("device_tracker") == {f"{e}_{mac}_tracker" for mac in MACS}, "scoped to the router, so two routers can both know a device"


async def test_the_unique_ids_do_not_change_when_the_entry_is_reloaded(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    before = {(e.domain, e.unique_id): e.entity_id for e in registry_entries(hass, entry)}
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    after = {(e.domain, e.unique_id): e.entity_id for e in registry_entries(hass, entry)}
    assert after == before


async def test_ap_mode_creates_none_of_the_per_client_entities(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    entry = await setup_router(HOST2, mode="ap", mac="94:83:C4:00:00:09", clients=8)
    actual = {(e.domain, e.unique_id) for e in registry_entries(hass, entry)}
    assert actual == expected_unique_ids(entry, IFACES, [], router_mode=False)
    assert not any(":" in unique_id for _, unique_id in actual), "no entity carries a client MAC"
    assert hass.states.async_all("device_tracker") == []
    assert state_of(hass, "sensor", f"{entry.entry_id}_mode").state == "ap"


@pytest.mark.parametrize(
    ("layout", "ifaces"),
    [
        ("tri", ["default_radio0", "guest2g", "default_radio1", "guest5g", "default_radio2"]),
        ("single", ["default_radio0"]),
        ("no_guest", ["default_radio0", "default_radio1"]),
    ],
)
async def test_wifi_entities_follow_the_routers_interfaces(hass: HomeAssistant, setup_router: SetupRouter, layout: str, ifaces: list[str]) -> None:
    entry = await setup_router(HOST2, wifi=layout, mac="94:83:C4:00:00:09")
    actual = {(e.domain, e.unique_id) for e in registry_entries(hass, entry) if "_wifi_" in e.unique_id}
    e = entry.entry_id
    assert actual == {(d, f"{e}_wifi_{n}{s}") for n in ifaces for d, s in (("switch", ""), ("text", "_ssid"), ("text", "_key"))}


async def test_a_router_without_wifi_still_loads(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    from testkit import remove_method

    router = world.add(HOST2, mac="94:83:C4:00:00:09")
    remove_method(router, "wifi.get_config")
    entry = await setup_router(HOST2, router=router)
    uids = {u.unique_id for u in registry_entries(hass, entry)}
    assert not any("_wifi_" in u for u in uids) and f"{entry.entry_id}_reboot" in uids


# ===================================================================================== sensors
async def test_router_sensors(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    e = entry.entry_id
    assert state_of(hass, "sensor", f"{e}_mode").state == "router"
    assert state_of(hass, "sensor", f"{e}_firmware_version").state == "4.8.3"
    assert state_of(hass, "sensor", f"{e}_connected_clients").state == "4"
    rx, tx = state_of(hass, "sensor", f"{e}_wan_speed_rx"), state_of(hass, "sensor", f"{e}_wan_speed_tx")
    assert (float(rx.state), float(tx.state)) == (12000.0, 1200.0)
    for state in (rx, tx):
        assert state.attributes["unit_of_measurement"] == "B/s"
        assert state.attributes["device_class"] == "data_rate" and state.attributes["state_class"] == "measurement"


async def test_mode_and_firmware_are_diagnostic(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    registry = er.async_get(hass)
    for suffix in ("mode", "firmware_version"):
        assert registry.async_get(entity_id(hass, "sensor", f"{entry.entry_id}_{suffix}")).entity_category is er.EntityCategory.DIAGNOSTIC
    assert registry.async_get(entity_id(hass, "sensor", f"{entry.entry_id}_wan_speed_rx")).entity_category is None


async def test_per_client_speed_sensors(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    e = entry.entry_id
    expected = {MACS[0]: (1000, 100), MACS[1]: (2000, 200), MACS[3]: (4000, 400), MACS[4]: (5000, 500), MACS[2]: (0, 0), MACS[5]: (0, 0)}
    for mac, (rx, tx) in expected.items():
        assert float(state_of(hass, "sensor", f"{e}_{mac}_rx").state) == rx
        assert float(state_of(hass, "sensor", f"{e}_{mac}_tx").state) == tx
    assert state_of(hass, "sensor", f"{e}_{MACS[0]}_rx").attributes["unit_of_measurement"] == "B/s"


async def test_sensors_follow_the_router(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator, router: MockRouter) -> None:
    e = entry.entry_id
    router.clients[2]["online"] = True
    router.clients[0]["online"] = False
    await coordinator.async_refresh()
    assert state_of(hass, "sensor", f"{e}_connected_clients").state == "4"  # one came, one went
    assert float(state_of(hass, "sensor", f"{e}_{MACS[2]}_rx").state) == 3000.0
    assert float(state_of(hass, "sensor", f"{e}_{MACS[0]}_rx").state) == 0.0
    assert float(state_of(hass, "sensor", f"{e}_wan_speed_rx").state) == 14000.0


async def test_sensor_states_do_not_turn_to_garbage_for_missing_data(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    from testkit import remove_method

    router = world.add(HOST2, mac="94:83:C4:00:00:09")
    remove_method(router, "clients.get_wan_speed")
    entry = await setup_router(HOST2, router=router)
    assert state_of(hass, "sensor", f"{entry.entry_id}_wan_speed_rx").state == STATE_UNKNOWN


# ===================================================================================== device trackers
async def test_trackers_report_who_is_connected(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter) -> None:
    for mac in MACS:
        state = state_of(hass, "device_tracker", tracker_uid(entry, mac))
        assert state.state == ("home" if mac in ONLINE else "not_home")
        assert state.attributes["source_type"] == "router"
    first = state_of(hass, "device_tracker", tracker_uid(entry, MACS[0]))
    assert first.attributes["ip"] == "192.168.8.10" and first.attributes["mac"] == MACS[0]
    assert first.attributes["host_name"] == "iPhone-Ann"


async def test_tracker_entity_ids_are_readable(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """A new install gets device_tracker.iphone_ann, not device_tracker.woow_glinet_aa_bb_cc_00_00_00."""
    registry = er.async_get(hass)
    ids = {mac: registry.async_get_entity_id("device_tracker", DOMAIN, tracker_uid(entry, mac)) for mac in MACS}
    assert ids == {
        MACS[0]: "device_tracker.iphone_ann", MACS[1]: "device_tracker.macbook_pro", MACS[2]: "device_tracker.living_room_tv",
        MACS[3]: "device_tracker.hue_bridge", MACS[4]: "device_tracker.esp32_kitchen", MACS[5]: "device_tracker.hp_laserjet",
    }  # fmt: skip
    assert hass.states.get("device_tracker.iphone_ann").attributes["friendly_name"] == "iPhone-Ann"


async def test_tracker_entity_ids_do_not_collide_between_routers(hass: HomeAssistant, entry: MockConfigEntry, setup_router: SetupRouter) -> None:
    second = await setup_router(HOST2, mac="94:83:C4:00:00:02")
    registry = er.async_get(hass)
    first_id = registry.async_get_entity_id("device_tracker", DOMAIN, tracker_uid(entry, MACS[0]))
    second_id = registry.async_get_entity_id("device_tracker", DOMAIN, tracker_uid(second, MACS[0]))
    assert first_id == "device_tracker.iphone_ann" and second_id == "device_tracker.iphone_ann_2"


async def test_trackers_follow_the_router(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator, router: MockRouter) -> None:
    router.clients[2]["online"] = True
    router.clients[1]["online"] = False
    await coordinator.async_refresh()
    assert state_of(hass, "device_tracker", tracker_uid(entry, MACS[2])).state == "home"
    assert state_of(hass, "device_tracker", tracker_uid(entry, MACS[1])).state == "not_home"


async def test_trackers_follow_a_renamed_client(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                router: MockRouter) -> None:
    router.configure(client_names=["Renamed phone"])
    await coordinator.async_refresh()
    state = state_of(hass, "device_tracker", tracker_uid(entry, MACS[0]))
    assert state.attributes["host_name"] == "Renamed phone"
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, f"client_{MACS[0]}"), entry.entry_id)
    assert device.name == "Renamed phone"


async def test_trackers_live_on_the_client_devices(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    client_device = devices.async_get_device_by_identifier((DOMAIN, f"client_{MACS[0]}"), entry.entry_id)
    for domain, unique_id in (("device_tracker", tracker_uid(entry, MACS[0])), ("sensor", f"{entry.entry_id}_{MACS[0]}_rx"),
                              ("switch", f"{entry.entry_id}_{MACS[0]}_blocked")):  # fmt: skip
        assert registry.async_get(entity_id(hass, domain, unique_id)).device_id == client_device.id, f"{domain} is on the client device"


async def test_trackers_are_enabled_by_default(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    registry = er.async_get(hass)
    assert all(registry.async_get(entity_id(hass, "device_tracker", tracker_uid(entry, mac))).disabled_by is None for mac in MACS)


async def test_the_tracker_entity_describes_itself(coordinator: GlinetCoordinator) -> None:
    from homeassistant.components.device_tracker import SourceType

    from custom_components.woow_glinet.device_tracker import GlinetClientTracker

    tracker = GlinetClientTracker(coordinator, MACS[0])
    assert tracker.unique_id == f"{coordinator.config_entry.entry_id}_{MACS[0]}_tracker", "scoped to the router (ScannerEntity would say: the MAC)"
    assert (tracker.mac_address, tracker.ip_address, tracker.hostname, tracker.is_connected) == (MACS[0], "192.168.8.10", "iPhone-Ann", True)
    assert tracker.source_type is SourceType.ROUTER
    info = tracker.device_info
    assert info is not None, "ScannerEntity would say None; ours ties the tracker to the client's device"
    assert info["identifiers"] == {(DOMAIN, f"client_{MACS[0]}")} and info["via_device_id"] == coordinator.router_device_id and info["name"] == "iPhone-Ann"
    assert tracker.entity_registry_enabled_default is True

    ghost = GlinetClientTracker(coordinator, "DE:AD:BE:EF:00:09")  # a client the router no longer lists
    assert (ghost.is_connected, ghost.ip_address, ghost.hostname) == (False, None, None)
    assert ghost.mac_address == "DE:AD:BE:EF:00:09" and ghost.device_info["name"] == "DE:AD:BE:EF:00:09"


async def test_two_routers_that_know_the_same_client_each_get_a_tracker(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld,
                                                                        caplog: pytest.LogCaptureFixture) -> None:
    first = await setup_router(HOST)
    second = await setup_router(HOST2, mac="94:83:C4:00:00:02")  # (the mock numbers its clients the same way on every router)
    for entry in (first, second):
        trackers = [e for e in registry_entries(hass, entry) if e.domain == "device_tracker"]
        assert len(trackers) == 6, f"{entry.entry_id} ended up with {len(trackers)} trackers"
    assert "does not generate unique IDs" not in caplog.text
    assert len(hass.states.async_all("device_tracker")) == 12


async def test_a_client_that_roams_to_the_second_router_is_home_there_only(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    first = await setup_router(HOST)
    second = await setup_router(HOST2, mac="94:83:C4:00:00:02")
    world.routers[HOST].clients[0]["online"] = False
    world.routers[HOST2].clients[0]["online"] = True
    await first.runtime_data.coordinator.async_refresh()
    await second.runtime_data.coordinator.async_refresh()
    assert state_of(hass, "device_tracker", tracker_uid(first, MACS[0])).state == "not_home"
    assert state_of(hass, "device_tracker", tracker_uid(second, MACS[0])).state == "home"


# ===================================================================================== switches
async def test_wifi_switches_show_whether_the_interface_is_on(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    e = entry.entry_id
    states = {name: state_of(hass, "switch", f"{e}_wifi_{name}").state for name in IFACES}
    assert states == {"default_radio0": STATE_ON, "guest2g": STATE_OFF, "default_radio1": STATE_ON, "guest5g": STATE_OFF}


async def test_wifi_switch_turns_the_interface_on_and_off(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter, activity: Any,
                                                          hass_admin_user: MockUser) -> None:
    switch = entity_id(hass, "switch", f"{entry.entry_id}_wifi_guest2g")

    await hass.services.async_call("switch", "turn_on", {"entity_id": switch}, blocking=True, context=Context(user_id=hass_admin_user.id))
    assert iface(router, "guest2g")["enabled"] is True
    assert hass.states.get(switch).state == STATE_ON, "the state follows without waiting for the next poll"
    last = activity.recent(1)[0]
    assert (last["msg"], last["channel"], last["user"]) == ("wifi_on", "entity", hass_admin_user.name)

    await hass.services.async_call("switch", "turn_off", {"entity_id": switch}, blocking=True)
    assert iface(router, "guest2g")["enabled"] is False
    assert hass.states.get(switch).state == STATE_OFF
    assert activity.recent(1)[0]["msg"] == "wifi_off"


async def test_wifi_switch_toggle(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter) -> None:
    switch = entity_id(hass, "switch", f"{entry.entry_id}_wifi_default_radio1")
    await hass.services.async_call("switch", "toggle", {"entity_id": switch}, blocking=True)
    assert iface(router, "default_radio1")["enabled"] is False


async def test_wifi_switch_error_reaches_the_caller(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter) -> None:
    router.configure(error_methods={"wifi.set_config": (-32602, "Invalid params")})
    switch = entity_id(hass, "switch", f"{entry.entry_id}_wifi_guest2g")
    with pytest.raises(HomeAssistantError, match="Invalid params"):
        await hass.services.async_call("switch", "turn_on", {"entity_id": switch}, blocking=True)
    assert hass.states.get(switch).state == STATE_OFF


async def test_block_switches(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter, activity: Any) -> None:
    e = entry.entry_id
    for mac in MACS:
        assert state_of(hass, "switch", f"{e}_{mac}_blocked").state == STATE_OFF
    switch = entity_id(hass, "switch", f"{e}_{MACS[1]}_blocked")

    await hass.services.async_call("switch", "turn_on", {"entity_id": switch}, blocking=True)
    assert router.black_mac == [MACS[1]]
    assert hass.states.get(switch).state == STATE_ON
    assert activity.recent(1)[0]["msg"] == "blocked" and activity.recent(1)[0]["channel"] == "entity"

    await hass.services.async_call("switch", "turn_off", {"entity_id": switch}, blocking=True)
    assert router.black_mac == []
    assert hass.states.get(switch).state == STATE_OFF
    assert activity.recent(1)[0]["msg"] == "unblocked"


async def test_block_switch_for_an_offline_device(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter) -> None:
    switch = entity_id(hass, "switch", f"{entry.entry_id}_{MACS[2]}_blocked")
    await hass.services.async_call("switch", "turn_on", {"entity_id": switch}, blocking=True)
    assert router.black_mac == [MACS[2]]


async def test_block_switch_shows_a_device_that_is_already_blocked(hass: HomeAssistant, setup_router: SetupRouter) -> None:
    entry = await setup_router(HOST2, mac="94:83:C4:00:00:09", black_mac=[MACS[3]])
    assert state_of(hass, "switch", f"{entry.entry_id}_{MACS[3]}_blocked").state == STATE_ON
    assert state_of(hass, "switch", f"{entry.entry_id}_{MACS[4]}_blocked").state == STATE_OFF


async def test_block_switch_refuses_in_white_list_mode(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                       router: MockRouter) -> None:
    router.configure(blacklist_mode="white")
    await coordinator.async_refresh()
    switch = entity_id(hass, "switch", f"{entry.entry_id}_{MACS[1]}_blocked")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("switch", "turn_on", {"entity_id": switch}, blocking=True)
    assert router.black_mac == [] and router.white_mac == []


async def test_two_block_switches_turned_off_together(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                      router: MockRouter) -> None:
    """An automation unblocking several devices at once: all of them must end up unblocked."""
    router.configure(black_mac=[MACS[0], MACS[1], MACS[3]])
    await coordinator.async_refresh()
    switches = [entity_id(hass, "switch", f"{entry.entry_id}_{mac}_blocked") for mac in (MACS[0], MACS[1], MACS[3])]
    await hass.services.async_call("switch", "turn_off", {"entity_id": switches}, blocking=True)
    assert router.black_mac == []


# ===================================================================================== text: SSID
async def test_ssid_text_shows_and_changes_the_name(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter, activity: Any) -> None:
    ssid = entity_id(hass, "text", f"{entry.entry_id}_wifi_default_radio0_ssid")
    assert hass.states.get(ssid).state == "MOCK-8f2"
    assert hass.states.get(ssid).attributes["min"] == 1 and hass.states.get(ssid).attributes["max"] == 32

    await hass.services.async_call("text", "set_value", {"entity_id": ssid, "value": "Home-WiFi"}, blocking=True)

    assert iface(router, "default_radio0")["ssid"] == "Home-WiFi"
    assert hass.states.get(ssid).state == "Home-WiFi"
    assert activity.recent(1)[0]["msg"] == "wifi_ssid" and activity.recent(1)[0]["channel"] == "entity"


async def test_ssid_text_refuses_what_the_router_would_not_take(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter) -> None:
    ssid = entity_id(hass, "text", f"{entry.entry_id}_wifi_default_radio0_ssid")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("text", "set_value", {"entity_id": ssid, "value": "客" * 11}, blocking=True)  # 33 bytes, 11 characters
    assert iface(router, "default_radio0")["ssid"] == "MOCK-8f2"


async def test_ssid_text_with_chinese_characters(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter) -> None:
    ssid = entity_id(hass, "text", f"{entry.entry_id}_wifi_guest2g_ssid")
    await hass.services.async_call("text", "set_value", {"entity_id": ssid, "value": "渥屋訪客"}, blocking=True)
    assert iface(router, "guest2g")["ssid"] == "渥屋訪客" and hass.states.get(ssid).state == "渥屋訪客"


# ===================================================================================== text: the Wi-Fi password is write-only
def key_unique_id(entry: MockConfigEntry, name: str = "default_radio0") -> str:
    return f"{entry.entry_id}_wifi_{name}_key"


async def test_password_entities_start_disabled(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    registry = er.async_get(hass)
    for name in IFACES:
        found = registry.async_get(entity_id(hass, "text", key_unique_id(entry, name)))
        assert found.disabled_by is RegistryEntryDisabler.INTEGRATION, f"{name}: new installs do not get a password entity"
        assert hass.states.get(found.entity_id) is None
    ssid = registry.async_get(entity_id(hass, "text", f"{entry.entry_id}_wifi_default_radio0_ssid"))
    assert ssid.disabled_by is None, "only the password is opt-in"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_enabled_password_entities_do_not_reveal_the_password_by_default(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    for name in IFACES:
        state = state_of(hass, "text", key_unique_id(entry, name))
        assert state.state == STATE_UNKNOWN
        assert WIFI_KEY not in json.dumps(state.as_dict(), default=str)
    secrets = [s for s in hass.states.async_all() if WIFI_KEY in json.dumps(s.as_dict(), default=str)]
    assert secrets == [], "the password appears in no state of any entity"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_password_can_still_be_written(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter, world: RouterWorld,
                                             activity: Any) -> None:
    key = entity_id(hass, "text", key_unique_id(entry))
    await hass.services.async_call("text", "set_value", {"entity_id": key, "value": "a-new-wifi-password"}, blocking=True)

    assert iface(router, "default_radio0")["key"] == "a-new-wifi-password"
    assert world.calls("wifi.set_config")[-1].args == {"iface_name": "default_radio0", "key": "a-new-wifi-password"}
    assert hass.states.get(key).state == STATE_UNKNOWN, "and it still reads back as unknown"
    everything = json.dumps([s.as_dict() for s in hass.states.async_all()], default=str) + json.dumps(activity.recent())
    assert "a-new-wifi-password" not in everything and WIFI_KEY not in everything
    assert activity.recent(1)[0]["msg"] == "wifi_key" and activity.recent(1)[0]["channel"] == "entity"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("value", "error"),
    [
        ("short", ValueError),  # Home Assistant's own min/max check on the entity (8..63) ...
        ("x" * 64, ValueError),
        ("tab\there-password", HomeAssistantError),  # ... and the integration's check (no control characters) behind it
        ("密" * 22, HomeAssistantError),  # 22 characters pass HA's check, but they are 66 bytes
    ],
)
async def test_password_entity_refuses_bad_values(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter, value: str, error: type) -> None:
    key = entity_id(hass, "text", key_unique_id(entry))
    with pytest.raises(error):
        await hass.services.async_call("text", "set_value", {"entity_id": key, "value": value}, blocking=True)
    assert iface(router, "default_radio0")["key"] == WIFI_KEY


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_the_option_makes_the_password_readable(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], {OPTION_EXPOSE_WIFI_PASSWORDS: True})
    await hass.async_block_till_done()

    assert entry.options[OPTION_EXPOSE_WIFI_PASSWORDS] is True
    for name in IFACES:
        assert state_of(hass, "text", key_unique_id(entry, name)).state == WIFI_KEY

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], {OPTION_EXPOSE_WIFI_PASSWORDS: False})
    await hass.async_block_till_done()
    assert state_of(hass, "text", key_unique_id(entry)).state == STATE_UNKNOWN, "and turning it off hides it again"


async def test_the_option_alone_does_not_enable_the_entity(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    hass.config_entries.async_update_entry(entry, options={OPTION_EXPOSE_WIFI_PASSWORDS: True})
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    found = er.async_get(hass).async_get(entity_id(hass, "text", key_unique_id(entry)))
    assert found.disabled_by is RegistryEntryDisabler.INTEGRATION and hass.states.get(found.entity_id) is None


async def test_a_user_who_enables_the_entity_and_the_option_sees_the_password(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    registry = er.async_get(hass)
    key = entity_id(hass, "text", key_unique_id(entry))
    registry.async_update_entity(key, disabled_by=None)
    hass.config_entries.async_update_entry(entry, options={OPTION_EXPOSE_WIFI_PASSWORDS: True})
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(key).state == WIFI_KEY


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_the_password_is_not_in_any_state_attribute_or_event(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    events = []
    hass.bus.async_listen("state_changed", lambda e: events.append(e.data["new_state"].as_dict() if e.data["new_state"] else None))
    await entry.runtime_data.coordinator.async_refresh()
    assert WIFI_KEY not in json.dumps(events, default=str)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("key", "shown"),
    [("", None), ("1234567", None), ("12345678", "12345678"), ("a-normal-password", "a-normal-password")],
    ids=["open-network", "too-short-for-wpa", "shortest-allowed", "normal"],
)
async def test_the_password_of_an_open_or_short_key_network_can_be_shown(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld,
                                                                         caplog: pytest.LogCaptureFixture, key: str, shown: str | None) -> None:
    """With the option on, a network without a password (a common open guest Wi-Fi) must not break its entity."""
    router = world.add(HOST2, mac="94:83:C4:00:00:09")
    iface(router, "guest2g").update(key=key, encryption="none" if not key else "psk2")
    data = {"host": HOST2, "username": "root", "password": "mockpass", "scheme": "https", "verify_ssl": False}
    entry = await setup_router(HOST2, router=router, entry=MockConfigEntry(
        domain=DOMAIN, unique_id="94:83:C4:00:00:09", title="Open", options={OPTION_EXPOSE_WIFI_PASSWORDS: True}, data=data))  # fmt: skip
    assert "Error adding entity" not in caplog.text and "too short" not in caplog.text
    state = hass.states.get(entity_id(hass, "text", key_unique_id(entry, "guest2g")))
    assert state is not None
    assert state.state == (STATE_UNKNOWN if shown is None else shown)
    assert state_of(hass, "text", key_unique_id(entry, "default_radio0")).state == WIFI_KEY, "the other networks are unaffected"


# ===================================================================================== button
async def test_reboot_button(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter, activity: Any, hass_admin_user: MockUser) -> None:
    button = entity_id(hass, "button", f"{entry.entry_id}_reboot")
    assert hass.states.get(button).attributes["device_class"] == "restart"

    await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True, context=Context(user_id=hass_admin_user.id))

    assert router.calls["system.reboot"] == 1
    last = activity.recent(1)[0]
    assert (last["msg"], last["channel"], last["user"], last["ok"]) == ("rebooted", "entity", hass_admin_user.name, True)


async def test_reboot_button_error(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter) -> None:
    router.configure(error_methods={"system.reboot": (-5, "Boom")})
    button = entity_id(hass, "button", f"{entry.entry_id}_reboot")
    with pytest.raises(HomeAssistantError, match="Boom"):
        await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)


async def test_reboot_button_where_the_router_hangs_up(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter) -> None:
    router.reboot_style = "drop"
    button = entity_id(hass, "button", f"{entry.entry_id}_reboot")
    await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
    assert router.calls["system.reboot"] == 1


# ===================================================================================== devices
async def test_router_level_entities_are_on_the_router_device(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator) -> None:
    registry = er.async_get(hass)
    e = entry.entry_id
    for domain, unique_id in (("sensor", f"{e}_mode"), ("sensor", f"{e}_wan_speed_rx"), ("button", f"{e}_reboot"),
                              ("switch", f"{e}_wifi_guest2g"), ("text", f"{e}_wifi_guest2g_ssid")):  # fmt: skip
        assert registry.async_get(entity_id(hass, domain, unique_id)).device_id == coordinator.router_device_id


async def test_the_router_device_description(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
    assert (device.manufacturer, device.model, device.name, device.sw_version) == ("GL.iNet", "GL-MOCK1200", "GL-MOCK1200", "4.8.3")


# ===================================================================================== names
async def test_every_translation_key_has_a_name_in_both_languages(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    from pathlib import Path

    translations = {
        lang: json.loads((Path(__file__).parents[1] / "custom_components/woow_glinet/translations" / f"{lang}.json").read_text(encoding="utf-8"))
        for lang in ("en", "zh-Hant")
    }
    used = {(e.domain, e.translation_key) for e in registry_entries(hass, entry) if e.translation_key}
    assert len(used) >= 10, "the entities are named through translation keys"
    for lang, data in translations.items():
        for domain, key in used:
            assert data["entity"][domain][key]["name"], f"{lang}: entity.{domain}.{key}.name is missing"


async def test_entities_have_readable_names(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    for state in hass.states.async_all():
        name = state.attributes.get("friendly_name", "")
        assert name and "{" not in name and "}" not in name, f"{state.entity_id}: {name!r}"
    assert state_of(hass, "switch", f"{entry.entry_id}_wifi_default_radio0").attributes["friendly_name"] == "GL-MOCK1200 Wi-Fi MOCK-8f2"
    assert state_of(hass, "sensor", f"{entry.entry_id}_wan_speed_rx").attributes["friendly_name"] == "GL-MOCK1200 WAN download speed"
    assert state_of(hass, "button", f"{entry.entry_id}_reboot").attributes["friendly_name"] == "GL-MOCK1200 Reboot"
    assert state_of(hass, "text", f"{entry.entry_id}_wifi_guest5g_ssid").attributes["friendly_name"] == "GL-MOCK1200 Wi-Fi MOCK-8f2-5G-Guest SSID"


async def test_client_entities_are_named_after_the_client(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator) -> None:
    """(After the first poll: until then the tracker platform may have named the device by its MAC, see test_coordinator.py.)"""
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert state_of(hass, "sensor", f"{entry.entry_id}_{MACS[0]}_rx").attributes["friendly_name"] == "iPhone-Ann Download speed"
    assert state_of(hass, "sensor", f"{entry.entry_id}_{MACS[1]}_tx").attributes["friendly_name"] == "MacBook Pro Upload speed"
    assert state_of(hass, "switch", f"{entry.entry_id}_{MACS[3]}_blocked").attributes["friendly_name"] == "Hue Bridge Block"


async def test_wifi_entity_names_follow_a_renamed_ssid(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                       router: MockRouter) -> None:
    """The entities are 'named after the SSID': when it changes the names follow, without a reload."""
    router.configure(ssids={"default_radio0": "Renamed-Net"})
    await coordinator.async_refresh()
    e = entry.entry_id
    assert state_of(hass, "switch", f"{e}_wifi_default_radio0").attributes["friendly_name"] == "GL-MOCK1200 Wi-Fi Renamed-Net"
    assert state_of(hass, "text", f"{e}_wifi_default_radio0_ssid").attributes["friendly_name"] == "GL-MOCK1200 Wi-Fi Renamed-Net SSID"
    assert state_of(hass, "text", f"{e}_wifi_default_radio0_ssid").state == "Renamed-Net"
    assert state_of(hass, "switch", f"{e}_wifi_guest2g").attributes["friendly_name"] == "GL-MOCK1200 Wi-Fi MOCK-8f2-Guest", "the others keep theirs"

    router.configure(ssids={"default_radio0": "Third-Name"})  # and again
    await coordinator.async_refresh()
    assert state_of(hass, "switch", f"{e}_wifi_default_radio0").attributes["friendly_name"] == "GL-MOCK1200 Wi-Fi Third-Name"


async def test_the_name_changes_when_the_integration_itself_renames_the_ssid(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    ssid = entity_id(hass, "text", f"{entry.entry_id}_wifi_guest5g_ssid")
    await hass.services.async_call("text", "set_value", {"entity_id": ssid, "value": "Visitors"}, blocking=True)
    assert hass.states.get(ssid).attributes["friendly_name"] == "GL-MOCK1200 Wi-Fi Visitors SSID"
    assert state_of(hass, "switch", f"{entry.entry_id}_wifi_guest5g").attributes["friendly_name"] == "GL-MOCK1200 Wi-Fi Visitors"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_the_password_entity_follows_the_ssid_too(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                        router: MockRouter) -> None:
    router.configure(ssids={"default_radio1": "Fast-Net"})
    await coordinator.async_refresh()
    assert state_of(hass, "text", key_unique_id(entry, "default_radio1")).attributes["friendly_name"] == "GL-MOCK1200 Wi-Fi Fast-Net password"


async def test_an_unchanged_ssid_keeps_the_cached_name_untouched(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator) -> None:
    switch = state_of(hass, "switch", f"{entry.entry_id}_wifi_default_radio0")
    for _ in range(3):
        await coordinator.async_refresh()
    assert state_of(hass, "switch", f"{entry.entry_id}_wifi_default_radio0").attributes["friendly_name"] == switch.attributes["friendly_name"]


async def test_wifi_entity_names_are_right_after_a_reload(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter) -> None:
    router.configure(ssids={"default_radio0": "Renamed-Net"})
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert state_of(hass, "switch", f"{entry.entry_id}_wifi_default_radio0").attributes["friendly_name"] == "GL-MOCK1200 Wi-Fi Renamed-Net"


# ===================================================================================== availability and growth
async def test_everything_goes_unavailable_when_the_router_stops_answering(hass: HomeAssistant, entry: MockConfigEntry,
                                                                           coordinator: GlinetCoordinator, world: RouterWorld) -> None:
    world.disconnect(HOST)
    await coordinator.async_refresh()
    states = [s for s in hass.states.async_all() if s.entity_id.split(".")[0] in {"sensor", "switch", "button", "text", "device_tracker"}]
    assert states and all(s.state == STATE_UNAVAILABLE for s in states)

    world.reconnect(HOST)
    await coordinator.async_refresh()
    assert not any(s.state == STATE_UNAVAILABLE for s in hass.states.async_all())


async def test_a_new_client_gets_its_entities(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator, router: MockRouter) -> None:
    add_clients(router, 8)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    e = entry.entry_id
    new = "AA:BB:CC:00:00:07"
    assert state_of(hass, "sensor", f"{e}_{new}_rx").state != STATE_UNAVAILABLE
    assert state_of(hass, "switch", f"{e}_{new}_blocked").state == STATE_OFF
    assert state_of(hass, "device_tracker", tracker_uid(entry, new)).state in ("home", "not_home")
    assert len([x for x in registry_entries(hass, entry) if x.domain == "device_tracker"]) == 8


async def test_a_client_is_not_added_twice(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator) -> None:
    before = len(registry_entries(hass, entry))
    for _ in range(3):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert len(registry_entries(hass, entry)) == before


async def test_a_client_that_disappears_goes_unavailable(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                         router: MockRouter) -> None:
    del router.clients[5]  # the router forgot it
    await coordinator.async_refresh()
    e = entry.entry_id
    assert state_of(hass, "sensor", f"{e}_{MACS[5]}_rx").state == STATE_UNAVAILABLE
    assert state_of(hass, "switch", f"{e}_{MACS[5]}_blocked").state == STATE_UNAVAILABLE
    assert state_of(hass, "sensor", f"{e}_{MACS[4]}_rx").state != STATE_UNAVAILABLE


async def test_a_wifi_interface_that_disappears_goes_unavailable(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                                router: MockRouter) -> None:
    router.configure(wifi="no_guest")
    await coordinator.async_refresh()
    e = entry.entry_id
    assert state_of(hass, "switch", f"{e}_wifi_guest2g").state == STATE_UNAVAILABLE
    assert state_of(hass, "text", f"{e}_wifi_guest2g_ssid").state == STATE_UNAVAILABLE
    assert state_of(hass, "switch", f"{e}_wifi_default_radio0").state == STATE_ON


async def test_nothing_errors_while_running(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                            caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    for _ in range(3):
        await coordinator.async_refresh()
    await hass.async_block_till_done()
    bad = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR and "woow_glinet" in (r.name + r.getMessage())]
    assert bad == []


# ===================================================================================== a client the router no longer lists
async def test_entities_of_a_vanished_client_fall_back_to_the_mac(coordinator: GlinetCoordinator) -> None:
    from custom_components.woow_glinet.sensor import GlinetClientSpeedSensor
    from custom_components.woow_glinet.switch import GlinetClientBlockSwitch

    ghost = "DE:AD:BE:EF:00:09"
    sensor, switch = GlinetClientSpeedSensor(coordinator, ghost, "rx"), GlinetClientBlockSwitch(coordinator, ghost)
    assert sensor.native_value is None and switch.is_on is None
    assert sensor._client_name() == ghost, "the device is named by its MAC until the router tells a name"
    assert sensor.available is False and switch.available is False


# ===================================================================================== a router that remembers a lot of devices
async def test_a_router_with_hundreds_of_remembered_clients(hass: HomeAssistant, setup_router: SetupRouter) -> None:
    """GL.iNet routers keep every device they have ever seen: 300 clients is a normal home that has had many visitors."""
    from custom_components.woow_glinet.const import HISTORY_CLIENTS_MAX
    from custom_components.woow_glinet.feed import router_snapshot

    entry = await setup_router(HOST2, clients=300, mac="94:83:C4:00:00:09")
    coordinator = entry.runtime_data.coordinator
    entries = registry_entries(hass, entry)

    assert len([e for e in entries if e.domain == "device_tracker"]) == 300
    assert len([e for e in entries if e.domain == "sensor" and e.unique_id.endswith(("_rx", "_tx")) and ":" in e.unique_id]) == 600
    assert len([e for e in entries if e.domain == "switch" and e.unique_id.endswith("_blocked")]) == 300
    assert len(list(dr.async_get(hass).devices)) == 301, "the router and one device per client"
    assert len(coordinator.history.clients) <= HISTORY_CLIENTS_MAX, "the in-memory history stays bounded"
    snapshot = json.dumps(router_snapshot(coordinator, with_history=True))
    assert len(snapshot) < 500_000, "the panel's snapshot stays small enough to send on every connect"
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True


# ===================================================================================== odd Wi-Fi interface lists
@pytest.mark.parametrize("ifaces", [None, [None], [{"ssid": "no-name"}]], ids=["null", "null-item", "no-name"])
async def test_odd_wifi_interface_lists_do_not_break_the_wifi_platforms(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld,
                                                                        caplog: pytest.LogCaptureFixture, ifaces: Any) -> None:
    from testkit import override

    router = world.add(HOST2, mac="94:83:C4:00:00:09")
    override(router, "wifi.get_config", lambda p: {"res": [{"band": "2G", "ifaces": ifaces}]})
    entry = await setup_router(HOST2, router=router)
    assert state_of(hass, "sensor", f"{entry.entry_id}_mode").state == "router", "(the rest of the router is fine)"
    assert "Error while setting up" not in caplog.text
