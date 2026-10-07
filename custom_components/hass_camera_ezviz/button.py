"""Button platform for the EZVIZ CN integration (PTZ / capture / AI / live)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EzvizConfigEntry
from .const import (
    API_FACE_DETECT,
    API_HUMAN_BODY,
    API_HUMAN_DETECT,
    API_VEHICLE_PROPS,
    BUTTON_TYPES,
    DOMAIN,
    EVENT_INTELLIGENCE,
    INTELLIGENCE_BUTTONS,
    PTZ_BUTTONS,
    PTZ_DIAGONAL_BUTTONS,
    PTZ_HORIZONTAL_BUTTONS,
    PTZ_VERTICAL_BUTTONS,
    ZOOM_BUTTONS,
)
from .coordinator import EzvizApiError, EzvizDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# ptz start 后保持方向运动的时长，之后发送 stop（点动控制）
PTZ_STEP_SECONDS = 0.5

INTELLIGENCE_APIS = {
    "vehicleprops": API_VEHICLE_PROPS,
    "humandetect": API_HUMAN_DETECT,
    "humanbody": API_HUMAN_BODY,
    "facedetect": API_FACE_DETECT,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzvizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EZVIZ button entities based on device capabilities."""
    coordinator = entry.runtime_data.coordinator
    buttons: list[EzvizButton] = []
    channels = coordinator.data.get("cameralistinfo") or []

    for device in coordinator.data.get("devicelistinfo") or []:
        serial = device["deviceSerial"]
        capacity = coordinator.data.get("capacity", {}).get(serial, {})

        kinds: list[str] = []
        if capacity.get("support_ptz") == "1":
            kinds.extend(PTZ_BUTTONS)
            if capacity.get("ptz_45", "0") == "0":
                kinds = [k for k in kinds if k not in PTZ_DIAGONAL_BUTTONS]
            if capacity.get("ptz_top_bottom", "0") == "0":
                kinds = [k for k in kinds if k not in PTZ_VERTICAL_BUTTONS]
            if capacity.get("ptz_left_right", "0") == "0":
                kinds = [k for k in kinds if k not in PTZ_HORIZONTAL_BUTTONS]
        if capacity.get("ptz_zoom") == "1":
            kinds.extend(ZOOM_BUTTONS)
        if capacity.get("support_capture") == "1":
            kinds.append("capture")
            kinds.extend(INTELLIGENCE_BUTTONS)
        kinds.append("liveget")

        for channel in channels:
            if (
                channel["deviceSerial"] == serial
                and channel.get("permission") == -1
            ):
                buttons.extend(
                    EzvizButton(coordinator, serial, channel["channelNo"], kind)
                    for kind in kinds
                )

    async_add_entities(buttons)


class EzvizButton(CoordinatorEntity[EzvizDataUpdateCoordinator], ButtonEntity):
    """A momentary EZVIZ action button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EzvizDataUpdateCoordinator,
        serial: str,
        channel: int,
        kind: str,
    ) -> None:
        super().__init__(coordinator)
        self._serial = serial
        self._channel = channel
        self._kind = kind
        translation_key, icon, direction, action = BUTTON_TYPES[kind]
        self._direction = direction
        self._action = action
        self._last_result: Any = None
        self._last_pic: str | None = None

        channel_prefix = f"{channel} " if channel > 1 else ""
        self._attr_translation_key = translation_key
        self._attr_translation_placeholders = {"channel": channel_prefix}
        self._attr_icon = icon
        self._attr_unique_id = f"ezviz_button_{kind}_{serial}_{channel}"

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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the last action result (pic url / AI result / live url)."""
        attrs: dict[str, Any] = {
            "querytime": self.coordinator.data.get("updatetime")
        }
        if self._last_pic:
            attrs["capture_pic"] = self._last_pic
        if self._kind == "liveget":
            attrs["liveaddress"] = self._last_result
        elif self._kind in INTELLIGENCE_APIS:
            attrs[self._kind] = self._last_result
        return attrs

    async def async_press(self) -> None:
        """Dispatch the configured action for this button."""
        try:
            if self._action == "move":
                await self.coordinator.async_ptz_start(
                    self._serial, self._channel, self._direction
                )
                await asyncio.sleep(PTZ_STEP_SECONDS)
                await self.coordinator.async_ptz_stop(self._serial, self._channel)
            elif self._action == "stop":
                await self.coordinator.async_ptz_stop(self._serial, self._channel)
            elif self._action == "capture":
                self._last_pic = await self.coordinator.async_capture(
                    self._serial, self._channel
                )
            elif self._action in INTELLIGENCE_APIS:
                self._last_pic = await self.coordinator.async_capture(
                    self._serial, self._channel
                )
                extra = (
                    {"operation": "number"}
                    if self._action == "humandetect"
                    else None
                )
                self._last_result = await self.coordinator.async_intelligence(
                    INTELLIGENCE_APIS[self._action], self._last_pic, extra
                )
                self.hass.bus.async_fire(
                    EVENT_INTELLIGENCE,
                    {
                        "device_serial": self._serial,
                        "channel_no": self._channel,
                        "type": self._action,
                        "capture_pic": self._last_pic,
                        "result": self._last_result,
                    },
                )
            elif self._action == "liveget":
                self._last_result = await self.coordinator.async_live_address(
                    self._serial, self._channel
                )
        except EzvizApiError as err:
            raise HomeAssistantError(
                f"EZVIZ action {self._action} failed on {self._serial}: {err}"
            ) from err
        self.async_write_ha_state()
