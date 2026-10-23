"""services.py: `woow_glinet.add_static_ip` and `woow_glinet.remove_static_ip`."""

from __future__ import annotations

import logging
from typing import Any

import pytest
import voluptuous as vol
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import device_registry as dr
from mock_router import MockRouter
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser

from custom_components.woow_glinet import async_get_coordinator_for_device
from custom_components.woow_glinet.actions import ActionError
from custom_components.woow_glinet.const import DOMAIN, SERVICE_ADD_STATIC_IP, SERVICE_REMOVE_STATIC_IP
from custom_components.woow_glinet.coordinator import GlinetCoordinator
from testkit import HOST2, RouterWorld

from conftest import SetupRouter

MAC2 = "AA:BB:CC:00:00:02"


@pytest.fixture
def device_id(coordinator: GlinetCoordinator) -> str:
    """The router's device."""
    assert coordinator.router_device_id
    return coordinator.router_device_id


def add_data(device_id: str, **overrides: Any) -> dict[str, Any]:
    return {"device_id": device_id, "mac": MAC2, "ip": "192.168.8.50", "name": "TV", **overrides}


async def call(hass: HomeAssistant, service: str, data: dict[str, Any], context: Context | None = None) -> None:
    await hass.services.async_call(DOMAIN, service, data, blocking=True, context=context)


# ===================================================================================== registration
async def test_both_services_exist_once_a_router_is_set_up(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert hass.services.has_service(DOMAIN, SERVICE_ADD_STATIC_IP)
    assert hass.services.has_service(DOMAIN, SERVICE_REMOVE_STATIC_IP)
    assert set(hass.services.async_services_for_domain(DOMAIN)) == {"add_static_ip", "remove_static_ip"}


async def test_a_second_router_does_not_register_them_again(hass: HomeAssistant, entry: MockConfigEntry, setup_router: SetupRouter) -> None:
    before = hass.services.async_services_for_domain(DOMAIN)
    await setup_router(HOST2, mac="94:83:C4:00:00:02")
    assert hass.services.async_services_for_domain(DOMAIN).keys() == before.keys()


# ===================================================================================== add_static_ip
async def test_add_static_ip(hass: HomeAssistant, device_id: str, router: MockRouter, world: RouterWorld,
                             coordinator: GlinetCoordinator, activity: Any) -> None:
    await call(hass, "add_static_ip", add_data(device_id))

    assert router.static_binds == [{"mac": MAC2, "ip": "192.168.8.50", "name": "TV"}]
    assert coordinator.data.static_binds == router.static_binds
    entry = activity.recent(1)[0]
    assert (entry["msg"], entry["channel"], entry["ok"]) == ("static_ip_added", "service", True)


async def test_add_static_ip_by_a_client_device_of_the_router(hass: HomeAssistant, coordinator: GlinetCoordinator, entry: MockConfigEntry,
                                                             router: MockRouter) -> None:
    """Any device that belongs to the router's config entry identifies the router."""
    registry = dr.async_get(hass)
    client_device = registry.async_get_device_by_identifier((DOMAIN, "client_AA:BB:CC:00:00:00"), entry.entry_id)
    assert client_device is not None
    await call(hass, "add_static_ip", add_data(client_device.id, mac="AA:BB:CC:00:00:00", ip="192.168.8.60", name="phone"))
    assert router.static_binds[0]["ip"] == "192.168.8.60"


async def test_add_static_ip_records_the_calling_user(hass: HomeAssistant, device_id: str, activity: Any, hass_admin_user: MockUser) -> None:
    await call(hass, "add_static_ip", add_data(device_id), Context(user_id=hass_admin_user.id))
    assert activity.recent(1)[0]["user"] == hass_admin_user.name


async def test_add_static_ip_from_an_automation_has_no_user(hass: HomeAssistant, device_id: str, activity: Any) -> None:
    await call(hass, "add_static_ip", add_data(device_id))
    assert activity.recent(1)[0]["user"] is None


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"mac": "not-a-mac"}, "invalid_mac"),
        ({"mac": "FF:FF:FF:FF:FF:FF"}, "invalid_mac"),
        ({"ip": "300.1.1.1"}, "invalid_ip"),
        ({"ip": "fe80::1"}, "invalid_ip"),
        ({"ip": "10.9.9.9"}, "ip_outside_lan"),
        ({"ip": "192.168.8.255"}, "ip_outside_lan"),
        ({"ip": "192.168.8.1"}, "ip_outside_lan"),
        ({"name": "   "}, "bad_name"),
    ],
)
async def test_add_static_ip_refusals(hass: HomeAssistant, device_id: str, router: MockRouter, world: RouterWorld,
                                      overrides: dict, code: str) -> None:
    with pytest.raises(ActionError) as err:
        await call(hass, "add_static_ip", add_data(device_id, **overrides))
    assert err.value.code == code
    assert isinstance(err.value, HomeAssistantError)
    assert router.static_binds == [] and world.count("lan.add_static_bind") == 0


async def test_add_static_ip_duplicates(hass: HomeAssistant, device_id: str, router: MockRouter) -> None:
    await call(hass, "add_static_ip", add_data(device_id))
    with pytest.raises(ActionError) as err:
        await call(hass, "add_static_ip", add_data(device_id, ip="192.168.8.51", name="again"))
    assert err.value.code == "mac_already_bound"
    with pytest.raises(ActionError) as err:
        await call(hass, "add_static_ip", add_data(device_id, mac="AA:BB:CC:00:00:00", name="other"))
    assert err.value.code == "ip_already_bound"
    assert len(router.static_binds) == 1


async def test_add_static_ip_refused_outside_router_mode(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    ap = await setup_router(HOST2, mode="ap", mac="94:83:C4:00:00:09")
    ap_device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, ap.entry_id), ap.entry_id)
    assert ap_device is not None
    with pytest.raises(ActionError) as err:
        await call(hass, "add_static_ip", add_data(ap_device.id))
    assert err.value.code == "not_router_mode"
    assert world.count("lan.add_static_bind", HOST2) == 0


async def test_the_service_goes_to_the_router_the_device_belongs_to(hass: HomeAssistant, entry: MockConfigEntry, setup_router: SetupRouter,
                                                                    world: RouterWorld) -> None:
    second = await setup_router(HOST2, mac="94:83:C4:00:00:02")
    second_device = second.runtime_data.coordinator.router_device_id
    await call(hass, "add_static_ip", add_data(second_device))
    assert world.routers[HOST2].static_binds and not world.routers["192.0.2.10"].static_binds


async def test_unknown_device(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    with pytest.raises(HomeAssistantError) as err:
        await call(hass, "add_static_ip", add_data("0123456789abcdef0123456789abcdef"))
    assert "0123456789abcdef0123456789abcdef" in str(err.value)
    assert not isinstance(err.value, ActionError)


async def test_a_device_of_another_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    other = MockConfigEntry(domain="some_other_domain")
    other.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(config_entry_id=other.entry_id, identifiers={("some_other_domain", "x")})
    with pytest.raises(HomeAssistantError):
        await call(hass, "add_static_ip", add_data(device.id))


@pytest.mark.parametrize("missing", ["device_id", "mac", "ip", "name"])
async def test_add_static_ip_needs_every_field(hass: HomeAssistant, device_id: str, missing: str) -> None:
    data = add_data(device_id)
    del data[missing]
    with pytest.raises(vol.Invalid):
        await call(hass, "add_static_ip", data)


async def test_add_static_ip_accepts_numbers_where_text_is_expected(hass: HomeAssistant, device_id: str, router: MockRouter) -> None:
    """YAML turns an unquoted name like 1234 into a number: cv.string takes it."""
    await call(hass, "add_static_ip", add_data(device_id, name=1234))
    assert router.static_binds[0]["name"] == "1234"


# ===================================================================================== remove_static_ip
async def test_remove_static_ip_always_explains_why_it_cannot(hass: HomeAssistant, device_id: str, router: MockRouter, world: RouterWorld,
                                                              activity: Any) -> None:
    router.static_binds = [{"mac": MAC2, "ip": "192.168.8.50", "name": "TV"}]
    with pytest.raises(HomeAssistantError) as err:
        await call(hass, "remove_static_ip", {"device_id": device_id, "mac": MAC2})
    message = str(err.value)
    assert "lan.remove_static_bind" in message and "uci delete" in message and "dnsmasq" in message, "the manual way out is spelled out"
    assert not isinstance(err.value, ActionError)
    assert world.count("lan.remove_static_bind") == 0, "it does not even try a call that is known to fail"
    assert router.static_binds == [{"mac": MAC2, "ip": "192.168.8.50", "name": "TV"}]
    assert activity.recent() == []


async def test_remove_static_ip_for_a_bind_that_does_not_exist_gives_the_same_answer(hass: HomeAssistant, device_id: str) -> None:
    with pytest.raises(HomeAssistantError) as err:
        await call(hass, "remove_static_ip", {"device_id": device_id, "mac": "DE:AD:BE:EF:00:02"})
    assert "uci delete" in str(err.value)


async def test_remove_static_ip_still_checks_the_device(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    with pytest.raises(HomeAssistantError) as err:
        await call(hass, "remove_static_ip", {"device_id": "0" * 32, "mac": MAC2})
    assert "uci delete" not in str(err.value), "an unknown device is reported as such"
    assert "0" * 32 in str(err.value)


@pytest.mark.parametrize("missing", ["device_id", "mac"])
async def test_remove_static_ip_needs_its_fields(hass: HomeAssistant, device_id: str, missing: str) -> None:
    data = {"device_id": device_id, "mac": MAC2}
    del data[missing]
    with pytest.raises(vol.Invalid):
        await call(hass, "remove_static_ip", data)


# ===================================================================================== the device lookup
async def test_the_lookup(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator, device_id: str) -> None:
    assert async_get_coordinator_for_device(hass, device_id) is coordinator
    assert async_get_coordinator_for_device(hass, "does-not-exist") is None


async def test_a_service_call_causes_no_deprecation_warning(hass: HomeAssistant, device_id: str, caplog: pytest.LogCaptureFixture) -> None:
    """DeviceEntry.config_entries is deprecated (a device belongs to one config entry) and goes away in Home Assistant 2027.10."""
    caplog.set_level(logging.WARNING)
    await call(hass, "add_static_ip", add_data(device_id))
    assert [r.getMessage() for r in caplog.records if "deprecated" in r.getMessage() and "woow_glinet" in r.getMessage()] == []


@pytest.mark.parametrize("service", ["add_static_ip", "remove_static_ip"])
async def test_a_service_call_for_an_entry_that_is_not_loaded_is_a_clean_error(hass: HomeAssistant, entry: MockConfigEntry, device_id: str,
                                                                              service: str) -> None:
    await hass.config_entries.async_unload(entry.entry_id)
    data = add_data(device_id) if service == "add_static_ip" else {"device_id": device_id, "mac": MAC2}
    with pytest.raises(HomeAssistantError) as err:
        await call(hass, service, data)
    assert device_id in str(err.value) and not isinstance(err.value, AttributeError)


async def test_a_service_call_for_a_router_that_could_not_be_set_up(hass: HomeAssistant, setup_router: SetupRouter, world: RouterWorld) -> None:
    """The router was offline when Home Assistant started: its devices exist (from earlier runs), the entry is retrying."""
    router = world.add(HOST2, mac="94:83:C4:00:00:02")
    entry = await setup_router(HOST2, router=router)
    device = entry.runtime_data.coordinator.router_device_id
    await hass.config_entries.async_unload(entry.entry_id)
    world.disconnect(HOST2)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state.value == "setup_retry"

    with pytest.raises(HomeAssistantError) as err:
        await call(hass, "add_static_ip", add_data(device))
    assert not isinstance(err.value, ActionError)


async def test_the_lookup_returns_none_unless_the_router_is_loaded(hass: HomeAssistant, entry: MockConfigEntry, coordinator: GlinetCoordinator,
                                                                  device_id: str) -> None:
    registry = dr.async_get(hass)
    client_device = registry.async_get_device_by_identifier((DOMAIN, "client_AA:BB:CC:00:00:00"), entry.entry_id)
    other = MockConfigEntry(domain="some_other_domain")
    other.add_to_hass(hass)
    foreign = registry.async_get_or_create(config_entry_id=other.entry_id, identifiers={("some_other_domain", "x")})

    assert async_get_coordinator_for_device(hass, device_id) is coordinator
    assert async_get_coordinator_for_device(hass, client_device.id) is coordinator, "any device of the router will do"
    assert async_get_coordinator_for_device(hass, foreign.id) is None
    assert async_get_coordinator_for_device(hass, "does-not-exist") is None

    await hass.config_entries.async_unload(entry.entry_id)
    assert async_get_coordinator_for_device(hass, device_id) is None


# ===================================================================================== who may call them
@pytest.mark.parametrize("service", ["add_static_ip", "remove_static_ip"])
async def test_a_read_only_user_cannot_use_the_router_services(hass: HomeAssistant, hass_ws_client: Any, entry: MockConfigEntry,
                                                               device_id: str, router: MockRouter, world: RouterWorld,
                                                               hass_read_only_access_token: str, service: str) -> None:
    """The same action in the panel (woow_glinet/static_ip/add) is administrators-only, so are the services."""
    client = await hass_ws_client(hass, hass_read_only_access_token)
    data = add_data(device_id) if service == "add_static_ip" else {"device_id": device_id, "mac": MAC2}
    await client.send_json_auto_id({"type": "call_service", "domain": DOMAIN, "service": service, "service_data": data})
    response = await client.receive_json()
    assert response["success"] is False and response["error"]["message"] == "Unauthorized", response
    assert router.static_binds == [] and world.count("lan.add_static_bind") == 0


@pytest.mark.parametrize("service", ["add_static_ip", "remove_static_ip"])
async def test_a_user_who_is_not_an_administrator_is_refused(hass: HomeAssistant, device_id: str, router: MockRouter, world: RouterWorld,
                                                             service: str) -> None:
    user = MockUser().add_to_hass(hass)  # not in the administrators group
    data = add_data(device_id) if service == "add_static_ip" else {"device_id": device_id, "mac": MAC2}
    with pytest.raises(Unauthorized):
        await call(hass, service, data, Context(user_id=user.id))
    assert router.static_binds == [] and world.count("lan.add_static_bind") == 0


async def test_an_administrator_can_use_the_services(hass: HomeAssistant, device_id: str, router: MockRouter, hass_admin_user: MockUser) -> None:
    await call(hass, "add_static_ip", add_data(device_id), Context(user_id=hass_admin_user.id))
    assert router.static_binds == [{"mac": MAC2, "ip": "192.168.8.50", "name": "TV"}]


async def test_an_automation_or_script_without_a_user_can_use_the_services(hass: HomeAssistant, device_id: str, router: MockRouter) -> None:
    """Automations and AI agents call services without a user context: the check only looks at calls made by a person."""
    await call(hass, "add_static_ip", add_data(device_id), Context())
    assert len(router.static_binds) == 1


async def test_an_administrator_can_use_the_router_services_over_the_api(hass: HomeAssistant, hass_ws_client: Any, entry: MockConfigEntry,
                                                                         device_id: str, router: MockRouter) -> None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "call_service", "domain": DOMAIN, "service": "add_static_ip", "service_data": add_data(device_id)})
    response = await client.receive_json()
    assert response["success"] is True
    assert router.static_binds == [{"mac": MAC2, "ip": "192.168.8.50", "name": "TV"}]
