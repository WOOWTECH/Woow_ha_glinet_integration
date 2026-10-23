"""Shared test kit: GL.iNet routers living in memory, reached through an in-process stand-in for aiohttp.

`tools/mock_router.py` already is a faithful GL.iNet 4.x /rpc server. Here it is plugged in *behind* the
integration's own HTTP layer so that the real `GlinetClient` code (JSON parsing, error mapping, login hashing,
session handling) runs unchanged and no socket is ever opened:

    GlinetClient --> MockSession.post(url, json=...) --> RouterWorld.serve() --> MockRouter.handle()

What the "wire" does on purpose, so the tests cannot cheat:
  * requests and responses are round-tripped through JSON (nothing is shared by reference);
  * every request yields to the event loop before and after the router handles it, so concurrent callers really
    interleave (a lock that is missing in the integration shows up as a lost update);
  * the exceptions raised are the ones aiohttp raises (ServerDisconnectedError, ClientConnectorError, TimeoutError).
"""

from __future__ import annotations

import asyncio
import copy
import json
import types
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import aiohttp
from aiohttp.client_reqrep import ConnectionKey

from mock_router import DropConnection, HttpFailure, MockRouter

HOST = "192.0.2.10"  # TEST-NET-1 (RFC 5737): can never be a real device
HOST2 = "192.0.2.20"
PASSWORD = "mockpass"
ROUTER_MAC = "94:83:C4:00:00:01"
ROUTER_TITLE = "GL-MOCK1200"  # the mock's board_info.hostname, which the config flow uses as the entry title
WIFI_KEY = "mock-wifi-key"  # the Wi-Fi password of every interface of the mock

# A made-up MAC for tests that need a device that is *not* in the router's client list.
STRANGER_MAC = "DE:AD:BE:EF:00:02"

_CONSTRUCTOR_ARGS = {"username", "password", "mac", "clients", "mode", "alg", "hash_method", "wifi", "seed", "session_ttl", "nonce_ttl"}


@dataclass
class Request:
    """One POST the integration made."""

    url: str
    scheme: str
    host: str
    payload: dict[str, Any]
    timeout: Any
    ssl: Any

    @property
    def method(self) -> str:
        """'challenge', 'login' or 'object.method' for a call."""
        if self.payload.get("method") == "call":
            params = self.payload["params"]
            return f"{params[1]}.{params[2]}"
        return str(self.payload.get("method"))

    @property
    def args(self) -> dict[str, Any]:
        params = self.payload.get("params")
        return params[3] if self.payload.get("method") == "call" else (params or {})


@dataclass
class Rule:
    """A one-off (or n-off) interference with the transport: raise `exc`, or answer `raw` bytes with `status`."""

    when: Callable[[Request], bool]
    exc: BaseException | None = None
    raw: bytes | None = None
    status: int = 200
    times: int | None = None  # None = forever
    hits: int = 0
    before: Callable[[], Any] | None = None


class _Response:
    def __init__(self, status: int, raw: bytes) -> None:
        self.status = status
        self._raw = raw

    async def read(self) -> bytes:
        return self._raw


class _Post:
    """The async context manager `session.post(...)` returns."""

    def __init__(self, world: RouterWorld, url: str, payload: dict[str, Any], timeout: Any, ssl: Any) -> None:
        self._args = (world, url, payload, timeout, ssl)

    async def __aenter__(self) -> _Response:
        world, url, payload, timeout, ssl = self._args
        return await world.serve(url, payload, timeout, ssl)

    async def __aexit__(self, *exc: object) -> None:
        return None


class MockSession:
    """Quacks like the part of aiohttp.ClientSession that GlinetClient uses."""

    def __init__(self, world: RouterWorld) -> None:
        self.world = world

    def post(self, url: str, *, json: Any = None, timeout: Any = None, ssl: Any = None, **kwargs: Any) -> _Post:
        assert not kwargs, f"GlinetClient passed an argument the stand-in does not model: {kwargs}"
        return _Post(self.world, url, json, timeout, ssl)


@dataclass
class RouterWorld:
    """All the routers a test can reach, by 'host' (the part between the scheme and /rpc)."""

    routers: dict[str, MockRouter] = field(default_factory=dict)
    requests: list[Request] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    unreachable: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.session = MockSession(self)

    # ------------------------------------------------------------------ building the world
    def add(self, host: str = HOST, router: MockRouter | None = None, **kwargs: Any) -> MockRouter:
        """Put a router on the network (a fresh, deterministic one unless given).

        Keywords are MockRouter constructor arguments, or - for the rest (blacklist_mode, black_mac, ...) - settings
        handed to `MockRouter.configure()` once it is built.
        """
        if router is None:
            router = MockRouter(**{k: v for k, v in kwargs.items() if k in _CONSTRUCTOR_ARGS})
            quiet(router)
            router.configure(**{k: v for k, v in kwargs.items() if k not in _CONSTRUCTOR_ARGS})
        else:
            quiet(router)
        self.routers[host] = router
        return router

    def disconnect(self, host: str = HOST) -> None:
        """The host stops answering: connections are refused."""
        self.unreachable.add(host)

    def reconnect(self, host: str = HOST) -> None:
        self.unreachable.discard(host)

    def inject(self, when: Callable[[Request], bool] | str, *, exc: BaseException | None = None,
               raw: bytes | None = None, status: int = 200, times: int | None = 1,
               before: Callable[[], Any] | None = None) -> Rule:
        """Interfere with matching requests before the router sees them. `when` may be an 'object.method' name."""
        if isinstance(when, str):
            name = when
            when = lambda req, name=name: req.method == name  # noqa: E731
        rule = Rule(when, exc, raw, status, times, before=before)
        self.rules.append(rule)
        return rule

    # ------------------------------------------------------------------ inspecting what happened
    def calls(self, name: str | None = None, host: str | None = None) -> list[Request]:
        """Requests made (optionally only for one 'object.method' / 'login' / 'challenge' and one host)."""
        return [r for r in self.requests if (name is None or r.method == name) and (host is None or r.host == host)]

    def count(self, name: str, host: str | None = None) -> int:
        return len(self.calls(name, host))

    # ------------------------------------------------------------------ the transport
    async def serve(self, url: str, payload: dict[str, Any], timeout: Any, ssl: Any) -> _Response:
        parts = urlsplit(url)
        request = Request(url, parts.scheme, parts.netloc, copy.deepcopy(payload), timeout, ssl)
        self.requests.append(request)
        await asyncio.sleep(0)  # the request is "on the wire": other tasks run now

        for rule in list(self.rules):
            if rule.times is not None and rule.hits >= rule.times:
                continue
            if rule.when(request):
                rule.hits += 1
                if rule.before is not None:
                    result = rule.before()
                    if asyncio.iscoroutine(result):
                        await result
                if rule.exc is not None:
                    raise rule.exc
                if rule.raw is not None:
                    return _Response(rule.status, rule.raw)

        router = self.routers.get(parts.netloc)
        if router is None or parts.netloc in self.unreachable:
            key = ConnectionKey(parts.hostname or "", parts.port or 443, parts.scheme == "https", False, None, None, None, None)
            raise aiohttp.ClientConnectorError(key, OSError(111, "Connection refused"))

        wire = json.loads(json.dumps(payload))  # what the router would receive
        try:
            out = router.handle(wire)
        except DropConnection as drop:
            if str(drop) == "hang":  # the caller would wait until its own timeout fires
                raise TimeoutError from drop
            raise aiohttp.ServerDisconnectedError("Server disconnected") from drop
        except HttpFailure as fail:
            return _Response(fail.status, json.dumps({"error": "mock failure"}).encode())
        raw = out if isinstance(out, bytes) else json.dumps(out).encode()
        await asyncio.sleep(0)  # ... and the answer travels back
        return _Response(200, raw)


def connection_key(host: str = HOST, port: int = 443) -> ConnectionKey:
    """What aiohttp's connector errors carry about the connection that failed."""
    return ConnectionKey(host, port, True, False, None, None, None, None)


# ---------------------------------------------------------------------- small helpers on the mock itself
def _quiet_tick(self: MockRouter) -> None:
    """The mock's traffic simulation without the dice: fixed speeds, and clients stay online/offline."""
    for index, client in enumerate(self.clients):
        if client["online"]:
            client["rx"], client["tx"] = 1000 * (index + 1), 100 * (index + 1)
        else:
            client["rx"] = client["tx"] = 0
        client["blocked"] = client["mac"] in self.black_mac


def normalize_clients(router: MockRouter, start: int = 0) -> None:
    """Clients 2, 5, 8 ... (index % 3 == 2) are offline, all others online. Only touches clients from `start` on."""
    for index, client in enumerate(router.clients):
        if index >= start:
            client["online"] = index % 3 != 2


def quiet(router: MockRouter) -> MockRouter:
    """Make a MockRouter deterministic and fast (no random online/offline flips, no sleeping)."""
    router._tick = types.MethodType(_quiet_tick, router)
    router.wifi_apply_seconds = 0.0
    router.reboot_seconds = 0.0
    normalize_clients(router)
    return router


def add_clients(router: MockRouter, count: int) -> None:
    """Grow the router's client list to `count` clients (the new ones follow the online/offline pattern)."""
    before = len(router.clients)
    router.set_clients(count)
    normalize_clients(router, start=before)


def override(router: MockRouter, name: str, fn: Callable[[dict], Any]) -> Callable[[dict], Any]:
    """Replace one 'object.method' of the mock; returns the original so a wrapper can delegate to it."""
    original = router.methods[name]
    router.methods[name] = fn
    return original


def remove_method(router: MockRouter, *names: str) -> None:
    """Make this firmware lack some methods (the router then answers -32601 'Method not found')."""
    for name in names:
        router.methods.pop(name, None)


def set_status(router: MockRouter, **system: Any) -> None:
    """Patch fields of the 'system' dict that system.get_status reports (lan_ip, lan_netmask, timestamp, ...)."""
    original = router.methods["system.get_status"]

    def patched(params: dict) -> dict:
        out = original(params)
        out["system"] = {**out["system"], **system}
        return out

    router.methods["system.get_status"] = patched


def iface(router: MockRouter, name: str) -> dict[str, Any]:
    """The mock's own (live) record of one Wi-Fi interface."""
    for band in router.bands:
        for candidate in band["ifaces"]:
            if candidate["name"] == name:
                return candidate
    raise KeyError(name)


def client_macs(router: MockRouter) -> list[str]:
    return [c["mac"] for c in router.clients]


def offline_mac(router: MockRouter) -> str:
    """A client of the mock that is currently offline (the mock draws that at random from its seed)."""
    for client in router.clients:
        if not client["online"]:
            return client["mac"]
    router.clients[-1]["online"] = False
    return router.clients[-1]["mac"]


def online_mac(router: MockRouter) -> str:
    for client in router.clients:
        if client["online"]:
            return client["mac"]
    router.clients[0]["online"] = True
    return router.clients[0]["mac"]
