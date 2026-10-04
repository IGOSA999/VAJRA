from __future__ import annotations

from datetime import date
from html import escape
import math

import numpy as np

from .solar import solar_position


LABELS = {
    "stone_masonry": "Stone masonry",
    "concrete_dense": "Dense concrete",
    "fired_clay_brick": "Fired clay brick",
    "rammed_earth": "Rammed earth",
    "adobe": "Adobe",
    "eps": "EPS insulation",
    "xps": "XPS insulation",
    "mineral_wool": "Mineral wool",
    "pir": "PIR insulation",
    "timber": "Timber",
    "water": "Water",
    "pcm_paraffin": "Paraffin PCM",
    "soil": "Soil",
    "single_clear": "Single glazing, clear",
    "double_clear": "Double glazing, clear",
    "double_low_e": "Double glazing, low-e",
}

FLOW_LABELS = {
    "wall_main": "Main wall",
    "wall_back": "Back wall",
    "wall_left": "Left wall",
    "wall_right": "Right wall",
    "roof": "Roof",
    "floor": "Floor",
    "glazing": "Glazing",
    "ventilation": "Ventilation",
    "interior_mass": "Interior mass",
}


def label(key: str) -> str:
    return LABELS.get(key, str(key).replace("_", " ").title())


def flow_label(key: str) -> str:
    return FLOW_LABELS.get(key, label(key))


def _pattern_for(material: str) -> str:
    m = material.lower()
    if "insulation" in m or m in {"eps", "xps", "mineral_wool", "pir"}:
        return "insulation"
    if m in {"timber"}:
        return "timber"
    if m in {"soil"}:
        return "soil"
    if m in {"water"}:
        return "water"
    if m in {"pcm_paraffin"}:
        return "pcm"
    if m in {"concrete_dense"}:
        return "concrete"
    return "masonry"


def section_svg(design: dict, weather_meta: dict | None = None, period: list[str] | None = None) -> str:
    g = design["geometry"]
    width = float(g["width_m"])
    length = float(g["length_m"])
    height = float(g["wall_height_m"])
    layers = design["constructions"]["wall"]
    roof = design["constructions"]["roof"]
    floor = design["constructions"]["floor"]
    opening = design.get("openings", [None])[0]
    window_w = float(opening["width_m"]) if opening else 0.0
    window_h = float(opening["height_m"]) if opening else 0.0
    window_sill = max(0.35, 0.45 * height - 0.25 * window_h)

    W, H = 980, 610
    left, base = 70, 450
    main_scale = min(62, 760 / max(width, 1.0), 300 / max(height, 1.0))
    body_w = width * main_scale
    body_h = height * main_scale
    top = base - body_h
    x0 = left
    x1 = x0 + body_w
    wy0 = base - (window_sill + window_h) * main_scale
    wy1 = base - window_sill * main_scale
    wx0 = x0 + max(0, (body_w - window_w * main_scale) / 2)
    wx1 = wx0 + window_w * main_scale

    hatch_defs = [
        '<pattern id="masonry" patternUnits="userSpaceOnUse" width="12" height="12"><path d="M0 0 L12 12 M-6 6 L6 18 M6 -6 L18 6" stroke="#1E2125" stroke-width="0.4" opacity="0.55"/></pattern>',
        '<pattern id="concrete" patternUnits="userSpaceOnUse" width="14" height="14"><circle cx="3" cy="4" r="1" fill="#1E2125"/><path d="M7 2 l4 4 l-4 4" fill="none" stroke="#1E2125" stroke-width="0.4"/></pattern>',
        '<pattern id="insulation" patternUnits="userSpaceOnUse" width="16" height="10"><path d="M0 5 L4 1 L8 9 L12 1 L16 5" fill="none" stroke="#1E2125" stroke-width="0.4"/></pattern>',
        '<pattern id="timber" patternUnits="userSpaceOnUse" width="16" height="16"><path d="M2 0 C8 4 1 10 14 16 M10 0 C1 5 12 10 4 16" fill="none" stroke="#1E2125" stroke-width="0.4"/></pattern>',
        '<pattern id="soil" patternUnits="userSpaceOnUse" width="14" height="14"><path d="M1 3 h5 M8 9 h5 M3 13 h5" stroke="#1E2125" stroke-width="0.4"/></pattern>',
        '<pattern id="water" patternUnits="userSpaceOnUse" width="16" height="10"><path d="M0 5 C4 0 12 10 16 5" fill="none" stroke="#1E2125" stroke-width="0.5"/></pattern>',
        '<pattern id="pcm" patternUnits="userSpaceOnUse" width="14" height="14"><path d="M0 0 L14 14 M14 0 L0 14" stroke="#1E2125" stroke-width="0.35" opacity="0.45"/></pattern>',
    ]

    # A compact wall-detail strip shows every layer at a 1:5 drawing scale.
    detail_x, detail_y, detail_w = 610, 190, 290
    detail_scale = 3.0  # px per mm at 1:5, intentionally enlarged for readability
    total_mm = sum(float(x["mm"]) for x in layers)
    if total_mm <= 0: total_mm = 1
    detail_h = 110
    layer_rects = []
    cursor = detail_x
    for layer in layers:
        mm = float(layer["mm"])
        rw = max(3, detail_w * mm / total_mm)
        pat = _pattern_for(layer["material"])
        layer_rects.append((cursor, rw, layer))
        cursor += rw
    detail = []
    for rx, rw, layer in layer_rects:
        detail.append(f'<rect x="{rx:.1f}" y="{detail_y}" width="{rw:.1f}" height="{detail_h}" fill="url(#{_pattern_for(layer["material"])})" stroke="#1E2125" stroke-width="0.7"/>')

    # Main section: facade elevation with roof/floor context and window cutout.
    svg = [f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="VAJRA shelter section drawing">
      <defs>{''.join(hatch_defs)}</defs>
      <rect width="100%" height="100%" fill="#FBFAF6"/>
      <text x="40" y="34" font-family="IBM Plex Sans" font-size="18" fill="#1E2125">Shelter section through glazed facade</text>
      <text x="40" y="55" font-family="IBM Plex Mono" font-size="11" fill="#5E6368">{width:.2f} m wide × {length:.2f} m long × {height:.2f} m high</text>
      <rect x="{x0:.1f}" y="{top:.1f}" width="{body_w:.1f}" height="{body_h:.1f}" fill="#F5F2EB" stroke="#1E2125" stroke-width="1.2"/>
      <rect x="{wx0:.1f}" y="{wy0:.1f}" width="{wx1-wx0:.1f}" height="{wy1-wy0:.1f}" fill="#FBFAF6" stroke="#1E2125" stroke-width="1.2"/>
      <line x1="{x0:.1f}" y1="{top:.1f}" x2="{x1:.1f}" y2="{top-24:.1f}" stroke="#1E2125" stroke-width="1.2"/>
      <line x1="{x1:.1f}" y1="{top-24:.1f}" x2="{x1:.1f}" y2="{top:.1f}" stroke="#1E2125" stroke-width="1.2"/>
      <rect x="{x0-8:.1f}" y="{base:.1f}" width="{body_w+16:.1f}" height="22" fill="url(#concrete)" stroke="#1E2125" stroke-width="0.7"/>
      <line x1="{x0-8:.1f}" y1="{base+22:.1f}" x2="{x1+8:.1f}" y2="{base+22:.1f}" stroke="#1E2125" stroke-width="1.2"/>
      <text x="{wx0:.1f}" y="{wy0-8:.1f}" font-family="IBM Plex Mono" font-size="10" fill="#1E2125">window {window_w:.2f} × {window_h:.2f} m</text>
      <line x1="{wx0:.1f}" y1="{wy0-4:.1f}" x2="{wx0:.1f}" y2="{wy0-35:.1f}" stroke="#1E2125" stroke-width="0.7"/>
      <line x1="{wx1:.1f}" y1="{wy0-4:.1f}" x2="{wx1:.1f}" y2="{wy0-35:.1f}" stroke="#1E2125" stroke-width="0.7"/>
      <line x1="{wx0:.1f}" y1="{wy0-28:.1f}" x2="{wx1:.1f}" y2="{wy0-28:.1f}" stroke="#1E2125" stroke-width="0.7"/>
      <path d="M55 {base:.1f} h35 M55 {top:.1f} h35 M72 {top:.1f} v{base-top:.1f}" stroke="#1E2125" fill="none" stroke-width="0.7"/>
      <text x="18" y="{(top+base)/2:.1f}" transform="rotate(-90 18 {(top+base)/2:.1f})" font-family="IBM Plex Mono" font-size="11" fill="#1E2125">Wall height {height:.2f} m</text>
      <line x1="{x0:.1f}" y1="{base+48:.1f}" x2="{x1:.1f}" y2="{base+48:.1f}" stroke="#1E2125" stroke-width="0.7"/>
      <path d="M{x0:.1f} {base+43:.1f} v10 M{x1:.1f} {base+43:.1f} v10" stroke="#1E2125" stroke-width="0.7"/>
      <text x="{(x0+x1)/2:.1f}" y="{base+66:.1f}" text-anchor="middle" font-family="IBM Plex Mono" font-size="11" fill="#1E2125">{width:.2f} m</text>
      <text x="40" y="{base+90:.1f}" font-family="IBM Plex Sans" font-size="12" fill="#5E6368">Glazed facade orientation: {float(g.get('azimuth_deg', 0)):.0f}°</text>
      <line x1="{x1+32:.1f}" y1="{top+42:.1f}" x2="{x1+32:.1f}" y2="{top+5:.1f}" stroke="#1E2125" stroke-width="1.0"/><path d="M{x1+32:.1f} {top:.1f} l-5 9 h10 z" fill="#1E2125"/>
      <text x="{x1+45:.1f}" y="{top+10:.1f}" font-family="IBM Plex Mono" font-size="10" fill="#1E2125">facing</text>
      <text x="{detail_x:.1f}" y="{detail_y-22:.1f}" font-family="IBM Plex Sans" font-size="15" fill="#1E2125">Wall detail, enlarged 1:5</text>
      {''.join(detail)}
      <text x="{detail_x:.1f}" y="{detail_y+detail_h+20:.1f}" font-family="IBM Plex Mono" font-size="10" fill="#5E6368">Outside → inside</text>
      {''.join(f'<text x="{rx+rw/2:.1f}" y="{detail_y+detail_h+39:.1f}" text-anchor="middle" font-family="IBM Plex Mono" font-size="9" fill="#1E2125">{escape(label(layer["material"]))}</text><text x="{rx+rw/2:.1f}" y="{detail_y+detail_h+53:.1f}" text-anchor="middle" font-family="IBM Plex Mono" font-size="9" fill="#5E6368">{float(layer["mm"]):.0f} mm</text>' for rx,rw,layer in layer_rects)}
    ''']

    # scale bar is computed from the actual main scale
    bar_m = 1.0
    bar_px = bar_m * main_scale
    sx, sy = 70, 555
    svg.append(f'<line x1="{sx}" y1="{sy}" x2="{sx+bar_px:.1f}" y2="{sy}" stroke="#1E2125" stroke-width="1.2"/><path d="M{sx} {sy-5}v10 M{sx+bar_px:.1f} {sy-5}v10" stroke="#1E2125" stroke-width="0.8"/><text x="{sx+bar_px/2:.1f}" y="{sy+17}" text-anchor="middle" font-family="IBM Plex Mono" font-size="10" fill="#1E2125">1 m</text>')
    date_range = ""
    if period:
        try:
            d0 = period[0][:10]
            d1 = period[-1][:10]
            date_range = f"{d0} to {d1}"
        except Exception:
            pass
    provider = (weather_meta or {}).get("provider") or (weather_meta or {}).get("source") or "Weather input"
    solar_note = ""
    if period:
        try:
            import pandas as pd
            start = pd.to_datetime(period[0], utc=True)
            end = pd.to_datetime(period[-1], utc=True)
            idx = pd.date_range(start.floor("h"), end.ceil("h"), freq="h", tz="UTC")
            lat = float((weather_meta or {}).get("lat", design.get("site", {}).get("lat", 34.1526)))
            lon = float((weather_meta or {}).get("lon", design.get("site", {}).get("lon", 77.5771)))
            zen, _ = solar_position(idx, lat, lon)
            solar_note = f"Solar noon elevation: {float(np.max(90.0 - zen)):.1f}°" if len(zen) else ""
        except Exception:
            solar_note = ""
    svg.append(f'''<g transform="translate(650,510)">
      <rect x="0" y="0" width="270" height="90" fill="#FBFAF6" stroke="#1E2125" stroke-width="0.8"/>
      <text x="10" y="18" font-family="IBM Plex Sans" font-size="11" fill="#1E2125">Design: {escape(str(design.get("name", "User design")))}</text>
      <text x="10" y="35" font-family="IBM Plex Mono" font-size="9" fill="#5E6368">Scale: 1:{max(1, int(round(1000/main_scale)))}</text>
      <text x="10" y="50" font-family="IBM Plex Mono" font-size="9" fill="#5E6368">Weather: {escape(str(provider))}</text>
      <text x="10" y="65" font-family="IBM Plex Mono" font-size="9" fill="#5E6368">{escape(date_range)}</text>
      <text x="10" y="79" font-family="IBM Plex Mono" font-size="9" fill="#5E6368">{escape(solar_note)}</text>
    </g></svg>''')
    return ''.join(svg)


def design_sheet_html(design: dict, result: dict) -> str:
    s = result["summary"]
    meta = result.get("meta", {})
    source = meta.get("weather_source", "Weather input")
    svg = section_svg(design, meta, meta.get("period"))
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>VAJRA design sheet</title>
    <style>@page {{size:A4;margin:14mm}} body{{font-family:"IBM Plex Sans",sans-serif;color:#1E2125;background:#fff}} h1,h2{{font-family:"Source Serif 4",serif;font-weight:400}} h1{{font-size:23px}} h2{{font-size:18px;border-bottom:1px solid #CFC8BA;padding-bottom:5px}} .mono{{font-family:"IBM Plex Mono",monospace}} table{{width:100%;border-collapse:collapse}} td,th{{border-bottom:1px solid #CFC8BA;padding:7px;text-align:left}} .note{{margin-top:15px;font-size:12px;color:#5E6368}}</style></head>
    <body><h1>VAJRA thermal shelter model</h1><div>Design: {escape(str(design['name']))}</div><p>Weather: {escape(str(meta.get('provider') or source))}. {escape(str(meta.get('year') or ''))}</p>
    {svg}
    <h2>Inputs</h2><table><tr><td>Plan</td><td class="mono">{design['geometry']['length_m']:.2f} m × {design['geometry']['width_m']:.2f} m × {design['geometry']['wall_height_m']:.2f} m</td></tr><tr><td>Main facade</td><td class="mono">{design['geometry']['azimuth_deg']:.0f}°</td></tr><tr><td>Wall</td><td>{escape(', '.join(f'{label(x["material"])} ({x["mm"]:.0f} mm)' for x in design['constructions']['wall']))}</td></tr><tr><td>Roof</td><td>{escape(', '.join(f'{label(x["material"])} ({x["mm"]:.0f} mm)' for x in design['constructions']['roof']))}</td></tr><tr><td>Floor</td><td>{escape(', '.join(f'{label(x["material"])} ({x["mm"]:.0f} mm)' for x in design['constructions']['floor']))}</td></tr></table>
    <h2>Metrics</h2><table><tr><th>Metric</th><th>Value</th></tr><tr><td>Indoor minimum</td><td class="mono">{s['t_min_c']:.2f} °C</td></tr><tr><td>Indoor maximum</td><td class="mono">{s['t_max_c']:.2f} °C</td></tr><tr><td>Mean indoor - outside</td><td class="mono">{s['mean_delta_c']:.2f} K</td></tr><tr><td>Hours above 0 °C</td><td class="mono">{s['hours_above_zero']:.0f} h</td></tr><tr><td>Heating energy</td><td class="mono">{s['heating_kwh']:.0f} kWh</td></tr></table>
    <p class="note">Values are model estimates. The ANSYS figure in the dashboard is a Level-A wall-panel cross-check. This prototype has not been validated against measured shelter data.</p>
    </body></html>'''
