"""Fixtures for the WOOW GL.iNet test suite.

Home Assistant is imported FIRST: 2026.10 installs `probatio` as `voluptuous` when `homeassistant` is imported, and the
integration (and the websocket decorators) must see that one.

Nothing in here talks to a network. The integration's aiohttp session is replaced by `testkit.MockSession`, which
hands every request to an in-memory `tools/mock_router.py`; on top of that pytest-socket (via the Home Assistant
pytest plugin) refuses real sockets, and `_no_foreign_connections` below also covers the tests that must
re-enable sockets for a loopback websocket.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The suite must not leave bytecode behind in the (read-only for us) integration and tools directories.
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "tools"), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

import homeassistant  # noqa: E402,F401  (installs probatio as `voluptuous`, as Home Assistant itself does)

import asyncio  # noqa: E402
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator  # noqa: E402
from typing import Any  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402
from homeassistant.config_entries import ConfigEntryState  # noqa: E402
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.woow_glinet.api import GlinetClient  # noqa: E402
from custom_components.woow_glinet.const import CONF_SCHEME, CONF_VERIFY_SSL, DOMAIN  # noqa: E402
from custom_components.woow_glinet.coordinator import GlinetCoordinator  # noqa: E402
from testkit import HOST, PASSWORD, ROUTER_MAC, ROUTER_TITLE, RouterWorld  # noqa: E402
from mock_router import MockRouter  # noqa: E402


def pytest_configure(config: pytest.Config) -> None:
    # The suite is made of async tests; do not depend on the caller having an ini file at the repo root.
    config.option.asyncio_mode = "auto"


# ---------------------------------------------------------------------------------------- the network
@pytest.fixture(autouse=True)
def _no_foreign_connections() -> Generator[None]:
    """Whatever else a test enables, a TCP connection to anything but loopback is a test bug (never a real router)."""
    original = asyncio.BaseEventLoop.create_connection

    async def guarded(self: Any, protocol_factory: Any, host: Any = None, *args: Any, **kwargs: Any) -> Any:
        if host not in (None, "127.0.0.1", "::1", "localhost"):
            raise AssertionError(f"test tried to open a connection to {host!r}; the suite must stay offline")
        return await original(self, protocol_factory, host, *args, **kwargs)

    with patch.object(asyncio.BaseEventLoop, "create_connection", guarded):
        yield


@pytest.fixture
def world() -> Generator[RouterWorld]:
    """The in-memory network. While it exists, the integration's HTTP session is the in-process stand-in."""
    world = RouterWorld()

    def fake_clientsession(hass: HomeAssistant, verify_ssl: bool = True, **kwargs: Any) -> Any:
        return world.session

    with patch("homeassistant.helpers.aiohttp_client.async_get_clientsession", fake_clientsession):
        yield world


@pytest.fixture
def router(world: RouterWorld) -> MockRouter:
    """The default router, 6 clients (0,1,3,4 online; 2,5 offline), at HOST, password PASSWORD."""
    return world.add(HOST)


@pytest.fixture
def client(world: RouterWorld, router: MockRouter) -> GlinetClient:
    """A bare API client (no Home Assistant) logged out, talking to the default router."""
    return GlinetClient(world.session, HOST, "root", PASSWORD, scheme="https", verify_ssl=False)


# ---------------------------------------------------------------------------------------- Home Assistant
@pytest.fixture
async def hass(hass: HomeAssistant, enable_custom_integrations: None, world: RouterWorld) -> AsyncGenerator[HomeAssistant]:
    """Home Assistant with this repo's custom integration enabled and the routers of `world` reachable.

    `frontend` and its twelve dependencies are stood in for by a flag: the real thing needs the 40 MB
    `home-assistant-frontend` wheel and has nothing to do with what is tested here. `http` and `websocket_api`
    are set up for real (the panel and the websocket commands are tested against the real objects); Home
    Assistant's pytest plugin keeps `http` from binding a port.
    """
    hass.config.components.add("frontend")
    yield hass


def entry_data(host: str = HOST, **overrides: Any) -> dict[str, Any]:
    data = {
        CONF_HOST: host,
        CONF_USERNAME: "root",
        CONF_PASSWORD: PASSWORD,
        CONF_SCHEME: "https",
        CONF_VERIFY_SSL: False,
    }
    data.update(overrides)
    return data


def make_entry(host: str = HOST, *, unique_id: str | None = ROUTER_MAC, title: str = ROUTER_TITLE,
               **overrides: Any) -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, title=title, unique_id=unique_id, data=entry_data(host, **overrides))


SetupRouter = Callable[..., Awaitable[MockConfigEntry]]


@pytest.fixture
def setup_router(hass: HomeAssistant, world: RouterWorld) -> SetupRouter:
    """Add a router to the network (unless it is already there), add its config entry and set it up."""

    async def _setup(host: str = HOST, *, router: MockRouter | None = None, expect: ConfigEntryState = ConfigEntryState.LOADED,
                     entry: MockConfigEntry | None = None, **router_kwargs: Any) -> MockConfigEntry:
        if router is not None or router_kwargs or host not in world.routers:
            world.add(host, router, **router_kwargs)
        entry = entry or make_entry(host, unique_id=world.routers[host].mac, title="GL-MOCK1200")
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is expect, f"entry ended up {entry.state} (wanted {expect}): {entry.reason}"
        return entry

    return _setup


@pytest.fixture
async def entry(setup_router: SetupRouter, router: MockRouter) -> MockConfigEntry:
    """The default router, set up through the real integration."""
    return await setup_router(HOST)


@pytest.fixture
def coordinator(entry: MockConfigEntry) -> GlinetCoordinator:
    return entry.runtime_data.coordinator


@pytest.fixture
def activity(hass: HomeAssistant, entry: MockConfigEntry) -> Any:
    return hass.data[DOMAIN]["activity"]


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Entities that are disabled by default (like the Wi-Fi password) are enabled for the tests that ask for this."""
    from unittest.mock import PropertyMock

    with patch("homeassistant.helpers.entity.Entity.entity_registry_enabled_default", new_callable=PropertyMock, return_value=True):
        yield
