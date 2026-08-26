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

SCALE_OPTIONS = {
    "震度1": 10,
    "震度2": 20,
    "震度3": 30,
    "震度4": 40,
    "震度5弱": 45,
    "震度5強": 50,
    "震度6弱": 55,
    "震度6強": 60,
    "震度7": 70,
}

SCALE_LABELS = {value: label for label, value in SCALE_OPTIONS.items()}


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    current_scale = defaults.get(CONF_MIN_SCALE, DEFAULT_MIN_SCALE)

    return vol.Schema(
        {
            vol.Required(
                CONF_MIN_SCALE,
                default=SCALE_LABELS.get(
                    current_scale, SCALE_LABELS[DEFAULT_MIN_SCALE]
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(SCALE_OPTIONS),
                    mode=selector.SelectSelectorMode.DROPDOWN,
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


def _convert_scale(user_input: dict[str, Any]) -> dict[str, Any]:
    """Convert the Japanese scale label to the numeric scale value."""
    data = dict(user_input)

    scale_label = data.get(CONF_MIN_SCALE)
    if isinstance(scale_label, str):
        data[CONF_MIN_SCALE] = SCALE_OPTIONS[scale_label]

    return data


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
                title="EEW Alert",
                data={},
                options=_convert_scale(user_input),
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_options_schema({}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EewAlertOptionsFlow:
        return EewAlertOptionsFlow(config_entry)


class EewAlertOptionsFlow(config_entries.OptionsFlow):
    """Handle updating the integration options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data=_convert_scale(user_input),
            )

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self._entry.options),
        )
