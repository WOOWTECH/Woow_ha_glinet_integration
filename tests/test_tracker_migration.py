"""The device_tracker unique-id migration (__init__._async_scope_tracker_unique_ids).

Until 0.4.0 a tracker was registered under the bare MAC (Home Assistant's ScannerEntity derives its unique id from it),
so a second router that knew the same device got no tracker. Trackers are now `<entry id>_<MAC>_tracker`; on upgrade the
existing registry rows are renamed in place, so the entity ids, names, areas and history users built on them survive.

These tests build the situation of a real upgrade: the legacy rows exist BEFORE the entry is loaded.
"""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.woow_glinet import _async_scope_tracker_unique_ids
from custom_components.woow_glinet.const import DOMAIN
from testkit import HOST, HOST2, RouterWorld

from conftest import make_entry

MACS = [f"AA:BB:CC:00:00:0{i}" for i in range(6)]
ONLINE = [MACS[0], MACS[1], MACS[3], MACS[4]]


def legacy_row(hass: HomeAssistant, entry: MockConfigEntry | None, unique_id: str, object_id: str, *, domain: str = "device_tracker",
               platform: str = DOMAIN, **kwargs: Any) -> er.RegistryEntry:
    """A registry row as the previous version left it."""
    return er.async_get(hass).async_get_or_create(
        domain, platform, unique_id, config_entry=entry, suggested_object_id=object_id, **kwargs
    )


async def load(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


def rows(hass: HomeAssistant, entry: MockConfigEntry, domain: str = "device_tracker") -> dict[str, er.RegistryEntry]:
    return {r.unique_id: r for r in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id) if r.domain == domain}


@pytest.fixture
def legacy_entry(hass: HomeAssistant, world: RouterWorld) -> MockConfigEntry:
    """An entry that is in Home Assistant but not loaded yet, for a router that is reachable."""
    world.add(HOST)
    entry = make_entry(HOST)
    entry.add_to_hass(hass)
    return entry


# ===================================================================================== bare MAC -> scoped
async def test_legacy_trackers_are_renamed_in_place(hass: HomeAssistant, legacy_entry: MockConfigEntry) -> None:
    old = {mac: legacy_row(hass, legacy_entry, mac, f"legacy_phone_{i}") for i, mac in enumerate(MACS)}
    old_ids = {mac: row.entity_id for mac, row in old.items()}
    assert old_ids[MACS[0]] == "device_tracker.legacy_phone_0"

    await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()

    found = rows(hass, legacy_entry)
    assert set(found) == {f"{legacy_entry.entry_id}_{mac}_tracker" for mac in MACS}, "every unique id is scoped now, none is a bare MAC"
    for mac in MACS:
        row = found[f"{legacy_entry.entry_id}_{mac}_tracker"]
        assert row.entity_id == old_ids[mac], "the entity id (dashboards, automations, history) is kept"
        assert row.id == old[mac].id, "it is the very same registry entry"


async def test_the_live_entities_take_over_the_migrated_rows(hass: HomeAssistant, legacy_entry: MockConfigEntry) -> None:
    for i, mac in enumerate(MACS):
        legacy_row(hass, legacy_entry, mac, f"legacy_phone_{i}")

    await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()

    states = hass.states.async_all("device_tracker")
    assert len(states) == 6, "no second set of trackers next to the migrated ones"
    assert sorted(s.entity_id for s in states) == [f"device_tracker.legacy_phone_{i}" for i in range(6)]
    for i, mac in enumerate(MACS):
        assert hass.states.get(f"device_tracker.legacy_phone_{i}").state == ("home" if mac in ONLINE else "not_home")


async def test_what_the_user_customised_survives(hass: HomeAssistant, legacy_entry: MockConfigEntry) -> None:
    registry = er.async_get(hass)
    row = legacy_row(hass, legacy_entry, MACS[0], "my_phone")
    registry.async_update_entity(row.entity_id, name="Ann's phone", icon="mdi:cellphone")
    disabled = legacy_row(hass, legacy_entry, MACS[1], "old_laptop")
    registry.async_update_entity(disabled.entity_id, disabled_by=RegistryEntryDisabler.USER)

    await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()

    migrated = registry.async_get("device_tracker.my_phone")
    assert migrated.unique_id == f"{legacy_entry.entry_id}_{MACS[0]}_tracker"
    assert (migrated.name, migrated.icon) == ("Ann's phone", "mdi:cellphone")
    assert registry.async_get("device_tracker.old_laptop").disabled_by is RegistryEntryDisabler.USER, "a tracker the user switched off stays off"
    assert hass.states.get("device_tracker.old_laptop") is None


async def test_a_legacy_tracker_for_a_client_the_router_no_longer_lists(hass: HomeAssistant, legacy_entry: MockConfigEntry) -> None:
    gone = "AA:BB:CC:00:00:99"
    legacy_row(hass, legacy_entry, gone, "visitor_long_gone")

    await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()

    assert rows(hass, legacy_entry)[f"{legacy_entry.entry_id}_{gone}_tracker"].entity_id == "device_tracker.visitor_long_gone", "scoped too: it keeps its history"
    assert len(hass.states.async_all("device_tracker")) == 6, "but no live entity pretends to be it"


async def test_lowercase_legacy_ids_are_migrated_to_what_the_entity_will_use(hass: HomeAssistant, world: RouterWorld) -> None:
    """A router that reports lowercase MACs: the old row (lowercase) and the new entity id (lowercase) must still meet."""
    router = world.add(HOST)
    for client in router.clients:
        client["mac"] = client["mac"].lower()
    entry = make_entry(HOST)
    entry.add_to_hass(hass)
    legacy_row(hass, entry, MACS[0].lower(), "lowercase_phone")

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert rows(hass, entry)[f"{entry.entry_id}_{MACS[0].lower()}_tracker"].entity_id == "device_tracker.lowercase_phone"
    assert len(hass.states.async_all("device_tracker")) == 6
    assert hass.states.get("device_tracker.lowercase_phone").state == "home"


# ===================================================================================== idempotent
async def test_the_migration_is_idempotent(hass: HomeAssistant, legacy_entry: MockConfigEntry) -> None:
    for i, mac in enumerate(MACS):
        legacy_row(hass, legacy_entry, mac, f"legacy_phone_{i}")
    await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()
    snapshot = {r.unique_id: (r.id, r.entity_id) for r in rows(hass, legacy_entry).values()}

    await _async_scope_tracker_unique_ids(hass, legacy_entry)  # again, by hand
    await _async_scope_tracker_unique_ids(hass, legacy_entry)

    assert {r.unique_id: (r.id, r.entity_id) for r in rows(hass, legacy_entry).values()} == snapshot


async def test_reloading_never_renames_a_scoped_tracker_again(hass: HomeAssistant, legacy_entry: MockConfigEntry) -> None:
    for i, mac in enumerate(MACS):
        legacy_row(hass, legacy_entry, mac, f"legacy_phone_{i}")
    await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()
    before = {r.unique_id: r.entity_id for r in rows(hass, legacy_entry).values()}

    for _ in range(2):
        await hass.config_entries.async_reload(legacy_entry.entry_id)
        await hass.async_block_till_done()

    assert {r.unique_id: r.entity_id for r in rows(hass, legacy_entry).values()} == before
    assert len(hass.states.async_all("device_tracker")) == 6
    assert all(f"{legacy_entry.entry_id}_{legacy_entry.entry_id}" not in unique_id for unique_id in before), "never prefixed twice"


async def test_a_new_install_has_nothing_to_migrate(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert set(rows(hass, entry)) == {f"{entry.entry_id}_{mac}_tracker" for mac in MACS}
    assert len(hass.states.async_all("device_tracker")) == 6


async def test_the_migration_runs_before_the_trackers_are_added(hass: HomeAssistant, legacy_entry: MockConfigEntry,
                                                                caplog: pytest.LogCaptureFixture) -> None:
    for i, mac in enumerate(MACS):
        legacy_row(hass, legacy_entry, mac, f"legacy_phone_{i}")
    await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()
    assert "does not generate unique IDs" not in caplog.text and "already exists" not in caplog.text


# ===================================================================================== what must be left alone
async def test_other_rows_of_the_same_entry_are_left_alone(hass: HomeAssistant, legacy_entry: MockConfigEntry) -> None:
    untouched = {
        "not-a-mac": legacy_row(hass, legacy_entry, "not-a-mac", "odd_one"),
        "short": legacy_row(hass, legacy_entry, "AA:BB:CC:00:00", "short_one"),
        "too-long": legacy_row(hass, legacy_entry, "AA:BB:CC:00:00:00:01", "long_one"),
        "not-hex": legacy_row(hass, legacy_entry, "AA:BB:CC:00:00:0Z", "not_hex_one"),
        "dashes": legacy_row(hass, legacy_entry, "AA-BB-CC-00-00-00", "dashed_one"),
        "plain": legacy_row(hass, legacy_entry, "aabbcc000000", "plain_one"),
        "already-scoped": legacy_row(hass, legacy_entry, f"{legacy_entry.entry_id}_{MACS[5]}_tracker", "scoped_one"),
        "other-domain-sensor": legacy_row(hass, legacy_entry, MACS[2], "mac_sensor", domain="sensor"),
        "other-domain-switch": legacy_row(hass, legacy_entry, MACS[3], "mac_switch", domain="switch"),
    }
    before = {name: row.unique_id for name, row in untouched.items()}

    await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    assert {name: registry.async_get(row.entity_id).unique_id for name, row in untouched.items()} == before


async def test_another_entrys_legacy_rows_are_not_touched(hass: HomeAssistant, world: RouterWorld) -> None:
    """Each entry migrates only its own rows (two bare-MAC rows for the same MAC cannot coexist: that was the bug)."""
    entry_a, entry_b = make_entry(HOST), make_entry(HOST2, unique_id="94:83:C4:00:00:02", title="Other")
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    mine = legacy_row(hass, entry_a, MACS[0], "mine")
    theirs = legacy_row(hass, entry_b, MACS[1], "theirs")

    await _async_scope_tracker_unique_ids(hass, entry_a)

    registry = er.async_get(hass)
    assert registry.async_get(mine.entity_id).unique_id == f"{entry_a.entry_id}_{MACS[0]}_tracker"
    assert registry.async_get(theirs.entity_id).unique_id == MACS[1], "waits for its own entry"

    await _async_scope_tracker_unique_ids(hass, entry_b)
    assert registry.async_get(theirs.entity_id).unique_id == f"{entry_b.entry_id}_{MACS[1]}_tracker"
    assert registry.async_get(mine.entity_id).unique_id == f"{entry_a.entry_id}_{MACS[0]}_tracker"


async def test_another_integrations_tracker_with_the_same_mac_is_left_alone(hass: HomeAssistant, legacy_entry: MockConfigEntry) -> None:
    """The home's other trackers (nmap, UniFi ...) use bare MACs too: not ours to rename."""
    foreign_entry = MockConfigEntry(domain="other_tracker_integration", title="Other")
    foreign_entry.add_to_hass(hass)
    foreign = legacy_row(hass, foreign_entry, MACS[0], "same_phone_elsewhere", platform="other_tracker_integration")
    unattached = legacy_row(hass, None, MACS[1], "no_config_entry", platform="yet_another_integration")

    await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    assert registry.async_get(foreign.entity_id).unique_id == MACS[0]
    assert registry.async_get(unattached.entity_id).unique_id == MACS[1]


# ===================================================================================== two routers
async def test_after_the_upgrade_two_routers_that_share_a_client_each_keep_a_tracker(hass: HomeAssistant, world: RouterWorld) -> None:
    """The reason for the migration. Before: router A owned the bare-MAC rows and router B got none."""
    router_a, router_b = world.add(HOST), world.add(HOST2, mac="94:83:C4:00:00:02")
    entry_a = make_entry(HOST)
    entry_b = make_entry(HOST2, unique_id="94:83:C4:00:00:02", title="Second")
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    for i, mac in enumerate(MACS):
        legacy_row(hass, entry_a, mac, f"phone_{i}")  # what the old version registered (only A's; B's were refused)

    await hass.config_entries.async_setup(entry_a.entry_id)  # (sets the integration up, and with it every entry of it)
    await hass.async_block_till_done()
    assert entry_a.state is ConfigEntryState.LOADED and entry_b.state is ConfigEntryState.LOADED

    assert set(rows(hass, entry_a)) == {f"{entry_a.entry_id}_{mac}_tracker" for mac in MACS}
    assert set(rows(hass, entry_b)) == {f"{entry_b.entry_id}_{mac}_tracker" for mac in MACS}
    assert len(hass.states.async_all("device_tracker")) == 12
    assert rows(hass, entry_a)[f"{entry_a.entry_id}_{MACS[0]}_tracker"].entity_id == "device_tracker.phone_0", "A keeps its entity ids"

    router_a.clients[0]["online"] = False  # the phone moves to router B
    router_b.clients[0]["online"] = True
    await entry_a.runtime_data.coordinator.async_refresh()
    await entry_b.runtime_data.coordinator.async_refresh()
    assert hass.states.get("device_tracker.phone_0").state == "not_home"
    assert hass.states.get(rows(hass, entry_b)[f"{entry_b.entry_id}_{MACS[0]}_tracker"].entity_id).state == "home"


async def test_two_routers_with_legacy_rows_each_are_migrated_separately(hass: HomeAssistant, world: RouterWorld) -> None:
    world.add(HOST)
    world.add(HOST2, mac="94:83:C4:00:00:02")
    entry_a, entry_b = make_entry(HOST), make_entry(HOST2, unique_id="94:83:C4:00:00:02", title="Second")
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    legacy_row(hass, entry_a, MACS[0], "a_phone")
    legacy_row(hass, entry_b, MACS[1], "b_phone")

    await hass.config_entries.async_setup(entry_a.entry_id)  # (sets the integration up, and with it every entry of it)
    await hass.async_block_till_done()

    assert f"{entry_a.entry_id}_{MACS[0]}_tracker" in rows(hass, entry_a)
    assert f"{entry_b.entry_id}_{MACS[1]}_tracker" in rows(hass, entry_b)
    registry = er.async_get(hass)
    assert registry.async_get("device_tracker.a_phone").config_entry_id == entry_a.entry_id
    assert registry.async_get("device_tracker.b_phone").config_entry_id == entry_b.entry_id


# ===================================================================================== in AP mode
async def test_in_ap_mode_legacy_rows_are_still_scoped_but_nothing_is_added(hass: HomeAssistant, world: RouterWorld) -> None:
    world.add(HOST, mode="ap")
    entry = make_entry(HOST)
    entry.add_to_hass(hass)
    legacy_row(hass, entry, MACS[0], "ap_phone")

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert set(rows(hass, entry)) == {f"{entry.entry_id}_{MACS[0]}_tracker"}
    assert rows(hass, entry)[f"{entry.entry_id}_{MACS[0]}_tracker"].entity_id == "device_tracker.ap_phone"
    assert hass.states.async_all("device_tracker") == [], "no per-client entities in AP mode"
