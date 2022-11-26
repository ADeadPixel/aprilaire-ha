"""The Aprilaire climate component"""

from __future__ import annotations

import logging

from homeassistant.components.climate import (
    HVAC_MODES,
    ClimateEntityFeature,
    HVACMode,
)

from homeassistant.const import (
    TEMP_CELSIUS,
    PRECISION_WHOLE,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.climate import ClimateEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AprilaireCoordinator
from .const import Action, FunctionalDomain, DOMAIN
from .utils import encode_temperature

HVAC_MODE_MAP = {
    1: HVACMode.OFF,
    2: HVACMode.HEAT,
    3: HVACMode.COOL,
    4: HVACMode.HEAT,
    5: HVACMode.AUTO,
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add climates for passed config_entry in HA."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([AprilaireClimate(coordinator)])


class AprilaireClimate(CoordinatorEntity, ClimateEntity):
    """Climate entity for Aprilaire"""

    def __init__(self, coordinator: AprilaireCoordinator) -> None:
        """Initialize the entity"""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._data = {}
        self._available = False

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        (action, functional_domain, attribute) = self._coordinator.data["event"]

        for key in self._coordinator.data:
            self._data[key] = self._coordinator.data[key]

        if (
            (action == Action.READ_RESPONSE or action == Action.COS)
            and functional_domain == FunctionalDomain.CONTROL
            and attribute == 1
        ):
            self._available = True

        self.async_write_ha_state()

    @property
    def should_poll(self):
        """Do not need to poll"""
        return False

    @property
    def available(self):
        """Get entity availability"""
        return self._available

    @property
    def name(self):
        """Get name of entity"""
        return "Aprilaire Thermostat"

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