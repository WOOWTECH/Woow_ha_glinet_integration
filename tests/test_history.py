"""history.py: the in-memory traffic history behind the panel's charts (ring sizes, per-client cap, ordering)."""

from __future__ import annotations

import json

from custom_components.woow_glinet.const import HISTORY_CLIENT_KEEP, HISTORY_CLIENTS_MAX, HISTORY_WAN_KEEP
from custom_components.woow_glinet.history import TrafficHistory


def client(mac: str, rx: object = 1, tx: object = 1, online: bool = True) -> dict:
    return {"mac": mac, "rx": rx, "tx": tx, "online": online}


def test_limits_are_what_the_panel_expects() -> None:
    assert (HISTORY_WAN_KEEP, HISTORY_CLIENT_KEEP, HISTORY_CLIENTS_MAX) == (1500, 360, 200)


def test_wan_ring_keeps_the_newest_samples_in_order() -> None:
    history = TrafficHistory()
    for i in range(HISTORY_WAN_KEEP + 25):
        history.add(float(i), {"speed_rx": i, "speed_tx": 2 * i}, [])

    series = history.wan_series()

    assert len(series) == HISTORY_WAN_KEEP
    assert series[0] == [25.0, 25, 50], "the 25 oldest samples were pushed out"
    assert series[-1] == [float(HISTORY_WAN_KEEP + 24), HISTORY_WAN_KEEP + 24, 2 * (HISTORY_WAN_KEEP + 24)]
    times = [s[0] for s in series]
    assert times == sorted(times)


def test_wan_series_is_json_friendly_and_a_copy() -> None:
    history = TrafficHistory()
    history.add(1.0, {"speed_rx": 5, "speed_tx": 6}, [])
    series = history.wan_series()
    assert series == [[1.0, 5, 6]]
    json.dumps(series)
    series[0][1] = 999
    series.append([2.0, 0, 0])
    assert history.wan_series() == [[1.0, 5, 6]], "the caller must not be able to edit the history"


def test_empty_history() -> None:
    history = TrafficHistory()
    assert history.wan_series() == []
    assert history.client_series("AA:BB:CC:00:00:01") == []


def test_per_client_ring_is_capped_and_ordered() -> None:
    history = TrafficHistory()
    for i in range(HISTORY_CLIENT_KEEP + 40):
        history.add(float(i), {}, [client("AA:00:00:00:00:01", rx=i, tx=i + 1)])

    series = history.client_series("AA:00:00:00:00:01")

    assert len(series) == HISTORY_CLIENT_KEEP
    assert series[0] == [40.0, 40, 41]
    assert series[-1][0] == float(HISTORY_CLIENT_KEEP + 39)
    assert [s[0] for s in series] == sorted(s[0] for s in series)


def test_clients_have_separate_series() -> None:
    history = TrafficHistory()
    history.add(1.0, {}, [client("A", rx=10), client("B", rx=20)])
    history.add(2.0, {}, [client("A", rx=11)])
    assert history.client_series("A") == [[1.0, 10, 1], [2.0, 11, 1]]
    assert history.client_series("B") == [[1.0, 20, 1]]


def test_only_online_clients_with_a_mac_are_recorded() -> None:
    history = TrafficHistory()
    history.add(
        1.0,
        {},
        [client("ON", rx=1), client("OFF", rx=2, online=False), {"mac": "", "rx": 3, "online": True}, {"rx": 4, "online": True}, client("ON2", rx=5)],
    )
    assert set(history.clients) == {"ON", "ON2"}


def test_a_client_that_goes_offline_keeps_its_old_samples() -> None:
    history = TrafficHistory()
    history.add(1.0, {}, [client("A", rx=7)])
    history.add(2.0, {}, [client("A", rx=0, online=False)])
    assert history.client_series("A") == [[1.0, 7, 1]]


def test_client_count_is_capped_dropping_the_least_recently_seen() -> None:
    history = TrafficHistory()
    history.add(1.0, {}, [client(f"c{i:03d}") for i in range(HISTORY_CLIENTS_MAX)])
    assert len(history.clients) == HISTORY_CLIENTS_MAX

    # c000 is seen again (so it is now the most recently seen), and a new client arrives
    history.add(2.0, {}, [client("c000"), client("new")])

    assert len(history.clients) == HISTORY_CLIENTS_MAX
    assert "c001" not in history.clients, "the least recently seen one goes"
    assert "c000" in history.clients and "new" in history.clients
    assert len(history.client_series("c000")) == 2, "a client that stays keeps its history"
    assert len(history.client_series("new")) == 1


def test_many_new_clients_at_once_drop_the_oldest_of_them() -> None:
    history = TrafficHistory()
    history.add(1.0, {}, [client(f"c{i:03d}") for i in range(HISTORY_CLIENTS_MAX + 50)])
    assert len(history.clients) == HISTORY_CLIENTS_MAX
    assert "c000" not in history.clients and "c049" not in history.clients
    assert "c050" in history.clients and f"c{HISTORY_CLIENTS_MAX + 49:03d}" in history.clients


def test_numbers_are_coerced_to_int() -> None:
    history = TrafficHistory()
    history.add(1.0, {"speed_rx": "1234", "speed_tx": 5.9}, [client("A", rx="77", tx=None)])
    assert history.wan_series() == [[1.0, 1234, 5]]
    assert history.client_series("A") == [[1.0, 77, 0]]


def test_garbage_numbers_become_zero() -> None:
    history = TrafficHistory()
    history.add(1.0, {"speed_rx": "n/a", "speed_tx": None}, [client("A", rx="x", tx=[])])
    assert history.wan_series() == [[1.0, 0, 0]]
    assert history.client_series("A") == [[1.0, 0, 0]]


def test_missing_fields_are_zero() -> None:
    history = TrafficHistory()
    history.add(1.0, {}, [{"mac": "A", "online": True}])
    assert history.wan_series() == [[1.0, 0, 0]]
    assert history.client_series("A") == [[1.0, 0, 0]]
