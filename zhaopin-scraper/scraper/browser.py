"""Selenium 浏览器自动化 — 处理 JS 动态渲染页面"""

from __future__ import annotations

import logging
import time
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

import config

logger = logging.getLogger(__name__)


class BrowserAutomation:
    """封装 Selenium 操作，用于抓取 JS 渲染的动态页面。"""

    def __init__(self, headless: bool = True, proxy: Optional[str] = None) -> None:
        opts = Options()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        if proxy:
            opts.add_argument(f"--proxy-server={proxy}")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=opts)
        self.driver.set_page_load_timeout(config.SELENIUM_TIMEOUT)
        self.wait = WebDriverWait(self.driver, config.SELENIUM_TIMEOUT)

    def get_page_source(self, url: str, wait_selector: Optional[str] = None) -> str:
        """加载页面并返回渲染后的 HTML。

        Args:
            url: 目标 URL
            wait_selector: 可选 CSS 选择器，等待该元素出现后再返回
        """
        logger.info("Selenium 加载: %s", url)
        self.driver.get(url)
        if wait_selector:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector)))
        time.sleep(1)  # JS 渲染缓冲
        return self.driver.page_source

    def scroll_to_bottom(self, pause: float = 1.5, max_scrolls: int = 20) -> str:
        """模拟滚动到底部以触发懒加载内容。"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        for _ in range(max_scrolls):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        return self.driver.page_source

    def close(self) -> None:
        try:
            self.driver.quit()
        except Exception:
            pass

    def __enter__(self) -> "BrowserAutomation":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
