"""Config flow with reauth."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AuthError, HsVeiturClient, HsVeiturError
from .const import (
    CONF_BACKFILL_MONTHS,
    CONF_CUSTOMER_ID,
    CONF_ENERGY_RATE,
    CONF_GRID_RATE,
    CONF_INCLUDE_VAT,
    CONF_PRIVATE_KEY,
    CONF_PUBLIC_KEY,
    DEFAULT_BACKFILL_MONTHS,
    DOMAIN,
)

STEP_USER = vol.Schema(
    {
        vol.Required(CONF_PUBLIC_KEY): str,
        vol.Required(CONF_PRIVATE_KEY): str,
        vol.Required(CONF_CUSTOMER_ID): str,
        vol.Optional(CONF_BACKFILL_MONTHS, default=DEFAULT_BACKFILL_MONTHS): vol.All(
            int, vol.Range(min=0, max=30)
        ),
    }
)
STEP_REAUTH = vol.Schema(
    {vol.Required(CONF_PUBLIC_KEY): str, vol.Required(CONF_PRIVATE_KEY): str}
)
STEP_OPTIONS = vol.Schema(
    {
        vol.Optional(CONF_GRID_RATE): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional(CONF_ENERGY_RATE): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Required(CONF_INCLUDE_VAT, default=True): bool,
    }
)


class HsVeiturOptionsFlow(OptionsFlow):
    """Custom pricing. Leave both rates empty to turn cost tracking off."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                STEP_OPTIONS, self.config_entry.options
            ),
        )


class HsVeiturConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HsVeiturOptionsFlow:
        return HsVeiturOptionsFlow()

    async def _validate(self, data: Mapping[str, Any]) -> str | None:
        """Make one narrow call (slow: up to a few minutes). Return an error key."""
        client = HsVeiturClient(
            async_get_clientsession(self.hass),
            data[CONF_PUBLIC_KEY],
            data[CONF_PRIVATE_KEY],
            data[CONF_CUSTOMER_ID],
        )
        end = datetime.now(UTC).replace(tzinfo=None)
        try:
            await client.validate(end - timedelta(days=2), end)
        except AuthError:
            return "invalid_auth"
        except HsVeiturError:
            return "cannot_connect"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_CUSTOMER_ID])
            self._abort_if_unique_id_configured()
            if error := await self._validate(user_input):
                errors["base"] = error
            else:
                return self.async_create_entry(title="HS Veitur", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**entry.data, **user_input}
            if error := await self._validate(data):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=STEP_REAUTH, errors=errors
        )
