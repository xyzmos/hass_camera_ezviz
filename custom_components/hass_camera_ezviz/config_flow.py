"""Config flow for the EZVIZ CN integration."""

from __future__ import annotations

import logging
from typing import Any

import requests
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from .const import (
    API_DEVICE_LIST,
    API_TIMEOUT,
    API_TOKEN,
    CONF_APP_KEY,
    CONF_APP_SECRET,
    CONF_CAMERA_INTERVAL,
    CONF_DEVICE_SERIAL,
    CONF_DEVICES,
    CONF_ENABLE_WEBHOOK,
    CONF_SWITCHS,
    CONF_UPDATE_INTERVAL,
    CONF_WEBHOOK_URL,
    DEFAULT_CAMERA_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    OPTIONAL_SWITCH_TYPES,
)

_LOGGER = logging.getLogger(__name__)


def _fetch_devices(appkey: str, appsecret: str) -> tuple[list[str] | None, str | None]:
    """Validate credentials and list device serials. Runs in executor."""
    try:
        resp = requests.post(
            API_TOKEN,
            data={"appKey": appkey, "appSecret": appsecret},
            timeout=API_TIMEOUT,
        )
        token_data = resp.json()
    except (requests.RequestException, ValueError) as err:
        _LOGGER.error("Token request failed: %s", err)
        return None, "cannot_connect"

    if token_data.get("code") != "200":
        _LOGGER.error(
            "Token request error, code=%s msg=%s",
            token_data.get("code"),
            token_data.get("msg"),
        )
        return None, "invalid_auth"

    access_token = token_data["data"]["accessToken"]
    try:
        resp = requests.post(
            API_DEVICE_LIST,
            data={"accessToken": access_token, "pageStart": 0, "pageSize": 50},
            timeout=API_TIMEOUT,
        )
        device_data = resp.json()
    except (requests.RequestException, ValueError) as err:
        _LOGGER.error("Device list request failed: %s", err)
        return None, "cannot_connect"

    if device_data.get("code") != "200":
        return None, "invalid_auth"

    serials = [d["deviceSerial"] for d in device_data.get("data") or []]
    return serials, None


class EzvizConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the EZVIZ config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> "EzvizOptionsFlow":
        """Return the options flow."""
        return EzvizOptionsFlow()

    async def _async_validate(
        self, appkey: str, appsecret: str
    ) -> tuple[list[str] | None, str | None]:
        return await self.hass.async_add_executor_job(
            _fetch_devices, appkey, appsecret
        )

    def _user_schema(self, defaults: dict[str, str] | None = None) -> vol.Schema:
        defaults = defaults or {}
        return vol.Schema(
            {
                vol.Required(
                    CONF_APP_KEY, default=defaults.get(CONF_APP_KEY, "")
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Required(
                    CONF_APP_SECRET, default=defaults.get(CONF_APP_SECRET, "")
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: ask for appKey/appSecret."""
        errors: dict[str, str] = {}
        if user_input is not None:
            appkey = user_input[CONF_APP_KEY].strip()
            appsecret = user_input[CONF_APP_SECRET].strip()
            serials, error = await self._async_validate(appkey, appsecret)
            if error is None:
                await self.async_set_unique_id(f"{DOMAIN}-{appkey}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"萤石云-{appkey[:8]}",
                    data={
                        CONF_APP_KEY: appkey,
                        CONF_APP_SECRET: appsecret,
                        CONF_DEVICES: serials or [],
                    },
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication when the appSecret becomes invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm new credentials and update the existing entry."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            appkey = reauth_entry.data[CONF_APP_KEY]
            appsecret = user_input[CONF_APP_SECRET].strip()
            serials, error = await self._async_validate(appkey, appsecret)
            if error is None:
                data = dict(reauth_entry.data)
                data[CONF_APP_SECRET] = appsecret
                data[CONF_DEVICES] = serials or data.get(CONF_DEVICES, [])
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=data
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_APP_SECRET): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )


class EzvizOptionsFlow(OptionsFlowWithReload):
    """Handle integration options; auto-reloads the entry on option change.

    OptionsFlowWithReload (HA 2025.9+) schedules the reload itself, replacing
    the deprecated update_listener + async_reload pattern.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and persist the options form into entry.options."""
        if user_input is not None:
            user_input.pop(CONF_WEBHOOK_URL, None)  # 只读展示字段
            return self.async_create_entry(data=user_input)

        entry = self.config_entry
        device_options = [
            {"value": serial, "label": serial}
            for serial in entry.data.get(CONF_DEVICES, [])
        ]

        # 已注册的 webhook 回调地址（只读展示，便于复制到开放平台）
        webhook_url = ""
        runtime = getattr(entry, "runtime_data", None)
        if runtime is not None and runtime.webhook_url:
            webhook_url = runtime.webhook_url

        schema_dict: dict[Any, Any] = {
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=entry.options.get(
                    CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=3, max=600)),
            vol.Optional(
                CONF_CAMERA_INTERVAL,
                default=entry.options.get(
                    CONF_CAMERA_INTERVAL, DEFAULT_CAMERA_INTERVAL
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=3, max=3600)),
            vol.Optional(
                CONF_DEVICE_SERIAL,
                default=entry.options.get(CONF_DEVICE_SERIAL, []),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=device_options, multiple=True, mode=SelectSelectorMode.LIST
                )
            ),
            vol.Optional(
                CONF_SWITCHS,
                default=entry.options.get(CONF_SWITCHS, OPTIONAL_SWITCH_TYPES[:1]),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=OPTIONAL_SWITCH_TYPES,
                    multiple=True,
                    translation_key=CONF_SWITCHS,
                )
            ),
            vol.Optional(
                CONF_ENABLE_WEBHOOK,
                default=entry.options.get(CONF_ENABLE_WEBHOOK, True),
            ): BooleanSelector(),
        }
        if webhook_url:
            schema_dict[
                vol.Optional(
                    CONF_WEBHOOK_URL,
                    description={"suggested_value": webhook_url},
                )
            ] = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema_dict))
