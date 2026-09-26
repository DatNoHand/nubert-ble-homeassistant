"""Button entities for Nubert X-2 one-shot actions (Bluetooth pairing mode).

Save Preset lives in select.py instead -- see NubertSavePresetSelect -- since it's naturally a
"choose which slot" action rather than a single trigger.
"""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, OPCODE_BT_PAIRING
from .device import NubertDevice


@dataclass(frozen=True, kw_only=True)
class NubertButtonDescription(ButtonEntityDescription):
    opcode: int = 0
    payload: bytes = b"\x01"


DESCRIPTIONS: tuple[NubertButtonDescription, ...] = (
    NubertButtonDescription(
        key="bt_pairing_mode",
        translation_key="bt_pairing_mode",
        opcode=OPCODE_BT_PAIRING,
        payload=bytes([0x00]),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: NubertDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(NubertButton(device, entry, desc) for desc in DESCRIPTIONS)


class NubertButton(ButtonEntity):
    _attr_has_entity_name = True
    entity_description: NubertButtonDescription

    def __init__(
        self, device: NubertDevice, entry: ConfigEntry, description: NubertButtonDescription
    ) -> None:
        self.entity_description = description
        self._device = device
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_{description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, address)})

    @property
    def available(self) -> bool:
        return self._device.state.available

    async def async_press(self) -> None:
        desc = self.entity_description
        await self._device.async_write(desc.opcode, desc.payload)
