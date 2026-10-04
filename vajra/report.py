from __future__ import annotations

from html import escape


def _drawing_svg(design: dict) -> str:
    g = design["geometry"]
    w, l, h = float(g["width_m"]), float(g["length_m"]), float(g["wall_height_m"])
    scale = 72
    wall_px = max(180, w * scale)
    h_px = max(120, h * scale)
    layers = design["constructions"]["wall"]
    thickness = sum(float(x["mm"]) for x in layers)
    outer = 22
    inner = outer + min(70, thickness / 5)
    roof_h = 35 if g["roof"]["type"] != "flat" else 10
    return f'''<svg viewBox="0 0 520 310" role="img" aria-label="Shelter section drawing">
      <rect x="38" y="{180-h_px/2:.1f}" width="{min(420,wall_px):.1f}" height="{h_px:.1f}" fill="none" stroke="#1E2125" stroke-width="1.2"/>
      <rect x="{38+outer:.1f}" y="{180-h_px/2+outer:.1f}" width="{max(80, min(420,wall_px)-2*outer):.1f}" height="{max(60,h_px-2*outer):.1f}" fill="#FBFAF6" stroke="#1E2125" stroke-width="1"/>
      <line x1="38" y1="{180-h_px/2:.1f}" x2="{38+min(420,wall_px):.1f}" y2="{180-h_px/2-roof_h:.1f}" stroke="#1E2125" stroke-width="1.2"/>
      <line x1="{38+min(420,wall_px):.1f}" y1="{180-h_px/2-roof_h:.1f}" x2="{38+min(420,wall_px):.1f}" y2="{180-h_px/2:.1f}" stroke="#1E2125" stroke-width="1.2"/>
      <line x1="70" y1="238" x2="420" y2="238" stroke="#CFC8BA" stroke-width="1"/>
      <text x="70" y="255" font-family="IBM Plex Mono" font-size="11" fill="#1E2125">wall: {escape(', '.join(f"{x['material']} {x['mm']} mm" for x in layers))}</text>
      <text x="70" y="274" font-family="IBM Plex Mono" font-size="11" fill="#5E6368">floor: {escape(', '.join(f"{x['material']} {x['mm']} mm" for x in design['constructions']['floor']))}</text>
      <text x="440" y="130" font-family="IBM Plex Mono" font-size="11" fill="#1E2125">N</text><line x1="450" y1="160" x2="450" y2="120" stroke="#1E2125" stroke-width="1.2"/><path d="M450 116 l-5 9 h10 z" fill="#1E2125"/>
      <text x="440" y="292" font-family="IBM Plex Mono" font-size="11" fill="#1E2125">1 m</text><line x1="400" y1="286" x2="470" y2="286" stroke="#1E2125" stroke-width="1.2"/>
    </svg>'''


def design_sheet_html(design: dict, result: dict) -> str:
    s = result["summary"]
    source = escape(str(result["meta"]["weather_source"]))
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>VAJRA design sheet</title>
    <style>@page {{size:A4;margin:14mm}} body{{font-family:"IBM Plex Sans",sans-serif;color:#1E2125;background:#fff}} h1,h2{{font-family:"Source Serif 4",serif;font-weight:400}} h1{{font-size:23px}} h2{{font-size:18px;border-bottom:1px solid #CFC8BA;padding-bottom:5px}} .mono{{font-family:"IBM Plex Mono",monospace}} table{{width:100%;border-collapse:collapse}} td,th{{border-bottom:1px solid #CFC8BA;padding:7px;text-align:left}} .note{{margin-top:15px;font-size:12px;color:#5E6368}}</style></head>
    <body><h1>VAJRA thermal shelter model</h1><div class="mono">Design: {escape(design['name'])}</div><p>Weather: {source} | {result['meta'].get('lat')} N, {result['meta'].get('lon')} E</p>
    { _drawing_svg(design) }
    <h2>Inputs</h2><table><tr><td>Plan</td><td class="mono">{design['geometry']['length_m']:.2f} m × {design['geometry']['width_m']:.2f} m × {design['geometry']['wall_height_m']:.2f} m</td></tr><tr><td>Main facade</td><td class="mono">{design['geometry']['azimuth_deg']:.0f}°</td></tr><tr><td>Wall</td><td>{escape(str(design['constructions']['wall']))}</td></tr><tr><td>Roof</td><td>{escape(str(design['constructions']['roof']))}</td></tr><tr><td>Floor</td><td>{escape(str(design['constructions']['floor']))}</td></tr></table>
    <h2>Metrics</h2><table><tr><th>Metric</th><th>Value</th></tr><tr><td>Indoor minimum</td><td class="mono">{s['t_min_c']:.2f} °C</td></tr><tr><td>Indoor maximum</td><td class="mono">{s['t_max_c']:.2f} °C</td></tr><tr><td>Comfort hours</td><td class="mono">{s['comfort_hours']:.1f} h</td></tr><tr><td>Heating energy</td><td class="mono">{s['heating_kwh']:.2f} kWh</td></tr></table>
    <p class="note">Values are model estimates. This prototype has not been compared with a measured shelter. Weather provenance is shown above.</p>
    </body></html>'''
