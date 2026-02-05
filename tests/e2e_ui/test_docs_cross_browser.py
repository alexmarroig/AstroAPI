import pytest
from playwright.sync_api import sync_playwright


@pytest.mark.parametrize("browser_name", ["chromium", "firefox", "webkit"])
def test_swagger_ui_cross_browser(browser_name):
    base_url = "http://127.0.0.1:8000"
    with sync_playwright() as p:
        browser_launcher = getattr(p, browser_name)
        browser = browser_launcher.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(f"{base_url}/docs", wait_until="domcontentloaded")
        page.wait_for_selector(".swagger-ui", timeout=15000)
        assert page.locator(".swagger-ui").is_visible()
        browser.close()
