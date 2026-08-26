"""japan.svg(Geolonia製、都道府県ポリゴンのシンプルなSVG)を
外部ライブラリなし(標準ライブラリのXMLパーサー + PIL)で描画するモジュール。

japan.svgは、都道府県ごとの <g data-code="N" transform="translate(x,y)"> の中に
<polygon points="..."> が並ぶだけの単純な構造なので、cairosvg等の重い
SVGレンダラーを使わずに座標変換だけで描画できる。
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
SVG_PATH = os.path.join(HERE, "japan.svg")

_NS = {"svg": "http://www.w3.org/2000/svg"}

_MATRIX_RE = re.compile(r"matrix\(([^)]+)\)")
_TRANSLATE_RE = re.compile(r"translate\(([^)]+)\)")
_PATH_TOKEN_RE = re.compile(r"[MLZ]|-?\d+(?:\.\d+)?")


def _parse_path_d(d: str) -> list[list[tuple[float, float]]]:
    """<path d="M x,y L x,y ... Z M x,y ..."> をサブパス(点リスト)の一覧に変換する。

    このSVGではM(moveto)/L(lineto)/Z(closepath)のみが使われており、
    曲線コマンド(C/Q/A等)は存在しないため、これだけ対応すれば十分。
    """
    tokens = _PATH_TOKEN_RE.findall(d)
    subpaths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "M":
            if current:
                subpaths.append(current)
            current = []
            x, y = float(tokens[i + 1]), float(tokens[i + 2])
            current.append((x, y))
            i += 3
        elif tok == "L":
            x, y = float(tokens[i + 1]), float(tokens[i + 2])
            current.append((x, y))
            i += 3
        elif tok == "Z":
            if current:
                subpaths.append(current)
            current = []
            i += 1
        else:
            i += 1
    if current:
        subpaths.append(current)
    return subpaths


def _parse_matrix(transform: str | None) -> tuple[float, float, float, float, float, float]:
    """transform属性から affine matrix (a,b,c,d,e,f) を取り出す。"""
    if not transform:
        return (1, 0, 0, 1, 0, 0)
    m = _MATRIX_RE.search(transform)
    if m:
        a, b, c, d, e, f = (float(v) for v in m.group(1).replace(",", " ").split())
        return (a, b, c, d, e, f)
    t = _TRANSLATE_RE.search(transform)
    if t:
        parts = t.group(1).replace(",", " ").split()
        tx = float(parts[0])
        ty = float(parts[1]) if len(parts) > 1 else 0.0
        return (1, 0, 0, 1, tx, ty)
    return (1, 0, 0, 1, 0, 0)


def _apply(m: tuple[float, float, float, float, float, float], x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _compose(
    m1: tuple[float, float, float, float, float, float],
    m2: tuple[float, float, float, float, float, float],
) -> tuple[float, float, float, float, float, float]:
    """m1 の後に m2 を適用する合成行列(m2 * m1)。"""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a2 * a1 + c2 * b1,
        b2 * a1 + d2 * b1,
        a2 * c1 + c2 * d1,
        b2 * c1 + d2 * d1,
        a2 * e1 + c2 * f1 + e2,
        b2 * e1 + d2 * f1 + f2,
    )


def load_prefecture_polygons() -> dict[int, list[list[tuple[float, float]]]]:
    """data-code -> ポリゴン(点リスト)のリスト、を返す。座標はviewBox(0..1000程度)基準。"""
    tree = ET.parse(SVG_PATH)
    root = tree.getroot()

    svg_map_g = root.find(".//svg:g[@class='svg-map']", _NS)
    outer_m = _parse_matrix(svg_map_g.get("transform"))

    prefectures_g = svg_map_g.find("svg:g[@class='prefectures']", _NS)
    mid_m = _parse_matrix(prefectures_g.get("transform"))
    base_m = _compose(mid_m, outer_m)

    result: dict[int, list[list[tuple[float, float]]]] = {}
    for g in prefectures_g.findall("svg:g", _NS):
        code = g.get("data-code")
        if not code:
            continue
        code_i = int(code)
        pref_m = _compose(_parse_matrix(g.get("transform")), base_m)

        polygons: list[list[tuple[float, float]]] = []
        for poly in g.findall(".//svg:polygon", _NS):
            pts_raw = poly.get("points", "").strip()
            if not pts_raw:
                continue
            # "x y x y ..." (空白区切り) と "x,y x,y ..." (カンマ区切り) の両方に対応
            nums = [float(v) for v in pts_raw.replace(",", " ").split()]
            pts: list[tuple[float, float]] = []
            for i in range(0, len(nums) - 1, 2):
                pts.append(_apply(pref_m, nums[i], nums[i + 1]))
            if len(pts) >= 3:
                polygons.append(pts)

        for path in g.findall(".//svg:path", _NS):
            d = path.get("d", "")
            if not d:
                continue
            for subpath in _parse_path_d(d):
                pts = [_apply(pref_m, x, y) for x, y in subpath]
                if len(pts) >= 3:
                    polygons.append(pts)

        if polygons:
            result[code_i] = polygons

    return result


def draw_map(
    draw: Any,
    origin_x: float,
    origin_y: float,
    map_size: float,
    code_color: dict[int, str],
    default_color: str = "#d7dbe0",
    outline_color: str = "#9aa0a6",
) -> None:
    """PIL ImageDraw に地図を描画する。

    origin_x, origin_y: 描画領域左上のピクセル座標
    map_size: 描画領域の一辺(viewBoxの1000をこのサイズに正規化)
    """
    polygons_by_code = load_prefecture_polygons()
    scale = map_size / 1000.0

    for code, polygons in polygons_by_code.items():
        color = code_color.get(code, default_color)
        for pts in polygons:
            scaled = [
                (origin_x + x * scale, origin_y + y * scale) for x, y in pts
            ]
            draw.polygon(scaled, fill=color, outline=outline_color)
