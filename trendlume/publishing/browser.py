# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Browser Automation Manager

Manages Playwright browser lifecycle, stealth anti-detection, context configuration,
and safe resource cleanup for social platform automation.
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

from loguru import logger
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from trendlume.publishing.cookie_helper import normalize_storage_state

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

STEALTH_INIT_SCRIPT = """
(() => {
    // Overwrite navigator.webdriver to hide automation flags
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
    });

    // Mock chrome object
    if (!window.chrome) {
        window.chrome = {
            runtime: {},
            loadTimes: () => {},
            csi: () => {},
            app: {},
        };
    }

    // Mock languages and plugins
    Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en'],
    });

    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
    });
})();
"""


class BrowserSession:
    """Encapsulates active Playwright session objects for clean usage"""

    def __init__(self, browser: Browser, context: BrowserContext, page: Page):
        self.browser = browser
        self.context = context
        self.page = page

    async def get_storage_state(self) -> Dict[str, Any]:
        """Extract current storage_state (cookies + localStorage) from context"""
        return await self.context.storage_state()


class BrowserManager:
    """
    Playwright Browser Context Manager with stealth protection and automated cleanup.
    """

    @classmethod
    @asynccontextmanager
    async def get_session(
        cls,
        credential_data: Optional[Any] = None,
        platform: str = "",
        headless: bool = True,
        user_agent: Optional[str] = None,
        timeout_ms: int = 60000,
    ) -> AsyncGenerator[BrowserSession, None]:
        """
        Async context manager providing an anti-detection BrowserSession.
        Guarantees browser and context closure upon exit.
        """
        normalized_state = normalize_storage_state(credential_data, platform=platform) if credential_data else None

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--lang=zh-CN",
        ]

        playwright = await async_playwright().start()
        browser = None
        context = None
        page = None

        try:
            browser = await playwright.chromium.launch(
                headless=headless,
                args=launch_args,
            )

            context_kwargs: Dict[str, Any] = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": user_agent or DEFAULT_USER_AGENT,
                "locale": "zh-CN",
                "timezone_id": "Asia/Shanghai",
            }

            if normalized_state and (normalized_state.get("cookies") or normalized_state.get("origins")):
                context_kwargs["storage_state"] = normalized_state

            context = await browser.new_context(**context_kwargs)
            await context.add_init_script(STEALTH_INIT_SCRIPT)
            context.set_default_timeout(timeout_ms)

            page = await context.new_page()
            session = BrowserSession(browser=browser, context=context, page=page)
            yield session

        finally:
            if page:
                try:
                    await page.close()
                except Exception as e:
                    logger.debug(f"Error closing page: {e}")
            if context:
                try:
                    await context.close()
                except Exception as e:
                    logger.debug(f"Error closing browser context: {e}")
            if browser:
                try:
                    await browser.close()
                except Exception as e:
                    logger.debug(f"Error closing browser: {e}")
            try:
                await playwright.stop()
            except Exception as e:
                logger.debug(f"Error stopping playwright: {e}")
