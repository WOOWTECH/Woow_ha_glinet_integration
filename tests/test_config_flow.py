"""config_flow.py: adding a router, re-authentication, reconfiguration and the options flow."""

from __future__ import annotations

from typing import Any

import pytest
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from mock_router import MockRouter
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.woow_glinet.config_flow import STEP_USER_SCHEMA, normalize_host
from custom_components.woow_glinet.const import (
    CONF_SCHEME,
    CONF_VERIFY_SSL,
    DEFAULT_HOST,
    DOMAIN,
    OPTION_EXPOSE_WIFI_PASSWORDS,
)
from testkit import HOST, HOST2, PASSWORD, ROUTER_MAC, ROUTER_TITLE, RouterWorld, override

from conftest import SetupRouter


def user_input(host: str = HOST, password: str = PASSWORD, **overrides: Any) -> dict[str, Any]:
    return {CONF_HOST: host, CONF_USERNAME: "root", CONF_PASSWORD: password, CONF_SCHEME: "https", CONF_VERIFY_SSL: False, **overrides}


async def start_user_flow(hass: HomeAssistant) -> dict[str, Any]:
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})


async def submit(hass: HomeAssistant, result: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    return await hass.config_entries.flow.async_configure(result["flow_id"], data)


# ===================================================================================== normalize_host
@pytest.mark.parametrize(
    ("typed", "host"),
    [
        ("192.168.8.1", "192.168.8.1"),
        ("https://1.2.3.4/x", "1.2.3.4"),
        ("http://1.2.3.4", "1.2.3.4"),
        ("https://192.168.8.1/admin/", "192.168.8.1"),
        ("  192.168.8.1  ", "192.168.8.1"),
        ("192.168.8.1/", "192.168.8.1"),
        ("192.168.8.1/admin#/overview", "192.168.8.1"),
        ("192.168.8.1:8443", "192.168.8.1:8443"),
        ("https://192.168.8.1:8443/rpc", "192.168.8.1:8443"),
        ("HTTPS://Router.Lan/admin", "Router.Lan"),
        ("router.lan", "router.lan"),
        ("http://[fe80::1]/x", "[fe80::1]"),
        ("ftp://1.2.3.4/x", "1.2.3.4"),
        ("", ""),
        ("https://", ""),
    ],
)
def test_normalize_host(typed: str, host: str) -> None:
    assert normalize_host(typed) == host


# ===================================================================================== user step
async def test_user_form(hass: HomeAssistant) -> None:
    result = await start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user" and result["errors"] == {}
    schema = result["data_schema"].schema
    assert [str(k) for k in schema] == [CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_SCHEME, CONF_VERIFY_SSL]
    assert DEFAULT_HOST == "192.168.8.1"
    defaults = {str(k): k.default() for k in schema if str(k) != CONF_PASSWORD}
    assert defaults == {CONF_HOST: "192.168.8.1", CONF_USERNAME: "root", CONF_SCHEME: "https", CONF_VERIFY_SSL: False}


async def test_user_flow_creates_the_entry(hass: HomeAssistant, router: MockRouter, world: RouterWorld) -> None:
    result = await submit(hass, await start_user_flow(hass), user_input())
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ROUTER_TITLE, "named after the router's hostname"
    assert result["data"] == user_input()
    entry = result["result"]
    assert entry.unique_id == ROUTER_MAC
    assert entry.state is ConfigEntryState.LOADED, "and it is set up right away"
    assert world.count("login") >= 1


async def test_user_flow_normalises_a_pasted_address(hass: HomeAssistant, router: MockRouter) -> None:
    result = await submit(hass, await start_user_flow(hass), user_input(f"https://{HOST}/admin/#/overview"))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == HOST


async def test_user_flow_with_a_port(hass: HomeAssistant, world: RouterWorld) -> None:
    world.add("192.0.2.10:8080")
    result = await submit(hass, await start_user_flow(hass), user_input("http://192.0.2.10:8080/rpc", **{CONF_SCHEME: "http"}))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.0.2.10:8080"
    assert result["data"][CONF_SCHEME] == "http"


async def test_user_flow_title_falls_back_to_the_host(hass: HomeAssistant, router: MockRouter) -> None:
    override(router, "system.get_info", lambda p: {"mac": ROUTER_MAC})  # no board_info
    result = await submit(hass, await start_user_flow(hass), user_input())
    assert result["type"] is FlowResultType.CREATE_ENTRY and result["title"] == HOST


async def test_user_flow_with_a_router_that_reports_nothing_about_itself(hass: HomeAssistant, router: MockRouter) -> None:
    """system.get_info answering with Lua's empty table: no MAC, so no unique id and no duplicate check - but it works."""
    override(router, "system.get_info", lambda p: [])
    result = await submit(hass, await start_user_flow(hass), user_input())
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST and result["result"].unique_id is None


async def test_user_flow_wrong_password(hass: HomeAssistant, router: MockRouter) -> None:
    result = await submit(hass, await start_user_flow(hass), user_input(password="wrong"))
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    result = await submit(hass, result, user_input())  # and the form can be sent again with the right one
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_wrong_username(hass: HomeAssistant, router: MockRouter) -> None:
    result = await submit(hass, await start_user_flow(hass), user_input(**{CONF_USERNAME: "nobody"}))
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_keeps_what_was_typed_when_it_fails(hass: HomeAssistant, router: MockRouter) -> None:
    result = await submit(hass, await start_user_flow(hass), user_input(HOST, "wrong", **{CONF_USERNAME: "admin"}))
    suggested = {str(k): k.description["suggested_value"] for k in result["data_schema"].schema if k.description}
    assert suggested[CONF_HOST] == HOST and suggested[CONF_USERNAME] == "admin"


async def test_user_flow_unreachable_router(hass: HomeAssistant, world: RouterWorld) -> None:
    result = await submit(hass, await start_user_flow(hass), user_input("192.0.2.99"))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize("mode", [True, "list", "html", "empty", "truncated"])
async def test_user_flow_something_that_is_not_a_router(hass: HomeAssistant, router: MockRouter, mode: object) -> None:
    router.configure(malformed=mode)
    result = await submit(hass, await start_user_flow(hass), user_input())
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    "inject",
    [{"exc": TimeoutError()}, {"raw": b"<html>nginx</html>", "status": 502}, {"raw": b'{"error": {"code": -5, "message": "boom"}}'}],
    ids=["timeout", "bad-gateway", "rpc-error"],
)
async def test_user_flow_trouble_while_probing(hass: HomeAssistant, router: MockRouter, world: RouterWorld, inject: dict) -> None:
    world.inject("system.get_info", times=None, **inject)
    result = await submit(hass, await start_user_flow(hass), user_input())
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_rejects_a_router_that_cuts_the_connection(hass: HomeAssistant, router: MockRouter) -> None:
    router.configure(dark_for=60)
    result = await submit(hass, await start_user_flow(hass), user_input())
    assert result["errors"] == {"base": "cannot_connect"}


async def test_the_same_router_cannot_be_added_twice(hass: HomeAssistant, router: MockRouter, entry: MockConfigEntry, world: RouterWorld) -> None:
    world.add(HOST2, mac=ROUTER_MAC)  # the same box reachable on a second address
    result = await submit(hass, await start_user_flow(hass), user_input(HOST2))
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_a_second_different_router_can_be_added(hass: HomeAssistant, entry: MockConfigEntry, world: RouterWorld) -> None:
    world.add(HOST2, mac="94:83:C4:00:00:02")
    result = await submit(hass, await start_user_flow(hass), user_input(HOST2))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_user_flow_validates_the_form(hass: HomeAssistant, router: MockRouter) -> None:
    result = await start_user_flow(hass)
    with pytest.raises(InvalidData):
        await submit(hass, result, user_input(**{CONF_SCHEME: "ftp"}))
    with pytest.raises(InvalidData):
        await submit(hass, result, {CONF_HOST: HOST, CONF_USERNAME: "root"})  # no password


def test_the_schema_offers_http_and_https_only() -> None:
    assert STEP_USER_SCHEMA(user_input(**{CONF_SCHEME: "http"}))[CONF_SCHEME] == "http"
    with pytest.raises(vol.Invalid):
        STEP_USER_SCHEMA(user_input(**{CONF_SCHEME: "gopher"}))


# ===================================================================================== reauth
async def broken_entry(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld, router_password: str = "changed") -> MockConfigEntry:
    """An entry whose stored password no longer matches the router: set up it fails, and HA asks for re-authentication."""
    world.add(HOST, password=router_password)
    return await setup_router(HOST, expect=ConfigEntryState.SETUP_ERROR)


def reauth_flow(hass: HomeAssistant) -> dict[str, Any]:
    (flow,) = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flow["context"]["source"] == config_entries.SOURCE_REAUTH
    return flow


async def test_reauth_form(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    entry = await broken_entry(hass, setup_router, world)
    flow = reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(flow["flow_id"])
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {"host": HOST, "name": entry.title}
    schema = {str(k): k for k in result["data_schema"].schema}
    assert set(schema) == {CONF_USERNAME, CONF_PASSWORD}
    assert schema[CONF_USERNAME].default() == "root", "the stored username is offered"


async def test_reauth_success(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    entry = await broken_entry(hass, setup_router, world)
    assert entry.data[CONF_PASSWORD] == PASSWORD
    flow = reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {CONF_USERNAME: "root", CONF_PASSWORD: "changed"})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "changed"
    assert entry.data[CONF_HOST] == HOST and entry.data[CONF_SCHEME] == "https", "only the credentials change"
    assert entry.state is ConfigEntryState.LOADED, "and the entry is reloaded with them"
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN) == []


async def test_reauth_with_a_new_username(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    world.add(HOST, username="admin", password="changed")
    entry = await setup_router(HOST, expect=ConfigEntryState.SETUP_ERROR)
    flow = reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "changed"})
    await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert (entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]) == ("admin", "changed")
    assert entry.state is ConfigEntryState.LOADED


async def test_reauth_wrong_password_again(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    entry = await broken_entry(hass, setup_router, world)
    flow = reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {CONF_USERNAME: "root", CONF_PASSWORD: "still-wrong"})
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_PASSWORD] == PASSWORD, "nothing is stored until the router accepts it"


async def test_reauth_router_unreachable(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    await broken_entry(hass, setup_router, world)
    flow = reauth_flow(hass)
    world.disconnect(HOST)
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {CONF_USERNAME: "root", CONF_PASSWORD: "changed"})
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "cannot_connect"}


async def test_reauth_with_the_credentials_of_a_different_router(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    """The address now answers as another router (another MAC): do not bind this entry to it."""
    entry = await broken_entry(hass, setup_router, world)
    world.add(HOST, mac="94:83:C4:00:00:99", password="changed")
    flow = reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {CONF_USERNAME: "root", CONF_PASSWORD: "changed"})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "wrong_device"
    assert entry.data[CONF_PASSWORD] == PASSWORD


async def test_reauth_started_by_hand(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter) -> None:
    router.configure(password="changed")
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_USERNAME: "root", CONF_PASSWORD: "changed"})
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED and entry.data[CONF_PASSWORD] == "changed"


# ===================================================================================== reconfigure
async def start_reconfigure(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, Any]:
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "reconfigure"
    return result


async def test_reconfigure_form(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    result = await start_reconfigure(hass, entry)
    assert result["description_placeholders"] == {"name": entry.title}
    suggested = {str(k): k.description["suggested_value"] for k in result["data_schema"].schema if k.description}
    assert suggested == {CONF_HOST: HOST, CONF_USERNAME: "root", CONF_SCHEME: "https", CONF_VERIFY_SSL: False}, "no password is shown"
    assert PASSWORD not in repr(result["data_schema"].schema) and PASSWORD not in repr(suggested)


async def test_reconfigure_to_a_new_address(hass: HomeAssistant, entry: MockConfigEntry, world: RouterWorld) -> None:
    world.add(HOST2, mac=ROUTER_MAC)  # the router moved to another address
    result = await start_reconfigure(hass, entry)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST2, CONF_USERNAME: "root", CONF_PASSWORD: "", CONF_SCHEME: "http", CONF_VERIFY_SSL: True}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reconfigure_successful"
    assert (entry.data[CONF_HOST], entry.data[CONF_SCHEME], entry.data[CONF_VERIFY_SSL]) == (HOST2, "http", True)
    assert entry.state is ConfigEntryState.LOADED
    assert world.count("system.get_status", HOST2) >= 1, "the reloaded entry talks to the new address"
    assert {r.scheme for r in world.requests if r.host == HOST2} == {"http"}


async def test_reconfigure_with_an_empty_password_keeps_the_old_one(hass: HomeAssistant, entry: MockConfigEntry, world: RouterWorld) -> None:
    result = await start_reconfigure(hass, entry)
    before = world.count("login")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_USERNAME: "root", CONF_PASSWORD: "", CONF_SCHEME: "https", CONF_VERIFY_SSL: False}
    )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PASSWORD] == PASSWORD
    assert world.count("login") > before, "and the probe really logged in with the stored password"


async def test_reconfigure_without_the_password_field_keeps_the_old_one(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    result = await start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_USERNAME: "root", CONF_SCHEME: "https", CONF_VERIFY_SSL: False}
    )
    assert result["reason"] == "reconfigure_successful" and entry.data[CONF_PASSWORD] == PASSWORD


async def test_reconfigure_with_a_new_password(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter) -> None:
    router.configure(password="rotated")
    result = await start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_USERNAME: "root", CONF_PASSWORD: "rotated", CONF_SCHEME: "https", CONF_VERIFY_SSL: False}
    )
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful" and entry.data[CONF_PASSWORD] == "rotated"
    assert entry.state is ConfigEntryState.LOADED


async def test_reconfigure_normalises_a_pasted_url(hass: HomeAssistant, entry: MockConfigEntry, world: RouterWorld) -> None:
    world.add(HOST2, mac=ROUTER_MAC)
    result = await start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: f"https://{HOST2}/admin/#/system", CONF_USERNAME: "root", CONF_PASSWORD: "", CONF_SCHEME: "https", CONF_VERIFY_SSL: False},
    )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == HOST2


async def test_reconfigure_to_another_router_is_refused(hass: HomeAssistant, entry: MockConfigEntry, world: RouterWorld) -> None:
    world.add(HOST2, mac="94:83:C4:00:00:77")  # a different box
    result = await start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST2, CONF_USERNAME: "root", CONF_PASSWORD: "", CONF_SCHEME: "https", CONF_VERIFY_SSL: False}
    )
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "wrong_device"
    assert entry.data[CONF_HOST] == HOST, "unchanged"


async def test_reconfigure_wrong_password(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    result = await start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_USERNAME: "root", CONF_PASSWORD: "wrong", CONF_SCHEME: "https", CONF_VERIFY_SSL: False}
    )
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_PASSWORD] == PASSWORD
    suggested = {str(k): k.description["suggested_value"] for k in result["data_schema"].schema if k.description}
    assert suggested[CONF_HOST] == HOST, "what was typed stays in the form"


async def test_reconfigure_unreachable_address(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    result = await start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.99", CONF_USERNAME: "root", CONF_PASSWORD: "", CONF_SCHEME: "https", CONF_VERIFY_SSL: False}
    )
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "cannot_connect"}
    assert entry.data[CONF_HOST] == HOST


async def test_reconfigure_can_be_corrected_after_an_error(hass: HomeAssistant, entry: MockConfigEntry, world: RouterWorld) -> None:
    world.add(HOST2, mac=ROUTER_MAC)
    result = await start_reconfigure(hass, entry)
    bad = {CONF_HOST: "192.0.2.99", CONF_USERNAME: "root", CONF_PASSWORD: "", CONF_SCHEME: "https", CONF_VERIFY_SSL: False}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], bad)
    assert result["errors"] == {"base": "cannot_connect"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**bad, CONF_HOST: HOST2})
    assert result["reason"] == "reconfigure_successful" and entry.data[CONF_HOST] == HOST2


# ===================================================================================== options flow
async def test_options_flow_form(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "init"
    schema = {str(k): k for k in result["data_schema"].schema}
    assert set(schema) == {OPTION_EXPOSE_WIFI_PASSWORDS}
    assert schema[OPTION_EXPOSE_WIFI_PASSWORDS].default() is False, "off unless asked for"


async def test_options_flow_stores_the_option_and_reloads_the_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert entry.options == {}
    before = entry.runtime_data.coordinator

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {OPTION_EXPOSE_WIFI_PASSWORDS: True})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {OPTION_EXPOSE_WIFI_PASSWORDS: True}
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.coordinator is not before, "the entry reloaded itself so the entities pick the option up"


async def test_options_flow_can_turn_it_off_again(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    hass.config_entries.async_update_entry(entry, options={OPTION_EXPOSE_WIFI_PASSWORDS: True})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    suggested = {str(k): k.description["suggested_value"] for k in result["data_schema"].schema if k.description}
    assert suggested == {OPTION_EXPOSE_WIFI_PASSWORDS: True}, "the form shows the current setting"

    result = await hass.config_entries.options.async_configure(result["flow_id"], {OPTION_EXPOSE_WIFI_PASSWORDS: False})
    await hass.async_block_till_done()
    assert entry.options == {OPTION_EXPOSE_WIFI_PASSWORDS: False}
    assert entry.state is ConfigEntryState.LOADED


async def test_options_flow_does_not_touch_the_connection_settings(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    before = dict(entry.data)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], {OPTION_EXPOSE_WIFI_PASSWORDS: True})
    assert dict(entry.data) == before and entry.unique_id == ROUTER_MAC


async def test_options_flow_rejects_a_non_boolean(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(result["flow_id"], {OPTION_EXPOSE_WIFI_PASSWORDS: "maybe"})



# ===================================================================================== a router that does not say who it is
async def test_reauth_with_a_router_that_reports_no_mac(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    """Without a MAC the 'same router?' check cannot run; the credentials are still updated."""
    entry = await broken_entry(hass, setup_router, world)
    override(world.routers[HOST], "system.get_info", lambda p: {})
    flow = reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {CONF_USERNAME: "root", CONF_PASSWORD: "changed"})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "changed"


async def test_reconfigure_with_a_router_that_reports_no_mac(hass: HomeAssistant, entry: MockConfigEntry, router: MockRouter) -> None:
    override(router, "system.get_info", lambda p: {})
    result = await start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_USERNAME: "root", CONF_PASSWORD: "", CONF_SCHEME: "http", CONF_VERIFY_SSL: False}
    )
    assert result["reason"] == "reconfigure_successful" and entry.data[CONF_SCHEME] == "http"


# ===================================================================================== Lua's [] for board_info
@pytest.mark.parametrize("board_info", [[], None], ids=["lua-empty-table", "null"])
async def test_user_flow_with_a_system_info_that_has_no_usable_board_info(hass: HomeAssistant, router: MockRouter, board_info: object) -> None:
    override(router, "system.get_info", lambda p: {"mac": ROUTER_MAC, "board_info": board_info})
    result = await submit(hass, await start_user_flow(hass), user_input())
    assert result["type"] is FlowResultType.CREATE_ENTRY and result["title"] == HOST
