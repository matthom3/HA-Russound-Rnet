"""Per-zone volume controls, writing directly over RNET.

Each number entity mirrors the volume_level of the corresponding existing
media_player.* entity (whose reads already work correctly) and only takes
over the write side for volume.
"""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import EventStateChangedData, async_track_state_change_event

from .const import CONTROLLER_ID, DOMAIN, ZONE_NAMES, media_player_entity_id
from .rnet import RNETClient, RNETError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up one volume control per configured zone."""
    client: RNETClient = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        RussoundZoneVolumeNumber(client, entry.entry_id, zone, name)
        for zone, name in ZONE_NAMES.items()
    )


class RussoundZoneVolumeNumber(NumberEntity):
    """Volume control for a single Russound zone."""

    _attr_should_poll = False
    _attr_native_min_value = 0.0
    _attr_native_max_value = 1.0
    _attr_native_step = 0.02
    _attr_mode = NumberMode.SLIDER

    def __init__(self, client: RNETClient, entry_id: str, zone: int, name: str) -> None:
        self._client = client
        self._zone = zone
        self._source_entity_id = media_player_entity_id(zone)
        self._attr_unique_id = f"{entry_id}_zone{zone}_volume"
        self._attr_name = f"{name} Volume"
        self._attr_native_value = 0.0

    async def async_added_to_hass(self) -> None:
        """Seed state from, and start tracking, the existing media_player entity."""
        source_state = self.hass.states.get(self._source_entity_id)
        if source_state is not None:
            self._sync_from_source_state(source_state)

        @callback
        def _source_changed(event: Event[EventStateChangedData]) -> None:
            new_state = event.data["new_state"]
            if new_state is None:
                return
            self._sync_from_source_state(new_state)
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(self.hass, [self._source_entity_id], _source_changed)
        )

    @callback
    def _sync_from_source_state(self, state: State) -> None:
        volume_level = state.attributes.get("volume_level")
        if isinstance(volume_level, (int, float)):
            self._attr_native_value = float(volume_level)

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.hass.async_add_executor_job(self._client.set_volume, CONTROLLER_ID, self._zone, value)
        except RNETError as err:
            _LOGGER.error("Failed to set volume for zone %s: %s", self._zone, err)
            return
        self._attr_native_value = value
        self.async_write_ha_state()
