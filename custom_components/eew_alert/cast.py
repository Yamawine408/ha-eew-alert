"""警告画像の生成とChromecastへのキャストを行うヘルパー。"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url

from . import mapsvg
from .const import PREFECTURES, SCALE_LABEL

_LOGGER = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(HERE, "fonts", "NotoSansJP.ttf")
IMAGE_FILENAME = "eew_alert.png"

WIDTH, HEIGHT = 1920, 1080
MAP_MARGIN = 40
MAP_SIZE = HEIGHT - MAP_MARGIN * 2
PANEL_X = MAP_SIZE + MAP_MARGIN * 2

BG_COLOR = "#ffffff"
MAP_BG_COLOR = "#e9edf2"
TITLE_COLOR = "#e60012"
TEXT_COLOR = "#111111"

# JIS都道府県コード(1〜47)。PREFECTURESの並び順と対応する。
_CODE_BY_NAME = {name: i + 1 for i, name in enumerate(PREFECTURES)}


def _pref_to_code(pref: str) -> int | None:
    """P2Pの府県予報区名(例: 千葉県 / 北海道道央)からJISコードを引く。"""
    if not pref:
        return None
    for name, code in _CODE_BY_NAME.items():
        if name in pref:
            return code
    return None


def _color_for(scale: int) -> str:
    if scale >= 55:
        return "#d9333f"  # 震度6弱以上: 赤
    if scale >= 45:
        return "#f5a623"  # 震度5弱以上(警報): 橙
    return "#f7d36b"  # それ未満: 薄い黄


def _wrap_text(draw, text: str, font, max_width: int) -> list[str]:
    """日本語向けに1文字ずつ折り返して、max_width以内に収まる行のリストを返す。"""
    lines: list[str] = []
    current = ""
    for ch in text:
        trial = current + ch
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def _generate_image(
    image_path: str, label: str, hypocenter: str, prefs: list[dict[str, Any]]
) -> None:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 地図エリアの背景
    draw.rectangle(
        [0, 0, PANEL_X - MAP_MARGIN, HEIGHT], fill=MAP_BG_COLOR
    )

    code_color: dict[int, str] = {}
    for p in prefs:
        code = _pref_to_code(p.get("pref", ""))
        if code:
            scale = int(p.get("scale", -1))
            existing = code_color.get(code)
            if existing is None or _color_for(scale) != existing:
                code_color[code] = _color_for(scale)

    try:
        mapsvg.draw_map(draw, MAP_MARGIN, MAP_MARGIN, MAP_SIZE, code_color)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("failed to draw map, continuing with text only")

    title_font = ImageFont.truetype(FONT_PATH, 70)
    sub_font = ImageFont.truetype(FONT_PATH, 46)
    warn_font = ImageFont.truetype(FONT_PATH, 58)
    area_font = ImageFont.truetype(FONT_PATH, 60)
    note_font = ImageFont.truetype(FONT_PATH, 30)
    for f in (title_font, warn_font, area_font):
        try:
            f.set_variation_by_name("Bold")
        except Exception:  # noqa: BLE001
            pass

    x = PANEL_X
    right_margin = 60
    max_width = WIDTH - PANEL_X - right_margin

    def draw_wrapped(y0: int, text: str, font, fill: str, line_height: int) -> int:
        y = y0
        for line in _wrap_text(draw, text, font, max_width):
            draw.text((x, y), line, font=font, fill=fill)
            y += line_height
        return y

    y = 60
    y = draw_wrapped(y, "緊急地震速報（警報）", title_font, TITLE_COLOR, 100)
    y += 10
    y = draw_wrapped(y, f"{hypocenter} で地震", sub_font, TEXT_COLOR, 60)
    y += 20
    draw.line([(x, y), (WIDTH - right_margin, y)], fill="#dddddd", width=2)
    y += 50
    y = draw_wrapped(y, "強い揺れに警戒：", warn_font, TEXT_COLOR, 90)
    y += 20

    if prefs:
        ranked = sorted(prefs, key=lambda p: -int(p.get("scale", -1)))
        parts = []
        for p in ranked[:8]:
            code = _pref_to_code(p.get("pref", ""))
            short_name = PREFECTURES[code - 1] if code else p.get("pref", "")
            scale_label = SCALE_LABEL.get(int(p.get("scale", -1)), "—")
            parts.append(f"{short_name} {scale_label}")
        area_text = "　".join(parts)
        draw_wrapped(y, area_text, area_font, TEXT_COLOR, 85)

    note_y = HEIGHT - 150
    note_y = draw_wrapped(
        note_y,
        "対象地域では、あわてずに、身の安全を確保してください。",
        note_font,
        "#666666",
        42,
    )
    draw_wrapped(
        note_y,
        f"予想最大震度 {label}。この情報は緊急地震速報の内容の一部です。",
        note_font,
        "#666666",
        42,
    )

    img.save(image_path)


async def async_cast_alert_image(
    hass: HomeAssistant,
    device_name: str,
    label: str,
    hypocenter: str,
    prefs: list[dict[str, Any]],
) -> None:
    """警告画像を生成し、指定したChromecastデバイスにキャストする。"""
    www_dir = hass.config.path("www")
    os.makedirs(www_dir, exist_ok=True)
    image_path = os.path.join(www_dir, IMAGE_FILENAME)

    await hass.async_add_executor_job(
        _generate_image, image_path, label, hypocenter, prefs
    )

    try:
        base_url = get_url(hass, prefer_external=False)
    except NoURLAvailableError:
        _LOGGER.error(
            "cast_alert: internal_url is not configured. "
            "Settings > System > Network で内部URLを設定してください。"
        )
        return

    image_url = f"{base_url}/local/{IMAGE_FILENAME}?v={time.time()}"

    await hass.async_add_executor_job(_cast_sync, device_name, image_url)


MAX_CAST_ATTEMPTS = 5
RETRY_WAIT_SECONDS = 3
CATT_TIMEOUT_SECONDS = 20


def _run_catt(device_name: str, *args: str) -> "subprocess.CompletedProcess[str]":
    import subprocess

    cmd = ["catt", "-d", device_name, *args]
    _LOGGER.debug("cast_alert: running %s", cmd)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=CATT_TIMEOUT_SECONDS,
    )


def _cast_sync(device_name: str, image_url: str) -> None:
    import time as _time

    # catt(pychromecastを内部で使う独立CLI)をサブプロセスとして呼ぶ。
    # HA本体のイベントループ内からpychromecastを直接呼ぶとハングする問題が
    # あったため、確実に別OSプロセスとして実行されるこの方式に切り替えた。
    for attempt in range(1, MAX_CAST_ATTEMPTS + 1):
        _LOGGER.debug(
            "cast_alert: attempt %d/%d for %r", attempt, MAX_CAST_ATTEMPTS, device_name
        )
        try:
            result = _run_catt(device_name, "cast", image_url)
        except Exception:
            _LOGGER.exception("cast_alert: catt cast failed (attempt %d)", attempt)
            _time.sleep(RETRY_WAIT_SECONDS)
            continue

        if result.returncode == 0:
            _LOGGER.info(
                "cast_alert: catt cast succeeded on attempt %d (device=%r)",
                attempt,
                device_name,
            )
            return

        _LOGGER.warning(
            "cast_alert: catt cast attempt %d failed (rc=%d): stdout=%s stderr=%s",
            attempt,
            result.returncode,
            result.stdout.strip(),
            result.stderr.strip(),
        )
        _time.sleep(RETRY_WAIT_SECONDS)

    _LOGGER.error(
        "cast_alert: giving up casting to %r after %d attempts",
        device_name,
        MAX_CAST_ATTEMPTS,
    )
