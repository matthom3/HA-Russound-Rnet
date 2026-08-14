"""Minimal direct RNET protocol client for power and volume writes.

aiorussound's bundled RNET client silently drops turn_on/turn_off/
volume_set frames for every zone but the first one it declares (reads and
select_source writes are unaffected). Rather than patch that dependency,
this talks straight to the controller over TCP for just those two
commands.

The control flow here (one blocking socket guarded by a lock, a mandatory
inter-command delay, template-based message construction with a summed
7-bit checksum) mirrors the approach used by the RNET client Home
Assistant's russound_rnet platform relied on for years before it was
migrated onto aiorussound, but is written from scratch for this
integration rather than reused verbatim.
"""
from __future__ import annotations

import logging
import socket
import threading
import time

_LOGGER = logging.getLogger(__name__)

# Fixed keypad code recommended by the RNET spec for an external/IP
# controller, and the minimum required delay between sent commands.
KEYPAD_CODE = 0x70
COMMAND_DELAY = 0.1
TERMINATOR = 0xF7

# @cc=controller, @zz=zone, @kk=keypad code, @pr=parameter (all zero-based
# on the wire). Zone sits near the end of both templates, unlike
# select_source where it appears much earlier.
_POWER_TEMPLATE = "F0 @cc 00 7F 00 00 @kk 05 02 02 00 00 F1 23 00 @pr 00 @zz 00 01"
_VOLUME_TEMPLATE = "F0 @cc 00 7F 00 00 @kk 05 02 02 00 00 F1 21 00 @pr 00 @zz 00 01"


class RNETError(Exception):
    """Raised when an RNET command could not be sent."""


class RNETClient:
    """Blocking TCP client that sends RNET power/volume command frames."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._lock = threading.Lock()
        self._sock: socket.socket | None = None
        self._last_send_monotonic: float | None = None

    def _open_socket(self) -> socket.socket:
        return socket.create_connection((self._host, self._port), timeout=5)

    def _ensure_connected(self) -> socket.socket:
        if self._sock is not None:
            try:
                self._sock.getpeername()
                return self._sock
            except OSError:
                self._sock.close()
                self._sock = None
        self._sock = self._open_socket()
        return self._sock

    @staticmethod
    def _build_message(template: str, controller: int, zone: int, param: int) -> bytes:
        byte_values = []
        for token in template.split():
            if token == "@cc":
                byte_values.append(controller - 1)
            elif token == "@zz":
                byte_values.append(zone - 1)
            elif token == "@kk":
                byte_values.append(KEYPAD_CODE)
            elif token == "@pr":
                byte_values.append(param)
            else:
                byte_values.append(int(token, 16))

        checksum = (sum(byte_values) + len(byte_values)) & 0x7F
        return bytes([*byte_values, checksum, TERMINATOR])

    def _send(self, message: bytes) -> None:
        with self._lock:
            if self._last_send_monotonic is not None:
                elapsed = time.monotonic() - self._last_send_monotonic
                if elapsed < COMMAND_DELAY:
                    time.sleep(COMMAND_DELAY - elapsed)
            try:
                sock = self._ensure_connected()
                sock.sendall(message)
            except OSError as err:
                if self._sock is not None:
                    self._sock.close()
                self._sock = None
                raise RNETError(f"Failed to send RNET command to {self._host}:{self._port}: {err}") from err
            finally:
                self._last_send_monotonic = time.monotonic()

    def set_power(self, controller: int, zone: int, power: bool) -> None:
        """Send a power on/off frame for the given zone. Blocking; run in an executor."""
        message = self._build_message(_POWER_TEMPLATE, controller, zone, 1 if power else 0)
        self._send(message)

    def set_volume(self, controller: int, zone: int, volume_level: float) -> None:
        """Send a volume frame for the given zone. volume_level is 0.0-1.0. Blocking; run in an executor."""
        param = round(max(0.0, min(1.0, volume_level)) * 50)
        message = self._build_message(_VOLUME_TEMPLATE, controller, zone, param)
        self._send(message)

    def close(self) -> None:
        """Close the underlying socket, if open. Blocking; run in an executor."""
        with self._lock:
            if self._sock is not None:
                self._sock.close()
                self._sock = None
