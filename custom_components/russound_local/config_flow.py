"""Config flow for the Russound RNET Local integration."""
from __future__ import annotations

import logging
import socket
from typing import Any

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_HOST, CONF_PORT, DEFAULT_PORT, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


async def _can_connect(hass: HomeAssistant, host: str, port: int) -> None:
    def _connect() -> None:
        with socket.create_connection((host, port), timeout=5):
            pass

    await hass.async_add_executor_job(_connect)


class RussoundLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Russound RNET Local."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Collect the iTach host/port for the direct RNET write path."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()
            try:
                await _can_connect(self.hass, host, port)
            except OSError as err:
                _LOGGER.warning("Cannot connect to %s:%s: %s", host, port, err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="Russound RNET (Local)", data=user_input)

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors)
