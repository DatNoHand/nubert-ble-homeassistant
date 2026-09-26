# Nubert X-2 BLE Control Protocol

Reverse-engineered BLE GATT control protocol for the Nubert nuPro X-4000 active speaker. The
device advertises as `nubert X-2 <serial>` (`nubert X-2` is the internal platform name used by the
app and firmware, not a retail model designation). No vendor documentation or public API exists
for this protocol.

## Transport

- Single GATT service, single characteristic, value handle `0x000c`.
- Service UUID: `8e2ceaaa-0e27-11e7-93ae-92361f002671`
- Characteristic UUID: `8e2cece4-0e27-11e7-93ae-92361f002671`
- Client to speaker: ATT Write Request (`0x12`, requires `0x13` Write Response) to handle `0x000c`.
  Write Command (no response) is not accepted.
- Speaker to client: ATT Handle Value Indication (`0x1d`, requires `0x1e` Confirmation from the
  client). The characteristic's declared GATT property is `notify`, but the device always uses
  indications rather than notifications in practice.
- The characteristic exposes zero GATT descriptors; no CCCD is present. This is a device-side
  property, not a client artifact.
- CCCD absence makes CoreBluetooth (macOS) refuse to enable notify/indicate on this characteristic
  (`start_notify()` fails with `CBATTErrorDomain code=10`). BlueZ (Linux) enables indications on
  this characteristic without a CCCD. Bluetooth pairing does not change this behavior on either
  stack. Any client needing live state must run on BlueZ.
- Every "set" write produces an indication carrying the applied value, keyed by `opcode - 1` (see
  Packet format). This gives per-command confirmation without polling.

## Packet format

```
[opcode: uint16 LE][payload: N bytes]
```

- Set opcodes have an odd low byte.
- The corresponding get/echo opcode is `set_opcode - 1` (even low byte); its payload is the
  new/current value.
- A separate opcode family (`0x86` prefix) requests a bulk status blob, returned as repeated
  `[subcode: u8][len: u8][value: len bytes]` tuples in a single indication.

## Opcode map

| Opcode (LE) | Function | Payload |
|---|---|---|
| `0x010B` | Volume | 1 byte. `dB = value - 100` |
| `0x010F` | Input select | 1 byte, 0-indexed: `0` AUX, `1` Bluetooth, `2` XLR, `3` AES, `4` Coax 1, `5` Coax 2, `6` Optical 1, `7` Optical 2, `8` USB, `9` Port |
| `0x011F` | Power on/off | 1 byte, boolean |
| `0x0121` | Bass | 1 byte. `dB = (value - 20) * 0.5`, range 10-30 (-5..+5 dB) |
| `0x0123` | Mid-High | 1 byte. `dB = (value - 20) * 0.5`, range 10-30 (-5..+5 dB) |
| `0x0125` | Balance | 1 byte. `dB = (value - 20) * 0.5`, center 20 |
| `0x0127` | Highpass frequency | 1 byte, Hz, range 10-140 |
| `0x0129` | Sub crossover frequency | 1 byte, Hz, range 20-140 |
| `0x012F` | Bluetooth pairing mode | 1 byte, `0x00` (one-shot trigger) |
| `0x0133` | Analog gain | 1 byte, boolean (`0x01` = +6 dB, `0x00` = 0 dB) |
| `0x0140` | Query 5-band EQ | 1 byte, `0x10` (trigger; see EQ readback section) |
| `0x0147` | Save preset | 1 byte, target preset slot index (not a fixed trigger byte) |
| `0x0149` | Preset select | 1 byte, preset index |
| `0x014B` | Mute | 1 byte, boolean |
| `0x0211` | 5-band EQ | 2 bytes: `[band_index 0-4][value]`. `dB = (value - 6) * (5/6)`, range 0-12 (-5..+5 dB) |
| `0x022B` | Loudness | 1 byte, boolean |

## Status blob (bulk readback)

Three status-query byte strings are used, corresponding to distinct parameter groups:

```
860d1e0a2022340e44604a6258c6e8
86042628321a
86072220242a749395
```

Each returns repeated `[subcode: u8][len: u8][value]` tuples in a single indication. Querying all
three and merging by subcode gives the full readable state.

| Subcode | Mirrors opcode | Function |
|---|---|---|
| `0x0a` | `0x010B` | Volume |
| `0x20` | `0x0121` | Bass |
| `0x22` | `0x0123` | Mid-High |
| `0x24` | `0x0125` | Balance |
| `0x26` | `0x0127` | Highpass |
| `0x28` | `0x0129` | Sub crossover |
| `0x2a` | `0x022B` | Loudness |
| `0x32` | `0x0133` | Analog gain |
| `0x4a` | `0x014B` | Mute |

Parameters with no bulk-status subcode (Input, Power, Preset) are read back only via the
per-command echo described in Packet format.

## 5-band EQ readback

The 5-band EQ (`0x0211`) is not carried by the bulk status blob under any subcode. It uses a
separate mechanism: writing `0x0140` with payload `0x10`, or writing any EQ band, produces an
indication shaped:

```
[subcode: 0x10][len: 0x05][band0][band1][band2][band3][band4]
```

containing all 5 live band values. `0x0140` is a pure query trigger; it has no other observed
effect on device state.

## Unresolved fields

| Field | Observed | Notes |
|---|---|---|
| Opcode `0x0048` | no payload | Even low byte suggests a get-style query; paired set opcode would be `0x0049` (Preset). Possibly re-queries the active preset. |
| Status subcode `0x00` | empty value | Present in every status blob response; likely a separator/marker rather than a parameter. |
| Status subcodes `0x1a`, `0x1e` | constant `0x00` | Did not change under any mapped parameter. |
| Status subcodes `0x34`, `0x44` | constant `0x02` | Ruled out as Input (stayed constant across 3 input switches). Untested against Preset. |

## Operational notes

- Only one BLE connection to the device is accepted at a time. A second client's connection
  attempt evicts the first; there is no coexistence.
- Two physical units may be present in range as a stereo pair, each independently addressable and
  independently controllable. BLE scans filtered by device name can match either unit; pin to a
  specific address once identified.
- The device's BLE address differs by host stack: CoreBluetooth (macOS) exposes a host-generated
  UUID rather than the underlying MAC; BlueZ (Linux) exposes the real MAC. These are not
  interchangeable between hosts.

## Reference implementation

- `custom_components/nubert_ble/` (in `nubert-ble-homeassistant`) — production integration
  implementing this protocol.
- `scripts/nubert_parse_btsnoop.py` — parses a PacketLogger BTSnoop capture into an ATT command
  timeline.
- `scripts/nubert_map_status.py` — BlueZ-only status-blob delta probing tool, used to derive the
  subcode map above.
- `scripts/nubert_replay.py` — single-command write replay (write-only; no live readback on
  CoreBluetooth, see Transport).
