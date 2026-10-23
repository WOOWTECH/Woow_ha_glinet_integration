"""actions.py: every write to a router (Wi-Fi, blocking, static IPs, forgetting a device, reboot).

These run the real integration against the in-memory router, so what is asserted is what the router ends up with,
what the router was asked (the exact RPC calls), and what the activity log says.
"""

from __future__ import annotations

import asyncio
import ssl
from typing import Any

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from mock_router import MockRouter
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.woow_glinet.actions import WIFI_APPLY_TIMEOUT, ActionError, GlinetActions, normalize_mac
from custom_components.woow_glinet.activity import ActivityLog, Origin
from custom_components.woow_glinet.const import DOMAIN
from custom_components.woow_glinet.coordinator import GlinetCoordinator
from testkit import HOST, STRANGER_MAC, RouterWorld, connection_key, iface, offline_mac, online_mac, set_status

PANEL = Origin("panel", user="Alice")
MAC0, MAC1, MAC2, MAC3, MAC4, MAC5 = (f"AA:BB:CC:00:00:0{i}" for i in range(6))  # 2 and 5 are offline


@pytest.fixture
def actions(coordinator: GlinetCoordinator) -> GlinetActions:
    return coordinator.actions


def newest(activity: ActivityLog) -> dict[str, Any]:
    return activity.recent(1)[0]


class NoLock:
    """An asyncio.Lock that does not lock: used to prove a test would notice a missing lock."""

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> None:
        return None


# ===================================================================================== normalize_mac
@pytest.mark.parametrize(
    "value",
    [
        "aa:bb:cc:dd:ee:ff",
        "AA:BB:CC:DD:EE:FF",
        "AA-BB-CC-DD-EE-FF",
        "aabb.ccdd.eeff",
        "aabbccddeeff",
        "AA BB CC DD EE FF",
        "  aa:bb:cc:dd:ee:ff \n",
        "aa:bb-cc.dd ee:ff",
    ],
)
def test_normalize_mac_accepts_every_common_notation(value: str) -> None:
    assert normalize_mac(value) == "AA:BB:CC:DD:EE:FF"


def test_normalize_mac_is_idempotent() -> None:
    assert normalize_mac(normalize_mac("94-83-c4-00-00-01")) == "94:83:C4:00:00:01"


def test_normalize_mac_keeps_locally_administered_unicast() -> None:
    assert normalize_mac("02:00:00:00:00:01") == "02:00:00:00:00:01"  # randomised phone MACs look like this


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        None,
        "AA:BB:CC:DD:EE",  # 5 bytes
        "AA:BB:CC:DD:EE:FF:00",  # 7 bytes
        "AA:BB:CC:DD:EE:GG",  # not hex
        "AABBCCDDEEF",  # 11 digits
        "AABBCCDDEEFF0",  # 13 digits
        "not a mac",
        "01:00:5E:00:00:01",  # IPv4 multicast
        "33:33:00:00:00:01",  # IPv6 multicast
        "FF:FF:FF:FF:FF:FF",  # broadcast
        "AB:CD:EF:01:23:45",  # low bit of the first byte set = group address
        "٠١:٢٣:٤٥:٦٧:٨٩:١٠",  # Arabic-Indic digits are not hex digits
    ],
)
def test_normalize_mac_rejects_bad_input(value: str | None) -> None:
    with pytest.raises(ActionError) as err:
        normalize_mac(value)  # type: ignore[arg-type]
    assert err.value.code == "invalid_mac"


def test_action_error_is_a_home_assistant_error_with_a_code() -> None:
    from homeassistant.exceptions import HomeAssistantError

    err = ActionError("some_code", "readable message")
    assert isinstance(err, HomeAssistantError)
    assert err.code == "some_code"
    assert str(err) == "readable message"


# ===================================================================================== set_wifi
async def test_set_wifi_turns_a_guest_network_on_and_off(actions: GlinetActions, router: MockRouter, world: RouterWorld,
                                                         coordinator: GlinetCoordinator, activity: ActivityLog) -> None:
    assert iface(router, "guest2g")["enabled"] is False

    await actions.set_wifi("guest2g", enabled=True, origin=PANEL)

    assert iface(router, "guest2g")["enabled"] is True
    assert world.calls("wifi.set_config")[-1].args == {"iface_name": "guest2g", "enabled": True}
    assert coordinator.data.wifi_bands[0]["ifaces"][1]["enabled"] is True, "the coordinator must have refreshed"
    entry = newest(activity)
    assert (entry["msg"], entry["ok"], entry["action"]) == ("wifi_on", True, "wifi")
    assert entry["args"]["iface"] == "guest2g"
    assert entry["args"]["ssid"] == "MOCK-8f2-Guest"
    assert (entry["channel"], entry["user"]) == ("panel", "Alice")
    assert entry["summary"] == 'WiFi "MOCK-8f2-Guest" (guest2g) turned on'

    await actions.set_wifi("guest2g", enabled=False, origin=PANEL)
    assert iface(router, "guest2g")["enabled"] is False
    assert newest(activity)["msg"] == "wifi_off"


async def test_set_wifi_renames_with_ascii_and_cjk(actions: GlinetActions, router: MockRouter, activity: ActivityLog) -> None:
    await actions.set_wifi("default_radio0", ssid="Home-5G", origin=PANEL)
    assert iface(router, "default_radio0")["ssid"] == "Home-5G"
    assert newest(activity)["msg"] == "wifi_ssid"
    assert newest(activity)["args"]["ssid"] == "Home-5G"

    await actions.set_wifi("default_radio0", ssid="渥屋智能", origin=PANEL)
    assert iface(router, "default_radio0")["ssid"] == "渥屋智能"


async def test_set_wifi_changes_the_password_and_never_logs_it(actions: GlinetActions, router: MockRouter, world: RouterWorld,
                                                              activity: ActivityLog, hass: HomeAssistant) -> None:
    secret = "t0p-s3cret-pass"
    await actions.set_wifi("default_radio1", key=secret, origin=PANEL)

    assert iface(router, "default_radio1")["key"] == secret
    assert world.calls("wifi.set_config")[-1].args == {"iface_name": "default_radio1", "key": secret}
    entry = newest(activity)
    assert entry["msg"] == "wifi_key"
    assert secret not in repr(activity.recent()), "the Wi-Fi password must never reach the activity log"
    assert secret not in activity.entries[-1].summary


async def test_set_wifi_sends_all_changes_in_one_router_call(actions: GlinetActions, router: MockRouter, world: RouterWorld,
                                                            activity: ActivityLog) -> None:
    before = world.count("wifi.set_config")
    await actions.set_wifi("guest5g", enabled=True, ssid="Guests", key="visitor-pass", origin=PANEL)

    assert world.count("wifi.set_config") == before + 1
    assert world.calls("wifi.set_config")[-1].args == {"iface_name": "guest5g", "enabled": True, "ssid": "Guests", "key": "visitor-pass"}
    assert iface(router, "guest5g")["ssid"] == "Guests"
    # one activity entry per thing that changed, oldest first: switched on, renamed, password changed
    assert [e.msg for e in activity.entries[-3:]] == ["wifi_on", "wifi_ssid", "wifi_key"]
    assert activity.entries[-3].args["ssid"] == "Guests", "the entries show the new name"


async def test_set_wifi_partial_patch_only_sends_what_changed(actions: GlinetActions, world: RouterWorld) -> None:
    await actions.set_wifi("default_radio0", ssid="OnlyName", origin=PANEL)
    assert world.calls("wifi.set_config")[-1].args == {"iface_name": "default_radio0", "ssid": "OnlyName"}


async def test_set_wifi_with_nothing_to_change_does_nothing(actions: GlinetActions, world: RouterWorld, activity: ActivityLog) -> None:
    before = len(activity.entries)
    await actions.set_wifi("default_radio0", origin=PANEL)
    assert world.count("wifi.set_config") == 0
    assert len(activity.entries) == before


async def test_set_wifi_unknown_interface(actions: GlinetActions, world: RouterWorld, activity: ActivityLog) -> None:
    with pytest.raises(ActionError) as err:
        await actions.set_wifi("no_such_iface", enabled=True, origin=PANEL)
    assert err.value.code == "no_such_wifi"
    assert world.count("wifi.set_config") == 0
    entry = newest(activity)
    assert (entry["msg"], entry["ok"], entry["args"]["code"]) == ("wifi_failed", False, "no_such_wifi")


@pytest.mark.parametrize(
    ("ssid", "ok"),
    [
        ("", False),  # 0 bytes
        ("a", True),
        ("a" * 32, True),  # the limit is in BYTES ...
        ("a" * 33, False),
        ("客" * 10, True),  # ... a Chinese character is 3 of them: 30
        ("客" * 11, False),  # 33
        ("客" * 8 + "a" * 8, True),  # 24 + 8 = 32
        ("客" * 8 + "a" * 9, False),  # 33
        ("😀" * 8, True),  # 4 bytes each: 32
        ("😀" * 9, False),
        ("é" * 16, True),  # 2 bytes each: 32
        ("é" * 17, False),
        (" ", True),  # one byte; whether the router likes it is the router's business
    ],
)
async def test_ssid_is_limited_to_32_bytes_not_characters(actions: GlinetActions, router: MockRouter, activity: ActivityLog,
                                                          ssid: str, ok: bool) -> None:
    if ok:
        await actions.set_wifi("default_radio0", ssid=ssid, origin=PANEL)
        assert iface(router, "default_radio0")["ssid"] == ssid
    else:
        with pytest.raises(ActionError) as err:
            await actions.set_wifi("default_radio0", ssid=ssid, origin=PANEL)
        assert err.value.code == "bad_ssid"
        assert iface(router, "default_radio0")["ssid"] == "MOCK-8f2", "a refused name must not reach the router"
        assert newest(activity)["args"]["code"] == "bad_ssid"


@pytest.mark.parametrize(
    ("key", "ok"),
    [
        ("1234567", False),  # 7
        ("12345678", True),  # 8
        ("x" * 63, True),
        ("x" * 64, False),
        ("", False),
        ("pass word with spaces", True),  # a space is printable
        ("~!@#$%^&*()_+-=[]{};:'\",.<>/?`|\\", True),  # printable ASCII punctuation
    ],
)
async def test_wifi_password_must_be_8_to_63_characters(actions: GlinetActions, router: MockRouter, key: str, ok: bool) -> None:
    if ok:
        await actions.set_wifi("default_radio0", key=key, origin=PANEL)
        assert iface(router, "default_radio0")["key"] == key
    else:
        with pytest.raises(ActionError) as err:
            await actions.set_wifi("default_radio0", key=key, origin=PANEL)
        assert err.value.code == "bad_key"
        assert iface(router, "default_radio0")["key"] == "mock-wifi-key"


@pytest.mark.parametrize(
    ("key", "ok"),
    [
        ("密" * 3, True),  # 9 bytes: the limit is in BYTES (WPA's 8..63 octets), not characters ...
        ("密" * 2, False),  # 6 bytes although the text is "long" enough in characters terms for nobody
        ("密" * 21, True),  # 63 bytes
        ("密" * 22, False),  # 66 bytes: only 22 characters, but over the limit
        ("é" * 4, True),  # 8 bytes (2 each)
        ("é" * 3, False),  # 6
        ("é" * 31 + "a", True),  # 63
        ("é" * 32, False),  # 64
        ("😀" * 2, True),  # 8 (4 each)
        ("😀" * 15 + "abc", True),  # 63
        ("😀" * 16, False),  # 64
    ],
)
async def test_wifi_password_limit_is_in_bytes(actions: GlinetActions, router: MockRouter, world: RouterWorld, key: str, ok: bool) -> None:
    """(the mock router counts bytes too, as the real firmware presumably does)"""
    if ok:
        await actions.set_wifi("default_radio0", key=key, origin=PANEL)
        assert world.calls("wifi.set_config")[-1].args == {"iface_name": "default_radio0", "key": key}
        assert iface(router, "default_radio0")["key"] == key
    else:
        with pytest.raises(ActionError) as err:
            await actions.set_wifi("default_radio0", key=key, origin=PANEL)
        assert err.value.code == "bad_key"
        assert iface(router, "default_radio0")["key"] == "mock-wifi-key"


CONTROL_CHARACTERS = ["\x00", "\x01", "\t", "\n", "\r", "\x1b", "\x1f", "\x7f"]


@pytest.mark.parametrize("where", ["start", "middle", "end", "alone"])
@pytest.mark.parametrize("char", CONTROL_CHARACTERS, ids=lambda c: f"U+{ord(c):04X}")
async def test_ssid_with_a_control_character_is_refused(actions: GlinetActions, router: MockRouter, world: RouterWorld,
                                                        activity: ActivityLog, char: str, where: str) -> None:
    ssid = {"start": char + "Home", "middle": "Ho" + char + "me", "end": "Home" + char, "alone": char}[where]
    with pytest.raises(ActionError) as err:
        await actions.set_wifi("default_radio0", ssid=ssid, origin=PANEL)
    assert err.value.code == "bad_ssid"
    assert world.count("wifi.set_config") == 0
    assert iface(router, "default_radio0")["ssid"] == "MOCK-8f2"
    assert newest(activity)["args"]["code"] == "bad_ssid"


@pytest.mark.parametrize("where", ["start", "middle", "end"])
@pytest.mark.parametrize("char", CONTROL_CHARACTERS, ids=lambda c: f"U+{ord(c):04X}")
async def test_password_with_a_control_character_is_refused(actions: GlinetActions, router: MockRouter, world: RouterWorld,
                                                            activity: ActivityLog, char: str, where: str) -> None:
    key = {"start": char + "password1", "middle": "pass" + char + "word1", "end": "password1" + char}[where]
    with pytest.raises(ActionError) as err:
        await actions.set_wifi("default_radio0", key=key, origin=PANEL)
    assert err.value.code == "bad_key"
    assert world.count("wifi.set_config") == 0
    assert iface(router, "default_radio0")["key"] == "mock-wifi-key"
    entry = newest(activity)
    assert entry["args"]["code"] == "bad_key" and entry["ok"] is False


@pytest.mark.parametrize("ssid", [" ", "a b", "~", "Café ☕", "客廳 5G", "\x7e\x20"])
async def test_printable_characters_are_still_fine_in_an_ssid(actions: GlinetActions, router: MockRouter, ssid: str) -> None:
    await actions.set_wifi("default_radio0", ssid=ssid, origin=PANEL)
    assert iface(router, "default_radio0")["ssid"] == ssid


async def test_a_control_character_in_the_key_blocks_a_valid_ssid_too(actions: GlinetActions, router: MockRouter, world: RouterWorld) -> None:
    with pytest.raises(ActionError) as err:
        await actions.set_wifi("default_radio0", ssid="Fine", key="bad\nkey-value", origin=PANEL)
    assert err.value.code == "bad_key"
    assert world.count("wifi.set_config") == 0


@pytest.mark.parametrize(("field", "code"), [("ssid", "bad_ssid"), ("key", "bad_key")])
async def test_a_string_that_cannot_be_encoded_is_refused_cleanly(actions: GlinetActions, world: RouterWorld, activity: ActivityLog,
                                                                  field: str, code: str) -> None:
    """A lone surrogate (JSON "\\ud800" from a websocket client) is not text the router could be given."""
    with pytest.raises(ActionError) as err:
        await actions.set_wifi("default_radio0", origin=PANEL, **{field: "abc\ud800def-padding"})
    assert err.value.code == code
    assert world.count("wifi.set_config") == 0
    assert (newest(activity)["msg"], newest(activity)["args"]["code"]) == ("wifi_failed", code)


async def test_a_refused_field_blocks_the_whole_patch(actions: GlinetActions, router: MockRouter, world: RouterWorld) -> None:
    """A good name next to a bad password: nothing at all is sent (no half-applied change)."""
    with pytest.raises(ActionError) as err:
        await actions.set_wifi("default_radio0", ssid="Fine", key="short", origin=PANEL)
    assert err.value.code == "bad_key"
    assert world.count("wifi.set_config") == 0
    assert iface(router, "default_radio0")["ssid"] == "MOCK-8f2"


async def test_router_rejecting_the_wifi_change(actions: GlinetActions, router: MockRouter, activity: ActivityLog) -> None:
    router.configure(error_methods={"wifi.set_config": (-32602, "Invalid params")})
    with pytest.raises(ActionError) as err:
        await actions.set_wifi("guest2g", enabled=True, origin=PANEL)
    assert err.value.code == "api_error"
    assert "Invalid params" in str(err.value)
    entry = newest(activity)
    assert (entry["msg"], entry["ok"], entry["args"]["code"]) == ("wifi_failed", False, "api_error")
    assert "Invalid params" in entry["args"]["error"]


async def test_set_wifi_after_the_password_was_changed_is_auth_failed(actions: GlinetActions, router: MockRouter, activity: ActivityLog) -> None:
    router.configure(password="changed-on-the-router")
    with pytest.raises(ActionError) as err:
        await actions.set_wifi("guest2g", enabled=True, origin=PANEL)
    assert err.value.code == "auth_failed"
    assert newest(activity)["args"]["code"] == "auth_failed"


# ===================================================================================== set_blocked
async def test_block_a_device(actions: GlinetActions, router: MockRouter, world: RouterWorld, coordinator: GlinetCoordinator,
                              activity: ActivityLog) -> None:
    await actions.set_blocked(MAC1, True, origin=PANEL)

    assert router.black_mac == [MAC1]
    assert world.calls("black_white_list.set_single_mac")[-1].args == {"mode": "black", "operate": "add", "mac": MAC1}
    assert world.count("black_white_list.set_config") == 0
    assert coordinator.data.black_mac == [MAC1]
    assert next(c for c in coordinator.data.clients if c["mac"] == MAC1)["blocked"] is True
    entry = newest(activity)
    assert (entry["msg"], entry["ok"], entry["action"]) == ("blocked", True, "block")
    assert entry["args"]["name"] == "MacBook Pro"
    assert entry["summary"] == f"Blocked MacBook Pro ({MAC1})"


async def test_block_normalises_the_mac(actions: GlinetActions, router: MockRouter, world: RouterWorld) -> None:
    await actions.set_blocked("aa-bb-cc-00-00-01", True, origin=PANEL)
    assert router.black_mac == [MAC1]
    assert world.calls("black_white_list.set_single_mac")[-1].args["mac"] == MAC1


async def test_block_a_device_the_router_has_never_seen(actions: GlinetActions, router: MockRouter, activity: ActivityLog) -> None:
    await actions.set_blocked(STRANGER_MAC, True, origin=PANEL)
    assert router.black_mac == [STRANGER_MAC]
    assert newest(activity)["args"]["name"] == STRANGER_MAC, "no client record: the MAC stands in for the name"


async def test_unblock_rewrites_the_list_without_that_mac(actions: GlinetActions, router: MockRouter, world: RouterWorld,
                                                         coordinator: GlinetCoordinator, activity: ActivityLog) -> None:
    router.configure(black_mac=[MAC0, MAC1, MAC3])
    await coordinator.async_refresh()

    await actions.set_blocked(MAC1, False, origin=PANEL)

    assert router.black_mac == [MAC0, MAC3]
    # set_single_mac with operate=remove is a silent no-op on the real firmware: the bulk rewrite is the only way
    assert world.count("black_white_list.set_single_mac") == 0
    assert world.calls("black_white_list.set_config")[-1].args == {"mode": "black", "mac": [MAC0, MAC3]}
    methods = [r.method for r in world.requests if r.method.startswith("black_white_list.")]
    assert methods.index("black_white_list.get_config") < methods.index("black_white_list.set_config")
    assert coordinator.data.black_mac == [MAC0, MAC3]
    assert newest(activity)["msg"] == "unblocked"
    assert newest(activity)["summary"] == f"Unblocked MacBook Pro ({MAC1})"


async def test_unblock_matches_the_mac_case_insensitively(actions: GlinetActions, router: MockRouter) -> None:
    router.black_mac = [MAC1.lower(), MAC3]
    await actions.set_blocked(MAC1, False, origin=PANEL)
    assert router.black_mac == [MAC3]


async def test_unblock_something_that_is_not_blocked(actions: GlinetActions, router: MockRouter, world: RouterWorld) -> None:
    await actions.set_blocked(MAC4, False, origin=PANEL)  # the mock omits black_mac when it is empty
    assert router.black_mac == []
    assert world.calls("black_white_list.set_config")[-1].args == {"mode": "black", "mac": []}


async def test_two_concurrent_unblocks_both_take_effect(actions: GlinetActions, router: MockRouter, coordinator: GlinetCoordinator) -> None:
    """Unblocking is read-modify-write of the whole list: without the lock the second writer erases the first."""
    router.configure(black_mac=[MAC0, MAC1, MAC3, MAC4])
    await coordinator.async_refresh()

    await asyncio.gather(
        actions.set_blocked(MAC0, False, origin=PANEL),
        actions.set_blocked(MAC1, False, origin=PANEL),
        actions.set_blocked(MAC3, False, origin=PANEL),
    )

    assert router.black_mac == [MAC4]


async def test_the_concurrent_unblock_test_is_not_vacuous(actions: GlinetActions, router: MockRouter, coordinator: GlinetCoordinator,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """With the lock taken away the very same scenario loses updates: the transport interleaves for real."""
    monkeypatch.setattr(actions, "_blocklist_lock", NoLock())
    router.configure(black_mac=[MAC0, MAC1, MAC3, MAC4])
    await coordinator.async_refresh()

    await asyncio.gather(
        actions.set_blocked(MAC0, False, origin=PANEL),
        actions.set_blocked(MAC1, False, origin=PANEL),
        actions.set_blocked(MAC3, False, origin=PANEL),
    )

    assert router.black_mac != [MAC4], "expected a lost update without the lock"
    assert MAC4 in router.black_mac


async def test_a_failed_unblock_releases_the_lock(actions: GlinetActions, router: MockRouter) -> None:
    router.configure(black_mac=[MAC1], error_methods={"black_white_list.set_config": (-32602, "Invalid params")})
    with pytest.raises(ActionError):
        await actions.set_blocked(MAC1, False, origin=PANEL)
    router.configure(error_methods={})
    await asyncio.wait_for(actions.set_blocked(MAC1, False, origin=PANEL), timeout=5)
    assert router.black_mac == []


async def test_blocking_is_refused_in_white_list_mode(actions: GlinetActions, router: MockRouter, world: RouterWorld,
                                                      coordinator: GlinetCoordinator, activity: ActivityLog) -> None:
    """In white-list mode 'adding to the list' means allow: doing it anyway would silently invert the meaning."""
    router.configure(blacklist_mode="white")
    await coordinator.async_refresh()

    for blocked in (True, False):
        with pytest.raises(ActionError) as err:
            await actions.set_blocked(MAC1, blocked, origin=PANEL)
        assert err.value.code == "not_blacklist_mode"

    assert world.count("black_white_list.set_single_mac") == 0
    assert world.count("black_white_list.set_config") == 0
    entry = newest(activity)
    assert (entry["msg"], entry["ok"], entry["args"]["code"]) == ("block_failed", False, "not_blacklist_mode")


async def test_blocking_is_refused_outside_router_mode(setup_router: Any, world: RouterWorld) -> None:
    entry = await setup_router("192.0.2.30", mode="ap")
    actions = entry.runtime_data.coordinator.actions
    with pytest.raises(ActionError) as err:
        await actions.set_blocked(MAC1, True, origin=PANEL)
    assert err.value.code == "not_router_mode"
    assert world.count("black_white_list.set_single_mac", "192.0.2.30") == 0


async def test_not_router_mode_is_reported_before_white_list_mode(setup_router: Any) -> None:
    entry = await setup_router("192.0.2.30", mode="repeater", blacklist_mode="white")
    with pytest.raises(ActionError) as err:
        await entry.runtime_data.coordinator.actions.set_blocked(MAC1, True, origin=PANEL)
    assert err.value.code == "not_router_mode"


async def test_router_error_while_blocking(actions: GlinetActions, router: MockRouter, activity: ActivityLog) -> None:
    router.configure(error_methods={"black_white_list.set_single_mac": (-32602, "Invalid params")})
    with pytest.raises(ActionError) as err:
        await actions.set_blocked(MAC1, True, origin=PANEL)
    assert err.value.code == "api_error"
    assert newest(activity)["args"]["code"] == "api_error"
    assert router.black_mac == []


# ===================================================================================== add_static_ip
async def test_add_static_ip(actions: GlinetActions, router: MockRouter, world: RouterWorld, coordinator: GlinetCoordinator,
                             activity: ActivityLog) -> None:
    await actions.add_static_ip(MAC2.lower(), "192.168.8.50", "TV", origin=PANEL)

    assert router.static_binds == [{"mac": MAC2, "ip": "192.168.8.50", "name": "TV"}]
    assert world.calls("lan.add_static_bind")[-1].args == {"mac": MAC2, "ip": "192.168.8.50", "name": "TV"}
    assert coordinator.data.static_binds == router.static_binds
    entry = newest(activity)
    assert (entry["msg"], entry["ok"], entry["action"]) == ("static_ip_added", True, "static_ip")
    assert entry["summary"] == f"Reserved 192.168.8.50 for TV ({MAC2})"


async def test_add_static_ip_trims_the_ip_and_the_name(actions: GlinetActions, router: MockRouter) -> None:
    await actions.add_static_ip(MAC2, "  192.168.8.51 ", "  Printer  ", origin=PANEL)
    assert router.static_binds == [{"mac": MAC2, "ip": "192.168.8.51", "name": "Printer"}]


@pytest.mark.parametrize("ip", ["192.168.8.2", "192.168.8.254", "192.168.8.100"])
async def test_add_static_ip_accepts_the_edges_of_the_lan(actions: GlinetActions, router: MockRouter, ip: str) -> None:
    await actions.add_static_ip(MAC2, ip, "x", origin=PANEL)
    assert router.static_binds[0]["ip"] == ip


@pytest.mark.parametrize(
    "ip",
    [
        "10.0.0.5",  # another network
        "192.168.9.5",  # next /24
        "192.168.8.0",  # the network address
        "192.168.8.255",  # the broadcast address
        "192.168.8.1",  # the router itself
        "8.8.8.8",
        "0.0.0.0",
    ],
)
async def test_add_static_ip_outside_the_lan_or_on_a_special_address(actions: GlinetActions, router: MockRouter, world: RouterWorld,
                                                                    activity: ActivityLog, ip: str) -> None:
    with pytest.raises(ActionError) as err:
        await actions.add_static_ip(MAC2, ip, "x", origin=PANEL)
    assert err.value.code == "ip_outside_lan"
    assert world.count("lan.add_static_bind") == 0
    entry = newest(activity)
    assert (entry["msg"], entry["ok"], entry["args"]["code"]) == ("static_ip_failed", False, "ip_outside_lan")


async def test_add_static_ip_uses_the_routers_real_netmask(actions: GlinetActions, router: MockRouter, coordinator: GlinetCoordinator) -> None:
    set_status(router, lan_netmask="255.255.0.0")
    await coordinator.async_refresh()
    await actions.add_static_ip(MAC2, "192.168.9.5", "wider lan", origin=PANEL)  # inside a /16
    with pytest.raises(ActionError) as err:
        await actions.add_static_ip(MAC3, "192.168.255.255", "broadcast of the /16", origin=PANEL)
    assert err.value.code == "ip_outside_lan"


async def test_add_static_ip_with_an_empty_name(actions: GlinetActions, world: RouterWorld) -> None:
    for name in ("", "   ", "\t\n"):
        with pytest.raises(ActionError) as err:
            await actions.add_static_ip(MAC2, "192.168.8.50", name, origin=PANEL)
        assert err.value.code == "bad_name"
    assert world.count("lan.add_static_bind") == 0


async def test_add_static_ip_duplicate_mac(actions: GlinetActions, router: MockRouter, coordinator: GlinetCoordinator,
                                           activity: ActivityLog) -> None:
    router.static_binds = [{"mac": MAC2.lower(), "ip": "192.168.8.60", "name": "old"}]
    await coordinator.async_refresh()
    with pytest.raises(ActionError) as err:
        await actions.add_static_ip(MAC2, "192.168.8.61", "again", origin=PANEL)
    assert err.value.code == "mac_already_bound"
    assert "192.168.8.60" in str(err.value), "the message names the address it already has"
    assert router.static_binds == [{"mac": MAC2.lower(), "ip": "192.168.8.60", "name": "old"}]
    assert newest(activity)["args"]["code"] == "mac_already_bound"


async def test_add_static_ip_duplicate_ip(actions: GlinetActions, router: MockRouter, coordinator: GlinetCoordinator) -> None:
    router.static_binds = [{"mac": MAC3, "ip": "192.168.8.60", "name": "taken"}]
    await coordinator.async_refresh()
    with pytest.raises(ActionError) as err:
        await actions.add_static_ip(MAC2, "192.168.8.60", "me too", origin=PANEL)
    assert err.value.code == "ip_already_bound"
    assert MAC3 in str(err.value), "the message names who has it"


async def test_add_static_ip_is_refused_outside_router_mode(setup_router: Any, world: RouterWorld) -> None:
    entry = await setup_router("192.0.2.30", mode="ap")
    with pytest.raises(ActionError) as err:
        await entry.runtime_data.coordinator.actions.add_static_ip(MAC2, "192.168.8.50", "x", origin=PANEL)
    assert err.value.code == "not_router_mode"
    assert world.count("lan.add_static_bind", "192.0.2.30") == 0


async def test_add_static_ip_router_error(actions: GlinetActions, router: MockRouter, activity: ActivityLog) -> None:
    router.configure(error_methods={"lan.add_static_bind": (-32602, "Invalid params")})
    with pytest.raises(ActionError) as err:
        await actions.add_static_ip(MAC2, "192.168.8.50", "x", origin=PANEL)
    assert err.value.code == "api_error"
    assert newest(activity)["msg"] == "static_ip_failed"


async def test_a_bad_mac_is_reported_before_anything_else(actions: GlinetActions, world: RouterWorld) -> None:
    with pytest.raises(ActionError) as err:
        await actions.add_static_ip("nonsense", "999.9.9.9", "", origin=PANEL)
    assert err.value.code == "invalid_mac"


# ===================================================================================== forget_client
async def test_forget_an_offline_device(actions: GlinetActions, router: MockRouter, world: RouterWorld, coordinator: GlinetCoordinator,
                                        activity: ActivityLog) -> None:
    assert MAC2 in (c["mac"] for c in coordinator.data.clients)
    assert offline_mac(router) == MAC2

    await actions.forget_client(MAC2, origin=PANEL)

    assert world.calls("clients.remove_offline")[-1].args == {"mac": MAC2}
    assert MAC2 not in (c["mac"] for c in router.clients)
    assert MAC2 not in (c["mac"] for c in coordinator.data.clients), "refreshed"
    entry = newest(activity)
    assert (entry["msg"], entry["ok"], entry["action"]) == ("client_forgotten", True, "forget")
    assert entry["args"]["name"] == "Living-room TV"


async def test_forget_refuses_an_online_device(actions: GlinetActions, router: MockRouter, world: RouterWorld, activity: ActivityLog) -> None:
    assert online_mac(router) == MAC0
    with pytest.raises(ActionError) as err:
        await actions.forget_client(MAC0, origin=PANEL)
    assert err.value.code == "client_online"
    assert world.count("clients.remove_offline") == 0
    assert MAC0 in (c["mac"] for c in router.clients)
    entry = newest(activity)
    assert (entry["msg"], entry["ok"], entry["args"]["code"]) == ("forget_failed", False, "client_online")


async def test_forget_unknown_device_is_left_to_the_router(actions: GlinetActions, world: RouterWorld) -> None:
    await actions.forget_client(STRANGER_MAC, origin=PANEL)
    assert world.calls("clients.remove_offline")[-1].args == {"mac": STRANGER_MAC}


async def test_forget_with_a_bad_mac(actions: GlinetActions) -> None:
    with pytest.raises(ActionError) as err:
        await actions.forget_client("zz", origin=PANEL)
    assert err.value.code == "invalid_mac"


async def test_forget_router_error(actions: GlinetActions, router: MockRouter, activity: ActivityLog) -> None:
    router.configure(error_methods={"clients.remove_offline": (-32602, "Invalid params")})
    with pytest.raises(ActionError) as err:
        await actions.forget_client(MAC2, origin=PANEL)
    assert err.value.code == "api_error"
    assert newest(activity)["msg"] == "forget_failed"


# ===================================================================================== reboot
async def test_reboot(actions: GlinetActions, router: MockRouter, world: RouterWorld, activity: ActivityLog) -> None:
    await actions.reboot(origin=PANEL)
    assert router.calls["system.reboot"] == 1
    entry = newest(activity)
    assert (entry["msg"], entry["ok"], entry["action"]) == ("rebooted", True, "reboot")
    assert entry["summary"] == "Rebooted GL-MOCK1200"


async def test_reboot_where_the_router_cuts_the_connection_is_a_success(actions: GlinetActions, router: MockRouter,
                                                                       activity: ActivityLog) -> None:
    """A router that is going down often hangs up instead of answering: that is the reboot working."""
    router.reboot_style = "drop"
    await actions.reboot(origin=PANEL)
    assert router.calls["system.reboot"] == 1
    assert (newest(activity)["msg"], newest(activity)["ok"]) == ("rebooted", True)


async def test_reboot_router_error_is_a_failure(actions: GlinetActions, router: MockRouter, activity: ActivityLog) -> None:
    router.configure(error_methods={"system.reboot": (-32602, "Invalid params")})
    with pytest.raises(ActionError) as err:
        await actions.reboot(origin=PANEL)
    assert err.value.code == "api_error"
    entry = newest(activity)
    assert (entry["msg"], entry["ok"], entry["args"]["code"]) == ("reboot_failed", False, "api_error")


async def test_reboot_method_not_found_is_a_failure(actions: GlinetActions, router: MockRouter) -> None:
    from testkit import remove_method

    remove_method(router, "system.reboot")
    with pytest.raises(ActionError) as err:
        await actions.reboot(origin=PANEL)
    assert err.value.code == "api_error"


async def test_reboot_timeout_is_a_failure(actions: GlinetActions, world: RouterWorld, activity: ActivityLog) -> None:
    """A request that timed out says nothing about the router having gone down: report it as not done."""
    world.inject("system.reboot", exc=TimeoutError())
    with pytest.raises(ActionError) as err:
        await actions.reboot(origin=PANEL)
    assert err.value.code == "api_error"
    assert newest(activity)["ok"] is False


async def test_reboot_with_wrong_credentials(actions: GlinetActions, router: MockRouter, activity: ActivityLog) -> None:
    router.configure(password="changed-on-the-router")
    with pytest.raises(ActionError) as err:
        await actions.reboot(origin=PANEL)
    assert err.value.code == "auth_failed"
    assert newest(activity)["args"]["code"] == "auth_failed"


async def test_reboot_against_an_unreachable_router_is_a_failure(actions: GlinetActions, world: RouterWorld, activity: ActivityLog) -> None:
    world.disconnect(HOST)  # connection refused: the request never reached the router
    with pytest.raises(ActionError) as err:
        await actions.reboot(origin=PANEL)
    assert err.value.code == "api_error"
    assert newest(activity)["ok"] is False
    assert newest(activity)["msg"] == "reboot_failed"


NEVER_CONNECTED = [
    aiohttp.ClientConnectorError(connection_key(), OSError(111, "Connection refused")),
    aiohttp.ClientConnectorError(connection_key(), OSError(65, "No route to host")),
    aiohttp.ClientConnectorDNSError(connection_key(), OSError("Name or service not known")),
    aiohttp.ClientConnectorCertificateError(connection_key(), ssl.SSLCertVerificationError("certificate verify failed")),
]


@pytest.mark.parametrize("exc", NEVER_CONNECTED, ids=lambda e: type(e).__name__ + "-" + str(getattr(e, "os_error", "cert"))[:20])
async def test_reboot_that_never_reached_the_router_is_a_failure(actions: GlinetActions, router: MockRouter, world: RouterWorld,
                                                                 activity: ActivityLog, exc: BaseException) -> None:
    world.inject("system.reboot", exc=exc)
    with pytest.raises(ActionError) as err:
        await actions.reboot(origin=PANEL)
    assert err.value.code == "api_error"
    assert router.calls["system.reboot"] == 0
    assert (newest(activity)["msg"], newest(activity)["ok"], newest(activity)["args"]["code"]) == ("reboot_failed", False, "api_error")


@pytest.mark.parametrize("exc", [aiohttp.ServerDisconnectedError("gone"), aiohttp.ClientOSError(104, "Connection reset by peer")], ids=["closed", "reset"])
async def test_reboot_whose_connection_is_cut_after_connecting_is_a_success(actions: GlinetActions, world: RouterWorld, activity: ActivityLog,
                                                                            exc: BaseException) -> None:
    world.inject("system.reboot", exc=exc)
    await actions.reboot(origin=PANEL)
    assert (newest(activity)["msg"], newest(activity)["ok"]) == ("rebooted", True)


# ===================================================================================== how long each write may take
def test_the_wifi_timeout_constant() -> None:
    assert WIFI_APPLY_TIMEOUT == 40, "the router needs ~9 s to apply a Wi-Fi change; a loaded one longer"


@pytest.mark.parametrize(
    "patch",
    [{"enabled": True}, {"ssid": "NewName"}, {"key": "a-new-password"}, {"enabled": True, "ssid": "NewName", "key": "a-new-password"}],
    ids=["enabled", "ssid", "key", "all-three"],
)
async def test_every_wifi_write_gets_the_long_timeout(actions: GlinetActions, world: RouterWorld, patch: dict) -> None:
    await actions.set_wifi("guest2g", origin=PANEL, **patch)
    assert [r.timeout for r in world.calls("wifi.set_config")] == [WIFI_APPLY_TIMEOUT]


async def test_nothing_else_gets_more_than_the_default(actions: GlinetActions, world: RouterWorld, router: MockRouter) -> None:
    await actions.set_wifi("guest2g", enabled=True, origin=PANEL)
    await actions.set_blocked(MAC1, True, origin=PANEL)
    await actions.set_blocked(MAC1, False, origin=PANEL)  # get_config + set_config
    await actions.add_static_ip(MAC2, "192.168.8.50", "TV", origin=PANEL)
    await actions.forget_client(MAC5, origin=PANEL)
    await actions.reboot(origin=PANEL)

    assert {r.timeout for r in world.calls("wifi.set_config")} == {WIFI_APPLY_TIMEOUT}
    others = {r.method: r.timeout for r in world.requests if r.method != "wifi.set_config"}
    assert {"black_white_list.set_single_mac", "black_white_list.set_config", "lan.add_static_bind", "clients.remove_offline", "system.reboot",
            "clients.get_list", "wifi.get_config", "challenge", "login"} <= set(others)  # fmt: skip
    assert set(others.values()) == {10}, "including the polls that follow every write"


async def test_a_wifi_write_that_takes_longer_than_even_that_is_a_failure(actions: GlinetActions, world: RouterWorld, activity: ActivityLog) -> None:
    world.inject("wifi.set_config", exc=TimeoutError())
    with pytest.raises(ActionError) as err:
        await actions.set_wifi("guest2g", enabled=True, origin=PANEL)
    assert err.value.code == "api_error"
    assert (newest(activity)["msg"], newest(activity)["ok"]) == ("wifi_failed", False)


# ===================================================================================== the activity log of failures
# (what to attempt, the ActionError code it must fail with, the activity message it must leave behind)
FAILURES = [
    pytest.param(lambda a: a.set_wifi("nope", enabled=True, origin=PANEL), "no_such_wifi", "wifi_failed", id="wifi-no-such-interface"),
    pytest.param(lambda a: a.set_wifi("guest2g", ssid="", origin=PANEL), "bad_ssid", "wifi_failed", id="wifi-bad-ssid"),
    pytest.param(lambda a: a.set_wifi("guest2g", key="short", origin=PANEL), "bad_key", "wifi_failed", id="wifi-bad-key"),
    pytest.param(lambda a: a.add_static_ip(MAC2, "10.1.1.1", "x", origin=PANEL), "ip_outside_lan", "static_ip_failed", id="static-outside-lan"),
    pytest.param(lambda a: a.add_static_ip(MAC5, "192.168.8.77", "x", origin=PANEL), "mac_already_bound", "static_ip_failed", id="static-duplicate-mac"),
    pytest.param(lambda a: a.add_static_ip(MAC2, "192.168.8.88", "x", origin=PANEL), "ip_already_bound", "static_ip_failed", id="static-duplicate-ip"),
    pytest.param(lambda a: a.forget_client(MAC0, origin=PANEL), "client_online", "forget_failed", id="forget-online-client"),
    pytest.param(
        lambda a: a.set_blocked("xx", True, origin=PANEL), "invalid_mac", "block_failed", id="block-bad-mac",
    ),
    pytest.param(
        lambda a: a.forget_client("xx", origin=PANEL), "invalid_mac", "forget_failed", id="forget-bad-mac",
    ),
    pytest.param(
        lambda a: a.add_static_ip(MAC2, "300.1.1.1", "x", origin=PANEL), "invalid_ip", "static_ip_failed", id="static-bad-ip",
    ),
    pytest.param(
        lambda a: a.add_static_ip(MAC2, "192.168.8.50", " ", origin=PANEL), "bad_name", "static_ip_failed", id="static-empty-name",
    ),
]


@pytest.mark.parametrize(("attempt", "code", "msg"), FAILURES)
async def test_every_failure_is_logged_with_its_code(actions: GlinetActions, router: MockRouter, coordinator: GlinetCoordinator,
                                                     activity: ActivityLog, attempt: Any, code: str, msg: str) -> None:
    router.static_binds = [{"mac": MAC5, "ip": "192.168.8.70", "name": "bound"}, {"mac": MAC4, "ip": "192.168.8.88", "name": "taken"}]
    await coordinator.async_refresh()
    before = len(activity.entries)

    with pytest.raises(ActionError) as err:
        await attempt(actions)

    assert err.value.code == code
    assert len(activity.entries) == before + 1, "exactly one new entry"
    entry = newest(activity)
    assert entry["ok"] is False
    assert entry["msg"] == msg
    assert entry["args"]["code"] == code
    assert entry["args"]["error"] == str(err.value)
    assert (entry["channel"], entry["user"]) == ("panel", "Alice")
    assert entry["summary"] and "?" not in entry["summary"], "a readable English line with every placeholder filled"


async def test_failures_outside_router_mode_are_logged_too(setup_router: Any) -> None:
    entry = await setup_router("192.0.2.30", mode="ap")
    coordinator = entry.runtime_data.coordinator
    activity = coordinator.hass.data["woow_glinet"]["activity"]
    for attempt, msg in (
        (coordinator.actions.set_blocked(MAC1, True, origin=PANEL), "block_failed"),
        (coordinator.actions.add_static_ip(MAC2, "192.168.8.50", "x", origin=PANEL), "static_ip_failed"),
    ):
        with pytest.raises(ActionError) as err:
            await attempt
        assert err.value.code == "not_router_mode"
        assert newest(activity)["msg"] == msg
        assert newest(activity)["args"]["code"] == "not_router_mode"


async def test_every_success_is_logged_ok(actions: GlinetActions, router: MockRouter, activity: ActivityLog) -> None:
    await actions.set_wifi("guest2g", enabled=True, origin=PANEL)
    await actions.set_blocked(MAC1, True, origin=PANEL)
    await actions.set_blocked(MAC1, False, origin=PANEL)
    await actions.add_static_ip(MAC2, "192.168.8.50", "TV", origin=PANEL)
    await actions.forget_client(MAC5, origin=PANEL)
    await actions.reboot(origin=PANEL)
    assert [e.msg for e in activity.entries] == ["wifi_on", "blocked", "unblocked", "static_ip_added", "client_forgotten", "rebooted"]
    assert all(e.ok for e in activity.entries)
    assert all(e.router == "GL-MOCK1200" and e.args["router"] == "GL-MOCK1200" for e in activity.entries)


async def test_entries_are_stamped_with_the_entry_and_the_time(actions: GlinetActions, entry: MockConfigEntry, activity: ActivityLog) -> None:
    import time

    before = time.time()
    await actions.set_wifi("guest2g", enabled=True, origin=PANEL)
    entry_logged = activity.entries[-1]
    assert entry_logged.entry_id == entry.entry_id
    assert before <= entry_logged.t <= time.time()


# ===================================================================================== the LAN lookup
async def test_the_lan_is_read_from_the_routers_status(actions: GlinetActions) -> None:
    import ipaddress

    assert actions.lan_network() == ipaddress.IPv4Network("192.168.8.0/24")


@pytest.mark.parametrize(
    "status",
    [{}, {"lan_ip": "192.168.8.1"}, {"lan_netmask": "255.255.255.0"}, {"lan_ip": "nonsense", "lan_netmask": "255.255.255.0"},
     {"lan_ip": "192.168.8.1", "lan_netmask": "garbage"}],
    ids=["nothing", "no-netmask", "no-ip", "bad-ip", "bad-netmask"],
)
async def test_without_a_usable_lan_there_is_no_range_to_check_against(actions: GlinetActions, coordinator: GlinetCoordinator, status: dict) -> None:
    coordinator.data.system = {"system": status}
    assert actions.lan_network() is None


async def test_a_router_that_does_not_report_its_lan_still_accepts_valid_reservations(actions: GlinetActions, router: MockRouter,
                                                                                      coordinator: GlinetCoordinator) -> None:
    """Without the LAN range the range check cannot run (the format and duplicate checks still do)."""
    coordinator.data.system = {}
    await actions.add_static_ip(MAC2, "192.168.8.50", "TV", origin=PANEL)
    assert router.static_binds[0]["ip"] == "192.168.8.50"
    with pytest.raises(ActionError) as err:
        await actions.add_static_ip(MAC3, "not-an-ip", "x", origin=PANEL)
    assert err.value.code == "invalid_ip"


async def test_actions_work_without_an_activity_log(hass: HomeAssistant, actions: GlinetActions, router: MockRouter) -> None:
    """The log is a convenience: a write must still go through if it is not there (e.g. the integration is being torn down)."""
    hass.data[DOMAIN].pop("activity")
    await actions.set_wifi("guest2g", enabled=True, origin=PANEL)
    assert iface(router, "guest2g")["enabled"] is True
    with pytest.raises(ActionError):
        await actions.set_wifi("nope", enabled=True, origin=PANEL)


# ===================================================================================== what is logged for malformed input
async def test_a_malformed_mac_is_logged_as_typed_but_bounded(actions: GlinetActions, activity: ActivityLog) -> None:
    with pytest.raises(ActionError):
        await actions.set_blocked("x" * 500, True, origin=PANEL)
    entry = newest(activity)
    assert (entry["msg"], entry["ok"], entry["action"], entry["args"]["code"]) == ("block_failed", False, "block", "invalid_mac")
    assert entry["args"]["mac"] == "x" * 64, "a hostile 500-character 'MAC' does not fill the log"
    assert "?" not in entry["summary"]


async def test_a_malformed_ip_is_logged_with_the_normalised_mac(actions: GlinetActions, activity: ActivityLog) -> None:
    with pytest.raises(ActionError):
        await actions.add_static_ip("aa-bb-cc-00-00-02", "9" * 500, "TV", origin=PANEL)
    entry = newest(activity)
    assert (entry["msg"], entry["args"]["code"], entry["args"]["mac"]) == ("static_ip_failed", "invalid_ip", MAC2)
    assert len(entry["args"]["ip"]) == 64 and "?" not in entry["summary"]


async def test_an_empty_name_is_logged_with_the_ip(actions: GlinetActions, activity: ActivityLog) -> None:
    with pytest.raises(ActionError):
        await actions.add_static_ip(MAC2, " 192.168.8.50 ", "  ", origin=PANEL)
    entry = newest(activity)
    assert (entry["msg"], entry["args"]["code"], entry["args"]["ip"], entry["args"]["mac"]) == ("static_ip_failed", "bad_name", "192.168.8.50", MAC2)


async def test_a_bad_mac_in_add_static_ip_is_logged_too(actions: GlinetActions, activity: ActivityLog) -> None:
    with pytest.raises(ActionError):
        await actions.add_static_ip("zz", "192.168.8.50", "TV", origin=PANEL)
    entry = newest(activity)
    assert (entry["msg"], entry["args"]["code"], entry["args"]["ip"]) == ("static_ip_failed", "invalid_mac", "192.168.8.50")


@pytest.mark.parametrize("raw", [None, "", "\x00\x01"])
async def test_odd_values_where_a_mac_is_expected(actions: GlinetActions, activity: ActivityLog, raw: Any) -> None:
    with pytest.raises(ActionError) as err:
        await actions.forget_client(raw, origin=PANEL)
    assert err.value.code == "invalid_mac"
    assert newest(activity)["msg"] == "forget_failed"


async def test_refusing_malformed_input_without_an_activity_log_still_raises_cleanly(hass: HomeAssistant, actions: GlinetActions) -> None:
    hass.data[DOMAIN].pop("activity")
    with pytest.raises(ActionError) as err:
        await actions.set_blocked("xx", True, origin=PANEL)
    assert err.value.code == "invalid_mac"
