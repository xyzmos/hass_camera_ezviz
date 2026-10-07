"""Camera platform for the EZVIZ CN integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
import voluptuous as vol

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EzvizConfigEntry
from .const import (
    API_TIMEOUT,
    CONF_CAMERA_INTERVAL,
    DEFAULT_CAMERA_INTERVAL,
    DOMAIN,
)
from .coordinator import EzvizApiError, EzvizDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_CAPTURE = "capture"
SERVICE_HUMANDETECT = "humandetect"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzvizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EZVIZ camera entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    snapshot_seconds = entry.options.get(
        CONF_CAMERA_INTERVAL, DEFAULT_CAMERA_INTERVAL
    )

    cameras: list[EzvizCamera] = []
    channels = coordinator.data.get("cameralistinfo") or []
    for device in coordinator.data.get("devicelistinfo") or []:
        serial = device["deviceSerial"]
        model = (coordinator.data.get(serial) or {}).get("model", "")
        # 猫眼/门铃类（CS-DP*）不能实时抓图，改取最近一条告警图片
        cameratype = "motion" if model.startswith("CS-DP") else "capture"
        for channel in channels:
            if (
                channel["deviceSerial"] == serial
                and channel.get("permission") == -1
            ):
                cameras.append(
                    EzvizCamera(
                        coordinator,
                        serial,
                        channel["channelNo"],
                        cameratype,
                        snapshot_seconds,
                    )
                )
    async_add_entities(cameras)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_CAPTURE,
        None,
        "async_service_capture",
    )
    platform.async_register_entity_service(
        SERVICE_HUMANDETECT,
        {
            vol.Required("picurl"): cv.string,
            vol.Optional("operation", default="number"): cv.string,
        },
        "async_service_humandetect",
        supports_response=SupportsResponse.ONLY,
    )


class EzvizCamera(CoordinatorEntity[EzvizDataUpdateCoordinator], Camera):
    """An EZVIZ camera entity backed by periodic cloud snapshots."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EzvizDataUpdateCoordinator,
        serial: str,
        channel: int,
        cameratype: str,
        snapshot_seconds: int,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._serial = serial
        self._channel = channel
        self._cameratype = cameratype
        self._snapshot_interval = timedelta(seconds=snapshot_seconds)
        self._next_snapshot_at: datetime | None = None
        self._last_image: bytes | None = None
        self._last_pic_url: str | None = None

        channel_prefix = f"{channel} " if channel > 1 else ""
        self._attr_translation_key = cameratype
        self._attr_translation_placeholders = {"channel": channel_prefix}
        self._attr_unique_id = f"ezviz_camera_{serial}_{channel}"

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
        return {"pic_url": self._last_pic_url, "channel_no": self._channel}

    def _fetch_image_bytes(self, url: str) -> bytes | None:
        try:
            resp = requests.get(url, timeout=API_TIMEOUT)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as err:
            _LOGGER.error("Failed to download snapshot %s: %s", url, err)
            return None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a throttled still image fetched from the EZVIZ cloud."""
        now = datetime.now(timezone.utc)
        if self._next_snapshot_at is not None and now <= self._next_snapshot_at:
            return self._last_image

        try:
            if self._cameratype == "motion":
                url = await self.coordinator.async_latest_alarm_pic(self._serial)
            else:
                url = await self.coordinator.async_capture(
                    self._serial, self._channel
                )
        except EzvizApiError as err:
            _LOGGER.error("Snapshot request failed for %s: %s", self._serial, err)
            return self._last_image

        if not url:
            _LOGGER.debug("No snapshot/alarm image available for %s", self._serial)
            return self._last_image

        image = await self.hass.async_add_executor_job(self._fetch_image_bytes, url)
        if image is not None:
            self._last_image = image
            self._last_pic_url = url
            self._next_snapshot_at = now + self._snapshot_interval
        return self._last_image

    async def async_service_capture(self) -> None:
        """Entity service: force a fresh snapshot."""
        url = await self.coordinator.async_capture(self._serial, self._channel)
        if url:
            image = await self.hass.async_add_executor_job(
                self._fetch_image_bytes, url
            )
            if image is not None:
                self._last_image = image
                self._last_pic_url = url
                self._next_snapshot_at = (
                    datetime.now(timezone.utc) + self._snapshot_interval
                )
                self.async_write_ha_state()

    async def async_service_humandetect(
        self, picurl: str, operation: str = "number"
    ) -> dict[str, Any]:
        """Entity service: run human detection on an image URL, return result."""
        from .const import API_HUMAN_DETECT

        response = await self.coordinator.async_intelligence(
            API_HUMAN_DETECT, picurl, {"operation": operation}
        )
        _LOGGER.debug("humandetect response: %s", response)
        return response
