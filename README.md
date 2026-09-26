# Nubert X-2 for Home Assistant

A custom Home Assistant integration for the **Nubert nuControl X-2** streaming preamplifier/speaker, controlled over its BLE GATT interface. There is no vendor API or public documentation for this protocol. It was reverse-engineered from scratch by capturing and decoding the official Nubert app's own Bluetooth traffic.

Tested against a **Nubert nuPro X-4000** stereo pair. The speakers advertise over BLE as `nubert X-2 <serial>` regardless of the retail model name.

> **AI-assisted disclosure.** This integration, including the protocol reverse-engineering, the integration code, and this documentation, was built in collaboration with Claude Sonnet 5 (Anthropic), directed and reviewed by a human throughout. Every opcode in [`docs/protocol.md`](docs/protocol.md) was validated against the real speaker before being marked confirmed. Open an issue if something doesn't match your unit.

## Features

- **`media_player`**: power on/off, volume set/step, mute, source select, sound mode select for presets.
- **`number`**: Bass, Mid-High, Balance, Highpass, Subwoofer crossover, and all 5 EQ bands.
- **`switch`**: Loudness, Analog gain.
- **`select`**: Preset, and Save to Preset.
- **`button`**: activate Bluetooth pairing mode.
- Live state sync via BLE indications. Switching presets re-polls the full state afterward, since the device never announces what changed.

## Requirements

Home Assistant on **Linux with BlueZ** and a real local Bluetooth adapter, or a remote adapter proxied to a BlueZ host.

**Will not work on macOS.** The Nubert X-2 exposes no CCCD descriptor on its control characteristic. CoreBluetooth refuses to subscribe without one, BlueZ tolerates it fine. See [`docs/protocol.md`](docs/protocol.md) for the full write-up.

## Installation

**HACS**: add this repository as a custom repository, then install "Nubert X-2".

**Manual**: copy `custom_components/nubert_ble/` into your `config/custom_components/` and restart Home Assistant. The integration auto-discovers the speaker via Bluetooth, or can be added manually with its MAC address.

## Known limitations

- **Only one BLE connection is allowed at a time.** If the official app connects, Home Assistant loses the connection and vice versa. Entities go `unavailable` and recover automatically once the connection is free again.
- **Power is write-only.** No readback opcode exists for it, so the UI is optimistic and defaults to "on" once connected.
- **The currently active preset number** is write-optimistic too. No opcode reports which of the 3 slots is active. Everything the preset actually changes (bass, EQ, highpass, etc.) reads back live, just not the slot index itself.
- Owners of a stereo pair get two separate devices/config entries. No stereo grouping.

## Roadmap

- **Nubert nuSub XW-900** support. Same app ecosystem, protocol not yet reverse-engineered against this model. Contributions/capture files welcome.

## Protocol documentation

[`docs/protocol.md`](docs/protocol.md): the full reverse-engineered reference. Opcodes, formulas, status-blob subcodes, and BLE transport quirks.

## Development

```
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests/
```

`tests/test_protocol.py` covers the pure encode/decode logic. No hardware or Home Assistant runtime required.

## License

MIT
