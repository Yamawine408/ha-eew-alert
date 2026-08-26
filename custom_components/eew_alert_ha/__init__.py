"""EEW Alert integration.

P2P地震情報(https://www.p2pquake.net/)のWebSocketに直接接続し、
緊急地震速報(code:556)を受信する。しきい値以上の震度を受信した場合、
Home Assistantに対しeew_alert_triggeredをトリガーする。
この時のテストトリガーの内容は以下の通り。

event_type: eew_alert_triggered
data:
  id: test
  scale: 50
  label: 5強
  hypocenter: テスト震源
  prefs:
    - pref: XX県
      scale: 50
origin: LOCAL
time_fired: '2026-08-26T04:41:48.112250+00:00'
context:
  id: 01M0Y5ZMTGKFTH1DVSV0GRY2N3
  parent_id: null
  user_id: null

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

from .const import (
    CONF_IGNORE_TEST,
    CONF_MIN_SCALE,
    CONF_TARGET_PREFS,
    DEFAULT_IGNORE_TEST,
    DEFAULT_MIN_SCALE,
    DEFAULT_TARGET_PREFS,
    DOMAIN,
    EVENT_EEW_CANCELLED,
    EVENT_EEW_TRIGGERED,
    SCALE_LABEL,
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
            "id": data.get("id", ""),
            "scale": max_scale,
            "label": self.state.label,
            "hypocenter": hypocenter,
            "prefs": prefs,
        }
        self.hass.bus.async_fire(EVENT_EEW_TRIGGERED, event_data)
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    listener = EewListener(hass, entry)
    await listener.async_start()
    hass.data[DOMAIN][entry.entry_id] = listener

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    listener: EewListener = hass.data[DOMAIN].pop(entry.entry_id)
    await listener.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
