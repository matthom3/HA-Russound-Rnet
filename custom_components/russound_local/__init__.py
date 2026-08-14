"""The Russound RNET Local integration.

Speaks RNET directly for power and volume writes only, working around a
write bug in aiorussound's bundled RNET client that silently drops
turn_on/turn_off/volume_set frames for every zone but the first declared
one. Reads, state display and select_source all continue to go through
the existing russound_rnet platform unchanged.
"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_POWER,
    ATTR_VOLUME_LEVEL,
    ATTR_ZONE,
    CONF_HOST,
    CONF_PORT,
    CONTROLLER_ID,
    DOMAIN,
    SERVICE_SET_POWER,
    SERVICE_SET_VOLUME,
    ZONES,
)
from .rnet import RNETClient, RNETError

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "number"]

SET_POWER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ZONE): vol.In(ZONES),
        vol.Required(ATTR_POWER): cv.boolean,
    }
)

SET_VOLUME_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ZONE): vol.In(ZONES),
        vol.Required(ATTR_VOLUME_LEVEL): vol.All(
            vol.Coerce(float), vol.Range(min=0.0, max=1.0)
        ),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Russound RNET Local from a config entry."""
    client = RNETClient(entry.data[CONF_HOST], entry.data[CONF_PORT])
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    async def handle_set_power(call: ServiceCall) -> None:
        zone = call.data[ATTR_ZONE]
        power = call.data[ATTR_POWER]
        try:
            await hass.async_add_executor_job(client.set_power, CONTROLLER_ID, zone, power)
        except RNETError as err:
            _LOGGER.error("Failed to set power for zone %s: %s", zone, err)

    async def handle_set_volume(call: ServiceCall) -> None:
        zone = call.data[ATTR_ZONE]
        volume_level = call.data[ATTR_VOLUME_LEVEL]
        try:
            await hass.async_add_executor_job(client.set_volume, CONTROLLER_ID, zone, volume_level)
        except RNETError as err:
            _LOGGER.error("Failed to set volume for zone %s: %s", zone, err)

    if not hass.services.has_service(DOMAIN, SERVICE_SET_POWER):
        hass.services.async_register(DOMAIN, SERVICE_SET_POWER, handle_set_power, schema=SET_POWER_SCHEMA)
    if not hass.services.has_service(DOMAIN, SERVICE_SET_VOLUME):
        hass.services.async_register(DOMAIN, SERVICE_SET_VOLUME, handle_set_volume, schema=SET_VOLUME_SCHEMA)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        client: RNETClient = hass.data[DOMAIN].pop(entry.entry_id)
        await hass.async_add_executor_job(client.close)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_SET_POWER)
            hass.services.async_remove(DOMAIN, SERVICE_SET_VOLUME)
    return unload_ok
