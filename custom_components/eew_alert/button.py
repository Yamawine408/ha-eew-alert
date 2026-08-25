"""EEW Alert test button."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SIGNAL_UPDATE, EewListener, EewState
from .const import CONF_CAST_DEVICE, CONF_TARGET_PREFS, DOMAIN, EVENT_EEW_TRIGGERED


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    listener: EewListener = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EewAlertTestButton(entry, listener)])


class EewAlertTestButton(ButtonEntity):
    """テスト用のダミー地震速報を発火させるボタン。

    実際のP2P地震情報を待たずに、キャスト・照明ON・解錠(設定していれば)の
    一連の動作を確認できる。対象都道府県の絞り込みは無視して必ず実行する。
    """

    _attr_has_entity_name = True
    _attr_name = "テスト送信"
    _attr_icon = "mdi:test-tube"

    def __init__(self, entry: ConfigEntry, listener: EewListener) -> None:
        self._entry = entry
        self._listener = listener
        self._attr_unique_id = f"{entry.entry_id}_test_button"

    async def async_press(self) -> None:
        target_prefs = self._entry.options.get(CONF_TARGET_PREFS) or []
        test_pref = f"{target_prefs[0]}県" if target_prefs else "千葉県"

        self._listener.state = EewState(
            label="5強",
            scale=50,
            hypocenter="テスト震源",
            prefs=[{"pref": test_pref, "scale": 50}],
            time="",
        )
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

        device_name = self._entry.options.get(CONF_CAST_DEVICE)

	## Adding the following to fire a test event ##
        self.hass.bus.async_fire(
            EVENT_EEW_TRIGGERED,
            {
                "id": "test",
                "scale": 50,
                "label": "5強",
                "hypocenter": "テスト震源",
                "prefs": [{"pref": test_pref, "scale": 50}],
            },
        )

        await self._listener._async_trigger_response(device_name, force=True)  # noqa: SLF001
