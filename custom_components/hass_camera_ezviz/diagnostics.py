"""Diagnostics support for the EZVIZ CN integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import EzvizConfigEntry
from .const import CONF_APP_KEY, CONF_APP_SECRET

TO_REDACT = {CONF_APP_KEY, CONF_APP_SECRET, "accessToken", "netAddress"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EzvizConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry with secrets redacted."""
    coordinator = entry.runtime_data.coordinator
    data = dict(coordinator.data)
    data.pop("params", None)  # accessToken
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
        },
        "devices": async_redact_data(data, TO_REDACT),
    }
