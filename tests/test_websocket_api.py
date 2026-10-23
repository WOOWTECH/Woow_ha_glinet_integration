"""websocket_api.py: the commands behind the panel - every `woow_glinet/*` command, its errors, admin-only, the live feed."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from mock_router import MockRouter
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.woow_glinet import websocket_api as ws_module
from custom_components.woow_glinet.actions import GlinetActions
from custom_components.woow_glinet.const import DOMAIN
from custom_components.woow_glinet.feed import PanelFeed
from testkit import WIFI_KEY, RouterWorld, iface

from conftest import SetupRouter

MAC0, MAC1, MAC2 = "AA:BB:CC:00:00:00", "AA:BB:CC:00:00:01", "AA:BB:CC:00:00:02"  # 2 is offline


@pytest.fixture
async def client(hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entry: MockConfigEntry) -> Any:
    """A websocket connection of an administrator, with the router set up."""
    return await hass_ws_client(hass)


async def call(client: Any, type_: str, **payload: Any) -> dict[str, Any]:
    await client.send_json_auto_id({"type": type_, **payload})
    return await asyncio.wait_for(client.receive_json(), timeout=10)


def ok(response: dict[str, Any]) -> Any:
    assert response["success"] is True, response
    return response["result"]


def error_code(response: dict[str, Any]) -> str:
    assert response["success"] is False, response
    return response["error"]["code"]


# Every command, with a payload that is valid for the default router (used by the generic tests below)
def commands(entry: MockConfigEntry) -> list[tuple[str, dict[str, Any]]]:
    e = entry.entry_id
    return [
        ("woow_glinet/snapshot", {}),
        ("woow_glinet/subscribe", {}),
        ("woow_glinet/refresh", {"entry_id": e}),
        ("woow_glinet/wifi/set", {"entry_id": e, "iface": "guest2g", "enabled": True}),
        ("woow_glinet/wifi/key", {"entry_id": e, "iface": "default_radio0"}),
        ("woow_glinet/client/block", {"entry_id": e, "mac": MAC1, "blocked": True}),
        ("woow_glinet/client/forget", {"entry_id": e, "mac": MAC2}),
        ("woow_glinet/client/history", {"entry_id": e, "mac": MAC0}),
        ("woow_glinet/static_ip/add", {"entry_id": e, "mac": MAC2, "ip": "192.168.8.50", "name": "TV"}),
        ("woow_glinet/reboot", {"entry_id": e}),
    ]


async def test_every_command_is_registered_and_tested(hass: HomeAssistant, client: Any, entry: MockConfigEntry) -> None:
    from homeassistant.components.websocket_api.const import DOMAIN as WEBSOCKET_API

    registered = {name for name in hass.data[WEBSOCKET_API] if str(name).startswith("woow_glinet/")}
    assert registered == {type_ for type_, _ in commands(entry)}, "a command without a test (or a test for a command that is gone)"
    assert len(registered) == 10 == len(ws_module._COMMANDS)


# ===================================================================================== admin only
@pytest.mark.parametrize("index", range(10))
async def test_a_non_admin_user_is_refused_everywhere(hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entry: MockConfigEntry,
                                                      hass_read_only_access_token: str, router: MockRouter, world: RouterWorld,
                                                      index: int) -> None:
    client = await hass_ws_client(hass, hass_read_only_access_token)
    type_, payload = commands(entry)[index]
    calls_before = list(world.requests)

    response = await call(client, type_, **payload)

    assert error_code(response) == "unauthorized"
    assert world.requests == calls_before, "a refused command must not reach the router"
    assert router.black_mac == [] and iface(router, "guest2g")["enabled"] is False


async def test_a_non_admin_cannot_subscribe_to_the_feed(hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entry: MockConfigEntry,
                                                        hass_read_only_access_token: str) -> None:
    client = await hass_ws_client(hass, hass_read_only_access_token)
    assert error_code(await call(client, "woow_glinet/subscribe")) == "unauthorized"
    assert hass.data[DOMAIN]["feed"]._subs == []


async def test_a_non_admin_cannot_read_the_wifi_key(hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entry: MockConfigEntry,
                                                    hass_read_only_access_token: str) -> None:
    client = await hass_ws_client(hass, hass_read_only_access_token)
    response = await call(client, "woow_glinet/wifi/key", entry_id=entry.entry_id, iface="default_radio0")
    assert error_code(response) == "unauthorized"
    assert WIFI_KEY not in json.dumps(response)


# ===================================================================================== snapshot / refresh
async def test_snapshot(client: Any, entry: MockConfigEntry) -> None:
    result = ok(await call(client, "woow_glinet/snapshot"))
    assert set(result) == {"routers", "activity", "live_interval"}
    assert result["live_interval"] == 5
    (router,) = result["routers"]
    assert router["entry_id"] == entry.entry_id and router["mode"] == "router" and len(router["clients"]) == 6
    assert "history" in router
    assert WIFI_KEY not in json.dumps(result)


async def test_snapshot_of_two_routers(hass: HomeAssistant, client: Any, setup_router: SetupRouter) -> None:
    second = await setup_router("192.0.2.20", mac="94:83:C4:00:00:02", clients=2)
    result = ok(await call(client, "woow_glinet/snapshot"))
    assert {r["entry_id"] for r in result["routers"]} >= {second.entry_id}
    assert len(result["routers"]) == 2


async def test_refresh_polls_the_router_again(client: Any, entry: MockConfigEntry, world: RouterWorld, router: MockRouter) -> None:
    before = world.count("clients.get_list")
    router.configure(ssids={"guest2g": "Renamed"})
    assert ok(await call(client, "woow_glinet/refresh", entry_id=entry.entry_id)) is None
    assert world.count("clients.get_list") == before + 1
    assert entry.runtime_data.coordinator.data.wifi_bands[0]["ifaces"][1]["ssid"] == "Renamed"


# ===================================================================================== errors common to the entry commands
ENTRY_COMMANDS = [
    ("woow_glinet/refresh", {}),
    ("woow_glinet/wifi/set", {"iface": "guest2g", "enabled": True}),
    ("woow_glinet/wifi/key", {"iface": "default_radio0"}),
    ("woow_glinet/client/block", {"mac": MAC1, "blocked": True}),
    ("woow_glinet/client/forget", {"mac": MAC2}),
    ("woow_glinet/client/history", {"mac": MAC0}),
    ("woow_glinet/static_ip/add", {"mac": MAC2, "ip": "192.168.8.50", "name": "TV"}),
    ("woow_glinet/reboot", {}),
]


@pytest.mark.parametrize(("type_", "payload"), ENTRY_COMMANDS)
async def test_an_unknown_entry_is_not_loaded(client: Any, router: MockRouter, type_: str, payload: dict) -> None:
    response = await call(client, type_, entry_id="does-not-exist", **payload)
    assert error_code(response) == "not_loaded"
    assert response["error"]["message"] == "That router is not loaded"


@pytest.mark.parametrize(("type_", "payload"), ENTRY_COMMANDS)
async def test_an_entry_that_is_not_loaded(hass: HomeAssistant, client: Any, entry: MockConfigEntry, type_: str, payload: dict) -> None:
    await hass.config_entries.async_unload(entry.entry_id)
    assert error_code(await call(client, type_, entry_id=entry.entry_id, **payload)) == "not_loaded"


async def test_an_entry_of_another_integration_is_not_loaded(hass: HomeAssistant, client: Any) -> None:
    other = MockConfigEntry(domain="some_other_domain")
    other.add_to_hass(hass)
    assert error_code(await call(client, "woow_glinet/reboot", entry_id=other.entry_id)) == "not_loaded"


@pytest.mark.parametrize(
    ("type_", "payload"),
    [
        ("woow_glinet/refresh", {}),  # no entry_id
        ("woow_glinet/wifi/set", {"entry_id": "x"}),  # no iface
        ("woow_glinet/wifi/set", {"entry_id": "x", "iface": "g", "enabled": "yes"}),  # not a bool
        ("woow_glinet/wifi/set", {"entry_id": "x", "iface": "g", "ssid": 5}),
        ("woow_glinet/wifi/key", {"entry_id": "x"}),
        ("woow_glinet/client/block", {"entry_id": "x", "mac": MAC1}),  # no blocked
        ("woow_glinet/client/block", {"entry_id": "x", "mac": MAC1, "blocked": "true"}),
        ("woow_glinet/client/forget", {"entry_id": "x"}),
        ("woow_glinet/client/history", {"entry_id": "x"}),
        ("woow_glinet/static_ip/add", {"entry_id": "x", "mac": MAC1, "ip": "1.2.3.4"}),  # no name
        ("woow_glinet/reboot", {"entry_id": 5}),
        ("woow_glinet/reboot", {}),
    ],
)
async def test_malformed_requests_are_rejected_by_the_schema(client: Any, world: RouterWorld, type_: str, payload: dict) -> None:
    before = list(world.requests)
    assert error_code(await call(client, type_, **payload)) == "invalid_format"
    assert world.requests == before


# ===================================================================================== wifi
async def test_wifi_set_changes_the_router_and_logs_who_did_it(client: Any, entry: MockConfigEntry, router: MockRouter,
                                                              hass_admin_user: Any, activity: Any) -> None:
    ok(await call(client, "woow_glinet/wifi/set", entry_id=entry.entry_id, iface="guest2g", enabled=True, ssid="Visitors", key="visitor-pass"))

    assert (iface(router, "guest2g")["enabled"], iface(router, "guest2g")["ssid"], iface(router, "guest2g")["key"]) == (True, "Visitors", "visitor-pass")
    entries = activity.recent()
    assert [e["msg"] for e in entries[:3]] == ["wifi_key", "wifi_ssid", "wifi_on"]
    assert all(e["channel"] == "panel" and e["user"] == hass_admin_user.name for e in entries[:3])


async def test_wifi_set_partial(client: Any, entry: MockConfigEntry, router: MockRouter, world: RouterWorld) -> None:
    ok(await call(client, "woow_glinet/wifi/set", entry_id=entry.entry_id, iface="default_radio1", ssid="Only-5G-name"))
    assert world.calls("wifi.set_config")[-1].args == {"iface_name": "default_radio1", "ssid": "Only-5G-name"}


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"iface": "nope", "enabled": True}, "no_such_wifi"),
        ({"iface": "guest2g", "ssid": ""}, "bad_ssid"),
        ({"iface": "guest2g", "ssid": "客" * 11}, "bad_ssid"),
        ({"iface": "guest2g", "ssid": "bad\nname"}, "bad_ssid"),
        ({"iface": "guest2g", "key": "short"}, "bad_key"),
        ({"iface": "guest2g", "key": "x" * 64}, "bad_key"),
        ({"iface": "guest2g", "key": "tab\tin-the-key"}, "bad_key"),
    ],
)
async def test_wifi_set_refusals_carry_their_code(client: Any, entry: MockConfigEntry, world: RouterWorld, payload: dict, code: str) -> None:
    response = await call(client, "woow_glinet/wifi/set", entry_id=entry.entry_id, **payload)
    assert error_code(response) == code
    assert response["error"]["message"], "a human-readable message goes with the code"
    assert world.count("wifi.set_config") == 0


async def test_wifi_set_router_error(client: Any, entry: MockConfigEntry, router: MockRouter) -> None:
    router.configure(error_methods={"wifi.set_config": (-32602, "Invalid params")})
    response = await call(client, "woow_glinet/wifi/set", entry_id=entry.entry_id, iface="guest2g", enabled=True)
    assert error_code(response) == "api_error"
    assert "Invalid params" in response["error"]["message"]


async def test_wifi_set_after_the_router_password_changed(client: Any, entry: MockConfigEntry, router: MockRouter) -> None:
    router.configure(password="changed")
    assert error_code(await call(client, "woow_glinet/wifi/set", entry_id=entry.entry_id, iface="guest2g", enabled=True)) == "auth_failed"


async def test_wifi_key_is_returned_only_on_request(client: Any, entry: MockConfigEntry, router: MockRouter) -> None:
    snapshot = await call(client, "woow_glinet/snapshot")
    assert WIFI_KEY not in json.dumps(snapshot)

    result = ok(await call(client, "woow_glinet/wifi/key", entry_id=entry.entry_id, iface="default_radio0"))
    assert result == {"key": WIFI_KEY}

    iface(router, "guest5g")["key"] = "another-key-123"
    await entry.runtime_data.coordinator.async_refresh()
    assert ok(await call(client, "woow_glinet/wifi/key", entry_id=entry.entry_id, iface="guest5g")) == {"key": "another-key-123"}


async def test_wifi_key_of_an_open_network_is_empty(client: Any, entry: MockConfigEntry, router: MockRouter) -> None:
    iface(router, "guest2g").update(key="", encryption="none")
    await entry.runtime_data.coordinator.async_refresh()
    assert ok(await call(client, "woow_glinet/wifi/key", entry_id=entry.entry_id, iface="guest2g")) == {"key": ""}


async def test_wifi_key_unknown_interface(client: Any, entry: MockConfigEntry) -> None:
    response = await call(client, "woow_glinet/wifi/key", entry_id=entry.entry_id, iface="nope")
    assert error_code(response) == "no_such_wifi"
    assert WIFI_KEY not in json.dumps(response)


# ===================================================================================== clients
async def test_block_and_unblock(client: Any, entry: MockConfigEntry, router: MockRouter) -> None:
    ok(await call(client, "woow_glinet/client/block", entry_id=entry.entry_id, mac=MAC1.lower(), blocked=True))
    assert router.black_mac == [MAC1]
    ok(await call(client, "woow_glinet/client/block", entry_id=entry.entry_id, mac=MAC1, blocked=False))
    assert router.black_mac == []


@pytest.mark.parametrize(
    ("mac", "code"),
    [("not a mac", "invalid_mac"), ("FF:FF:FF:FF:FF:FF", "invalid_mac"), ("01:00:5E:00:00:01", "invalid_mac")],
)
async def test_block_with_a_bad_mac(client: Any, entry: MockConfigEntry, world: RouterWorld, mac: str, code: str) -> None:
    assert error_code(await call(client, "woow_glinet/client/block", entry_id=entry.entry_id, mac=mac, blocked=True)) == code
    assert world.count("black_white_list.set_single_mac") == 0


async def test_block_in_white_list_mode(client: Any, entry: MockConfigEntry, router: MockRouter) -> None:
    router.configure(blacklist_mode="white")
    await entry.runtime_data.coordinator.async_refresh()
    assert error_code(await call(client, "woow_glinet/client/block", entry_id=entry.entry_id, mac=MAC1, blocked=True)) == "not_blacklist_mode"


async def test_block_outside_router_mode(hass: HomeAssistant, client: Any, setup_router: SetupRouter) -> None:
    ap = await setup_router("192.0.2.30", mode="ap")
    assert error_code(await call(client, "woow_glinet/client/block", entry_id=ap.entry_id, mac=MAC1, blocked=True)) == "not_router_mode"


async def test_forget_an_offline_client(client: Any, entry: MockConfigEntry, router: MockRouter) -> None:
    ok(await call(client, "woow_glinet/client/forget", entry_id=entry.entry_id, mac=MAC2))
    assert MAC2 not in [c["mac"] for c in router.clients]


async def test_forget_an_online_client_is_refused(client: Any, entry: MockConfigEntry, router: MockRouter) -> None:
    assert error_code(await call(client, "woow_glinet/client/forget", entry_id=entry.entry_id, mac=MAC0)) == "client_online"
    assert MAC0 in [c["mac"] for c in router.clients]


async def test_client_history(client: Any, entry: MockConfigEntry) -> None:
    coordinator = entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await coordinator.async_live_poll()
    result = ok(await call(client, "woow_glinet/client/history", entry_id=entry.entry_id, mac=MAC0))
    assert set(result) == {"series"}
    assert len(result["series"]) == 3
    t, rx, tx = result["series"][-1]
    assert isinstance(t, float) and (rx, tx) == (1000, 100)


async def test_client_history_of_an_unknown_or_offline_client_is_empty(client: Any, entry: MockConfigEntry) -> None:
    assert ok(await call(client, "woow_glinet/client/history", entry_id=entry.entry_id, mac="DE:AD:BE:EF:00:01")) == {"series": []}
    assert ok(await call(client, "woow_glinet/client/history", entry_id=entry.entry_id, mac=MAC2)) == {"series": []}


# ===================================================================================== static IP
async def test_static_ip_add(client: Any, entry: MockConfigEntry, router: MockRouter) -> None:
    ok(await call(client, "woow_glinet/static_ip/add", entry_id=entry.entry_id, mac=MAC2, ip="192.168.8.50", name="TV"))
    assert router.static_binds == [{"mac": MAC2, "ip": "192.168.8.50", "name": "TV"}]


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"mac": "zz", "ip": "192.168.8.50", "name": "x"}, "invalid_mac"),
        ({"mac": MAC2, "ip": "999.1.1.1", "name": "x"}, "invalid_ip"),
        ({"mac": MAC2, "ip": "10.0.0.5", "name": "x"}, "ip_outside_lan"),
        ({"mac": MAC2, "ip": "192.168.8.1", "name": "x"}, "ip_outside_lan"),
        ({"mac": MAC2, "ip": "192.168.8.50", "name": "  "}, "bad_name"),
    ],
)
async def test_static_ip_add_refusals(client: Any, entry: MockConfigEntry, world: RouterWorld, payload: dict, code: str) -> None:
    assert error_code(await call(client, "woow_glinet/static_ip/add", entry_id=entry.entry_id, **payload)) == code
    assert world.count("lan.add_static_bind") == 0


async def test_static_ip_add_duplicates(client: Any, entry: MockConfigEntry, router: MockRouter) -> None:
    ok(await call(client, "woow_glinet/static_ip/add", entry_id=entry.entry_id, mac=MAC2, ip="192.168.8.50", name="TV"))
    assert error_code(await call(client, "woow_glinet/static_ip/add", entry_id=entry.entry_id, mac=MAC2, ip="192.168.8.51", name="x")) == "mac_already_bound"
    assert error_code(await call(client, "woow_glinet/static_ip/add", entry_id=entry.entry_id, mac=MAC1, ip="192.168.8.50", name="x")) == "ip_already_bound"


# ===================================================================================== reboot
async def test_reboot(client: Any, entry: MockConfigEntry, router: MockRouter) -> None:
    assert ok(await call(client, "woow_glinet/reboot", entry_id=entry.entry_id)) is None
    assert router.calls["system.reboot"] == 1


async def test_reboot_where_the_router_hangs_up(client: Any, entry: MockConfigEntry, router: MockRouter) -> None:
    router.reboot_style = "drop"
    assert ok(await call(client, "woow_glinet/reboot", entry_id=entry.entry_id)) is None


async def test_reboot_router_error(client: Any, entry: MockConfigEntry, router: MockRouter) -> None:
    router.configure(error_methods={"system.reboot": (-5, "Boom")})
    assert error_code(await call(client, "woow_glinet/reboot", entry_id=entry.entry_id)) == "api_error"


async def test_any_other_home_assistant_error_is_reported_as_failed(client: Any, entry: MockConfigEntry) -> None:
    async def explode(self: GlinetActions, *, origin: Any) -> None:
        raise HomeAssistantError("something else")

    with patch.object(GlinetActions, "reboot", explode):
        response = await call(client, "woow_glinet/reboot", entry_id=entry.entry_id)
    assert error_code(response) == "failed" and response["error"]["message"] == "something else"


async def test_an_unexpected_exception_does_not_kill_the_connection(client: Any, entry: MockConfigEntry) -> None:
    async def explode(self: GlinetActions, *, origin: Any) -> None:
        raise RuntimeError("bug")

    with patch.object(GlinetActions, "reboot", explode):
        response = await call(client, "woow_glinet/reboot", entry_id=entry.entry_id)
    assert error_code(response) == "unknown_error"
    assert ok(await call(client, "woow_glinet/snapshot"))["routers"], "the connection still works"


# ===================================================================================== the live feed
async def next_event(client: Any, subscription: int, kind: str | None = None) -> dict[str, Any]:
    """The next event of a subscription (optionally the next of one `kind`)."""
    while True:
        message = await asyncio.wait_for(client.receive_json(), timeout=10)
        assert message["id"] == subscription and message["type"] == "event", message
        if kind is None or message["event"]["kind"] == kind:
            return message["event"]


async def subscribe(client: Any, subscription: int = 100) -> int:
    await client.send_json({"id": subscription, "type": "woow_glinet/subscribe"})
    response = await asyncio.wait_for(client.receive_json(), timeout=10)
    assert response["id"] == subscription and response["success"] is True and response["result"] is None
    return subscription


async def test_subscribe_delivers_router_events(client: Any, entry: MockConfigEntry, router: MockRouter) -> None:
    sub = await subscribe(client)
    router.configure(ssids={"guest2g": "Renamed"})

    await entry.runtime_data.coordinator.async_refresh()

    event = await next_event(client, sub, "router")
    assert event["router"]["entry_id"] == entry.entry_id
    assert event["router"]["wifi"][0]["ifaces"][1]["ssid"] == "Renamed"
    assert WIFI_KEY not in json.dumps(event)


async def test_subscribe_delivers_live_events(hass: HomeAssistant, client: Any, entry: MockConfigEntry) -> None:
    sub = await subscribe(client)
    feed: PanelFeed = hass.data[DOMAIN]["feed"]

    await feed._tick(dt_util.utcnow())  # (what the 5 s timer does: see test_feed.py for the timer itself)

    event = await next_event(client, sub, "live")
    assert event["entry_id"] == entry.entry_id
    assert event["wan"] == {"rx": 12000, "tx": 1200}
    assert len(event["clients"]) == 6


async def call_with_events(client: Any, subscription: int, type_: str, **payload: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Send a command on a connection that also has a subscription: (the answer, the events that came before it)."""
    await client.send_json({"id": subscription + 1, "type": type_, **payload})  # (ids only ever go up)
    events: list[dict[str, Any]] = []
    while True:
        message = await asyncio.wait_for(client.receive_json(), timeout=10)
        if message["id"] == subscription + 1:
            return message, events
        assert message["id"] == subscription and message["type"] == "event"
        events.append(message["event"])


async def test_subscribe_delivers_activity_events(client: Any, entry: MockConfigEntry, hass_admin_user: Any) -> None:
    sub = await subscribe(client)

    answer, events = await call_with_events(client, sub, "woow_glinet/wifi/set", entry_id=entry.entry_id, iface="guest2g", enabled=True)

    ok(answer)
    (activity,) = [e for e in events if e["kind"] == "activity"]
    assert activity["entries"][0]["msg"] == "wifi_on"
    assert activity["entries"][0]["user"] == hass_admin_user.name and activity["entries"][0]["channel"] == "panel"
    assert [e["kind"] for e in events] == ["activity", "router"], "the change, then the refreshed router state"
    assert events[1]["router"]["wifi"][0]["ifaces"][1]["enabled"] is True


async def test_subscribe_delivers_router_removed(hass: HomeAssistant, client: Any, entry: MockConfigEntry) -> None:
    sub = await subscribe(client)
    await hass.config_entries.async_unload(entry.entry_id)
    event = await next_event(client, sub, "router_removed")
    assert event == {"kind": "router_removed", "entry_id": entry.entry_id}


async def test_unsubscribing_stops_the_feed(hass: HomeAssistant, client: Any, entry: MockConfigEntry) -> None:
    feed: PanelFeed = hass.data[DOMAIN]["feed"]
    sub = await subscribe(client)
    assert len(feed._subs) == 1 and feed._stop_live is not None

    await client.send_json({"id": 101, "type": "unsubscribe_events", "subscription": sub})
    response = await asyncio.wait_for(client.receive_json(), timeout=10)
    assert response["success"] is True

    assert feed._subs == [] and feed._stop_live is None and feed._stop_activity is None
    assert hass.data[DOMAIN]["activity"]._listeners == []


async def test_closing_the_connection_stops_the_feed(hass: HomeAssistant, client: Any, entry: MockConfigEntry) -> None:
    feed: PanelFeed = hass.data[DOMAIN]["feed"]
    await subscribe(client)
    assert len(feed._subs) == 1
    await client.close()
    for _ in range(50):
        await hass.async_block_till_done()
        if not feed._subs:
            break
        await asyncio.sleep(0.01)
    assert feed._subs == [] and feed._stop_live is None


async def test_two_panels_each_get_the_events(hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entry: MockConfigEntry) -> None:
    one, two = await hass_ws_client(hass), await hass_ws_client(hass)
    sub_one, sub_two = await subscribe(one, 11), await subscribe(two, 22)
    await entry.runtime_data.coordinator.async_refresh()
    assert (await next_event(one, sub_one, "router"))["router"]["entry_id"] == entry.entry_id
    assert (await next_event(two, sub_two, "router"))["router"]["entry_id"] == entry.entry_id


async def test_the_commands_exist_even_with_no_router_set_up(hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entry: MockConfigEntry) -> None:
    """They are registered once for the integration (async_setup), not per router."""
    await hass.config_entries.async_unload(entry.entry_id)
    client = await hass_ws_client(hass)
    result = ok(await call(client, "woow_glinet/snapshot"))
    assert result["routers"] == []
