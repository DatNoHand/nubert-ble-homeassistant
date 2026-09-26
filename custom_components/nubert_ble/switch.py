"""Switch entities for Nubert X-2 boolean settings (Loudness, Analog Gain)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, OPCODE_ANALOG_GAIN, OPCODE_LOUDNESS
from .device import NubertDevice


@dataclass(frozen=True, kw_only=True)
class NubertSwitchDescription(SwitchEntityDescription):
    opcode: int = 0
    get_value: Callable[[NubertDevice], bool | None] = lambda d: None


DESCRIPTIONS: tuple[NubertSwitchDescription, ...] = (
    NubertSwitchDescription(
        key="loudness",
        translation_key="loudness",
        opcode=OPCODE_LOUDNESS,
        get_value=lambda d: d.state.loudness,
    ),
    NubertSwitchDescription(
        key="analog_gain",
        translation_key="analog_gain",
        opcode=OPCODE_ANALOG_GAIN,
        get_value=lambda d: d.state.analog_gain,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: NubertDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(NubertSwitch(device, entry, desc) for desc in DESCRIPTIONS)


class NubertSwitch(SwitchEntity):
    _attr_has_entity_name = True
    entity_description: NubertSwitchDescription

    def __init__(
        self, device: NubertDevice, entry: ConfigEntry, description: NubertSwitchDescription
    ) -> None:
        self.entity_description = description
        self._device = device
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_{description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, address)})

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.add_listener(self._handle_update))

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._device.state.available

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.get_value(self._device)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.async_write(self.entity_description.opcode, bytes([0x01]))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.async_write(self.entity_description.opcode, bytes([0x00]))
