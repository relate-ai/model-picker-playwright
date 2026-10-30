import json
import os
import sys
import urllib.request

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

# Load canonical catalog from the same API the dashboard uses.
with urllib.request.urlopen(URL + "/api/catalog", timeout=60) as r:
    catalog = json.load(r)
models = catalog["catalog"]["models"]
catalog_count = len(models)
providers = sorted({m["provider"] for m in models})
billing_types = sorted({m["billing_type"] for m in models})
capabilities = ["text", "tools", "reasoning", "vision"]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # Desktop functional and data checks.
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "desktop.png"), full_page=True)

    check("desktop title", "Relate Model Picker" in page.title(), page.title())
    check("catalog total row count", page.locator("#modelTable tbody tr").count() == catalog_count,
          str(page.locator("#modelTable tbody tr").count()))

    # Every provider filter must match catalog counts exactly.
    for provider in providers:
        page.select_option("#providerFilter", provider)
        page.wait_for_timeout(200)
        expected = sum(1 for m in models if m["provider"] == provider)
        actual = page.locator("#modelTable tbody tr").count()
        check(f"provider filter {provider}", actual == expected, f"expected {expected}, got {actual}")
    page.select_option("#providerFilter", "")

    # Every billing filter must match catalog counts exactly.
    for billing in billing_types:
        page.select_option("#billingFilter", billing)
        page.wait_for_timeout(200)
        expected = sum(1 for m in models if m["billing_type"] == billing)
        actual = page.locator("#modelTable tbody tr").count()
        check(f"billing filter {billing}", actual == expected, f"expected {expected}, got {actual}")
    page.select_option("#billingFilter", "")

    # Capability filters must match catalog counts exactly.
    for capability in capabilities:
        page.select_option("#capabilityFilter", capability)
        page.wait_for_timeout(200)
        expected = sum(1 for m in models if capability in (m.get("capabilities") or []))
        actual = page.locator("#modelTable tbody tr").count()
        check(f"capability filter {capability}", actual == expected, f"expected {expected}, got {actual}")
    page.select_option("#capabilityFilter", "")

    # Search every model id must return exactly one row.
    search_failures = 0
    for m in models:
        page.fill("#searchInput", m["id"])
        page.wait_for_timeout(50)
        if page.locator("#modelTable tbody tr").count() != 1:
            search_failures += 1
    page.fill("#searchInput", "")
    check("search every model id", search_failures == 0, f"{search_failures} failures")

    # Sort options must not error and retain full row count.
    for sort_value in ["id", "provider", "-input_usd_per_million", "input_usd_per_million",
                       "-output_usd_per_million", "context"]:
        page.select_option("#sortSelect", sort_value)
        page.wait_for_timeout(100)
        check(f"sort {sort_value}", page.locator("#modelTable tbody tr").count() == catalog_count,
              str(page.locator("#modelTable tbody tr").count()))
    page.select_option("#sortSelect", "id")

    # Model detail must show the selected model id and a context value for sampled models.
    sample_models = [models[0], models[len(models) // 2], models[-1]]
    for provider in providers:
        provider_models = [m for m in models if m["provider"] == provider]
        if provider_models:
            sample_models.append(provider_models[0])
    seen = set()
    for m in sample_models:
        if m["id"] in seen:
            continue
        seen.add(m["id"])
        page.fill("#searchInput", m["id"])
        page.wait_for_timeout(150)
        page.locator("#modelTable tbody tr").first.click()
        page.wait_for_timeout(200)
        detail = page.locator("#detailPanel").inner_text()
        check(f"detail {m['id']}", m["id"] in detail, detail[:160])
        page.fill("#searchInput", "")

    # Compare up to four models.
    page.select_option("#providerFilter", "")
    page.wait_for_timeout(200)
    for i in range(4):
        page.locator(".compare-check").nth(i).check()
    page.wait_for_timeout(300)
    check("compare four cards", page.locator(".compare-card").count() == 4,
          str(page.locator(".compare-card").count()))
    page.click("#clearCompare")
    page.wait_for_timeout(200)
    check("clear compare", page.locator(".compare-card").count() == 0)

    # Routing cases count and required fields.
    routing_cases = page.locator(".routing-case").count()
    check("routing cases 19", routing_cases == 19, str(routing_cases))
    routing_text = page.locator("#routingCases").inner_text()
    check("routing has real cases", "REAL" in routing_text)
    check("routing has dry cases", "DRY_RUN" in routing_text or "DRY" in routing_text)

    # Telemetry is locked without token.
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(500)
    tel_meta = page.locator("#telemetryMeta").inner_text()
    check("telemetry locked without token", "requires private token" in tel_meta.lower() or "401" in tel_meta, tel_meta)

    if TOKEN:
        page.evaluate(f"localStorage.setItem('modelPickerToken', '{TOKEN}')")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(1000)
        tel_meta2 = page.locator("#telemetryMeta").inner_text()
        check("telemetry unlocks with token", "invocation" in tel_meta2.lower() or "events" in tel_meta2.lower(), tel_meta2)
        tel_rows = page.locator("#telemetryTable tbody tr").count()
        check("telemetry rows present", tel_rows > 0, str(tel_rows))

    # Mobile checks.
    mpage = browser.new_page(viewport={"width": 390, "height": 844})
    mpage.goto(URL, wait_until="networkidle", timeout=60000)
    mpage.screenshot(path=os.path.join(SCREENSHOT_DIR, "mobile.png"), full_page=True)
    overflow = mpage.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 2")
    check("mobile no horizontal overflow", not overflow)
    mpage.close()

    browser.close()

result = "ALL VISUAL CHECKS PASSED" if not failures else "FAILED CHECKS: " + ", ".join(failures)
print(result)
with open(os.path.join(SCREENSHOT_DIR, "result.txt"), "w") as f:
    f.write(result + "\n")
with open(os.path.join(SCREENSHOT_DIR, "container.log"), "w") as f:
    f.write(result + "\n")
if failures:
    sys.exit(1)
