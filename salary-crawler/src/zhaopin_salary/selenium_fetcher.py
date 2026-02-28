from __future__ import annotations

import time


def render_dynamic_page(
    url: str,
    wait_seconds: float = 2.5,
    scroll_rounds: int = 2,
    headless: bool = True,
) -> str:
    """Render dynamic content with Selenium and return HTML."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,1200")

    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        time.sleep(wait_seconds)
        for _ in range(scroll_rounds):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(wait_seconds)
        return driver.page_source
    finally:
        driver.quit()

