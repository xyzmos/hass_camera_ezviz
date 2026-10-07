"""Webhook support: receive device alarm messages pushed by the EZVIZ cloud."""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url

from .const import DOMAIN, EVENT_WEBHOOK

_LOGGER = logging.getLogger(__name__)

WEBHOOK_PATH = f"/api/{DOMAIN}/webhook"

DATA_VIEW = "view"
DATA_WEBHOOK_IDS = "webhook_ids"


class EzvizWebhookView(HomeAssistantView):
    """HTTP view that receives EZVIZ cloud message callbacks."""

    url = f"{WEBHOOK_PATH}/{{webhook_id}}"
    name = f"api:{DOMAIN}:webhook"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request, webhook_id: str) -> web.Response:
        """Handle one pushed alarm message."""
        if webhook_id not in self.hass.data[DOMAIN][DATA_WEBHOOK_IDS]:
            return self.json_message("Unknown webhook", 404)

        body = await request.text()
        _LOGGER.debug("EZVIZ webhook raw message: %s", body)
        try:
            data: dict[str, Any] = json.loads(body)
        except json.JSONDecodeError as err:
            _LOGGER.error("Failed to parse EZVIZ webhook body: %s", err)
            return self.json_message("Invalid JSON", 400)

        header = data.get("header") or {}
        event_data = {
            "webhook_id": webhook_id,
            "message_id": header.get("messageId"),
            "device_id": header.get("deviceId"),
            "message_type": header.get("type"),
            "channel_no": header.get("channelNo"),
            "message_time": header.get("messageTime"),
            "body": data.get("body"),
        }
        self.hass.bus.async_fire(EVENT_WEBHOOK, event_data)
        _LOGGER.debug("Fired %s: %s", EVENT_WEBHOOK, event_data)

        return self.json({"messageId": header.get("messageId")})


def async_register(hass: HomeAssistant, webhook_id: str) -> str:
    """Register the shared webhook view (once) and allow this webhook id."""
    domain_data = hass.data.setdefault(
        DOMAIN, {DATA_VIEW: None, DATA_WEBHOOK_IDS: set()}
    )
    if domain_data.get(DATA_VIEW) is None:
        view = EzvizWebhookView(hass)
        hass.http.register_view(view)
        domain_data[DATA_VIEW] = view
        _LOGGER.debug("Registered EZVIZ webhook view at %s/{webhook_id}", WEBHOOK_PATH)
    domain_data[DATA_WEBHOOK_IDS].add(webhook_id)
    return webhook_id


def async_unregister(hass: HomeAssistant, webhook_id: str) -> None:
    """Stop accepting messages for this webhook id."""
    domain_data = hass.data.get(DOMAIN)
    if domain_data:
        domain_data[DATA_WEBHOOK_IDS].discard(webhook_id)
    _LOGGER.info("EZVIZ webhook unregistered: %s", webhook_id)


def async_get_webhook_url(hass: HomeAssistant, webhook_id: str) -> str | None:
    """Return the external URL the user should configure on open.ys7.com."""
    try:
        base_url = get_url(hass, prefer_external=True)
    except Exception:  # 未配置任何 URL
        return None
    return f"{base_url}{WEBHOOK_PATH}/{webhook_id}"
