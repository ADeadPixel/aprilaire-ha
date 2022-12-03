"""The Aprilaire climate component"""

from __future__ import annotations

import logging

from homeassistant.components.climate import (
    HVAC_MODES,
    ClimateEntityFeature,
    HVACMode,
    FAN_AUTO,
    FAN_ON,
)

from homeassistant.const import (
    TEMP_CELSIUS,
    PRECISION_WHOLE,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.climate import ClimateEntity

from . import AprilaireCoordinator
from .const import FunctionalDomain, DOMAIN, LOG_NAME
from .entity import BaseAprilaireEntity
from .utils import encode_temperature

FAN_CIRCULATE = "Circulate"

HVAC_MODE_MAP = {
    1: HVACMode.OFF,
    2: HVACMode.HEAT,
    3: HVACMode.COOL,
    4: HVACMode.HEAT,
    5: HVACMode.AUTO,
}

FAN_MODE_MAP = {
    1: FAN_ON,
    2: FAN_AUTO,
    3: FAN_CIRCULATE,
}

_LOGGER = logging.getLogger(LOG_NAME)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add climates for passed config_entry in HA."""

    coordinator: AprilaireCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    if not coordinator.data or "mac_address" not in coordinator.data:
        data = await coordinator.client.wait_for_response(FunctionalDomain.IDENTIFICATION, 2, 30)

        if not data or "mac_address" not in data:
            _LOGGER.error("Missing MAC address, cannot create unique ID")
            return

    async_add_entities([AprilaireClimate(coordinator)])


class AprilaireClimate(BaseAprilaireEntity, ClimateEntity):
    """Climate entity for Aprilaire"""

    @property
    def name(self):
        """Get name of entity"""
        
        return f"Aprilaire Thermostat Climate"

    @property
    def temperature_unit(self):
        """Get temperature units"""
        return TEMP_CELSIUS

    @property
    def precision(self):
        """Get precision"""
        return PRECISION_WHOLE

    @property
    def supported_features(self):
        """Get supported features"""
        features = 0

        if "mode" not in self._data:
            features = features | ClimateEntityFeature.TARGET_TEMPERATURE
        else:
            mode = self._data["mode"]

            if mode == 5:
                features = features | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            else:
                features = features | ClimateEntityFeature.TARGET_TEMPERATURE

        features = features | ClimateEntityFeature.FAN_MODE

        return features

    @property
    def current_temperature(self):
        """Get current temperature"""
        return (
            self._data["indoor_temperature_controlling_sensor_value"]
            if "indoor_temperature_controlling_sensor_value" in self._data
            else None
        )

    @property
    def target_temperature_low(self):
        """Get heat setpoint"""
        return self._data["heat_setpoint"] if "heat_setpoint" in self._data else None

    @property
    def target_temperature_high(self):
        """Get cool setpoint"""
        return self._data["cool_setpoint"] if "cool_setpoint" in self._data else None

    @property
    def current_humidity(self):
        """Get current humidity"""
        return (
            self._data["indoor_humidity_controlling_sensor_value"]
            if "indoor_humidity_controlling_sensor_value" in self._data
            else None
        )

    @property
    def hvac_mode(self) -> HVAC_MODES:
        """Get HVAC mode"""
        if "mode" not in self._data:
            return None

        mode = self._data["mode"]

        if mode not in HVAC_MODE_MAP:
            return None

        return HVAC_MODE_MAP[mode]

    @property
    def hvac_modes(self) -> list[HVAC_MODES]:
        """Get supported HVAC modes"""
        return [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]

    @property
    def fan_mode(self):
        """Get fan mode"""
        if "fan_mode" not in self._data:
            return None

        fan_mode = self._data["fan_mode"]

        if fan_mode not in FAN_MODE_MAP:
            return None

        return FAN_MODE_MAP[fan_mode]

    @property
    def fan_modes(self):
        """Get supported fan modes"""
        return [FAN_AUTO, FAN_ON, FAN_CIRCULATE]

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode"""
        try:
            mode_value_index = list(HVAC_MODE_MAP.values()).index(hvac_mode)
        except ValueError:
            _LOGGER.error("Invalid HVAC mode %s", hvac_mode)
            return

        mode_value = list(HVAC_MODE_MAP.keys())[mode_value_index]

        await self._coordinator.client.update_mode(mode_value)

        await self._coordinator.client.read_control()

    async def async_set_temperature(self, **kwargs) -> None:
        """Set the temperature setpoints"""
        cool_setpoint = 0
        heat_setpoint = 0

        if "target_temp_low" in kwargs:
            heat_setpoint = encode_temperature(kwargs.get("target_temp_low"))
        if "target_temp_high" in kwargs:
            cool_setpoint = encode_temperature(kwargs.get("target_temp_high"))

        await self._coordinator.client.update_setpoint(cool_setpoint, heat_setpoint)

        await self._coordinator.client.read_control()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""

        try:
            fan_mode_value_index = list(FAN_MODE_MAP.values()).index(fan_mode)
        except ValueError:
            _LOGGER.error("Invalid fan mode %s", fan_mode)
            return

        fan_mode_value = list(FAN_MODE_MAP.keys())[fan_mode_value_index]

        await self._coordinator.client.update_fan_mode(fan_mode_value)

        await self._coordinator.client.read_control()