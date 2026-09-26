"""Number entities for Nubert X-2 tone/DSP controls."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import protocol
from .const import (
    DOMAIN,
    EQ_BAND_COUNT,
    EQ_BAND_MAX,
    EQ_BAND_MIN,
    HIGHPASS_MAX_HZ,
    HIGHPASS_MIN_HZ,
    OPCODE_BALANCE,
    OPCODE_BASS,
    OPCODE_EQ_BAND,
    OPCODE_HIGHPASS,
    OPCODE_MID_HIGH,
    OPCODE_SUB_CROSSOVER,
    SUB_CROSSOVER_MAX_HZ,
    SUB_CROSSOVER_MIN_HZ,
    TONE_MAX_DB,
    TONE_MIN_DB,
    TONE_STEP_DB,
)
from .device import NubertDevice


@dataclass(frozen=True, kw_only=True)
class NubertNumberDescription(NumberEntityDescription):
    opcode: int = 0
    get_value: Callable[[NubertDevice], float | int | None] = lambda d: None
    to_byte: Callable[[float], int] = int
    band_index: int | None = None


def _eq_band_get(index: int) -> Callable[[NubertDevice], float]:
    def _get(d: NubertDevice) -> float:
        return protocol.eq_band_byte_to_db(d.state.eq_bands[index])

    return _get


EQ_BAND_STEP = 10.0 / (EQ_BAND_MAX - EQ_BAND_MIN)

DESCRIPTIONS: tuple[NubertNumberDescription, ...] = (
    NubertNumberDescription(
        key="bass",
        translation_key="bass",
        native_min_value=TONE_MIN_DB,
        native_max_value=TONE_MAX_DB,
        native_step=TONE_STEP_DB,
        native_unit_of_measurement="dB",
        mode=NumberMode.SLIDER,
        opcode=OPCODE_BASS,
        get_value=lambda d: d.state.bass_db,
        to_byte=protocol.db_to_tone_byte,
    ),
    NubertNumberDescription(
        key="mid_high",
        translation_key="mid_high",
        native_min_value=TONE_MIN_DB,
        native_max_value=TONE_MAX_DB,
        native_step=TONE_STEP_DB,
        native_unit_of_measurement="dB",
        mode=NumberMode.SLIDER,
        opcode=OPCODE_MID_HIGH,
        get_value=lambda d: d.state.mid_high_db,
        to_byte=protocol.db_to_tone_byte,
    ),
    NubertNumberDescription(
        key="balance",
        translation_key="balance",
        native_min_value=TONE_MIN_DB,
        native_max_value=TONE_MAX_DB,
        native_step=TONE_STEP_DB,
        native_unit_of_measurement="dB",
        mode=NumberMode.SLIDER,
        opcode=OPCODE_BALANCE,
        get_value=lambda d: d.state.balance_db,
        to_byte=protocol.db_to_tone_byte,
    ),
    NubertNumberDescription(
        key="highpass",
        translation_key="highpass",
        native_min_value=HIGHPASS_MIN_HZ,
        native_max_value=HIGHPASS_MAX_HZ,
        native_step=1,
        native_unit_of_measurement="Hz",
        mode=NumberMode.SLIDER,
        opcode=OPCODE_HIGHPASS,
        get_value=lambda d: d.state.highpass_hz,
        to_byte=lambda hz: protocol.clamp_hz(round(hz), HIGHPASS_MIN_HZ, HIGHPASS_MAX_HZ),
    ),
    NubertNumberDescription(
        key="sub_crossover",
        translation_key="sub_crossover",
        native_min_value=SUB_CROSSOVER_MIN_HZ,
        native_max_value=SUB_CROSSOVER_MAX_HZ,
        native_step=1,
        native_unit_of_measurement="Hz",
        mode=NumberMode.SLIDER,
        opcode=OPCODE_SUB_CROSSOVER,
        get_value=lambda d: d.state.sub_crossover_hz,
        to_byte=lambda hz: protocol.clamp_hz(
            round(hz), SUB_CROSSOVER_MIN_HZ, SUB_CROSSOVER_MAX_HZ
        ),
    ),
    *(
        NubertNumberDescription(
            key=f"eq_band_{i}",
            translation_key="eq_band",
            translation_placeholders={"band": str(i + 1)},
            native_min_value=protocol.eq_band_byte_to_db(EQ_BAND_MIN),
            native_max_value=protocol.eq_band_byte_to_db(EQ_BAND_MAX),
            native_step=EQ_BAND_STEP,
            native_unit_of_measurement="dB",
            mode=NumberMode.SLIDER,
            opcode=OPCODE_EQ_BAND,
            get_value=_eq_band_get(i),
            to_byte=protocol.db_to_eq_band_byte,
            band_index=i,
        )
        for i in range(EQ_BAND_COUNT)
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: NubertDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(NubertNumber(device, entry, desc) for desc in DESCRIPTIONS)


class NubertNumber(NumberEntity):
    _attr_has_entity_name = True
    entity_description: NubertNumberDescription

    def __init__(
        self, device: NubertDevice, entry: ConfigEntry, description: NubertNumberDescription
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
    def native_value(self) -> float | None:
        return self.entity_description.get_value(self._device)

    async def async_set_native_value(self, value: float) -> None:
        desc = self.entity_description
        byte_value = desc.to_byte(value)
        if desc.band_index is not None:
            payload = protocol.encode_eq_band(desc.band_index, byte_value)
        else:
            payload = bytes([byte_value])
        await self._device.async_write(desc.opcode, payload)
