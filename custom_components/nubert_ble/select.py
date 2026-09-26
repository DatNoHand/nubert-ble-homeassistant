"""Select entity for Nubert X-2 preset slots."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, OPCODE_PRESET, OPCODE_SAVE_PRESET, PRESET_COUNT
from .device import NubertDevice

PRESET_OPTIONS = [str(i) for i in range(1, PRESET_COUNT + 1)]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: NubertDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NubertPresetSelect(device, entry), NubertSavePresetSelect(device, entry)])


class NubertPresetSelect(SelectEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "preset"
    _attr_options = PRESET_OPTIONS

    def __init__(self, device: NubertDevice, entry: ConfigEntry) -> None:
        self._device = device
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_preset"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, address)})

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.add_listener(self._handle_update))

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._device.state.available

    @property
    def current_option(self) -> str | None:
        # No confirmed live readback for preset (see docs/concepts/nubert-ble-protocol.md) --
        # write-optimistic only.
        preset = self._device.state.preset
        return str(preset) if preset is not None else None

    async def async_select_option(self, option: str) -> None:
        preset_index = int(option)
        await self._device.async_write(OPCODE_PRESET, bytes([preset_index]))
        self._device.state.preset = preset_index
        self.async_write_ha_state()
        # Preset switches change several DSP parameters together but the device never announces
        # what changed -- re-poll so bass/mid-high/highpass/EQ etc. catch up.
        await self._device.async_refresh_status()


class NubertSavePresetSelect(SelectEntity):
    """Fire-and-remember action selector: choosing an option immediately saves the current
    settings into that preset slot. There's no real "current selection" for a save action, so
    this just remembers the last-chosen slot as its displayed state.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "save_preset"
    _attr_options = PRESET_OPTIONS
    _attr_icon = "mdi:content-save"

    def __init__(self, device: NubertDevice, entry: ConfigEntry) -> None:
        self._device = device
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_save_preset_select"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, address)})
        self._current_option: str | None = None

    @property
    def available(self) -> bool:
        return self._device.state.available

    @property
    def current_option(self) -> str | None:
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        preset_index = int(option)
        await self._device.async_write(OPCODE_SAVE_PRESET, bytes([preset_index]))
        self._current_option = option
        self.async_write_ha_state()
