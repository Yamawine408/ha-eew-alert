"""EEW Alert sensor entity."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SIGNAL_UPDATE, EewListener
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    listener: EewListener = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EewAlertSensor(entry, listener)])


class EewAlertSensor(SensorEntity):
    """直近の緊急地震速報の状態を表示するセンサー。"""

    _attr_has_entity_name = True
    _attr_name = "最新の震度"
    _attr_icon = "mdi:pulse"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, listener: EewListener) -> None:
        self._entry = entry
        self._listener = listener
        self._attr_unique_id = f"{entry.entry_id}_latest"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self._handle_update)
        )

    def _handle_update(self) -> None:
        # イベントループ以外のスレッド(例: ボタン押下時のテスト経路)から
        # 呼ばれる可能性があるため、スレッドセーフな更新方法を使う。
        self.schedule_update_ha_state()

    @property
    def native_value(self) -> str:
        return self._listener.state.label

    @property
    def extra_state_attributes(self) -> dict:
        s = self._listener.state
        return {
            "scale": s.scale,
            "hypocenter": s.hypocenter,
            "prefs": s.prefs,
            "time": s.time,
        }
