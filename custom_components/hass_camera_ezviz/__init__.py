"""EZVIZ CN (萤石云开放平台) integration for Home Assistant."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import webhook
from .const import (
    CONF_APP_KEY,
    CONF_APP_SECRET,
    CONF_CAMERA_INTERVAL,
    CONF_DEVICE_SERIAL,
    CONF_ENABLE_WEBHOOK,
    CONF_SWITCHS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_CAMERA_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    OPTIONAL_SWITCH_TYPES,
)
from .coordinator import EzvizDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass
class EzvizRuntimeData:
    """Runtime data attached to each config entry."""

    coordinator: EzvizDataUpdateCoordinator
    webhook_id: str | None = None
    webhook_url: str | None = None


type EzvizConfigEntry = ConfigEntry[EzvizRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration (config-entry only)."""
    hass.data.setdefault(DOMAIN, {"webhook_ids": set()})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EzvizConfigEntry) -> bool:
    """Set up EZVIZ from a config entry."""
    update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    device_serials = entry.options.get(CONF_DEVICE_SERIAL, [])
    enabled_switches = entry.options.get(CONF_SWITCHS, OPTIONAL_SWITCH_TYPES[:1])

    coordinator = EzvizDataUpdateCoordinator(
        hass,
        entry.data[CONF_APP_KEY],
        entry.data[CONF_APP_SECRET],
        device_serials,
        enabled_switches,
        update_interval,
    )

    # ConfigEntryAuthFailed 直接向上传播触发 reauth；
    # 其他失败被包装为 ConfigEntryNotReady 自动重试
    await coordinator.async_config_entry_first_refresh()

    runtime = EzvizRuntimeData(coordinator=coordinator)
    entry.runtime_data = runtime

    if entry.options.get(CONF_ENABLE_WEBHOOK, True):
        try:
            runtime.webhook_id = webhook.async_register(hass, entry.entry_id)
            runtime.webhook_url = webhook.async_get_webhook_url(
                hass, runtime.webhook_id
            )
            if runtime.webhook_url:
                _LOGGER.info("EZVIZ webhook registered: %s", runtime.webhook_url)
            else:
                _LOGGER.warning(
                    "EZVIZ webhook enabled but no reachable HA URL is configured"
                )
        except Exception as err:  # webhook 失败不应阻塞集成加载
            _LOGGER.error("Failed to register EZVIZ webhook: %s", err)

    _LOGGER.debug(
        "camera snapshot interval option: %s",
        entry.options.get(CONF_CAMERA_INTERVAL, DEFAULT_CAMERA_INTERVAL),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EzvizConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    runtime = entry.runtime_data
    if runtime.webhook_id:
        webhook.async_unregister(hass, runtime.webhook_id)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: EzvizConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
