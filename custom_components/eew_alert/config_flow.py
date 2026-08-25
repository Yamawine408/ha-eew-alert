"""Config flow for EEW Alert."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_CAST_DEVICE,
    CONF_IGNORE_TEST,
    CONF_MIN_SCALE,
    CONF_PRESENCE_ENTITIES,
    CONF_TARGET_LIGHTS,
    CONF_TARGET_LOCKS,
    CONF_TARGET_PREFS,
    DEFAULT_IGNORE_TEST,
    DEFAULT_MIN_SCALE,
    DEFAULT_PRESENCE_ENTITIES,
    DEFAULT_TARGET_LIGHTS,
    DEFAULT_TARGET_LOCKS,
    DEFAULT_TARGET_PREFS,
    DOMAIN,
    PREFECTURES,
    SCALE_LABEL,
)

_LOGGER = logging.getLogger(__name__)

SCALE_OPTIONS = [
    selector.SelectOptionDict(value=str(code), label=f"震度{label}以上")
    for code, label in SCALE_LABEL.items()
]


def _discover_chromecast_names_sync() -> list[str]:
    # pychromecastを直接HAのexecutorから呼ぶとハングするため、
    # 独立したOSプロセスとして動く`catt scan`を使う(cast.py参照)。
    import re
    import subprocess

    result = subprocess.run(
        ["catt", "scan"], capture_output=True, text=True, timeout=15
    )
    names: set[str] = set()
    # 出力例: "192.168.1.23 - 寝室 - Google Nest Hub"
    for line in result.stdout.splitlines():
        m = re.match(r"^\S+\s+-\s+(.+?)\s+-\s+.+$", line.strip())
        if m:
            names.add(m.group(1))
    return sorted(names)


async def _async_discover_chromecast_names(hass: HomeAssistant) -> list[str]:
    try:
        return await hass.async_add_executor_job(_discover_chromecast_names_sync)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Chromecast discovery failed")
        return []


def _options_schema(defaults: dict[str, Any], device_names: list[str]) -> vol.Schema:
    # 検出済み一覧に、現在設定されている値が含まれていなければ追加しておく
    # (電源が切れている等で今回検出できなかった場合でも選べるように)
    current = defaults.get(CONF_CAST_DEVICE)
    options = list(device_names)
    if current and current not in options:
        options.append(current)

    return vol.Schema(
        {
            vol.Optional(
                CONF_CAST_DEVICE, default=current or ""
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    multiple=False,
                    custom_value=True,  # 検出できない場合は手入力も可能
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_TARGET_PREFS,
                default=defaults.get(CONF_TARGET_PREFS, DEFAULT_TARGET_PREFS),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=PREFECTURES,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_MIN_SCALE,
                default=str(defaults.get(CONF_MIN_SCALE, DEFAULT_MIN_SCALE)),
            ): vol.All(
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=SCALE_OPTIONS,
                        multiple=False,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Coerce(int),
            ),
            vol.Optional(
                CONF_TARGET_LIGHTS,
                default=defaults.get(CONF_TARGET_LIGHTS, DEFAULT_TARGET_LIGHTS),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="light", multiple=True)
            ),
            vol.Optional(
                CONF_TARGET_LOCKS,
                default=defaults.get(CONF_TARGET_LOCKS, DEFAULT_TARGET_LOCKS),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="lock", multiple=True)
            ),
            vol.Optional(
                CONF_PRESENCE_ENTITIES,
                default=defaults.get(
                    CONF_PRESENCE_ENTITIES, DEFAULT_PRESENCE_ENTITIES
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["person", "device_tracker"], multiple=True
                )
            ),
            vol.Optional(
                CONF_IGNORE_TEST,
                default=defaults.get(CONF_IGNORE_TEST, DEFAULT_IGNORE_TEST),
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

        device_names = await _async_discover_chromecast_names(self.hass)
        return self.async_show_form(
            step_id="user", data_schema=_options_schema({}, device_names)
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EewAlertOptionsFlow:
        return EewAlertOptionsFlow(config_entry)


class EewAlertOptionsFlow(config_entries.OptionsFlow):
    """設定の後から変更用(震度しきい値・キャスト先デバイス名など)。"""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        device_names = await _async_discover_chromecast_names(self.hass)
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self._entry.options, device_names),
        )
