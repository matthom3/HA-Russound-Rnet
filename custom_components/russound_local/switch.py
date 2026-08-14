"""Per-zone power switches, writing directly over RNET.

Each switch mirrors the state of the corresponding existing
media_player.* entity (whose reads already work correctly) and only takes
over the write side for power.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import EventStateChangedData, async_track_state_change_event

from .const import CONTROLLER_ID, DOMAIN, ZONE_NAMES, media_player_entity_id
from .rnet import RNETClient, RNETError

_LOGGER = logging.getLogger(__name__)

_INACTIVE_STATES = ("off", "unavailable", "unknown")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up one power switch per configured zone."""
    client: RNETClient = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        RussoundZonePowerSwitch(client, entry.entry_id, zone, name)
        for zone, name in ZONE_NAMES.items()
    )


class RussoundZonePowerSwitch(SwitchEntity):
    """Power switch for a single Russound zone."""

    _attr_should_poll = False

    def __init__(self, client: RNETClient, entry_id: str, zone: int, name: str) -> None:
        self._client = client
        self._zone = zone
        self._source_entity_id = media_player_entity_id(zone)
        self._attr_unique_id = f"{entry_id}_zone{zone}_power"
        self._attr_name = f"{name} Power"
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Seed state from, and start tracking, the existing media_player entity."""
        source_state = self.hass.states.get(self._source_entity_id)
        if source_state is not None:
            self._attr_is_on = source_state.state not in _INACTIVE_STATES

        @callback
        def _source_changed(event: Event[EventStateChangedData]) -> None:
            new_state = event.data["new_state"]
            if new_state is None:
                return
            self._attr_is_on = new_state.state not in _INACTIVE_STATES
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(self.hass, [self._source_entity_id], _source_changed)
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_power(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_power(False)

    async def _set_power(self, power: bool) -> None:
        try:
            await self.hass.async_add_executor_job(self._client.set_power, CONTROLLER_ID, self._zone, power)
        except RNETError as err:
            _LOGGER.error("Failed to set power for zone %s: %s", self._zone, err)
            return
        self._attr_is_on = power
        self.async_write_ha_state()
