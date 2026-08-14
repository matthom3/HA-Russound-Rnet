"""Constants for the Russound RNET Local integration."""
from homeassistant.util import slugify

DOMAIN = "russound_local"

CONF_HOST = "host"
CONF_PORT = "port"
DEFAULT_PORT = 4999

# Single MCA-C3, no linked controllers.
CONTROLLER_ID = 1

SERVICE_SET_POWER = "set_power"
SERVICE_SET_VOLUME = "set_volume"

ATTR_ZONE = "zone"
ATTR_POWER = "power"
ATTR_VOLUME_LEVEL = "volume_level"

# 1-based zone number -> friendly name. Zone 6 is physically unused and
# has no corresponding media_player entity, so it's intentionally omitted.
ZONE_NAMES = {
    1: "Deck",
    2: "Dining",
    3: "Patio",
    4: "Hot Tub",
    5: "Firepit",
}

ZONES = list(ZONE_NAMES)


def media_player_entity_id(zone: int) -> str:
    """Return the existing russound_rnet media_player entity this zone mirrors."""
    return f"media_player.{slugify(ZONE_NAMES[zone])}"
