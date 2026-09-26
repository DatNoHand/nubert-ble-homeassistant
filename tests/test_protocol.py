"""Unit tests for protocol.py -- pure logic, no hardware/HA needed.

Loads const.py/protocol.py directly by file path rather than via `from nubert_ble import ...`,
since importing the nubert_ble package normally runs __init__.py, which imports real
homeassistant modules not needed (or installed) for testing pure protocol logic.
"""
import importlib.util
import sys
import types
from pathlib import Path

_PKG_DIR = Path(__file__).parent.parent / "custom_components" / "nubert_ble"

# Register a stub "nubert_ble" package so protocol.py's `from . import const` resolves, without
# triggering the real package's __init__.py (which imports homeassistant).
_pkg = types.ModuleType("nubert_ble")
_pkg.__path__ = [str(_PKG_DIR)]
sys.modules["nubert_ble"] = _pkg


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"nubert_ble.{name}", _PKG_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"nubert_ble.{name}"] = module
    spec.loader.exec_module(module)
    return module


const = _load("const")
protocol = _load("protocol")


def test_encode_write():
    assert protocol.encode_write(const.OPCODE_VOLUME, bytes([0x2E])) == bytes.fromhex("0b012e")
    assert protocol.encode_write(const.OPCODE_MUTE, bytes([0x01])) == bytes.fromhex("4b0101")


def test_parse_status_blob():
    payload = bytes.fromhex("860f1e01000a012e20011422011a340102")
    parsed = protocol.parse_status_blob(payload)
    assert parsed == {
        0x1E: bytes([0x00]),
        0x0A: bytes([0x2E]),
        0x20: bytes([0x14]),
        0x22: bytes([0x1A]),
        0x34: bytes([0x02]),
    }


def test_parse_status_blob_rejects_non_bulk():
    assert protocol.parse_status_blob(bytes.fromhex("0a012e")) is None


def test_parse_echo():
    opcode, value = protocol.parse_echo(bytes.fromhex("0a012e"))
    assert opcode == 0x010A
    assert value == bytes([0x2E])


def test_parse_echo_rejects_bulk_blob():
    assert protocol.parse_echo(bytes.fromhex("860f1e0100")) is None


def test_parse_eq_bands_push():
    payload = bytes.fromhex("1005" + "0406060606")
    assert protocol.parse_eq_bands_push(payload) == bytes([0x04, 0x06, 0x06, 0x06, 0x06])


def test_parse_eq_bands_push_rejects_wrong_length():
    assert protocol.parse_eq_bands_push(bytes.fromhex("1004" + "06060606")) is None


def test_parse_eq_bands_push_rejects_other_subcode():
    assert protocol.parse_eq_bands_push(bytes.fromhex("0a012e")) is None


def test_volume_roundtrip():
    assert protocol.volume_byte_to_db(46) == -54.0
    assert protocol.db_to_volume_byte(-54.0) == 46


def test_tone_roundtrip():
    assert protocol.tone_byte_to_db(20) == 0.0
    assert protocol.tone_byte_to_db(21) == 0.5
    assert protocol.tone_byte_to_db(10) == -5.0
    assert protocol.tone_byte_to_db(30) == 5.0
    assert protocol.db_to_tone_byte(0.5) == 21
    assert protocol.db_to_tone_byte(-5.0) == 10


def test_tone_clamps_out_of_range():
    assert protocol.db_to_tone_byte(999) == 30
    assert protocol.db_to_tone_byte(-999) == 10


def test_eq_band_roundtrip():
    assert protocol.eq_band_byte_to_db(6) == 0.0
    assert protocol.eq_band_byte_to_db(0) == -5.0
    assert protocol.eq_band_byte_to_db(12) == 5.0
    assert protocol.db_to_eq_band_byte(0.0) == 6
    assert protocol.db_to_eq_band_byte(-5.0) == 0
    assert protocol.db_to_eq_band_byte(5.0) == 12


def test_encode_eq_band():
    assert protocol.encode_eq_band(0, 6) == bytes([0x00, 0x06])
    assert protocol.encode_eq_band(4, 11) == bytes([0x04, 0x0B])


def test_encode_eq_band_rejects_bad_index():
    import pytest

    with pytest.raises(ValueError):
        protocol.encode_eq_band(5, 6)


def test_clamp_hz():
    assert protocol.clamp_hz(200, const.HIGHPASS_MIN_HZ, const.HIGHPASS_MAX_HZ) == 140
    assert protocol.clamp_hz(0, const.HIGHPASS_MIN_HZ, const.HIGHPASS_MAX_HZ) == 10
    assert protocol.clamp_hz(80, const.HIGHPASS_MIN_HZ, const.HIGHPASS_MAX_HZ) == 80
