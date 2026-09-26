"""Media player entity for a Nubert X-2 speaker (power, volume, mute, source)."""
from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import protocol
from .const import (
    DOMAIN,
    INPUT_NAMES,
    OPCODE_INPUT,
    OPCODE_MUTE,
    OPCODE_POWER,
    OPCODE_PRESET,
    OPCODE_VOLUME,
    PRESET_COUNT,
)
from .device import NubertDevice

SOUND_MODE_LIST = [str(i) for i in range(1, PRESET_COUNT + 1)]

SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
)

VOLUME_STEP_DB = 1.0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: NubertDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NubertMediaPlayer(device, entry)])


class NubertMediaPlayer(MediaPlayerEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = SUPPORTED_FEATURES
    _attr_source_list = INPUT_NAMES
    _attr_sound_mode_list = SOUND_MODE_LIST

    def __init__(self, device: NubertDevice, entry: ConfigEntry) -> None:
        self._device = device
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_media_player"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=entry.title,
            manufacturer="Nubert",
            model="X-2",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.add_listener(self._handle_update))

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._device.state.available

    @property
    def state(self) -> MediaPlayerState | None:
        # Power has no reliable live readback (see docs/concepts/nubert-ble-protocol.md) --
        # write-optimistic only, defaulting to ON once connected (see NubertState.power_on).
        if self._device.state.power_on is False:
            return MediaPlayerState.OFF
        if self._device.state.power_on is True:
            return MediaPlayerState.ON
        return None

    @property
    def volume_level(self) -> float | None:
        db = self._device.state.volume_db
        if db is None:
            return None
        return max(0.0, min(1.0, (db + 100) / 100))

    @property
    def is_volume_muted(self) -> bool | None:
        return self._device.state.muted

    @property
    def source(self) -> str | None:
        idx = self._device.state.input_index
        if idx is None or not 0 <= idx < len(INPUT_NAMES):
            return None
        return INPUT_NAMES[idx]

    @property
    def sound_mode(self) -> str | None:
        # Exposes Preset via the standard media_player "sound mode" concept, matching how other
        # receiver integrations surface EQ/preset modes. No confirmed live readback (see
        # docs/concepts/nubert-ble-protocol.md) -- write-optimistic, shared with select.preset.
        preset = self._device.state.preset
        return str(preset) if preset is not None else None

    async def async_turn_on(self) -> None:
        await self._device.async_write(OPCODE_POWER, bytes([0x01]))
        self._device.state.power_on = True
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        await self._device.async_write(OPCODE_POWER, bytes([0x00]))
        self._device.state.power_on = False
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        db = volume * 100 - 100
        await self._device.async_write(OPCODE_VOLUME, bytes([protocol.db_to_volume_byte(db)]))

    async def async_mute_volume(self, mute: bool) -> None:
        await self._device.async_write(OPCODE_MUTE, bytes([1 if mute else 0]))

    async def async_select_source(self, source: str) -> None:
        if source not in INPUT_NAMES:
            return
        await self._device.async_write(OPCODE_INPUT, bytes([INPUT_NAMES.index(source)]))

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        preset_index = int(sound_mode)
        await self._device.async_write(OPCODE_PRESET, bytes([preset_index]))
        self._device.state.preset = preset_index
        self.async_write_ha_state()
        # Preset switches change several DSP parameters together but the device never announces
        # what changed -- re-poll so bass/mid-high/highpass/EQ etc. catch up.
        await self._device.async_refresh_status()

    async def async_volume_up(self) -> None:
        current_db = self._device.state.volume_db
        if current_db is None:
            return
        await self.async_set_volume_level(
            protocol.db_to_volume_byte(current_db + VOLUME_STEP_DB) / 100
        )

    async def async_volume_down(self) -> None:
        current_db = self._device.state.volume_db
        if current_db is None:
            return
        await self.async_set_volume_level(
            protocol.db_to_volume_byte(current_db - VOLUME_STEP_DB) / 100
        )
