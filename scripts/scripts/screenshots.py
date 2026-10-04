from pathlib import Path
import asyncio
import base64
import json
import urllib.request
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
FONTS = [
    "IBMPlexSans-Regular.woff2",
    "IBMPlexSans-SemiBold.woff2",
    "IBMPlexMono-Regular.woff2",
    "SourceSerif4-Regular.woff2",
]


def get_json(path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:8000{path}", timeout=60) as r:
        return json.loads(r.read().decode())


def data_url(path: Path) -> str:
    return "data:font/woff2;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def build_html(materials, default):
    css = (WEB / "app.css").read_text(encoding="utf-8")
    js = (WEB / "app.js").read_text(encoding="utf-8")
    plotly = (WEB / "vendor" / "plotly.min.js").read_text(encoding="utf-8")
    index = (WEB / "index.html").read_text(encoding="utf-8")
    for name in FONTS:
        css = css.replace(f'url("./fonts/{name}")', f'url("{data_url(WEB / "fonts" / name)}")')
    body = index.split('<body>', 1)[1].split('</body>', 1)[0]
    body = body.replace('<link rel="stylesheet" href="/static/app.css">', '')
    mock = f'''<script>
const MATERIALS = {json.dumps(materials, ensure_ascii=False)};
const DEFAULT = {json.dumps(default, ensure_ascii=False)};
window.fetch = async (url) => {{
  const u = String(url);
  if (u.includes('/api/materials')) return new Response(JSON.stringify(MATERIALS), {{headers: {{'Content-Type': 'application/json'}}}});
  if (u.includes('/api/weather-info')) return new Response(JSON.stringify({{meta: DEFAULT.result.meta, rows: DEFAULT.result.series.time.length}}), {{headers: {{'Content-Type': 'application/json'}}}});
  if (u.includes('/api/default')) return new Response(JSON.stringify(DEFAULT), {{headers: {{'Content-Type': 'application/json'}}}});
  if (u.includes('/api/run')) return new Response(JSON.stringify(DEFAULT.result), {{headers: {{'Content-Type': 'application/json'}}}});
  if (u.includes('/api/compare')) return new Response(JSON.stringify({{rows: []}}), {{headers: {{'Content-Type': 'application/json'}}}});
  if (u.includes('/api/compare-materials')) return new Response(JSON.stringify({{rows: []}}), {{headers: {{'Content-Type': 'application/json'}}}});
  throw new Error('Screenshot mock has no response for ' + u);
}};
</script>'''
    body = body.replace('<script src="/static/vendor/plotly.min.js"></script>', '<script>' + plotly + '</script>')
    body = body.replace('<script src="/static/app.js"></script>', mock + '<script>' + js + '</script>')
    return '<!doctype html><html><head><meta charset="utf-8"><style>' + css + '</style></head><body>' + body + '</body></html>'


async def render(browser_type, html, width, height, out_path):
    browser = await browser_type.launch(executable_path='/usr/bin/chromium', headless=True)
    page = await browser.new_page(viewport={"width": width, "height": height})
    await page.set_content(html, wait_until="domcontentloaded", timeout=30000)
    await page.evaluate("document.fonts.ready")
    await page.wait_for_timeout(900)
    status = await page.evaluate("""() => ({
        plexSans: document.fonts.check('15px "IBM Plex Sans"'),
        plexMono: document.fonts.check('15px "IBM Plex Mono"'),
        sourceSerif: document.fonts.check('23px "Source Serif 4"'),
        titleFamily: getComputedStyle(document.querySelector('.tool-title')).fontFamily,
        bodyFamily: getComputedStyle(document.body).fontFamily
    })""")
    await page.screenshot(path=str(out_path), full_page=False)
    await browser.close()
    return status


async def main():
    html = build_html(get_json('/api/materials'), get_json('/api/default'))
    async with async_playwright() as p:
        status_1440 = await render(p.chromium, html, 1440, 900, ROOT / 'screenshot_1440.png')
        status_390 = await render(p.chromium, html, 390, 844, ROOT / 'screenshot_390.png')
    status = {'1440': status_1440, '390': status_390}
    (ROOT / 'font_status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    print(json.dumps(status, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
