import os
import sys
from playwright.sync_api import sync_playwright

URL = os.environ.get("DASHBOARD_URL", "https://model-picker.relate-ai.site")
TOKEN = os.environ.get("MODEL_PICKER_TOKEN", "")
SCREENSHOT_DIR = os.environ.get("SCREENSHOT_DIR", "/app/screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

failures = []

def check(name, condition, detail=""):
    if condition:
        print(f"PASS: {name}")
    else:
        print(f"FAIL: {name} {detail}")
        failures.append(name)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    # Desktop
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(URL, wait_until="networkidle", timeout=60000)
    check("desktop title", "Relate Model Picker" in page.title(), page.title())
    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "desktop.png"), full_page=True)

    rows = page.locator("#modelTable tbody tr").count()
    check("catalog row count 213", rows == 213, f"got {rows}")

    # Search
    page.fill("#searchInput", "beam-free")
    page.wait_for_timeout(300)
    filtered = page.locator("#modelTable tbody tr").count()
    check("search filters", filtered >= 1 and filtered < rows, f"got {filtered}")
    page.fill("#searchInput", "")

    # Provider filter
    page.select_option("#providerFilter", "openrouter")
    page.wait_for_timeout(300)
    prov_rows = page.locator("#modelTable tbody tr").count()
    check("provider filter", prov_rows > 0 and prov_rows < 213, f"got {prov_rows}")
    page.select_option("#providerFilter", "")

    # Sort
    page.select_option("#sortSelect", "-input_usd_per_million")
    page.wait_for_timeout(300)
    check("sort applies", page.locator("#modelTable tbody tr").count() == 213)

    # Model detail
    first_id = page.locator("#modelTable tbody tr").first.get_attribute("data-id")
    page.locator("#modelTable tbody tr").first.click()
    page.wait_for_timeout(300)
    detail_text = page.locator("#detailPanel").inner_text()
    check("model detail populated", len(detail_text) > 50, detail_text[:120])

    # Compare
    page.locator(".compare-check").first.check()
    page.wait_for_timeout(200)
    compare_cards = page.locator(".compare-card").count()
    check("compare card", compare_cards >= 1, f"got {compare_cards}")

    # Routing cases
    routing_cases = page.locator(".routing-case").count()
    check("routing cases 19", routing_cases == 19, f"got {routing_cases}")

    # Telemetry without token
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(500)
    tel_meta = page.locator("#telemetryMeta").inner_text()
    check("telemetry locked without token", "requires private token" in tel_meta.lower() or "401" in tel_meta, tel_meta)

    # Telemetry with token via localStorage
    if TOKEN:
        page.evaluate(f"localStorage.setItem('modelPickerToken', '{TOKEN}')")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(1000)
        tel_meta2 = page.locator("#telemetryMeta").inner_text()
        check("telemetry unlocks with token", "invocation" in tel_meta2.lower() or "events" in tel_meta2.lower(), tel_meta2)
        tel_rows = page.locator("#telemetryTable tbody tr").count()
        check("telemetry rows present", tel_rows > 0, f"got {tel_rows}")

    # Mobile
    mpage = browser.new_page(viewport={"width": 390, "height": 844})
    mpage.goto(URL, wait_until="networkidle", timeout=60000)
    mpage.screenshot(path=os.path.join(SCREENSHOT_DIR, "mobile.png"), full_page=True)
    overflow = mpage.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 2")
    check("mobile no horizontal overflow", not overflow)
    mpage.close()

    browser.close()

if failures:
    print("FAILED CHECKS:", failures)
    sys.exit(1)
print("ALL VISUAL CHECKS PASSED")
PY