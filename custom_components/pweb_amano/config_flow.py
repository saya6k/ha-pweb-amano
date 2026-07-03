"""Config flow for PWEB Amano."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .api import PwebAmanoApiClient, normalize_base_url
from .const import DOMAIN
from .exceptions import PwebAmanoAuthError, PwebAmanoConnectionError

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class PwebAmanoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PWEB Amano."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_USERNAME]}"
            )
            self._abort_if_unique_id_configured()

            client = PwebAmanoApiClient(
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                await client.async_login()
            except PwebAmanoAuthError:
                errors["base"] = "invalid_auth"
            except PwebAmanoConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=normalize_base_url(user_input[CONF_HOST]),
                    data=user_input,
                )
            finally:
                await client.async_close()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
