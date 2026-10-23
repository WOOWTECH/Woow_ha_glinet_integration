"""Config flow for the WOOW GL.iNet integration."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client

from .api import GlinetApiError, GlinetClient, GlinetInvalidAuth
from .sanitize import as_dict, text
from .const import (
    CONF_SCHEME,
    CONF_VERIFY_SSL,
    DEFAULT_HOST,
    DEFAULT_SCHEME,
    DEFAULT_USERNAME,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    OPTION_EXPOSE_WIFI_PASSWORDS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SCHEME, default=DEFAULT_SCHEME): vol.In(["http", "https"]),
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


def normalize_host(value: str) -> str:
    """"https://192.168.8.1/admin" -> "192.168.8.1": people paste the address they type into a browser."""
    host = re.sub(r"^[A-Za-z][A-Za-z0-9+.-]*://", "", value.strip())
    return host.split("/", 1)[0].strip()


async def _async_probe(hass: HomeAssistant, data: Mapping[str, Any]) -> dict[str, Any]:
    """Log in with these settings and return the router's system.get_info.

    Raises GlinetInvalidAuth for rejected credentials and GlinetApiError for everything else.
    """
    session = aiohttp_client.async_get_clientsession(hass, verify_ssl=data[CONF_VERIFY_SSL])
    client = GlinetClient(
        session,
        data[CONF_HOST],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        scheme=data[CONF_SCHEME],
        verify_ssl=data[CONF_VERIFY_SSL],
    )
    await client.login()
    info = await client.call("system", "get_info")
    return info if isinstance(info, dict) else {}


class WoowGlinetOptionsFlow(OptionsFlowWithReload):
    """The integration's options (one so far: whether Wi-Fi passwords show up as entity states); the entry reloads itself."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        schema = vol.Schema({vol.Required(OPTION_EXPOSE_WIFI_PASSWORDS, default=False): bool})
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, self.config_entry.options),
        )


class WoowGlinetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle adding one GL.iNet router, and fixing its credentials / address later."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> WoowGlinetOptionsFlow:
        return WoowGlinetOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = {**user_input, CONF_HOST: normalize_host(user_input[CONF_HOST])}
            try:
                info = await _async_probe(self.hass, user_input)
            except GlinetInvalidAuth:
                errors["base"] = "invalid_auth"
            except GlinetApiError:
                errors["base"] = "cannot_connect"
            else:
                mac = text(info.get("mac"))
                if mac:
                    await self.async_set_unique_id(mac)
                    self._abort_if_unique_id_configured()
                title = text(as_dict(info.get("board_info")).get("hostname")) or user_input[CONF_HOST]
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The router rejected the stored credentials (the password was changed)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            updates = {CONF_USERNAME: user_input[CONF_USERNAME], CONF_PASSWORD: user_input[CONF_PASSWORD]}
            try:
                info = await _async_probe(self.hass, {**entry.data, **updates})
            except GlinetInvalidAuth:
                errors["base"] = "invalid_auth"
            except GlinetApiError:
                errors["base"] = "cannot_connect"
            else:
                if mac := text(info.get("mac")):
                    await self.async_set_unique_id(mac)
                    self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(entry, data_updates=updates)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=entry.data[CONF_USERNAME]): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={"host": entry.data[CONF_HOST], "name": entry.title},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address / protocol / credentials of an existing router without removing it."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {
                **entry.data,
                **user_input,
                CONF_HOST: normalize_host(user_input[CONF_HOST]),
                # leaving the password empty keeps the stored one
                CONF_PASSWORD: user_input.get(CONF_PASSWORD) or entry.data[CONF_PASSWORD],
            }
            try:
                info = await _async_probe(self.hass, data)
            except GlinetInvalidAuth:
                errors["base"] = "invalid_auth"
            except GlinetApiError:
                errors["base"] = "cannot_connect"
            else:
                if mac := text(info.get("mac")):
                    await self.async_set_unique_id(mac)
                    self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(entry, data_updates=data)

        suggested = user_input or {k: v for k, v in entry.data.items() if k != CONF_PASSWORD}
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Required(CONF_SCHEME): vol.In(["http", "https"]),
                vol.Required(CONF_VERIFY_SSL): bool,
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            description_placeholders={"name": entry.title},
            errors=errors,
        )
