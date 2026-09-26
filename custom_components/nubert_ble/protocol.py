"""Pure encode/decode helpers for the Nubert X-2 BLE protocol. No BLE I/O here -- keeps this
fully unit-testable without hardware. See docs/concepts/nubert-ble-protocol.md (infrastructure
repo) for how these were derived.
"""
from __future__ import annotations

from . import const


def encode_write(opcode: int, payload: bytes = b"") -> bytes:
    """Build a [opcode: u16 LE][payload] command ready to write to CHAR_UUID."""
    return opcode.to_bytes(2, "little") + payload


def parse_status_blob(payload: bytes) -> dict[int, bytes] | None:
    """Parse a bulk status-query indication: [0x86][len][subcode][len][value]...

    Returns None if payload isn't a bulk-status blob (e.g. it's a plain single-opcode echo).
    """
    if len(payload) < 2 or payload[0] != 0x86:
        return None
    length = payload[1]
    data = payload[2 : 2 + length]
    result: dict[int, bytes] = {}
    i = 0
    while i + 2 <= len(data):
        subcode = data[i]
        vlen = data[i + 1]
        value = data[i + 2 : i + 2 + vlen]
        if len(value) != vlen:
            break
        result[subcode] = value
        i += 2 + vlen
    return result


def parse_eq_bands_push(payload: bytes) -> bytes | None:
    """Parse the dedicated 5-band EQ push: [0x10][0x05][band0..band4].

    Sent unprompted after any EQ_BAND write, and also after writing OPCODE_EQ_QUERY -- this is
    NOT part of the bulk 0x86 status-blob mechanism (that never carries EQ bands at all). Returns
    the 5 raw band bytes, or None if payload doesn't match this shape.
    """
    if (
        len(payload) < 2 + const.EQ_BAND_COUNT
        or payload[0] != const.STATUS_SUBCODE_EQ_BANDS
        or payload[1] != const.EQ_BAND_COUNT
    ):
        return None
    return payload[2 : 2 + const.EQ_BAND_COUNT]


def parse_echo(payload: bytes) -> tuple[int, bytes] | None:
    """Parse a single-opcode echo indication: [opcode: u16 LE][value].

    Every "set" write triggers an indication using opcode-1 carrying the applied value. Returns
    None for bulk status blobs (handled by parse_status_blob instead).
    """
    if len(payload) < 2 or payload[0] == 0x86:
        return None
    opcode = int.from_bytes(payload[0:2], "little")
    return opcode, payload[2:]


def volume_byte_to_db(value: int) -> float:
    return float(value - const.VOLUME_DB_OFFSET)


def db_to_volume_byte(db: float) -> int:
    db = max(const.VOLUME_MIN_DB, min(const.VOLUME_MAX_DB, db))
    return round(db) + const.VOLUME_DB_OFFSET


def tone_byte_to_db(value: int) -> float:
    """Shared by Bass / Mid-Hi / Balance."""
    return (value - const.TONE_CENTER) * const.TONE_STEP_DB


def db_to_tone_byte(db: float) -> int:
    db = max(const.TONE_MIN_DB, min(const.TONE_MAX_DB, db))
    return round(db / const.TONE_STEP_DB) + const.TONE_CENTER


def eq_band_byte_to_db(value: int) -> float:
    return (value - const.EQ_BAND_FLAT) * (10.0 / (const.EQ_BAND_MAX - const.EQ_BAND_MIN))


def db_to_eq_band_byte(db: float) -> int:
    db = max(const.TONE_MIN_DB, min(const.TONE_MAX_DB, db))
    step = 10.0 / (const.EQ_BAND_MAX - const.EQ_BAND_MIN)
    value = round(db / step) + const.EQ_BAND_FLAT
    return max(const.EQ_BAND_MIN, min(const.EQ_BAND_MAX, value))


def encode_eq_band(band_index: int, value: int) -> bytes:
    if not 0 <= band_index < const.EQ_BAND_COUNT:
        raise ValueError(f"band_index must be 0-{const.EQ_BAND_COUNT - 1}")
    return bytes([band_index, value])


def clamp_hz(hz: int, min_hz: int, max_hz: int) -> int:
    return max(min_hz, min(max_hz, hz))
