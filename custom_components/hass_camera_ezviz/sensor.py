"""Sensor platform for the EZVIZ CN integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EzvizConfigEntry
from .const import DOMAIN, SENSOR_TYPES, STATE_LABELS
from .coordinator import EzvizDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzvizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EZVIZ sensor entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    sensors = [
        EzvizSensor(coordinator, device["deviceSerial"], kind)
        for device in coordinator.data.get("devicelistinfo") or []
        for kind in SENSOR_TYPES
    ]
    async_add_entities(sensors)


class EzvizSensor(CoordinatorEntity[EzvizDataUpdateCoordinator], SensorEntity):
    """A per-device status sensor fed by the update coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: EzvizDataUpdateCoordinator, serial: str, kind: str
    ) -> None:
        super().__init__(coordinator)
        self._serial = serial
        self._kind = kind
        api_field, translation_key, icon, labels_key, enabled_default = (
            SENSOR_TYPES[kind]
        )
        self._api_field = api_field
        self._labels = STATE_LABELS.get(labels_key) if labels_key else None
        self._attr_translation_key = translation_key
        self._attr_icon = icon
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_unique_id = f"ezviz_sensor_{kind}_{serial}"

        for device in coordinator.data.get("devicelistinfo") or []:
            if device["deviceSerial"] == serial:
                self._attr_device_info = {
                    "identifiers": {(DOMAIN, serial)},
                    "name": device.get("deviceName"),
                    "manufacturer": "Ezviz",
                    "model": device.get("deviceType"),
                    "sw_version": device.get("deviceVersion"),
                }
                break

    @property
    def native_value(self) -> Any:
        """Return the mapped status label (or raw value) for this sensor."""
        device = self.coordinator.data.get(self._serial) or {}
        value = device.get(self._api_field)
        if value is None:
            return None
        if self._labels is not None and isinstance(value, int):
            if 0 <= value < len(self._labels):
                return self._labels[value]
            return value
        return value
