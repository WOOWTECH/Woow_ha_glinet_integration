"""panel.py: the sidebar panel - registered once however many routers come up at the same time, removed with the last one."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.components import frontend, panel_custom
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from mock_router import MockRouter
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.woow_glinet import panel
from custom_components.woow_glinet.const import DOMAIN, PANEL_ELEMENT, PANEL_FILE, PANEL_ICON, PANEL_STATIC, PANEL_URL
from testkit import HOST, HOST2, RouterWorld

from conftest import SetupRouter, make_entry

STATIC_URL = f"{PANEL_STATIC}/{PANEL_FILE}"


class NoLock:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> None:
        return None


def registered_panel(hass: HomeAssistant) -> frontend.Panel | None:
    return hass.data.get(frontend.DATA_PANELS, {}).get(PANEL_URL)


class Spies:
    """Counts how often the two registrations happen.

    With `overlap`, the first static-route registration is held open until a second caller arrives (or 0.2 s pass):
    Home Assistant's real implementation yields to an executor thread there, so whether two registrations overlap
    would otherwise depend on thread timing. Under the integration's lock the second caller can never arrive, so the
    wait just times out; without the lock both are inside at once, which is exactly the original crash.
    """

    def __init__(self, hass: HomeAssistant, overlap: bool = False) -> None:
        self.static: list[str] = []
        self.panels: list[dict[str, Any]] = []
        self._hass = hass
        self._overlap = overlap
        self._arrivals = 0
        self._both = asyncio.Event()

    async def install(self, stack: Any) -> Spies:
        await async_setup_component(self._hass, "http", {})  # (so hass.http exists to be watched)
        original_static = self._hass.http.async_register_static_paths
        original_panel = panel_custom.async_register_panel

        async def static(configs: Any) -> None:
            self.static += [c.url_path for c in configs]
            if self._overlap:
                self._arrivals += 1
                if self._arrivals >= 2:
                    self._both.set()
                try:
                    await asyncio.wait_for(self._both.wait(), timeout=0.2)
                except TimeoutError:
                    pass
            await original_static(configs)

        async def register(hass: HomeAssistant, **kwargs: Any) -> None:
            self.panels.append(kwargs)
            await original_panel(hass, **kwargs)

        stack.enter_context(patch.object(self._hass.http, "async_register_static_paths", static))
        stack.enter_context(patch.object(panel_custom, "async_register_panel", register))
        return self


@pytest.fixture
def spies(hass: HomeAssistant) -> Any:
    from contextlib import ExitStack

    async def build(overlap: bool = False) -> tuple[Spies, ExitStack]:
        stack = ExitStack()
        return await Spies(hass, overlap).install(stack), stack

    return build


# ===================================================================================== the bundle
def test_the_bundle_exists_and_is_not_empty() -> None:
    bundle = Path(panel.BUNDLE)
    assert bundle.name == PANEL_FILE == "woow-glinet-panel.js"
    assert bundle.parent.name == "frontend" and bundle.parent.parent.name == "woow_glinet"
    assert bundle.is_file(), f"{bundle} is missing: the panel would not load"
    assert bundle.stat().st_size > 10_000, "an empty or truncated build"


def test_the_bundle_defines_the_element_the_panel_asks_for() -> None:
    text = Path(panel.BUNDLE).read_text(encoding="utf-8")
    assert PANEL_ELEMENT == "woow-glinet-panel"
    assert PANEL_ELEMENT in text
    assert "customElements" in text, "not a web component bundle"


def test_the_bundle_talks_to_the_commands_the_integration_registers() -> None:
    """A rename on one side only would leave the panel silently dead."""
    from custom_components.woow_glinet import websocket_api

    text = Path(panel.BUNDLE).read_text(encoding="utf-8")
    import re

    in_bundle = set(re.findall(r"woow_glinet/[a-z_/]+", text))
    registered = {
        "woow_glinet/snapshot", "woow_glinet/subscribe", "woow_glinet/refresh", "woow_glinet/wifi/set", "woow_glinet/wifi/key",
        "woow_glinet/client/block", "woow_glinet/client/forget", "woow_glinet/client/history", "woow_glinet/static_ip/add",
        "woow_glinet/reboot",
    }  # fmt: skip
    assert len(websocket_api._COMMANDS) == len(registered)
    assert in_bundle >= registered, f"the panel never calls: {registered - in_bundle}"
    assert in_bundle <= registered, f"the panel calls commands that do not exist: {in_bundle - registered}"


# ===================================================================================== registration
async def test_registering_the_panel(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    found = registered_panel(hass)
    assert found is not None
    assert found.component_name == "custom"
    assert (found.sidebar_title, found.sidebar_icon, found.frontend_url_path) == ("WOOW GL.iNet", PANEL_ICON, PANEL_URL)
    assert found.require_admin is True, "the panel is for administrators"
    custom = found.config["_panel_custom"]
    assert custom["name"] == PANEL_ELEMENT
    assert custom["embed_iframe"] is False and custom["trust_external"] is False
    digest = hashlib.md5(Path(panel.BUNDLE).read_bytes(), usedforsecurity=False).hexdigest()[:8]
    assert custom["module_url"] == f"{STATIC_URL}?v={digest}", "the content hash makes browsers fetch a new build"
    assert hass.data[DOMAIN]["panel"] is True and hass.data[DOMAIN]["panel_static"] is True


async def test_the_bundle_is_served(hass: HomeAssistant, entry: MockConfigEntry, hass_client_no_auth: Any) -> None:
    client = await hass_client_no_auth()
    response = await client.get(STATIC_URL)
    assert response.status == 200
    assert "javascript" in response.headers["Content-Type"]
    assert await response.read() == Path(panel.BUNDLE).read_bytes()


async def test_the_module_url_changes_with_the_bundle(hass: HomeAssistant, tmp_path: Path, spies: Any) -> None:
    tracker, stack = await spies()
    urls = []
    with stack:
        for content in (b"console.log(1)", b"console.log(2)"):
            bundle = tmp_path / PANEL_FILE
            bundle.write_bytes(content)
            hass.data.setdefault(DOMAIN, {}).pop("panel", None)
            frontend.async_remove_panel(hass, PANEL_URL, warn_if_unknown=False)
            with patch.object(panel, "BUNDLE", bundle):
                await panel.async_register_panel(hass)
            urls.append(tracker.panels[-1]["module_url"])
    assert urls[0] != urls[1]
    assert urls[0] == f"{STATIC_URL}?v={hashlib.md5(b'console.log(1)', usedforsecurity=False).hexdigest()[:8]}"
    assert len(tracker.static) == 1, "the static route is registered once per run, it cannot be removed"


async def test_registering_twice_is_a_no_op(hass: HomeAssistant, entry: MockConfigEntry, spies: Any) -> None:
    tracker, stack = await spies()
    with stack:
        await panel.async_register_panel(hass)
        await panel.async_register_panel(hass)
    assert tracker.static == [] and tracker.panels == []


# ===================================================================================== two routers at once (the regression)
async def two_entries(hass: HomeAssistant, world: RouterWorld) -> tuple[MockConfigEntry, MockConfigEntry]:
    world.add(HOST)
    world.add(HOST2, mac="94:83:C4:00:00:02")
    first = make_entry(HOST, unique_id="94:83:C4:00:00:01")
    second = make_entry(HOST2, unique_id="94:83:C4:00:00:02", title="Second")
    first.add_to_hass(hass)
    second.add_to_hass(hass)
    return first, second


async def test_two_entries_set_up_at_the_same_time_register_the_panel_once(
    hass: HomeAssistant, world: RouterWorld, spies: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """Regression: the second entry used to crash with 'Added route will never be executed'."""
    tracker, stack = await spies(overlap=True)
    first, second = await two_entries(hass, world)

    with stack:
        await asyncio.gather(hass.config_entries.async_setup(first.entry_id), hass.config_entries.async_setup(second.entry_id))
        await hass.async_block_till_done()

    assert first.state is ConfigEntryState.LOADED and second.state is ConfigEntryState.LOADED
    assert tracker.static == [STATIC_URL], "the static route exactly once"
    assert len(tracker.panels) == 1, "the panel exactly once"
    assert registered_panel(hass) is not None
    assert "Could not register" not in caplog.text and "Added route will never be executed" not in caplog.text
    assert hass.states.async_entity_ids("sensor"), "and both routers' entities came up"


async def test_the_concurrent_registration_test_is_not_vacuous(hass: HomeAssistant, world: RouterWorld, spies: Any,
                                                              caplog: pytest.LogCaptureFixture) -> None:
    """Take the lock away and the very same scenario trips over the static route again."""
    hass.data[DOMAIN] = {"panel_lock": NoLock()}
    tracker, stack = await spies(overlap=True)
    first, second = await two_entries(hass, world)

    with stack:
        await asyncio.gather(hass.config_entries.async_setup(first.entry_id), hass.config_entries.async_setup(second.entry_id))
        await hass.async_block_till_done()

    assert len(tracker.static) == 2, "both registered the route"
    assert "Added route will never be executed" in caplog.text
    assert first.state is ConfigEntryState.LOADED and second.state is ConfigEntryState.LOADED, "(the entities survive it, see below)"


async def test_three_entries_at_once(hass: HomeAssistant, world: RouterWorld, spies: Any) -> None:
    tracker, stack = await spies(overlap=True)
    entries = []
    for i, host in enumerate((HOST, HOST2, "192.0.2.30")):
        world.add(host, mac=f"94:83:C4:00:00:0{i + 1}")
        entries.append(make_entry(host, unique_id=f"94:83:C4:00:00:0{i + 1}", title=f"R{i}"))
        entries[-1].add_to_hass(hass)
    with stack:
        await asyncio.gather(*(hass.config_entries.async_setup(e.entry_id) for e in entries))
        await hass.async_block_till_done()
    assert all(e.state is ConfigEntryState.LOADED for e in entries)
    assert tracker.static == [STATIC_URL] and len(tracker.panels) == 1


# ===================================================================================== a registration that fails
@pytest.mark.parametrize("failing", ["static", "panel", "bundle"])
async def test_a_failing_registration_does_not_break_the_entities(
    hass: HomeAssistant, setup_router: SetupRouter, router: MockRouter, caplog: pytest.LogCaptureFixture, failing: str, tmp_path: Path
) -> None:
    await async_setup_component(hass, "http", {})
    from contextlib import ExitStack

    with ExitStack() as stack:
        if failing == "static":
            stack.enter_context(patch.object(hass.http, "async_register_static_paths", side_effect=RuntimeError("Added route will never be executed")))
        elif failing == "panel":
            stack.enter_context(patch.object(panel_custom, "async_register_panel", side_effect=ValueError("Overwriting panel woow-glinet")))
        else:
            stack.enter_context(patch.object(panel, "BUNDLE", tmp_path / "missing.js"))
        entry = await setup_router(HOST)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.async_entity_ids("sensor") and hass.states.async_entity_ids("switch") and hass.states.async_entity_ids("button")
    assert all(s.state != "unavailable" for s in hass.states.async_all("sensor"))
    assert registered_panel(hass) is None
    assert not hass.data[DOMAIN].get("panel"), "not marked as registered: a later setup tries again"
    if failing == "bundle":
        assert "is missing; the sidebar panel is not available" in caplog.text
    else:
        assert "Could not register the WOOW GL.iNet sidebar panel" in caplog.text


async def test_a_later_setup_registers_the_panel_after_an_earlier_failure(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    await async_setup_component(hass, "http", {})
    with patch.object(panel_custom, "async_register_panel", side_effect=ValueError("boom")):
        first = await setup_router(HOST)
    assert registered_panel(hass) is None and first.state is ConfigEntryState.LOADED

    second = await setup_router(HOST2, mac="94:83:C4:00:00:02")
    assert second.state is ConfigEntryState.LOADED
    assert registered_panel(hass) is not None and hass.data[DOMAIN]["panel"] is True


async def test_a_failure_after_the_static_route_does_not_register_it_again(hass: HomeAssistant, setup_router: SetupRouter, spies: Any) -> None:
    tracker, stack = await spies()
    with stack:
        with patch.object(panel_custom, "async_register_panel", side_effect=ValueError("boom")):
            await setup_router(HOST)
        assert hass.data[DOMAIN]["panel_static"] is True and not hass.data[DOMAIN].get("panel")
        await setup_router(HOST2, mac="94:83:C4:00:00:02")
    assert tracker.static == [STATIC_URL], "a static route cannot be removed: never registered twice"


async def test_a_failed_registration_does_not_leave_the_lock_held(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    hass.data[DOMAIN].pop("panel", None)
    frontend.async_remove_panel(hass, PANEL_URL, warn_if_unknown=False)
    with patch.object(panel_custom, "async_register_panel", side_effect=ValueError("boom")):
        await asyncio.wait_for(panel.async_register_panel(hass), timeout=5)
    await asyncio.wait_for(panel.async_register_panel(hass), timeout=5)
    assert registered_panel(hass) is not None


# ===================================================================================== removal
async def test_the_panel_goes_with_the_last_router(hass: HomeAssistant, setup_router: SetupRouter) -> None:
    first = await setup_router(HOST)
    second = await setup_router(HOST2, mac="94:83:C4:00:00:02")
    assert registered_panel(hass) is not None

    await hass.config_entries.async_unload(first.entry_id)
    assert registered_panel(hass) is not None and hass.data[DOMAIN]["panel"] is True, "another router still needs it"

    await hass.config_entries.async_unload(second.entry_id)
    assert registered_panel(hass) is None
    assert not hass.data[DOMAIN].get("panel")


async def test_unloading_a_single_router_removes_the_panel(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert registered_panel(hass) is not None
    await hass.config_entries.async_unload(entry.entry_id)
    assert registered_panel(hass) is None


async def test_the_panel_comes_back_when_a_router_is_reloaded(hass: HomeAssistant, entry: MockConfigEntry, spies: Any) -> None:
    tracker, stack = await spies()
    with stack:
        await hass.config_entries.async_unload(entry.entry_id)
        assert registered_panel(hass) is None
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert registered_panel(hass) is not None
    assert tracker.static == [], "the route from the first load is still there"
    assert len(tracker.panels) == 1


async def test_reloading_one_of_two_routers_keeps_the_panel(hass: HomeAssistant, setup_router: SetupRouter) -> None:
    first = await setup_router(HOST)
    await setup_router(HOST2, mac="94:83:C4:00:00:02")
    seen = []
    unsub = hass.bus.async_listen(frontend.EVENT_PANELS_UPDATED, lambda event: seen.append(registered_panel(hass) is not None))
    await hass.config_entries.async_reload(first.entry_id)
    await hass.async_block_till_done()
    unsub()
    assert seen == [] and registered_panel(hass) is not None, "the panel is never taken away while a router is loaded"


async def test_removing_the_panel_when_it_was_never_registered_is_harmless(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    hass.data[DOMAIN] = {}
    with caplog.at_level(logging.WARNING):
        panel.async_remove_panel(hass)
    assert "woow-glinet" not in caplog.text


async def test_a_router_that_fails_to_set_up_does_not_register_the_panel(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    world.add(HOST, password="not-the-stored-one")
    await setup_router(HOST, expect=ConfigEntryState.SETUP_ERROR)
    assert registered_panel(hass) is None


async def test_a_failed_unload_leaves_the_panel_alone(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=False):
        assert await hass.config_entries.async_unload(entry.entry_id) is False
    assert registered_panel(hass) is not None and hass.data[DOMAIN]["panel"] is True
    assert entry.state is ConfigEntryState.FAILED_UNLOAD


# ===================================================================================== the content hash
async def test_the_panel_registers_on_a_python_that_forbids_md5_for_security(hass: HomeAssistant, setup_router: SetupRouter,
                                                                            caplog: pytest.LogCaptureFixture,
                                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """A FIPS-enabled Python refuses hashlib.md5() unless usedforsecurity=False is passed: the hash is only a cache-buster."""
    real = hashlib.md5

    def fips_md5(data: bytes = b"", *, usedforsecurity: bool = True) -> object:
        if usedforsecurity:
            raise ValueError("[digital envelope routines] unsupported")
        return real(data, usedforsecurity=False)

    monkeypatch.setattr(panel, "hashlib", SimpleNamespace(md5=fips_md5))
    entry = await setup_router(HOST)

    assert entry.state is ConfigEntryState.LOADED
    found = registered_panel(hass)
    assert found is not None, "the panel was not registered"
    digest = real(Path(panel.BUNDLE).read_bytes(), usedforsecurity=False).hexdigest()[:8]
    assert found.config["_panel_custom"]["module_url"] == f"{STATIC_URL}?v={digest}"
    assert "Could not register" not in caplog.text
