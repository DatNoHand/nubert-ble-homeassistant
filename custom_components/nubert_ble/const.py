"""Constants for the Nubert X-2 BLE integration.

All opcode/subcode/formula details below come from reverse-engineering documented in
docs/concepts/nubert-ble-protocol.md in the `infrastructure` repo. That file is the
source of truth if these ever need to be revisited.
"""

DOMAIN = "nubert_ble"

SERVICE_UUID = "8e2ceaaa-0e27-11e7-93ae-92361f002671"
CHAR_UUID = "8e2cece4-0e27-11e7-93ae-92361f002671"

# Bulk "get status" query blobs (marker 0x86 + len + subcode list). The device answers with
# whichever subset of subcodes it recognizes for the given query; querying all three and merging
# gives the fullest picture.
STATUS_QUERIES = (
    bytes.fromhex("860d1e0a2022340e44604a6258c6e8"),
    bytes.fromhex("86042628321a"),
    bytes.fromhex("86072220242a749395"),
)

# opcode (uint16 LE) constants -- "set" commands (odd low byte)
OPCODE_VOLUME = 0x010B
OPCODE_INPUT = 0x010F
OPCODE_POWER = 0x011F
OPCODE_BASS = 0x0121
OPCODE_MID_HIGH = 0x0123
OPCODE_BALANCE = 0x0125
OPCODE_HIGHPASS = 0x0127
OPCODE_SUB_CROSSOVER = 0x0129
OPCODE_BT_PAIRING = 0x012F
OPCODE_ANALOG_GAIN = 0x0133
OPCODE_SAVE_PRESET = 0x0147
OPCODE_PRESET = 0x0149
OPCODE_MUTE = 0x014B
OPCODE_EQ_BAND = 0x0211
OPCODE_LOUDNESS = 0x022B

# Dedicated "give me the live 5-band EQ state" trigger -- NOT part of the bulk 0x86 status-query
# mechanism (confirmed: subcode 0x10 never appears in any bulk-query response, even right after a
# preset switch). Writing this opcode with payload 0x10 makes the device push an unsolicited
# indication shaped [0x10][0x05][band0..band4] -- the official app sends this when its EQ screen
# opens. Discovered 2026-09-26 from nubert_app_4.log record [431]/[436] and confirmed live.
OPCODE_EQ_QUERY = 0x0140
EQ_QUERY_TRIGGER = bytes([0x10])

# Status-blob subcode -> which opcode it mirrors (for live readback via the bulk query)
STATUS_SUBCODE_VOLUME = 0x0A
STATUS_SUBCODE_BASS = 0x20
STATUS_SUBCODE_MID_HIGH = 0x22
STATUS_SUBCODE_BALANCE = 0x24
STATUS_SUBCODE_HIGHPASS = 0x26
STATUS_SUBCODE_SUB_CROSSOVER = 0x28
STATUS_SUBCODE_LOUDNESS = 0x2A
STATUS_SUBCODE_ANALOG_GAIN = 0x32
STATUS_SUBCODE_MUTE = 0x4A

# Not a bulk-query subcode -- the tuple-shaped tag on the dedicated EQ-band push (see
# OPCODE_EQ_QUERY above).
STATUS_SUBCODE_EQ_BANDS = 0x10

# 0-indexed input list (order confirmed by user)
INPUT_NAMES = [
    "AUX",
    "Bluetooth",
    "XLR",
    "AES",
    "Coax 1",
    "Coax 2",
    "Optical 1",
    "Optical 2",
    "USB",
    "Port",
]

# Preset count (only 3 exist)
PRESET_COUNT = 3

# 5-band EQ
EQ_BAND_COUNT = 5
EQ_BAND_MIN = 0
EQ_BAND_MAX = 12
EQ_BAND_FLAT = 6  # value representing 0dB / flat

# Volume: value = dB + 100, single byte so value must stay 0-100 (i.e. dB -100..0)
VOLUME_DB_OFFSET = 100
VOLUME_MIN_DB = -100.0
VOLUME_MAX_DB = 0.0

# Bass / Mid-Hi / Balance: dB = (value - 20) * 0.5, range 10-30 (-5..+5dB)
TONE_CENTER = 20
TONE_STEP_DB = 0.5
TONE_MIN_DB = -5.0
TONE_MAX_DB = 5.0

# Highpass / Sub crossover Hz ranges
HIGHPASS_MIN_HZ = 10
HIGHPASS_MAX_HZ = 140
SUB_CROSSOVER_MIN_HZ = 20
SUB_CROSSOVER_MAX_HZ = 140

# Two known physical units seen during reverse-engineering (a stereo pair); not special-cased in
# code, just noted here for reference. Each becomes its own config entry.
KNOWN_UNIT_NAMES = ("nubert X-2 C7C3", "nubert X-2 C72A")

# Device only supports ONE BLE management connection at a time. If the official phone app is
# connected, this integration cannot connect (and vice versa) -- this is a firmware limitation,
# not something fixable here. See device.py reconnect/backoff handling.
RECONNECT_BACKOFF_SECONDS = (5, 15, 30, 60)
