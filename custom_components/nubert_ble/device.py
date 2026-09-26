"""Persistent BLE connection + push-state manager for one Nubert X-2 unit."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from bleak import BleakClient
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from . import const, protocol

_LOGGER = logging.getLogger(__name__)


@dataclass
class NubertState:
    """Live/optimistic state mirror for one Nubert unit."""

    volume_db: float | None = None
    muted: bool | None = None
    input_index: int | None = None
    # Write-optimistic; no reliable readback exists (see protocol doc). Defaults to True on
    # connect since the device stays BLE-reachable even after writing "power off" during testing
    # -- an unconditional "unknown" state was worse UX than assuming on-when-reachable.
    power_on: bool | None = True
    bass_db: float | None = None
    mid_high_db: float | None = None
    balance_db: float | None = None
    highpass_hz: int | None = None
    sub_crossover_hz: int | None = None
    loudness: bool | None = None
    analog_gain: bool | None = None
    preset: int | None = None  # write-optimistic only, no confirmed readback subcode
    eq_bands: list[int] = field(default_factory=lambda: [const.EQ_BAND_FLAT] * const.EQ_BAND_COUNT)
    available: bool = False


class NubertDevice:
    """Owns the single persistent GATT connection to one Nubert X-2 unit.

    The device only accepts one BLE management connection at a time (firmware limitation) -- if
    the official phone app connects, this loop will fail to (re)connect until it disconnects.
    Reconnection uses capped backoff rather than erroring loudly.
    """

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self.hass = hass
        self.address = address
        self.state = NubertState()
        self._client: BleakClient | None = None
        self._listeners: list[Callable[[], None]] = []
        self._connection_task: asyncio.Task | None = None
        self._stopping = False

    def add_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(callback)

        def remove() -> None:
            self._listeners.remove(callback)

        return remove

    def _notify_listeners(self) -> None:
        for cb in self._listeners:
            cb()

    async def async_start(self) -> None:
        self._stopping = False
        self._connection_task = asyncio.create_task(self._connection_loop())

    async def async_stop(self) -> None:
        self._stopping = True
        if self._connection_task:
            self._connection_task.cancel()
        if self._client and self._client.is_connected:
            await self._client.disconnect()

    async def _connection_loop(self) -> None:
        backoff_idx = 0
        while not self._stopping:
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if ble_device is None:
                await asyncio.sleep(const.RECONNECT_BACKOFF_SECONDS[backoff_idx])
                backoff_idx = min(backoff_idx + 1, len(const.RECONNECT_BACKOFF_SECONDS) - 1)
                continue
            try:
                self._client = await establish_connection(
                    BleakClient, ble_device, self.address, self._disconnected_callback
                )
                await self._client.start_notify(const.CHAR_UUID, self._handle_indication)
                self.state.available = True
                backoff_idx = 0
                self._notify_listeners()
                await self._prime_status()
                while self._client.is_connected and not self._stopping:
                    await asyncio.sleep(5)
            except Exception as err:  # noqa: BLE001 -- must keep retrying regardless of cause
                _LOGGER.debug("Nubert %s connection attempt failed: %s", self.address, err)
                self.state.available = False
                self._notify_listeners()
                await asyncio.sleep(const.RECONNECT_BACKOFF_SECONDS[backoff_idx])
                backoff_idx = min(backoff_idx + 1, len(const.RECONNECT_BACKOFF_SECONDS) - 1)

    def _disconnected_callback(self, _client: BleakClient) -> None:
        self.state.available = False
        self._notify_listeners()

    def _handle_indication(self, _handle: int, data: bytearray) -> None:
        payload = bytes(data)
        blob = protocol.parse_status_blob(payload)
        if blob is not None:
            self._apply_status_blob(blob)
        elif (eq_bands := protocol.parse_eq_bands_push(payload)) is not None:
            self.state.eq_bands = list(eq_bands)
        else:
            echo = protocol.parse_echo(payload)
            if echo is not None:
                self._apply_echo(*echo)
        self._notify_listeners()

    async def _prime_status(self) -> None:
        for query in const.STATUS_QUERIES:
            if self._client is None or not self._client.is_connected:
                return
            await self._client.write_gatt_char(const.CHAR_UUID, query, response=True)
            await asyncio.sleep(0.3)
        if self._client is None or not self._client.is_connected:
            return
        await self._client.write_gatt_char(
            const.CHAR_UUID, protocol.encode_write(const.OPCODE_EQ_QUERY, const.EQ_QUERY_TRIGGER),
            response=True,
        )
        await asyncio.sleep(0.3)

    async def async_refresh_status(self) -> None:
        """Re-run the full status refresh (bulk queries + EQ-band push).

        Needed after a preset switch: the device changes several DSP parameters together, but
        only echoes parameters written directly by us -- it never proactively announces what a
        preset switch changed. Call this after writing OPCODE_PRESET so the number/switch
        entities catch up.
        """
        await asyncio.sleep(0.3)  # let the device settle into the new preset before polling
        await self._prime_status()

    def _apply_status_blob(self, blob: dict[int, bytes]) -> None:
        s = self.state
        if const.STATUS_SUBCODE_VOLUME in blob:
            s.volume_db = protocol.volume_byte_to_db(blob[const.STATUS_SUBCODE_VOLUME][0])
        if const.STATUS_SUBCODE_BASS in blob:
            s.bass_db = protocol.tone_byte_to_db(blob[const.STATUS_SUBCODE_BASS][0])
        if const.STATUS_SUBCODE_MID_HIGH in blob:
            s.mid_high_db = protocol.tone_byte_to_db(blob[const.STATUS_SUBCODE_MID_HIGH][0])
        if const.STATUS_SUBCODE_BALANCE in blob:
            s.balance_db = protocol.tone_byte_to_db(blob[const.STATUS_SUBCODE_BALANCE][0])
        if const.STATUS_SUBCODE_HIGHPASS in blob:
            s.highpass_hz = blob[const.STATUS_SUBCODE_HIGHPASS][0]
        if const.STATUS_SUBCODE_SUB_CROSSOVER in blob:
            s.sub_crossover_hz = blob[const.STATUS_SUBCODE_SUB_CROSSOVER][0]
        if const.STATUS_SUBCODE_LOUDNESS in blob:
            s.loudness = bool(blob[const.STATUS_SUBCODE_LOUDNESS][0])
        if const.STATUS_SUBCODE_ANALOG_GAIN in blob:
            s.analog_gain = bool(blob[const.STATUS_SUBCODE_ANALOG_GAIN][0])
        if const.STATUS_SUBCODE_MUTE in blob:
            s.muted = bool(blob[const.STATUS_SUBCODE_MUTE][0])

    def _apply_echo(self, opcode: int, value: bytes) -> None:
        if not value:
            return
        s = self.state
        v = value[0]
        if opcode == const.OPCODE_VOLUME - 1:
            s.volume_db = protocol.volume_byte_to_db(v)
        elif opcode == const.OPCODE_INPUT - 1:
            s.input_index = v
        elif opcode == const.OPCODE_MUTE - 1:
            s.muted = bool(v)
        elif opcode == const.OPCODE_BASS - 1:
            s.bass_db = protocol.tone_byte_to_db(v)
        elif opcode == const.OPCODE_MID_HIGH - 1:
            s.mid_high_db = protocol.tone_byte_to_db(v)
        elif opcode == const.OPCODE_BALANCE - 1:
            s.balance_db = protocol.tone_byte_to_db(v)
        elif opcode == const.OPCODE_HIGHPASS - 1:
            s.highpass_hz = v
        elif opcode == const.OPCODE_SUB_CROSSOVER - 1:
            s.sub_crossover_hz = v
        elif opcode == const.OPCODE_LOUDNESS - 1:
            s.loudness = bool(v)
        elif opcode == const.OPCODE_ANALOG_GAIN - 1:
            s.analog_gain = bool(v)
        elif opcode == const.OPCODE_EQ_BAND - 1 and len(value) >= 2:
            band_index, band_value = value[0], value[1]
            if 0 <= band_index < const.EQ_BAND_COUNT:
                s.eq_bands[band_index] = band_value
        # OPCODE_POWER and OPCODE_PRESET: no reliable echo semantics confirmed live -- left
        # write-optimistic, set directly by the entities that write them.

    async def async_write(self, opcode: int, payload: bytes = b"") -> None:
        if self._client is None or not self._client.is_connected:
            raise ConnectionError(f"Nubert {self.address} is not connected")
        await self._client.write_gatt_char(
            const.CHAR_UUID, protocol.encode_write(opcode, payload), response=True
        )
