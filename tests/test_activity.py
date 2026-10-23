"""activity.py: the ring buffer of who-changed-what, its persistence, live listeners and user lookup."""

from __future__ import annotations

import ast
import inspect
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Context, HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockUser, async_fire_time_changed

from custom_components.woow_glinet import actions as actions_module
from custom_components.woow_glinet.activity import MESSAGES, SAVE_DELAY, Activity, ActivityLog, Origin, summarize
from custom_components.woow_glinet.const import ACTIVITY_KEEP, DOMAIN

STORE_KEY = f"{DOMAIN}.activity"


def make(i: int = 0, **kwargs: Any) -> Activity:
    return Activity(t=1000.0 + i, channel="panel", action="wifi", summary=f"entry {i}", **kwargs)


async def new_log(hass: HomeAssistant) -> ActivityLog:
    log = ActivityLog(hass)
    await log.async_load()
    return log


# ------------------------------------------------------------------------------------------- the ring buffer
async def test_ring_buffer_keeps_the_newest_entries(hass: HomeAssistant) -> None:
    log = await new_log(hass)
    for i in range(ACTIVITY_KEEP + 5):
        log.record(make(i))

    assert ACTIVITY_KEEP == 300
    assert len(log.entries) == ACTIVITY_KEEP
    assert log.entries[0].summary == "entry 5", "the five oldest are gone"
    assert log.entries[-1].summary == f"entry {ACTIVITY_KEEP + 4}"


async def test_recent_is_newest_first_and_limited(hass: HomeAssistant) -> None:
    log = await new_log(hass)
    for i in range(10):
        log.record(make(i))

    recent = log.recent(3)
    assert [e["summary"] for e in recent] == ["entry 9", "entry 8", "entry 7"]
    assert len(log.recent()) == 10
    assert isinstance(recent[0], dict) and recent[0]["channel"] == "panel"


async def test_recent_defaults_to_200(hass: HomeAssistant) -> None:
    log = await new_log(hass)
    for i in range(250):
        log.record(make(i))
    recent = log.recent()
    assert len(recent) == 200
    assert recent[0]["summary"] == "entry 249" and recent[-1]["summary"] == "entry 50"


@pytest.mark.parametrize("limit", [0, -1, -200])
async def test_recent_with_nothing_asked_for_is_empty(hass: HomeAssistant, limit: int) -> None:
    log = await new_log(hass)
    for i in range(5):
        log.record(make(i))
    assert log.recent(limit) == [], "(a slice like [-0:] would have returned the whole log)"


async def test_recent_with_a_limit_larger_than_the_log(hass: HomeAssistant) -> None:
    log = await new_log(hass)
    for i in range(3):
        log.record(make(i))
    assert [e["summary"] for e in log.recent(1000)] == ["entry 2", "entry 1", "entry 0"]
    assert [e["summary"] for e in log.recent(1)] == ["entry 2"]


async def test_recent_returns_copies(hass: HomeAssistant) -> None:
    log = await new_log(hass)
    log.record(make(0, args={"mac": "AA"}))
    first = log.recent()
    first[0]["args"]["mac"] = "tampered"
    first.clear()
    assert log.recent()[0]["args"]["mac"] == "AA"


async def test_entry_defaults(hass: HomeAssistant) -> None:
    entry = make(1)
    assert (entry.ok, entry.user, entry.entry_id, entry.router, entry.msg, entry.args) == (True, None, None, "", "", {})


async def test_default_args_are_not_shared_between_entries(hass: HomeAssistant) -> None:
    a, b = make(1), make(2)
    a.args["x"] = 1
    assert b.args == {}


# ------------------------------------------------------------------------------------------- persistence
async def test_entries_survive_a_restart(hass: HomeAssistant, hass_storage: dict[str, Any], freezer: FrozenDateTimeFactory) -> None:
    log = await new_log(hass)
    log.record(make(1, ok=False, user="Alice", entry_id="e1", router="R", msg="wifi_failed", args={"code": "bad_ssid"}))
    log.record(make(2))
    assert STORE_KEY not in hass_storage, "writes are delayed, not one per entry"

    freezer.tick(timedelta(seconds=SAVE_DELAY + 1))  # the Store counts on the loop's monotonic clock
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    stored = hass_storage[STORE_KEY]
    assert stored["version"] == 1
    assert len(stored["data"]["entries"]) == 2

    restarted = await new_log(hass)
    assert restarted.entries == log.entries
    assert restarted.entries[0].args == {"code": "bad_ssid"} and restarted.entries[0].user == "Alice"


async def test_pending_entries_are_written_when_home_assistant_stops(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    log = await new_log(hass)
    log.record(make(1))
    assert STORE_KEY not in hass_storage

    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()

    assert len(hass_storage[STORE_KEY]["data"]["entries"]) == 1


async def test_load_from_an_empty_store(hass: HomeAssistant) -> None:
    assert (await new_log(hass)).entries == []


async def test_load_ignores_fields_it_does_not_know(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """A store written by a newer version (extra fields) must still load after a downgrade."""
    hass_storage[STORE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORE_KEY,
        "data": {"entries": [{"t": 5.0, "channel": "service", "action": "reboot", "summary": "x", "from_the_future": [1, 2]}]},
    }
    log = await new_log(hass)
    assert [(e.t, e.channel, e.action) for e in log.entries] == [(5.0, "service", "reboot")]


async def test_a_full_log_round_trips_in_order(hass: HomeAssistant, hass_storage: dict[str, Any], freezer: FrozenDateTimeFactory) -> None:
    log = await new_log(hass)
    for i in range(ACTIVITY_KEEP + 20):
        log.record(make(i))
    freezer.tick(timedelta(seconds=SAVE_DELAY + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    restarted = await new_log(hass)
    assert [e.summary for e in restarted.entries] == [e.summary for e in log.entries]
    assert len(restarted.entries) == ACTIVITY_KEEP


GOOD = {"t": 5.0, "channel": "panel", "action": "wifi", "summary": "kept", "ok": True}


@pytest.mark.parametrize(
    "stored",
    [
        {"entries": [{"t": 1.0}]},  # a required field missing
        {"entries": ["not a dict", 5, None, [1, 2]]},  # entries that are not objects
        {"entries": None},
        {"entries": "text"},
        {"entries": {"t": 1}},  # an object where the list should be
        {"entries": 7},
        {},
        {"unrelated": True},
        [],  # the whole store is not an object
        "garbage",
        5,
    ],
    ids=["missing-fields", "non-dict-entries", "entries-null", "entries-string", "entries-object", "entries-number", "empty-object",
         "no-entries-key", "store-is-a-list", "store-is-a-string", "store-is-a-number"],
)
async def test_a_damaged_store_does_not_stop_the_integration(hass: HomeAssistant, hass_storage: dict[str, Any], stored: Any) -> None:
    hass_storage[STORE_KEY] = {"version": 1, "minor_version": 1, "key": STORE_KEY, "data": stored}
    log = ActivityLog(hass)
    await log.async_load()  # must not raise
    assert log.entries == []
    log.record(make(1))  # and the log is usable afterwards
    assert len(log.entries) == 1


async def test_only_the_damaged_entries_are_dropped(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    hass_storage[STORE_KEY] = {
        "version": 1, "minor_version": 1, "key": STORE_KEY,
        "data": {"entries": [{"t": 1.0}, GOOD, "junk", {**GOOD, "summary": "also kept", "from_the_future": 1}, None]},
    }  # fmt: skip
    log = await new_log(hass)
    assert [e.summary for e in log.entries] == ["kept", "also kept"]


async def test_a_damaged_activity_store_does_not_keep_the_routers_from_loading(hass: HomeAssistant, hass_storage: dict[str, Any],
                                                                              setup_router: Any) -> None:
    hass_storage[STORE_KEY] = {"version": 1, "minor_version": 1, "key": STORE_KEY, "data": {"entries": [{"t": 1.0}, GOOD]}}
    entry = await setup_router("192.0.2.10")  # expects LOADED
    assert entry.state is ConfigEntryState.LOADED
    assert [a["summary"] for a in hass.data[DOMAIN]["activity"].recent()] == ["kept"]


# ------------------------------------------------------------------------------------------- listeners
async def test_listeners_get_every_new_entry(hass: HomeAssistant) -> None:
    log = await new_log(hass)
    seen_a: list[dict[str, Any]] = []
    seen_b: list[dict[str, Any]] = []
    unsub_a = log.subscribe(seen_a.append)
    log.subscribe(seen_b.append)

    log.record(make(1, args={"mac": "AA"}))
    assert seen_a == seen_b
    assert seen_a[0]["entries"][0]["summary"] == "entry 1"
    assert seen_a[0]["entries"][0]["args"] == {"mac": "AA"}

    unsub_a()
    log.record(make(2))
    assert len(seen_a) == 1 and len(seen_b) == 2


async def test_listener_payload_is_a_copy(hass: HomeAssistant) -> None:
    log = await new_log(hass)
    seen: list[dict[str, Any]] = []
    log.subscribe(seen.append)
    log.record(make(1, args={"k": "v"}))
    seen[0]["entries"][0]["args"]["k"] = "changed"
    assert log.entries[0].args == {"k": "v"}


async def test_recording_without_listeners_is_fine(hass: HomeAssistant) -> None:
    log = await new_log(hass)
    log.record(make(1))
    assert len(log.entries) == 1


async def test_async_record_builds_the_entry(hass: HomeAssistant) -> None:
    log = await new_log(hass)
    await log.async_record(Origin("service"), "entry-1", "My Router", "block", "blocked", {"name": "Phone", "mac": "AA:BB"})
    entry = log.entries[-1]
    assert (entry.channel, entry.action, entry.msg, entry.ok, entry.entry_id, entry.router) == ("service", "block", "blocked", True, "entry-1", "My Router")
    assert entry.summary == "Blocked Phone (AA:BB)"
    assert entry.args == {"name": "Phone", "mac": "AA:BB", "router": "My Router"}
    assert entry.user is None
    assert abs(entry.t - dt_util.utcnow().timestamp()) < 5


# ------------------------------------------------------------------------------------------- who did it
async def test_user_comes_from_the_origin_when_the_panel_knows_it(hass: HomeAssistant) -> None:
    log = await new_log(hass)
    with patch.object(hass.auth, "async_get_user", new_callable=AsyncMock) as lookup:
        await log.async_record(Origin("panel", user="Alice"), "e", "R", "reboot", "rebooted", {})
    assert log.entries[-1].user == "Alice"
    lookup.assert_not_called()


async def test_user_is_looked_up_from_the_context_and_cached(hass: HomeAssistant) -> None:
    log = await new_log(hass)
    bob = MockUser(name="Bob").add_to_hass(hass)
    original = hass.auth.async_get_user
    with patch.object(hass.auth, "async_get_user", new_callable=AsyncMock, side_effect=original) as lookup:
        for _ in range(3):
            await log.async_record(Origin("service", Context(user_id=bob.id)), "e", "R", "reboot", "rebooted", {})
    assert [e.user for e in log.entries] == ["Bob", "Bob", "Bob"]
    assert lookup.await_count == 1, "one lookup per user, not per entry"


async def test_unknown_user_id_gives_no_user(hass: HomeAssistant) -> None:
    log = await new_log(hass)
    await log.async_record(Origin("service", Context(user_id="0" * 32)), "e", "R", "reboot", "rebooted", {})
    assert log.entries[-1].user is None


@pytest.mark.parametrize("origin", [Origin("entity"), Origin("entity", Context()), Origin("service", Context(user_id=None))])
async def test_no_user_when_nobody_is_logged_in(hass: HomeAssistant, origin: Origin) -> None:
    """An automation or a script has a context without a user."""
    log = await new_log(hass)
    await log.async_record(origin, "e", "R", "reboot", "rebooted", {})
    assert log.entries[-1].user is None


# ------------------------------------------------------------------------------------------- the English line
def test_every_message_has_a_template() -> None:
    assert len(MESSAGES) == 14
    for msg, template in MESSAGES.items():
        assert isinstance(template, str) and template, msg


@pytest.mark.parametrize(
    ("msg", "args", "expected"),
    [
        ("wifi_on", {"ssid": "Home", "iface": "default_radio0"}, 'WiFi "Home" (default_radio0) turned on'),
        ("wifi_off", {"ssid": "Home", "iface": "guest2g"}, 'WiFi "Home" (guest2g) turned off'),
        ("wifi_ssid", {"ssid": "New", "iface": "default_radio1"}, 'WiFi default_radio1: name changed to "New"'),
        ("wifi_key", {"ssid": "Home", "iface": "default_radio0"}, 'WiFi "Home" (default_radio0): password changed'),
        ("wifi_failed", {"iface": "x", "error": "boom"}, "WiFi x: boom"),
        ("blocked", {"name": "Phone", "mac": "AA"}, "Blocked Phone (AA)"),
        ("unblocked", {"name": "Phone", "mac": "AA"}, "Unblocked Phone (AA)"),
        ("block_failed", {"mac": "AA", "error": "e"}, "Could not change the block of AA: e"),
        ("static_ip_added", {"ip": "1.2.3.4", "name": "TV", "mac": "AA"}, "Reserved 1.2.3.4 for TV (AA)"),
        ("static_ip_failed", {"ip": "1.2.3.4", "mac": "AA", "error": "e"}, "Could not reserve 1.2.3.4 for AA: e"),
        ("client_forgotten", {"name": "TV", "mac": "AA"}, "Forgot the offline device TV (AA)"),
        ("forget_failed", {"mac": "AA", "error": "e"}, "Could not forget AA: e"),
        ("rebooted", {"router": "R"}, "Rebooted R"),
        ("reboot_failed", {"router": "R", "error": "e"}, "Could not reboot R: e"),
    ],
)
def test_summaries(msg: str, args: dict[str, Any], expected: str) -> None:
    assert summarize(msg, args) == expected


def test_summary_survives_missing_arguments_and_braces() -> None:
    assert summarize("blocked", {}) == "Blocked ? (?)"
    assert summarize("wifi_failed", {"iface": "x", "error": "{not} a {template}"}) == "WiFi x: {not} a {template}"
    assert summarize("some_unknown_message", {"a": 1}) == "some_unknown_message"


def test_actions_only_use_messages_that_exist_and_use_all_of_them() -> None:
    """Every message key `actions.py` records is in MESSAGES (the panel translates by it), and none is orphaned."""
    tree = ast.parse(inspect.getsource(actions_module))
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "_record":
            for arg in node.args[2:3]:  # the message key: a literal, or `"a" if cond else "b"`
                branches = [arg.body, arg.orelse] if isinstance(arg, ast.IfExp) else [arg]
                used |= {b.value for b in branches if isinstance(b, ast.Constant) and isinstance(b.value, str)}
    assert used, "found no _record() calls: the test is out of date"
    assert used <= set(MESSAGES), f"unknown messages recorded: {used - set(MESSAGES)}"
    assert set(MESSAGES) <= used, f"messages nobody records: {set(MESSAGES) - used}"
