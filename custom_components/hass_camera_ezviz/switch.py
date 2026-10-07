"""Switch platform for the EZVIZ CN integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EzvizConfigEntry
from .const import CONF_SWITCHS, DOMAIN, OPTIONAL_SWITCH_TYPES, SWITCH_TYPES
from .coordinator import EzvizApiError, EzvizDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzvizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EZVIZ switch entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    enabled = set(entry.options.get(CONF_SWITCHS, OPTIONAL_SWITCH_TYPES[:1]))

    switches: list[EzvizSwitch] = []
    for device in coordinator.data.get("devicelistinfo") or []:
        serial = device["deviceSerial"]
        capacity = coordinator.data.get("capacity", {}).get(serial, {})

        kinds: set[str] = set()
        if "soundswitch" in enabled:
            kinds.add("soundswitch")
        if "on_off" in enabled and capacity.get("support_privacy") == "1":
            kinds.add("on_off")
        # 布撤防开关跟随设备能力，不受选项开关
        if capacity.get("support_defence") == "1":
            kinds.add("defence")

        switches.extend(EzvizSwitch(coordinator, serial, kind) for kind in kinds)

    async_add_entities(switches)


class EzvizSwitch(CoordinatorEntity[EzvizDataUpdateCoordinator], SwitchEntity):
    """A switch backed by the EZVIZ device status cache."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: EzvizDataUpdateCoordinator, serial: str, kind: str
    ) -> None:
        super().__init__(coordinator)
        self._serial = serial
        self._kind = kind
        translation_key, icon = SWITCH_TYPES[kind]
        self._attr_translation_key = translation_key
        self._attr_icon = icon
        self._attr_unique_id = f"ezviz_switch_{kind}_{serial}"

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
    def is_on(self) -> bool | None:
        """Read the latest value straight from the coordinator cache."""
        device = self.coordinator.data.get(self._serial) or {}
        value = device.get(self._kind)
        if value is None:
            return None
        return value == 1

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        device = self.coordinator.data.get(self._serial) or {}
        return {
            "defence": device.get("defence"),
            "alarmSoundMode": device.get("alarmSoundMode"),
            "netAddress": device.get("netAddress"),
            "uptime": device.get("updateTime"),
            "querytime": self.coordinator.data.get("updatetime"),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set_switch(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set_switch(False)

    async def _async_set_switch(self, turn_on: bool) -> None:
        """Call the proper set API, then optimistically update local state."""
        try:
            if self._kind == "on_off":
                # enable=0 表示监控开启（关闭遮蔽）
                await self.coordinator.async_set_privacy(self._serial, turn_on)
            elif self._kind == "soundswitch":
                await self.coordinator.async_set_sound(self._serial, turn_on)
            elif self._kind == "defence":
                await self.coordinator.async_set_defence(self._serial, turn_on)
            else:
                raise HomeAssistantError(f"Unsupported switch kind: {self._kind}")
        except EzvizApiError as err:
            raise HomeAssistantError(
                f"Failed to set {self._kind} on {self._serial}: {err}"
            ) from err

        device = self.coordinator.data.get(self._serial)
        if device is not None:
            if self._kind == "defence":
                device["defence"] = 1 if turn_on else 0
            else:
                device[self._kind] = 1 if turn_on else 0
        self.async_write_ha_state()
