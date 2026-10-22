"""Config flow for the WOOW GL.iNet integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import aiohttp_client

from .api import GlinetApiError, GlinetAuthError, GlinetClient
from .const import (
    CONF_SCHEME,
    CONF_VERIFY_SSL,
    DEFAULT_HOST,
    DEFAULT_SCHEME,
    DEFAULT_USERNAME,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
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


class WoowGlinetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle adding one GL.iNet router."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(
                self.hass, verify_ssl=user_input[CONF_VERIFY_SSL]
            )
            client = GlinetClient(
                session,
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                scheme=user_input[CONF_SCHEME],
                verify_ssl=user_input[CONF_VERIFY_SSL],
            )
            try:
                await client.login()
                info = await client.call("system", "get_info")
            except GlinetAuthError:
                errors["base"] = "invalid_auth"
            except GlinetApiError:
                errors["base"] = "cannot_connect"
            else:
                mac = (info or {}).get("mac")
                if mac:
                    await self.async_set_unique_id(mac)
                    self._abort_if_unique_id_configured()
                title = (info or {}).get("board_info", {}).get("hostname") or user_input[
                    CONF_HOST
                ]
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
