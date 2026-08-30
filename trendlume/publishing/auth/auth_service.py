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
Platform Authentication Service

Handles QR code login orchestration, real-time scanning feedback, and cookie normalization.
"""

import asyncio
import base64
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from loguru import logger

from trendlume.publishing.browser import BrowserManager


@dataclass
class QRSessionState:
    """Active interactive QR Code Login Session"""
    session_id: str
    platform: str
    status: str = "initializing"  # initializing, pending, scanned, success, expired, timeout, error
    qrcode_data_url: Optional[str] = None
    storage_state: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    user_info: Dict[str, Any] = field(default_factory=dict)


async def _locator_to_data_url(locator) -> str:
    """Extract src or take screenshot of locator as Base64 Data URL."""
    try:
        src = await locator.get_attribute("src")
        if src and src.startswith("data:image"):
            return src
    except Exception:
        pass
    screenshot_bytes = await locator.screenshot()
    return f"data:image/png;base64,{base64.b64encode(screenshot_bytes).decode('utf-8')}"


class PlatformAuthService:
    """
    Manages interactive login sessions for social platforms (Douyin, Mock).
    """

    def __init__(self):
        self._sessions: Dict[str, QRSessionState] = {}

    def start_qr_session(self, platform: str, headless: bool = True) -> QRSessionState:
        """
        Start an async interactive QR login session for the given platform.
        Runs in a dedicated background thread with ProactorEventLoop on Windows.
        """
        platform_clean = platform.lower().strip()
        session_id = f"qr_{platform_clean}_{uuid.uuid4().hex[:8]}"

        session = QRSessionState(
            session_id=session_id,
            platform=platform_clean,
            status="initializing",
        )
        self._sessions[session_id] = session

        def _run_in_thread():
            if sys.platform == "win32":
                new_loop = asyncio.ProactorEventLoop()
            else:
                new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                new_loop.run_until_complete(self._run_login_flow(session, headless=headless))
            except Exception as ex:
                logger.error(f"Error in background login thread for {session_id}: {ex}")
            finally:
                try:
                    new_loop.close()
                except Exception:
                    pass

        t = threading.Thread(target=_run_in_thread, daemon=True, name=f"QRAuth_{session_id}")
        t.start()

        logger.info(f"Started QR login session {session_id} for {platform_clean}")
        return session

    def get_qr_session(self, session_id: str) -> Optional[QRSessionState]:
        """Get state of an active or recent QR login session"""
        return self._sessions.get(session_id)

    def cancel_qr_session(self, session_id: str) -> bool:
        """Cancel an ongoing QR login session"""
        session = self._sessions.get(session_id)
        if session:
            session.status = "error"
            session.error_message = "Session cancelled by user"
            return True
        return False

    async def _run_login_flow(self, session: QRSessionState, headless: bool = True):
        """Dispatches login flow to platform-specific worker"""
        try:
            if session.platform == "douyin":
                await self._douyin_qr_flow(session, headless=headless)
            elif session.platform == "mock":
                await self._mock_qr_flow(session)
            else:
                session.status = "error"
                session.error_message = f"Unsupported platform for QR login: {session.platform}"
        except asyncio.CancelledError:
            session.status = "error"
            session.error_message = "Login cancelled"
        except Exception as e:
            logger.error(f"Error in QR login session {session.session_id}: {e}")
            session.status = "error"
            session.error_message = str(e)

    async def _poll_for_login(self, session: QRSessionState, b_session, check_func, timeout_msg: str):
        """Generic polling loop for QR login status"""
        max_seconds = 180
        poll_interval = 2
        elapsed = 0

        while elapsed < max_seconds:
            if session.status == "error":
                break
            
            try:
                is_logged_in = await check_func()
                if is_logged_in:
                    session.storage_state = await b_session.get_storage_state()
                    session.status = "success"
                    logger.info(f"{session.platform} login succeeded for session {session.session_id}")
                    return
            except Exception as e:
                logger.debug(f"Error during {session.platform} login check: {e}")

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        if session.status != "success":
            session.status = "timeout"
            session.error_message = timeout_msg

    # ========================================================================
    # Platform QR Login Flows
    # ========================================================================

    async def _douyin_qr_flow(self, session: QRSessionState, headless: bool = True):
        """
        Handles Douyin creator center QR code capture and login polling.
        """
        async with BrowserManager.get_session(platform="douyin", headless=headless, timeout_ms=120000) as b_session:
            page = b_session.page
            await page.goto("https://creator.douyin.com/", wait_until="domcontentloaded", timeout=60000)
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            scan_login_tab = page.get_by_text("扫码登录", exact=True).first
            await scan_login_tab.wait_for(state="attached", timeout=60000)

            qrcode_selectors = [
                'div#animate_qrcode_container img[src^="data:image"]',
                'div[class*="animate_qrcode_container"] img[src^="data:image"]',
                'div[class*="scan_qrcode_login_content"] img[src^="data:image"]',
                'div[class*="qrcode"] img[src^="data:image"]',
                'img[aria-label="二维码"]',
                'div#animate_qrcode_container canvas',
                'div[class*="animate_qrcode_container"] canvas',
                'div[class*="scan_qrcode_login_content"] canvas',
                'canvas',
            ]

            async def extract_qr() -> Optional[str]:
                for sel in qrcode_selectors:
                    loc = page.locator(sel).first
                    try:
                        await loc.wait_for(state="attached", timeout=5000)
                        if await loc.count():
                            src = await loc.get_attribute("src")
                            if src and src.startswith("data:image/"):
                                return src
                            # Fallback if canvas/screenshot needed
                            return await _locator_to_data_url(loc)
                    except Exception:
                        continue
                return None

            qr_data = await extract_qr()
            if not qr_data:
                fb = page.locator('div[class*="login"] img, div[class*="qrcode"] img, canvas').first
                await fb.wait_for(state="visible", timeout=10000)
                qr_data = await _locator_to_data_url(fb)

            session.qrcode_data_url = qr_data
            session.status = "pending"
            logger.info(f"Douyin QR code acquired for session {session.session_id}")

            async def check_login():
                if "creator.douyin.com/creator-micro" in page.url:
                    login_markers = [
                        page.get_by_text("扫码登录", exact=True).first,
                        page.get_by_text("手机号登录", exact=True).first,
                        page.get_by_text("二维码失效", exact=True).first,
                        page.get_by_role("img", name="二维码").first,
                    ]
                    has_visible_marker = False
                    for marker in login_markers:
                        if await marker.count():
                            try:
                                if await marker.is_visible():
                                    has_visible_marker = True
                                    break
                            except Exception:
                                pass
                    if not has_visible_marker:
                        await page.wait_for_timeout(2000)
                        return True

                expired_box = page.get_by_text("二维码失效", exact=True).first
                if await expired_box.count() and await expired_box.is_visible():
                    await expired_box.click()
                    await page.wait_for_timeout(1500)
                    new_qr = await extract_qr()
                    if new_qr:
                        session.qrcode_data_url = new_qr
                return False

            await self._poll_for_login(session, b_session, check_login, "抖音扫码登录超时")

    async def _mock_qr_flow(self, session: QRSessionState):
        """Simulates QR generation and fast automatic login for tests"""
        session.qrcode_data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        session.status = "pending"
        await asyncio.sleep(0.5)
        session.storage_state = {
            "cookies": [{"name": "mock_session", "value": "mock_val_123", "domain": ".mock.com", "path": "/"}],
            "origins": [],
        }
        session.status = "success"
        session.user_info = {"username": "mock_creator", "display_name": "Mock Creator Pro"}


# Global singleton
auth_service = PlatformAuthService()
