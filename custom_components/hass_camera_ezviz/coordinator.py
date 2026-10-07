"""DataUpdateCoordinator for the EZVIZ Open Platform API."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import timedelta
from typing import Any

import requests

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_ALARM_LIST,
    API_CAMERA_LIST,
    API_CAPTURE,
    API_DEFENCE_SET,
    API_DEVICE_CAPACITY,
    API_DEVICE_INFO,
    API_DEVICE_LIST,
    API_FACE_DETECT,
    API_HUMAN_BODY,
    API_HUMAN_DETECT,
    API_LIVE_ADDRESS,
    API_PTZ_START,
    API_PTZ_STOP,
    API_SCENE_SWITCH_SET,
    API_SCENE_SWITCH_STATUS,
    API_SOUND_SET,
    API_SOUND_STATUS,
    API_TIMEOUT,
    API_TOKEN,
    API_VEHICLE_PROPS,
    AUTH_ERROR_CODES,
    DOMAIN,
    PAGE_SIZE,
    TOKEN_REFRESH_MARGIN_MS,
)

_LOGGER = logging.getLogger(__name__)


class EzvizApiError(Exception):
    """Raised when the EZVIZ open API returns a non-200 code."""

    def __init__(
        self,
        code: str | int | None,
        message: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            f"EZVIZ API error code={code} msg={message} endpoint={endpoint}"
        )
        self.code = str(code)
        self.message = message
        self.endpoint = endpoint


def _is_auth_error(err: Exception) -> bool:
    return isinstance(err, EzvizApiError) and err.code in AUTH_ERROR_CODES


class EzvizDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manage token, device/camera list and per-device status polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        appkey: str,
        appsecret: str,
        device_serials: list[str],
        enabled_switches: list[str],
        update_interval_seconds: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval_seconds),
        )
        self.appkey = appkey
        self.appsecret = appsecret
        self.device_serials = device_serials
        self.enabled_switches = enabled_switches
        self._expire_time_ms = 0
        self._data: dict[str, Any] = {
            "devicelistinfo": [],
            "cameralistinfo": [],
            "capacity": {},
            "params": {"accessToken": ""},
        }

    # ------------------------------------------------------------------
    # Low level HTTP helpers (blocking, run in executor)
    # ------------------------------------------------------------------

    def _http_post(self, url: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Blocking POST helper executed in the executor pool."""
        try:
            resp = requests.post(url, data=data, timeout=API_TIMEOUT)
        except requests.RequestException as err:
            _LOGGER.error("POST %s failed: %s", url, err)
            return None
        try:
            return json.loads(resp.text)
        except ValueError:
            _LOGGER.error("POST %s returned non-JSON: %s", url, resp.text[:200])
            return None

    def _http_get(self, url: str) -> dict[str, Any] | None:
        """Blocking GET helper executed in the executor pool."""
        try:
            resp = requests.get(url, timeout=API_TIMEOUT)
        except requests.RequestException as err:
            _LOGGER.error("GET %s failed: %s", url, err)
            return None
        try:
            return json.loads(resp.text)
        except ValueError:
            _LOGGER.error("GET %s returned non-JSON: %s", url, resp.text[:200])
            return None

    # ------------------------------------------------------------------
    # Access token
    # ------------------------------------------------------------------

    @property
    def access_token(self) -> str:
        """Return the current access token."""
        return self._data["params"]["accessToken"]

    async def _async_fetch_token(self) -> None:
        """Request a new accessToken with appKey/appSecret."""
        response = await self.hass.async_add_executor_job(
            self._http_post,
            API_TOKEN,
            {"appKey": self.appkey, "appSecret": self.appsecret},
        )
        if not response or response.get("code") != "200":
            code = response.get("code") if isinstance(response, dict) else None
            msg = response.get("msg") if isinstance(response, dict) else None
            raise EzvizApiError(code, msg)
        self._data["params"]["accessToken"] = response["data"]["accessToken"]
        self._expire_time_ms = int(response["data"]["expireTime"])
        _LOGGER.info("EZVIZ accessToken refreshed")

    async def async_ensure_token(self) -> str:
        """Return a valid token, refreshing it when it is about to expire."""
        if self._expire_time_ms < time.time() * 1000 + TOKEN_REFRESH_MARGIN_MS:
            await self._async_fetch_token()
        return self.access_token

    # ------------------------------------------------------------------
    # Generic API call with one token-refresh retry
    # ------------------------------------------------------------------

    async def _async_call(
        self, url: str, params: dict[str, Any] | None = None, method: str = "post"
    ) -> dict[str, Any]:
        """Call an open API; retry once after refreshing an expired token."""
        payload = dict(params or {})
        for attempt in range(2):
            payload["accessToken"] = await self.async_ensure_token()
            helper = self._http_get if method == "get" else self._http_post
            if method == "get":
                query = "&".join(f"{k}={v}" for k, v in payload.items())
                response = await self.hass.async_add_executor_job(
                    helper, f"{url}?{query}"
                )
            else:
                response = await self.hass.async_add_executor_job(helper, url, payload)
            if response is None:
                raise EzvizApiError(None, "request failed")
            if "meta" in response:
                if response["meta"].get("code") == 200:
                    return response
                code, msg = response["meta"].get("code"), response["meta"].get("message")
            else:
                if response.get("code") == "200":
                    return response
                code, msg = response.get("code"), response.get("msg")
            if code == "10002" and attempt == 0:
                _LOGGER.debug("accessToken expired, refreshing and retrying")
                self._expire_time_ms = 0
                continue
            raise EzvizApiError(code, msg)
        raise EzvizApiError(None, "unreachable")

    # ------------------------------------------------------------------
    # Polling: device list / camera list / capacity / per-device status
    # ------------------------------------------------------------------

    async def _async_fetch_device_list(self) -> None:
        devices: list[dict[str, Any]] = []
        page_start = 0
        while True:
            resp = await self._async_call(
                API_DEVICE_LIST, {"pageStart": page_start, "pageSize": PAGE_SIZE}
            )
            page = resp.get("page", {})
            devices.extend(resp.get("data") or [])
            total = int(page.get("total", len(devices)))
            page_start += PAGE_SIZE
            if len(devices) >= total or not resp.get("data"):
                break
        if self.device_serials:
            wanted = set(self.device_serials)
            devices = [d for d in devices if d["deviceSerial"] in wanted]
        self._data["devicelistinfo"] = devices

    async def _async_fetch_camera_list(self) -> None:
        channels: list[dict[str, Any]] = []
        page_start = 0
        while True:
            resp = await self._async_call(
                API_CAMERA_LIST, {"pageStart": page_start, "pageSize": PAGE_SIZE}
            )
            page = resp.get("page", {})
            channels.extend(resp.get("data") or [])
            total = int(page.get("total", len(channels)))
            page_start += PAGE_SIZE
            if len(channels) >= total or not resp.get("data"):
                break
        if self.device_serials:
            wanted = set(self.device_serials)
            channels = [c for c in channels if c["deviceSerial"] in wanted]
        self._data["cameralistinfo"] = channels

    async def _async_fetch_device_status(self, serial: str) -> None:
        """Fetch device info plus each enabled switch status."""
        resp = await self._async_call(API_DEVICE_INFO, {"deviceSerial": serial})
        self._data[serial] = resp.get("data") or {}

        capacity = self._data["capacity"].get(serial) or {}
        support_privacy = capacity.get("support_privacy") == "1"

        if "on_off" in self.enabled_switches and support_privacy:
            try:
                resp = await self._async_call(
                    API_SCENE_SWITCH_STATUS, {"deviceSerial": serial}
                )
                # enable=0 表示监控开启（未遮蔽），映射为开关 on
                self._data[serial]["on_off"] = (
                    1 if resp["data"].get("enable") == 0 else 0
                )
            except EzvizApiError as err:
                _LOGGER.debug("on_off status unavailable for %s: %s", serial, err)

        if "soundswitch" in self.enabled_switches:
            try:
                resp = await self._async_call(
                    API_SOUND_STATUS, {"deviceSerial": serial}
                )
                self._data[serial]["soundswitch"] = (
                    1 if resp["data"].get("enable") == 1 else 0
                )
            except EzvizApiError as err:
                _LOGGER.debug("soundswitch status unavailable for %s: %s", serial, err)

    async def _async_update_data(self) -> dict[str, Any]:
        """Refresh all data; raise typed errors for the coordinator."""
        try:
            await self._async_fetch_device_list()
            await self._async_fetch_camera_list()

            serials = [d["deviceSerial"] for d in self._data["devicelistinfo"]]
            capacity = self._data["capacity"]
            missing = [s for s in serials if s not in capacity]
            if missing:
                results = await asyncio.gather(
                    *(
                        self._async_call(API_DEVICE_CAPACITY, {"deviceSerial": s})
                        for s in missing
                    )
                )
                for serial, resp in zip(missing, results):
                    capacity[serial] = resp.get("data") or {}

            if serials:
                await asyncio.gather(
                    *(self._async_fetch_device_status(s) for s in serials)
                )
        except EzvizApiError as err:
            if _is_auth_error(err):
                raise ConfigEntryAuthFailed(
                    f"EZVIZ authentication failed: {err.message}"
                ) from err
            raise UpdateFailed(str(err)) from err

        self._data["updatetime"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        return self._data

    # ------------------------------------------------------------------
    # Operations used by button / switch / camera platforms
    # ------------------------------------------------------------------

    async def async_ptz_start(self, serial: str, channel: int, direction: int) -> None:
        await self._async_call(
            API_PTZ_START,
            {
                "deviceSerial": serial,
                "channelNo": channel,
                "direction": direction,
                "speed": 1,
            },
        )

    async def async_ptz_stop(self, serial: str, channel: int) -> None:
        await self._async_call(
            API_PTZ_STOP, {"deviceSerial": serial, "channelNo": channel}
        )

    async def async_capture(self, serial: str, channel: int) -> str:
        """Capture a snapshot; return the picUrl."""
        resp = await self._async_call(
            API_CAPTURE, {"deviceSerial": serial, "channelNo": channel}
        )
        return (resp.get("data") or {}).get("picUrl", "")

    async def async_latest_alarm_pic(self, serial: str, days: int = 3) -> str:
        """Return the latest alarm picture URL of a device (may be empty)."""
        start_time = int(round(time.time() * 1000)) - days * 24 * 3600 * 1000
        resp = await self._async_call(
            API_ALARM_LIST,
            {"deviceSerial": serial, "startTime": start_time, "status": 2},
        )
        data = resp.get("data") or []
        if data:
            return data[0].get("alarmPicUrl", "")
        return ""

    async def async_live_address(
        self, serial: str, channel: int, protocol: int = 3, expire: int = 300
    ) -> str:
        """Return a temporary live (HLS) address."""
        resp = await self._async_call(
            API_LIVE_ADDRESS,
            {
                "deviceSerial": serial,
                "channelNo": channel,
                "protocol": protocol,
                "expireTime": expire,
            },
        )
        return (resp.get("data") or {}).get("url", "")

    async def async_intelligence(
        self, api: str, image: str, extra: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Call an AI analysis API (vehicle/human/face) with an image URL."""
        params: dict[str, Any] = {"dataType": 0, "image": image}
        if extra:
            params.update(extra)
        return await self._async_call(api, params)

    async def async_set_privacy(self, serial: str, enable_monitor: bool) -> None:
        """Set privacy/scene switch. enable_monitor=True 开启监控(关闭遮蔽)."""
        await self._async_call(
            API_SCENE_SWITCH_SET,
            {"deviceSerial": serial, "enable": 0 if enable_monitor else 1},
        )

    async def async_set_sound(self, serial: str, enable: bool) -> None:
        await self._async_call(
            API_SOUND_SET, {"deviceSerial": serial, "enable": 1 if enable else 0}
        )

    async def async_set_defence(self, serial: str, enable: bool) -> None:
        await self._async_call(
            API_DEFENCE_SET,
            {"deviceSerial": serial, "isDefence": 1 if enable else 0},
        )
