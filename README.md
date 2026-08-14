# HA-Russound-Rnet

Home Assistant setup for a Russound MCA-C3 (6-zone), connected via a Global
Cache iTach IP2SL (Ethernet-to-RS232 bridge) at `192.168.1.239:4999`.

## Background

The stock `russound_rnet` platform (backed by `aiorussound`'s bundled RNET
client) correctly handles **reads** and **`select_source` writes** for all
zones, but `turn_on` / `turn_off` / `volume_set` writes silently produce no
frame at all for any zone except the first declared one. This was confirmed
via debug log capture across all 6 zones on the hardware above.

Rather than wait on an upstream fix or patch `aiorussound` itself,
[`custom_components/russound_local`](custom_components/russound_local) speaks
RNET directly for just power and volume, bypassing `aiorussound` entirely for
those two commands. Reads, state display, source selection, and the existing
`media_player.*` entities are untouched — they already work correctly.

The RNET framing/checksum logic follows the approach used by
[`laf/russound`](https://github.com/laf/russound), the RNET client Home
Assistant's `russound_rnet` platform relied on for years before it was
migrated onto `aiorussound`'s unified client, reimplemented from scratch for
this integration (see [`rnet.py`](custom_components/russound_local/rnet.py)).

## What's here

`custom_components/russound_local/` is a small local-only integration
exposing:

- Two services: `russound_local.set_power` (`zone`, `power`) and
  `russound_local.set_volume` (`zone`, `volume_level`).
- A `switch.*_power` and `number.*_volume` entity per zone (Deck, Dining,
  Patio, Hot Tub, Firepit), which mirror the state/`volume_level` of the
  corresponding existing `media_player.*` entity but own the write path.

Zone 6 ("Not Used") has no `media_player` entity and is intentionally
excluded.

## Install

1. Copy `custom_components/russound_local` into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Settings → Devices & Services → Add Integration → "Russound RNET (Local)".
   Enter the iTach's host (`192.168.1.239`) and port (`4999`).

## Testing

1. Confirm the iTach accepts a raw connection: `nc 192.168.1.239 4999` should open cleanly.
2. Toggle `switch.patio_power` (or call `russound_local.set_power` with `zone: 3`) and confirm via the keypad or `media_player.patio`'s state that the zone actually powers on/off.
3. Repeat for `number.patio_volume` / `russound_local.set_volume` at a couple of different levels, on a couple of different zones.
4. Confirm zone 1 (Deck) still works too — it was never broken by the original bug, but worth confirming this path doesn't regress it.
