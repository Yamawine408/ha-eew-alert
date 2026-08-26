"""Config flow for EEW Alert."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_IGNORE_TEST,
    CONF_MIN_SCALE,
    CONF_TARGET_PREFS,
    DEFAULT_IGNORE_TEST,
    DEFAULT_MIN_SCALE,
    DEFAULT_TARGET_PREFS,
    DOMAIN,
    PREFECTURES,
)


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_MIN_SCALE,
                default=DEFAULT_MIN_SCALE,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=10,
                    max=70,
                    step=5,
                    mode=selector.NumberSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_TARGET_PREFS,
                default=defaults.get(
                    CONF_TARGET_PREFS, DEFAULT_TARGET_PREFS
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=PREFECTURES,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_IGNORE_TEST,
                default=defaults.get(
                    CONF_IGNORE_TEST, DEFAULT_IGNORE_TEST
                ),
            ): bool,
        }
    )


class EewAlertConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="EEW Alert", data={}, options=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=_options_schema({})
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EewAlertOptionsFlow:
        return EewAlertOptionsFlow(config_entry)


class EewAlertOptionsFlow(config_entries.OptionsFlow):
    """設定の後から変更用(地域、震度しきい値など)。"""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self._entry.options),
        )
