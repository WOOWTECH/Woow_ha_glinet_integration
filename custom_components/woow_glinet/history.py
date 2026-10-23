"""In-memory traffic history for the panel's charts (WAN and per client); not persisted."""

from __future__ import annotations

from collections import deque
from typing import Any

from .const import HISTORY_CLIENT_KEEP, HISTORY_CLIENTS_MAX, HISTORY_WAN_KEEP
from .sanitize import as_int

Sample = tuple[float, int, int]  # (unix time, rx bytes/s, tx bytes/s)


class TrafficHistory:
    """Speed samples taken on every poll, by the coordinator (30 s) and the panel's live poll (5 s)."""

    def __init__(self) -> None:
        self.wan: deque[Sample] = deque(maxlen=HISTORY_WAN_KEEP)
        self.clients: dict[str, deque[Sample]] = {}

    def add(self, when: float, wan: dict[str, Any], clients: list[dict[str, Any]]) -> None:
        self.wan.append((when, as_int(wan.get("speed_rx")), as_int(wan.get("speed_tx"))))
        for client in clients:
            mac = client.get("mac")
            if not mac or not client.get("online"):
                continue
            series = self.clients.pop(mac, None)  # re-inserted below: dict order = least recently seen first
            if series is None:
                series = deque(maxlen=HISTORY_CLIENT_KEEP)
            series.append((when, as_int(client.get("rx")), as_int(client.get("tx"))))
            self.clients[mac] = series
        while len(self.clients) > HISTORY_CLIENTS_MAX:
            del self.clients[next(iter(self.clients))]

    def wan_series(self) -> list[list[float | int]]:
        return [list(s) for s in self.wan]

    def client_series(self, mac: str) -> list[list[float | int]]:
        return [list(s) for s in self.clients.get(mac, ())]
