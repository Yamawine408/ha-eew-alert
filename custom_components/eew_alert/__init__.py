"""EEW Alert integration.

P2P地震情報(https://www.p2pquake.net/)のWebSocketに直接接続し、
緊急地震速報(code:556)を受信する。しきい値以上の震度を受信した場合、
自動的に警告画像を生成してChromecast/Google Home系デバイスへキャストする。

MQTTブローカーや外部コンテナは不要。HAだけで完結する。
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .cast import async_cast_alert_image
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
    EVENT_EEW_CANCELLED,
    EVENT_EEW_TRIGGERED,
    SCALE_LABEL,
    SERVICE_CAST_ALERT,
    WS_URL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button"]

SIGNAL_UPDATE = f"{DOMAIN}_update"


@dataclass
class EewState:
    """最新の受信状態。"""

    label: str = "不明"
    scale: int = -1
    hypocenter: str = ""
    prefs: list[dict[str, Any]] = field(default_factory=list)
    time: str = ""


class EewListener:
    """P2P地震情報WebSocketの購読・再接続を管理する。"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.state = EewState()
        self._task: asyncio.Task | None = None
        self._session: aiohttp.ClientSession | None = None
        self._stopped = False

    async def async_start(self) -> None:
        self._session = aiohttp.ClientSession()
        self._task = self.hass.loop.create_task(self._run())

    async def async_stop(self) -> None:
        self._stopped = True
        if self._task:
            self._task.cancel()
        if self._session:
            await self._session.close()

    async def _run(self) -> None:
        backoff = 5
        while not self._stopped:
            try:
                async with self._session.ws_connect(WS_URL, heartbeat=30) as ws:
                    _LOGGER.info("Connected to P2P Quake WebSocket")
                    backoff = 5
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            self._handle_message(msg.data)
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("P2P Quake WebSocket error: %s; retrying in %ss", err, backoff)
            if self._stopped:
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

    def _handle_message(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except ValueError:
            return

        if data.get("code") != 556:
            return  # 緊急地震速報(発表)のみ扱う

        ignore_test = self.entry.options.get(CONF_IGNORE_TEST, DEFAULT_IGNORE_TEST)
        issue = data.get("issue", {}) or {}
        if ignore_test and (data.get("test") or issue.get("type") == "Test"):
            return

        if data.get("cancelled"):
            self.hass.bus.async_fire(EVENT_EEW_CANCELLED, {"id": data.get("id", "")})
            return

        eq = data.get("earthquake", {}) or {}
        hypocenter = (eq.get("hypocenter", {}) or {}).get("name", "不明")
        areas = data.get("areas", []) or []
        max_scale = max(
            (a.get("scaleTo", a.get("scaleFrom", -1)) for a in areas), default=-1
        )
        prefs = [
            {"pref": a.get("pref", ""), "scale": a.get("scaleTo", a.get("scaleFrom", -1))}
            for a in areas
            if a.get("pref")
        ]

        self.state = EewState(
            label=SCALE_LABEL.get(max_scale, "不明"),
            scale=max_scale,
            hypocenter=hypocenter,
            prefs=prefs,
            time=eq.get("originTime") or data.get("time", ""),
        )

        event_data = {
            "scale": max_scale,
            "label": self.state.label,
            "hypocenter": hypocenter,
            "prefs": prefs,
        }
        self.hass.bus.async_fire(EVENT_EEW_TRIGGERED, event_data)
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

        min_scale = self.entry.options.get(CONF_MIN_SCALE, DEFAULT_MIN_SCALE)
        device_name = self.entry.options.get(CONF_CAST_DEVICE)
        target_prefs = self.entry.options.get(CONF_TARGET_PREFS, DEFAULT_TARGET_PREFS)

        if target_prefs:
            # 対象都道府県が設定されている場合は、その地域の震度で判定する
            relevant_scale = max(
                (
                    p.get("scale", -1)
                    for p in prefs
                    if any(t in p.get("pref", "") for t in target_prefs)
                ),
                default=-1,
            )
        else:
            relevant_scale = max_scale

        if relevant_scale >= min_scale:
            self.hass.async_create_task(self._async_trigger_response(device_name))

    def _is_anyone_home(self) -> bool:
        """在宅検知用エンティティが1つでも'home'状態ならTrue。未設定なら常にTrue。"""
        presence_entities = self.entry.options.get(
            CONF_PRESENCE_ENTITIES, DEFAULT_PRESENCE_ENTITIES
        )
        if not presence_entities:
            return True
        return any(
            self.hass.states.is_state(entity_id, "home")
            for entity_id in presence_entities
        )

    async def _async_trigger_response(
        self, device_name: str | None, force: bool = False
    ) -> None:
        """キャスト・照明ON・解錠を、1つ失敗しても他を止めずに実行する。

        在宅検知用エンティティが設定されている場合は、誰も在宅でなければ
        何も実行しない(無人の家で照明・解錠を作動させても意味がなく、
        特に解錠は誤って空き家状態を招くリスクがあるため)。
        force=Trueの場合は在宅検知を無視する(テストボタン用)。
        """
        if not force and not self._is_anyone_home():
            _LOGGER.info("eew_alert: no one home, skipping response")
            return

        if device_name:
            try:
                await async_cast_alert_image(
                    self.hass,
                    device_name,
                    self.state.label,
                    self.state.hypocenter,
                    self.state.prefs,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("cast_alert_image failed")

        target_lights = self.entry.options.get(CONF_TARGET_LIGHTS, DEFAULT_TARGET_LIGHTS)
        if target_lights:
            try:
                await self.hass.services.async_call(
                    "light", "turn_on", {"entity_id": target_lights}, blocking=True
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("light.turn_on failed")

        # 解錠は安全確保のためのオプション機能。誤作動時のリスクがあるため、
        # ユーザーが明示的に対象ロックを設定した場合のみ動作する。
        target_locks = self.entry.options.get(CONF_TARGET_LOCKS, DEFAULT_TARGET_LOCKS)
        if target_locks:
            try:
                await self.hass.services.async_call(
                    "lock", "unlock", {"entity_id": target_locks}, blocking=True
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("lock.unlock failed")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    listener = EewListener(hass, entry)
    await listener.async_start()
    hass.data[DOMAIN][entry.entry_id] = listener

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _handle_cast_alert(call) -> None:
        device_name = call.data.get("device_name") or entry.options.get(CONF_CAST_DEVICE)
        if not device_name:
            _LOGGER.error("cast_alert: device_name not specified and no default configured")
            return
        label = call.data.get("label", listener.state.label)
        hypocenter = call.data.get("hypocenter", listener.state.hypocenter)
        prefs = call.data.get("prefs", listener.state.prefs)
        await async_cast_alert_image(hass, device_name, label, hypocenter, prefs)

    hass.services.async_register(DOMAIN, SERVICE_CAST_ALERT, _handle_cast_alert)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    listener: EewListener = hass.data[DOMAIN].pop(entry.entry_id)
    await listener.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
