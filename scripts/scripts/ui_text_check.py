from __future__ import annotations
import asyncio
import re
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8000"
BAD = [
    re.compile(r"\b[A-Za-z0-9]+_[A-Za-z0-9_]+\b"),
    re.compile(r"undefined|null|NaN|\[object", re.I),
    re.compile(r"2024-\d\d-\d\dT\d\d:\d\d"),
    re.compile(r"\b\d+\.\d{3,}\b"),
]

async def check(page):
    visible = await page.locator("body").inner_text()
    for pattern in BAD:
        if pattern.search(visible):
            raise AssertionError(f"UI text check failed: {pattern.pattern}")
    if "|" in visible:
        raise AssertionError("UI text check failed: pipe separator")
    empty = await page.locator(".status.error:empty, td.error:empty").count()
    if empty:
        raise AssertionError("empty error element")
    return visible

async def check_width(page, width, height):
    await page.set_viewport_size({"width": width, "height": height})
    await check(page)

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(URL, wait_until="networkidle")
        await page.wait_for_selector("#temp-chart .plotly", timeout=120000)
        await check(page)
        await page.get_by_role("button", name="Run", exact=True).click()
        await page.wait_for_selector("#temp-chart .plotly", timeout=120000)
        await check(page)
        await page.get_by_role("button", name="Compare designs", exact=True).click()
        await page.wait_for_selector("#compare-table tbody tr", timeout=180000)
        await check(page)
        await page.get_by_role("button", name="Compare wall materials", exact=True).click()
        await page.wait_for_selector("#material-table tbody tr", timeout=180000)
        await check(page)
        await check_width(page, 390, 844)
        await page.get_by_role("button", name="Compare designs", exact=True).click()
        await page.wait_for_selector("#compare-table tbody tr", timeout=180000)
        await check(page)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
