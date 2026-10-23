"""feed.py: what the panel sees. `router_snapshot` (shape, no secrets, numbers) and `PanelFeed` (live polling, events)."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import timedelta
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import json_bytes
from mock_router import MockRouter
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.woow_glinet.activity import Origin
from custom_components.woow_glinet.const import DOMAIN, LIVE_INTERVAL
from custom_components.woow_glinet.coordinator import GlinetCoordinator
from custom_components.woow_glinet.feed import PanelFeed, client_record, router_snapshot
from testkit import HOST, HOST2, ROUTER_MAC, WIFI_KEY, RouterWorld, remove_method

TOP_LEVEL_KEYS = {
    "entry_id", "title", "host", "available", "fetched_at", "mode", "model", "hostname", "firmware", "mac", "lan_ip",
    "uptime", "load", "memory", "flash", "wan", "stations", "wifi", "clients", "static_binds", "blocklist",
    "auth_failed", "features",
}  # fmt: skip


class Sink(list):
    """A panel connection: collects the events pushed to it."""

    def __call__(self, event: dict[str, Any]) -> None:
        self.append(event)

    def of(self, kind: str) -> list[dict[str, Any]]:
        return [e for e in self if e["kind"] == kind]


@pytest.fixture(autouse=True)
def _frozen_clock(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """Time stands still until a test moves it. Autouse, so it is in place before Home Assistant and the router
    entry exist: timers scheduled during setup are then on the same clock as the ones the tests fire."""
    return freezer


@pytest.fixture
def feed(hass: HomeAssistant, entry: MockConfigEntry) -> PanelFeed:
    return hass.data[DOMAIN]["feed"]


async def tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float = LIVE_INTERVAL + 1) -> None:
    """Let `seconds` pass: the 5 s live timer fires, then everything it started is allowed to finish.

    The live poll (like the coordinator's own refresh) runs as a background task, which block_till_done()
    only waits for when asked to.
    """
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def walk(value: Any):
    """Every key and every value, at any depth."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from walk(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from walk(item)
    else:
        yield value


# ===================================================================================== router_snapshot: shape
async def test_snapshot_shape_and_values(coordinator: GlinetCoordinator, entry: MockConfigEntry) -> None:
    snap = router_snapshot(coordinator)

    assert set(snap) == TOP_LEVEL_KEYS
    assert snap["entry_id"] == entry.entry_id and snap["title"] == "GL-MOCK1200" and snap["host"] == HOST
    assert snap["available"] is True and snap["auth_failed"] is False
    assert snap["mode"] == "router"
    assert (snap["model"], snap["hostname"], snap["firmware"], snap["mac"]) == ("GL-MOCK1200", "GL-MOCK1200", "4.8.3", ROUTER_MAC)
    assert snap["lan_ip"] == "192.168.8.1"
    assert snap["load"] == [0.5, 0.6, 0.55]
    assert snap["uptime"] > 80000
    assert snap["memory"] == {"total": 121548800, "free": 21835776, "cache": 6815744}
    assert snap["flash"] == {"total": 134217728, "free": 85434368}
    assert snap["wan"] == {"online": True, "links": ["wan"], "rx": 12000, "tx": 1200}
    assert snap["stations"] == {"wireless": 2, "cable": 2}
    assert snap["blocklist"] == {"mode": "black", "black": [], "white": []}
    assert snap["static_binds"] == []
    assert isinstance(snap["fetched_at"], float)


async def test_snapshot_wifi_section(coordinator: GlinetCoordinator) -> None:
    wifi = router_snapshot(coordinator)["wifi"]
    assert [b["band"] for b in wifi] == ["2G", "5G"]
    assert set(wifi[0]) == {"band", "channel", "hwmode", "htmode", "ifaces"}
    main, guest = wifi[0]["ifaces"]
    assert set(main) == {"name", "ssid", "enabled", "up", "guest", "hidden", "encryption", "bssid"}
    assert (main["name"], main["ssid"], main["enabled"], main["up"], main["guest"]) == ("default_radio0", "MOCK-8f2", True, True, False)
    assert (guest["name"], guest["enabled"], guest["up"], guest["guest"]) == ("guest2g", False, False, True)
    assert main["encryption"] == "psk2" and main["bssid"].startswith("D2:00:00:")
    assert wifi[1]["ifaces"][0]["ssid"] == "MOCK-8f2-5G"


async def test_snapshot_clients(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    clients = router_snapshot(coordinator)["clients"]
    assert [c["mac"] for c in clients] == [f"AA:BB:CC:00:00:0{i}" for i in range(6)]
    first = clients[0]
    assert set(first) == {"mac", "ip", "name", "alias", "online", "blocked", "iface", "rx", "tx", "total_rx", "total_tx",
                          "limit_rx", "limit_tx", "since", "static_ip"}  # fmt: skip
    assert (first["name"], first["ip"], first["online"], first["iface"]) == ("iPhone-Ann", "192.168.8.10", True, "cable")
    assert (first["rx"], first["tx"]) == (1000, 100)
    assert clients[2]["online"] is False and clients[2]["rx"] == 0


async def test_snapshot_without_history_has_no_history_and_with_it_has_the_wan_series(coordinator: GlinetCoordinator) -> None:
    assert "history" not in router_snapshot(coordinator)
    snap = router_snapshot(coordinator, with_history=True)
    assert set(snap["history"]) == {"wan"}
    assert len(snap["history"]["wan"]) >= 1
    t, rx, tx = snap["history"]["wan"][0]
    assert isinstance(t, float) and (rx, tx) == (12000, 1200)


async def test_snapshot_is_json_serialisable(coordinator: GlinetCoordinator) -> None:
    snap = router_snapshot(coordinator, with_history=True)
    assert json.loads(json.dumps(snap)) == snap
    json_bytes(snap)  # the encoder the websocket API uses


async def test_snapshot_static_ip_matches_case_insensitively(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    router.static_binds = [{"mac": "aa:bb:cc:00:00:01", "ip": "192.168.8.99", "name": "mine"}]
    await coordinator.async_refresh()
    snap = router_snapshot(coordinator)
    assert snap["clients"][1]["static_ip"] == "192.168.8.99"
    assert snap["clients"][0]["static_ip"] is None
    assert snap["static_binds"] == [{"mac": "aa:bb:cc:00:00:01", "ip": "192.168.8.99", "name": "mine"}]


async def test_snapshot_blocklist_and_blocked_flag(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    router.configure(black_mac=["AA:BB:CC:00:00:03"])
    await coordinator.async_refresh()
    snap = router_snapshot(coordinator)
    assert snap["blocklist"]["black"] == ["AA:BB:CC:00:00:03"]
    assert [c["mac"] for c in snap["clients"] if c["blocked"]] == ["AA:BB:CC:00:00:03"]


async def test_snapshot_in_ap_mode(setup_router: Any) -> None:
    entry = await setup_router("192.0.2.30", mode="ap")
    snap = router_snapshot(entry.runtime_data.coordinator)
    assert snap["mode"] == "ap"
    assert set(snap) == TOP_LEVEL_KEYS


async def test_snapshot_of_a_router_without_system_status(setup_router: Any, world: RouterWorld) -> None:
    router = world.add("192.0.2.30")
    remove_method(router, "system.get_status")
    entry = await setup_router("192.0.2.30", router=router)
    snap = router_snapshot(entry.runtime_data.coordinator)
    assert (snap["lan_ip"], snap["uptime"], snap["load"], snap["memory"], snap["flash"]) == (None, None, None, None, None)
    assert snap["wan"]["online"] is False and snap["wan"]["links"] == []
    assert snap["stations"] == {"wireless": None, "cable": None}


# ===================================================================================== router_snapshot: secrets
async def test_snapshot_has_no_wifi_key_anywhere(coordinator: GlinetCoordinator, activity: Any) -> None:
    snap = router_snapshot(coordinator, with_history=True)
    leaves = list(walk(snap))
    assert WIFI_KEY not in leaves
    assert WIFI_KEY not in json.dumps(snap)
    names = {x for x in leaves if isinstance(x, str)}
    assert not {"key", "passwd", "password", "psk", "secret"} & names, "no secret-looking field names at any depth"


async def test_snapshot_does_not_pick_up_a_new_password(coordinator: GlinetCoordinator) -> None:
    await coordinator.actions.set_wifi("default_radio0", key="a-brand-new-secret", origin=Origin("panel", user="x"))
    assert "a-brand-new-secret" not in json.dumps(router_snapshot(coordinator, with_history=True))


# ===================================================================================== router_snapshot: numbers and times
async def test_snapshot_numbers_are_ints(coordinator: GlinetCoordinator) -> None:
    snap = router_snapshot(coordinator)
    for client in snap["clients"]:
        for field in ("rx", "tx", "total_rx", "total_tx", "limit_rx", "limit_tx"):
            assert type(client[field]) is int, f"{field} is {type(client[field]).__name__}"  # the router sends totals as strings
    assert type(snap["wan"]["rx"]) is int and type(snap["wan"]["tx"]) is int
    assert snap["clients"][0]["total_rx"] > 1_000_000


@pytest.mark.parametrize(("raw", "expected"), [("123", 123), (45.9, 45), (None, 0), ("", 0), ("12.5", 12), ("1e3", 1000), ("abc", 0), ([], 0), (True, 1), (float("nan"), 0), (float("inf"), 0), (10**400, 0)])
def test_client_record_coerces_numbers(raw: Any, expected: int) -> None:
    record = client_record({"mac": "AA", "rx": raw, "tx": raw, "total_rx": raw, "total_tx": raw, "limit_rx": raw, "limit_tx": raw}, {}, 0.0)
    assert all(record[f] == expected and type(record[f]) is int for f in ("rx", "tx", "total_rx", "total_tx", "limit_rx", "limit_tx"))


def test_client_record_missing_fields() -> None:
    record = client_record({}, {}, 0.0)
    assert record == {
        "mac": "", "ip": "", "name": "", "alias": "", "online": False, "blocked": False, "iface": "", "rx": 0, "tx": 0,
        "total_rx": 0, "total_tx": 0, "limit_rx": 0, "limit_tx": 0, "since": None, "static_ip": None,
    }  # fmt: skip


@pytest.mark.parametrize(
    ("client", "skew", "expected"),
    [
        ({"online": True, "online_time": 1000}, 0.0, 1000.0),
        ({"online": True, "online_time": 1000}, 120.5, 1120.5),
        ({"online": True, "online_time": 1000}, -30.0, 970.0),
        ({"online": True, "online_time": "1000"}, 10.0, 1010.0),
        ({"online": False, "online_time": 1000}, 0.0, None),
        ({"online": True, "online_time": 0}, 0.0, None),
        ({"online": True}, 0.0, None),
        ({"online": True, "online_time": None}, 0.0, None),
    ],
)
def test_client_record_converts_since_to_this_hosts_clock(client: dict, skew: float, expected: float | None) -> None:
    since = client_record({"mac": "AA", **client}, {}, skew)["since"]
    assert since == expected
    assert since is None or type(since) is float


async def test_snapshot_since_uses_the_measured_clock_skew(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    coordinator.clock_skew = 3600.0  # this host is an hour ahead of the router
    snap = router_snapshot(coordinator)
    by_mac = {c["mac"]: c for c in router.clients}
    for client in snap["clients"]:
        raw = by_mac[client["mac"]]
        assert client["since"] == (float(raw["online_time"]) + 3600.0 if raw["online"] else None)


async def test_clock_skew_is_measured_from_the_router(coordinator: GlinetCoordinator) -> None:
    assert abs(coordinator.clock_skew) < 5, "mock and test share a clock"


def test_client_record_static_ip_lookup() -> None:
    statics = {"AA:BB": {"mac": "aa:bb", "ip": "1.2.3.4", "name": "x"}}
    assert client_record({"mac": "aa:bb"}, statics, 0.0)["static_ip"] == "1.2.3.4"
    assert client_record({"mac": "CC:DD"}, statics, 0.0)["static_ip"] is None


# ===================================================================================== router_snapshot: features & auth
FEATURES = [
    ("clients.get_wan_speed", "wan_speed"),
    ("clients.get_list", "clients"),
    ("wifi.get_config", "wifi"),
    ("lan.get_static_bind_list", "static_ip"),
    ("black_white_list.get_config", "blocklist"),
]


async def test_features_are_all_on_for_a_complete_firmware(coordinator: GlinetCoordinator) -> None:
    assert router_snapshot(coordinator)["features"] == {
        "static_ip_remove": False,  # lan.remove_static_bind answers "Invalid params" on the firmware this was written for
        "wan_speed": True, "clients": True, "wifi": True, "static_ip": True, "blocklist": True,
    }  # fmt: skip


@pytest.mark.parametrize(("method", "feature"), FEATURES)
async def test_a_missing_method_switches_its_feature_off(setup_router: Any, world: RouterWorld, method: str, feature: str) -> None:
    router = world.add("192.0.2.30")
    remove_method(router, method)
    entry = await setup_router("192.0.2.30", router=router)
    features = router_snapshot(entry.runtime_data.coordinator)["features"]
    assert features[feature] is False
    assert all(v for k, v in features.items() if k not in (feature, "static_ip_remove")), "only that one feature goes"


async def test_snapshot_reports_auth_failed(coordinator: GlinetCoordinator) -> None:
    coordinator.auth_failed = True
    assert router_snapshot(coordinator)["auth_failed"] is True


async def test_snapshot_reports_a_router_that_stopped_answering(coordinator: GlinetCoordinator, world: RouterWorld) -> None:
    world.disconnect(HOST)
    await coordinator.async_refresh()
    assert router_snapshot(coordinator)["available"] is False


# ===================================================================================== PanelFeed.snapshot
async def test_feed_snapshot(feed: PanelFeed, entry: MockConfigEntry) -> None:
    snap = feed.snapshot()
    assert set(snap) == {"routers", "activity", "live_interval"}
    assert snap["live_interval"] == LIVE_INTERVAL == 5
    assert [r["entry_id"] for r in snap["routers"]] == [entry.entry_id]
    assert "history" in snap["routers"][0]
    assert snap["activity"] == []
    json_bytes(snap)


async def test_feed_snapshot_has_the_activity_newest_first(feed: PanelFeed, coordinator: GlinetCoordinator) -> None:
    await coordinator.actions.set_wifi("guest2g", enabled=True, origin=Origin("panel", user="x"))
    await coordinator.actions.set_wifi("guest2g", enabled=False, origin=Origin("panel", user="x"))
    assert [a["msg"] for a in feed.snapshot()["activity"]] == ["wifi_off", "wifi_on"]


async def test_feed_snapshot_lists_only_loaded_routers(hass: HomeAssistant, feed: PanelFeed, entry: MockConfigEntry,
                                                       setup_router: Any, world: RouterWorld) -> None:
    second = await setup_router(HOST2, mac="94:83:C4:00:00:02")
    assert {r["entry_id"] for r in feed.snapshot()["routers"]} == {entry.entry_id, second.entry_id}
    await hass.config_entries.async_unload(second.entry_id)
    assert [r["entry_id"] for r in feed.snapshot()["routers"]] == [entry.entry_id]


# ===================================================================================== PanelFeed: live polling
async def test_the_first_subscriber_starts_live_polling_and_the_last_one_stops_it(
    hass: HomeAssistant, feed: PanelFeed, world: RouterWorld, freezer: FrozenDateTimeFactory
) -> None:
    base = world.count("clients.get_wan_speed")
    await tick(hass, freezer)
    assert world.count("clients.get_wan_speed") == base, "nobody is looking: the router is not polled faster"

    sink = Sink()
    unsubscribe = feed.subscribe(sink)
    await tick(hass, freezer)
    assert world.count("clients.get_wan_speed") == base + 1
    assert world.count("clients.get_list") >= 1
    assert len(sink.of("live")) == 1

    await tick(hass, freezer)
    assert len(sink.of("live")) == 2

    unsubscribe()
    await tick(hass, freezer)
    assert world.count("clients.get_wan_speed") == base + 2, "unsubscribing stops the fast poll"
    assert len(sink.of("live")) == 2


async def test_unsubscribing_twice_is_harmless(feed: PanelFeed) -> None:
    unsubscribe = feed.subscribe(Sink())
    unsubscribe()
    unsubscribe()
    assert feed._subs == [] and feed._stop_live is None and feed._stop_activity is None


async def test_two_panels_share_one_poll(hass: HomeAssistant, feed: PanelFeed, world: RouterWorld, activity: Any,
                                         freezer: FrozenDateTimeFactory) -> None:
    one, two = Sink(), Sink()
    unsub_one = feed.subscribe(one)
    unsub_two = feed.subscribe(two)
    assert len(activity._listeners) == 1, "one activity subscription for any number of panels"

    base = world.count("clients.get_wan_speed")
    await tick(hass, freezer)
    assert world.count("clients.get_wan_speed") == base + 1, "polled once for both"
    assert len(one.of("live")) == len(two.of("live")) == 1

    unsub_one()
    await tick(hass, freezer)
    assert len(one.of("live")) == 1 and len(two.of("live")) == 2, "the second panel keeps being served"

    unsub_two()
    assert activity._listeners == []
    await tick(hass, freezer)
    assert len(two.of("live")) == 2


async def test_live_event_payload(hass: HomeAssistant, feed: PanelFeed, entry: MockConfigEntry, router: MockRouter,
                                  freezer: FrozenDateTimeFactory) -> None:
    sink = Sink()
    feed.subscribe(sink)
    await tick(hass, freezer)

    (event,) = sink.of("live")
    assert set(event) == {"kind", "entry_id", "t", "wan", "clients"}
    assert event["entry_id"] == entry.entry_id
    assert event["wan"] == {"rx": 12000, "tx": 1200}
    assert [c["mac"] for c in event["clients"]] == [f"AA:BB:CC:00:00:0{i}" for i in range(6)]
    assert event["clients"][0]["rx"] == 1000 and event["clients"][0]["online"] is True
    assert event["t"] == pytest.approx(time.time(), abs=1.0)  # (frozen) now
    json_bytes(event)


async def test_live_poll_feeds_the_history(hass: HomeAssistant, feed: PanelFeed, coordinator: GlinetCoordinator,
                                           freezer: FrozenDateTimeFactory) -> None:
    feed.subscribe(Sink())
    before = len(coordinator.history.wan)
    await tick(hass, freezer)
    await tick(hass, freezer)
    assert len(coordinator.history.wan) == before + 2
    assert len(coordinator.history.client_series("AA:BB:CC:00:00:00")) >= 3


async def test_live_poll_skips_a_router_whose_credentials_were_rejected(
    hass: HomeAssistant, feed: PanelFeed, coordinator: GlinetCoordinator, world: RouterWorld, freezer: FrozenDateTimeFactory
) -> None:
    sink = Sink()
    feed.subscribe(sink)
    coordinator.auth_failed = True
    base = world.count("clients.get_wan_speed")

    await tick(hass, freezer)

    assert world.count("clients.get_wan_speed") == base, "no retries with a wrong password"
    assert sink.of("live") == []


async def test_live_poll_skips_routers_that_are_not_in_router_mode(
    hass: HomeAssistant, feed: PanelFeed, entry: MockConfigEntry, setup_router: Any, world: RouterWorld, freezer: FrozenDateTimeFactory
) -> None:
    ap = await setup_router("192.0.2.30", mode="ap")
    sink = Sink()
    feed.subscribe(sink)
    base = world.count("clients.get_wan_speed", "192.0.2.30")
    await tick(hass, freezer)
    assert world.count("clients.get_wan_speed", "192.0.2.30") == base
    assert [e["entry_id"] for e in sink.of("live")] == [entry.entry_id], "only the router-mode router is polled fast"
    assert ap.entry_id not in [e["entry_id"] for e in sink.of("live")]


async def test_live_poll_does_not_pile_up_on_a_slow_router(hass: HomeAssistant, feed: PanelFeed, entry: MockConfigEntry,
                                                           world: RouterWorld, freezer: FrozenDateTimeFactory) -> None:
    release = asyncio.Event()
    world.inject("clients.get_wan_speed", before=release.wait, times=1)
    sink = Sink()
    feed.subscribe(sink)
    base = world.count("clients.get_wan_speed")

    freezer.tick(timedelta(seconds=6))
    async_fire_time_changed(hass)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert world.count("clients.get_wan_speed") == base + 1, "the first poll is under way and stuck"

    for _ in range(2):  # two more ticks while the router is still thinking (24 s in all: before the 30 s entity refresh)
        freezer.tick(timedelta(seconds=6))
        async_fire_time_changed(hass)
        await asyncio.sleep(0)
    assert world.count("clients.get_wan_speed") == base + 1, "no second request while one is outstanding"
    assert entry.entry_id in feed._busy

    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(sink.of("live")) == 1 and feed._busy == set()

    await tick(hass, freezer)
    assert world.count("clients.get_wan_speed") == base + 2, "and it polls again afterwards"


async def test_live_poll_survives_a_router_that_stops_answering(
    hass: HomeAssistant, feed: PanelFeed, world: RouterWorld, freezer: FrozenDateTimeFactory
) -> None:
    sink = Sink()
    feed.subscribe(sink)
    world.inject("clients.get_wan_speed", exc=TimeoutError(), times=1)

    await tick(hass, freezer)
    assert sink.of("live") == [] and feed._busy == set(), "no event, no crash, not stuck busy"

    await tick(hass, freezer)
    assert len(sink.of("live")) == 1, "the next tick tries again"


async def test_live_poll_that_finds_the_password_changed_asks_for_reauthentication(
    hass: HomeAssistant, feed: PanelFeed, coordinator: GlinetCoordinator, entry: MockConfigEntry, router: MockRouter,
    world: RouterWorld, freezer: FrozenDateTimeFactory
) -> None:
    sink = Sink()
    feed.subscribe(sink)
    router.configure(password="changed-on-the-router")

    await tick(hass, freezer)

    assert coordinator.auth_failed is True
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f["context"]["source"] for f in flows] == ["reauth"]
    assert sink.of("live") == []

    base = world.count("login")
    await tick(hass, freezer)
    assert world.count("login") == base, "and the panel stops hammering the router with the old password"


async def test_one_slow_router_does_not_hold_up_the_others(
    hass: HomeAssistant, feed: PanelFeed, setup_router: Any, world: RouterWorld, freezer: FrozenDateTimeFactory
) -> None:
    second = await setup_router(HOST2, mac="94:83:C4:00:00:02")
    world.inject(lambda req: req.method == "clients.get_wan_speed" and req.host == HOST, exc=TimeoutError(), times=None)
    sink = Sink()
    feed.subscribe(sink)

    await tick(hass, freezer)

    assert [e["entry_id"] for e in sink.of("live")] == [second.entry_id]


# ===================================================================================== PanelFeed: events
async def test_router_event_after_a_refresh(hass: HomeAssistant, feed: PanelFeed, coordinator: GlinetCoordinator, router: MockRouter) -> None:
    sink = Sink()
    feed.subscribe(sink)
    router.configure(ssids={"guest2g": "Renamed"})

    await coordinator.async_refresh()

    (event,) = sink.of("router")
    assert set(event) == {"kind", "router"}
    assert set(event["router"]) == TOP_LEVEL_KEYS
    assert event["router"]["wifi"][0]["ifaces"][1]["ssid"] == "Renamed"
    assert WIFI_KEY not in json.dumps(event)
    json_bytes(event)


async def test_router_event_not_sent_to_a_panel_that_left(hass: HomeAssistant, feed: PanelFeed, coordinator: GlinetCoordinator) -> None:
    sink = Sink()
    feed.subscribe(sink)()
    await coordinator.async_refresh()
    assert sink == []


async def test_router_removed_event_when_an_entry_unloads(hass: HomeAssistant, feed: PanelFeed, entry: MockConfigEntry) -> None:
    sink = Sink()
    feed.subscribe(sink)
    await hass.config_entries.async_unload(entry.entry_id)
    assert sink.of("router_removed") == [{"kind": "router_removed", "entry_id": entry.entry_id}]


async def test_activity_event_when_something_is_changed(feed: PanelFeed, coordinator: GlinetCoordinator) -> None:
    sink = Sink()
    feed.subscribe(sink)
    await coordinator.actions.set_wifi("guest2g", enabled=True, origin=Origin("panel", user="Alice"))
    (event,) = sink.of("activity")
    assert set(event) == {"kind", "entries"}
    assert event["entries"][0]["msg"] == "wifi_on" and event["entries"][0]["user"] == "Alice"
    assert sink.of("router"), "and the refreshed router state is pushed as well"


async def test_no_events_after_the_last_panel_left(feed: PanelFeed, coordinator: GlinetCoordinator) -> None:
    sink = Sink()
    feed.subscribe(sink)()
    await coordinator.actions.set_wifi("guest2g", enabled=True, origin=Origin("panel", user="Alice"))
    assert sink == []


async def test_router_updated_ignores_a_coordinator_without_data(feed: PanelFeed, coordinator: GlinetCoordinator) -> None:
    sink = Sink()
    feed.subscribe(sink)
    saved, coordinator.data = coordinator.data, None
    try:
        feed.router_updated(coordinator)
    finally:
        coordinator.data = saved
    assert sink == []


async def test_coordinators_are_only_the_loaded_ones_with_data(hass: HomeAssistant, feed: PanelFeed, entry: MockConfigEntry,
                                                               coordinator: GlinetCoordinator) -> None:
    assert feed.coordinators() == [coordinator]
    await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert feed.coordinators() == []



# ===================================================================================== odd answers from the router
@pytest.mark.parametrize("key", ["network", "wifi", "client", "service", "system"])
@pytest.mark.parametrize(
    "junk", [None, 5, "text", {}, [], [None, 5, "x"]], ids=["null", "number", "string", "empty-object", "empty-list", "junk-items"]
)
async def test_the_snapshot_survives_odd_parts_of_the_status(coordinator: GlinetCoordinator, router: MockRouter, key: str, junk: Any) -> None:
    """The status is read from a Lua firmware that serialises empty tables as [] and may send anything: the panel must still load."""
    original = router.methods["system.get_status"]
    router.methods["system.get_status"] = lambda params: {**original(params), key: junk}
    await coordinator.async_refresh()

    snap = router_snapshot(coordinator, with_history=True)

    json.dumps(snap)
    assert snap["mode"] == "router" and len(snap["clients"]) == 6 and snap["firmware"] == "4.8.3"
    json_bytes(PanelFeed.snapshot(coordinator.hass.data[DOMAIN]["feed"]))


async def test_the_snapshot_uses_what_is_usable_in_a_partly_odd_status(coordinator: GlinetCoordinator, router: MockRouter) -> None:
    original = router.methods["system.get_status"]
    router.methods["system.get_status"] = lambda params: {
        **original(params),
        "network": [None, 5, {"interface": "wan", "online": True}, {"interface": "wwan", "online": False}],
        "client": [None, {"wireless_total": 3, "cable_total": 4}],
        "wifi": [None, "x", {"name": "default_radio0", "up": True}, {"name": "guest2g", "up": False}],
    }
    await coordinator.async_refresh()
    snap = router_snapshot(coordinator)
    assert snap["wan"]["links"] == ["wan"] and snap["wan"]["online"] is True
    assert snap["stations"] == {"wireless": 3, "cable": 4}
    main, guest = snap["wifi"][0]["ifaces"]
    assert (main["up"], guest["up"]) == (True, False)


@pytest.mark.parametrize(
    ("ifaces", "expected"),
    [(None, 0), (5, 0), ("text", 0), ({}, 0), ([], 0), ([None, "x", 7], 0), ([None, "x", {"name": "a", "ssid": "S", "enabled": 1}], 1)],
    ids=["null", "number", "string", "empty-object", "empty-list", "junk-items", "one-good-item"],
)
async def test_the_snapshot_survives_odd_interface_lists(coordinator: GlinetCoordinator, ifaces: Any, expected: int) -> None:
    coordinator.data.wifi_bands = [{"band": "2G", "ifaces": ifaces}]
    snap = router_snapshot(coordinator)
    json.dumps(snap)
    assert len(snap["wifi"][0]["ifaces"]) == expected
    if expected:
        assert snap["wifi"][0]["ifaces"][0]["ssid"] == "S" and snap["wifi"][0]["ifaces"][0]["enabled"] is True


async def test_live_events_survive_junk_clients(hass: HomeAssistant, feed: PanelFeed, router: MockRouter, freezer: FrozenDateTimeFactory) -> None:
    from testkit import override

    sink = Sink()
    feed.subscribe(sink)
    good = {"mac": "AA:BB:CC:00:00:70", "name": "Kept", "online": True, "rx": 5, "tx": 6}
    override(router, "clients.get_list", lambda p: {"clients": [None, "x", 5, [], {"no": "mac"}, good]})

    await tick(hass, freezer)

    (event,) = sink.of("live")
    assert [c["mac"] for c in event["clients"]] == ["AA:BB:CC:00:00:70"]


# ===================================================================================== a client record the panel cannot read
@pytest.mark.parametrize("since", ["garbage", [1], {"a": 1}, 10**400], ids=["text", "list", "object", "huge-int"])
def test_a_client_with_an_unparseable_online_time_does_not_break_the_panel(since: Any) -> None:
    assert client_record({"mac": "AA", "online": True, "online_time": since}, {}, 0.0)["since"] is None
