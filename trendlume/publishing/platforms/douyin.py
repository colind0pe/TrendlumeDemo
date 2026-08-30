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
Douyin (抖音) Platform Publisher Adapter

Implements full browser automation for Douyin creator micro platform (creator.douyin.com).
"""

import asyncio
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from trendlume.models.metadata import (
    DouyinConstraints,
    DouyinDeclaration,
    DouyinVisibility,
)
from trendlume.models.publishing import (
    Credential,
    CredentialType,
    PlatformName,
    PublishJob,
    SocialAccount,
)
from trendlume.publishing.base import (
    AccountCheckResult,
    BasePlatformPublisher,
    PlatformCapabilities,
    PublishResult,
)
from trendlume.publishing.browser import BrowserManager
from trendlume.publishing.verification import verification_manager


async def _native_click(page, locator) -> bool:
    """
    Dispatches real mouse move and complete pointer/mouse event sequences for ByteDance Semi Design components.
    """
    try:
        await locator.scroll_into_view_if_needed(timeout=5000)
    except Exception:
        pass
    try:
        box = await locator.bounding_box()
    except Exception:
        box = None
    if not box:
        try:
            await locator.click(timeout=8000)
            return True
        except Exception:
            return False
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    try:
        await page.mouse.move(x, y)
        await asyncio.sleep(0.15)
        await page.mouse.click(x, y)
        await asyncio.sleep(0.2)
        await page.evaluate(
            """({x, y}) => {
                const el = document.elementFromPoint(x, y);
                if (!el) return;
                const opts = {bubbles:true,cancelable:true,composed:true,clientX:x,clientY:y,view:window,pointerId:1,pointerType:'mouse',isPrimary:true,button:0,buttons:1};
                for (const t of ['pointerover','pointerenter','pointerdown','mousedown','pointerup','mouseup','click']) {
                    const C = t.startsWith('pointer') ? PointerEvent : MouseEvent;
                    try { el.dispatchEvent(new C(t, opts)); } catch(e){ try{ el.dispatchEvent(new MouseEvent(t,opts)); }catch(_){} }
                }
            }""",
            {"x": x, "y": y},
        )
        return True
    except Exception:
        return False


async def _clear_blocking_overlays(page) -> None:
    """
    Clear blocking popovers/overlays (topics, mention suggestions, shepherd onboarding guides, lingering portals)
    and blur active inputs.
    """
    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass
    try:
        await page.evaluate(
            """() => {
                if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
                document.querySelectorAll('.shepherd-element, .shepherd-modal-overlay-container').forEach(e => e.remove());
                document.querySelectorAll('[class*="mention-wrapper"]').forEach(e => {
                    const p = e.closest('.semi-portal');
                    (p || e).remove();
                });
            }"""
        )
    except Exception:
        pass
    await asyncio.sleep(0.3)


async def _handle_sms_verification(
    page,
    job: Optional[PublishJob] = None,
    account: Optional[SocialAccount] = None,
    max_wait_seconds: int = 120,
) -> Optional[bool]:
    """
    Detects Douyin SMS verification modal ('接收短信验证码'), auto-clicks '获取验证码',
    registers an interactive verification request in verification_manager, awaits verification code from UI/API,
    inputs it, and submits verification.

    Returns:
        True if verification succeeded.
        False if verification modal was present but timed out waiting for code or failed.
        None if no verification modal was present.
    """
    try:
        sms_modal = page.locator(
            '.semi-modal-content:has-text("接收短信验证码"), .semi-modal-content:has-text("短信验证码"), div:has-text("接收短信验证码")'
        ).first
        sms_input = page.locator(
            'input[placeholder*="验证码"], input[type="tel"], input[placeholder*="短信"]'
        ).first

        has_modal = await sms_modal.count() and await sms_modal.is_visible()
        has_input = await sms_input.count() and await sms_input.is_visible()

        if not has_modal and not has_input:
            return None

        logger.warning("=" * 60)
        logger.warning("【抖音短信验证】检测到抖音发布触发手机短信二次验证弹窗！")

        # 1. Click "获取验证码" if visible
        get_code_btn = page.get_by_text("获取验证码", exact=True).first
        if not await get_code_btn.count():
            get_code_btn = page.locator(
                'button:has-text("获取验证码"), span:has-text("获取验证码"), div:has-text("获取验证码")'
            ).first

        if await get_code_btn.count() and await get_code_btn.is_visible():
            logger.info("Clicking '获取验证码' to request SMS verification code from Douyin...")
            try:
                await get_code_btn.click(timeout=3000)
            except Exception:
                await _native_click(page, get_code_btn)
            await asyncio.sleep(1)
            logger.warning("已自动点击「获取验证码」，短信已发送至您的手机，请在 UI 界面输入。")

        # 2. Register interactive verification request in verification_manager
        job_id = job.job_id if job else f"dy_{int(time.time())}"
        account_id = account.account_id if account else ""
        account_name = account.account_name if account else ""
        title = job.title if job else ""

        req = verification_manager.request_code(
            job_id=job_id,
            account_id=account_id,
            account_name=account_name,
            title=title,
            platform="douyin",
            prompt="抖音发布触发手机短信二次验证，已自动请求发送验证码。请在前端页面输入收到的短信验证码。",
            timeout_seconds=max_wait_seconds,
        )

        logger.warning(
            f"【抖音短信验证】已创建 UI 交互验证码请求 (Request ID: {req.request_id})，等待用户在 UI 界面输入验证码（最多 {max_wait_seconds} 秒）..."
        )
        logger.warning("=" * 60)

        # 3. Asynchronously wait for code submission from UI / API
        code = await verification_manager.wait_for_code(req.request_id)

        if not code:
            logger.warning(f"Douyin SMS verification timed out or cancelled after {max_wait_seconds}s (Request ID: {req.request_id}).")
            return False

        # 4. Enter code into input
        logger.info(f"Received verification code from UI: {code}. Entering into Douyin SMS input...")
        if await sms_input.count() and await sms_input.is_visible():
            await sms_input.click()
            await page.keyboard.press("Control+KeyA")
            await page.keyboard.press("Delete")
            await sms_input.fill(code)
            await asyncio.sleep(0.5)

        # 5. Click "验证" button
        verify_btn = page.locator(
            'div.uc-ui-verify_sms-verify_button:has-text("验证"), .semi-modal-content button:has-text("验证"), button:has-text("验证")'
        ).first
        if not await verify_btn.count():
            verify_btn = page.get_by_role("button", name="验证", exact=True).first

        if await verify_btn.count():
            logger.info("Clicking '验证' button...")
            try:
                await verify_btn.click(force=True, timeout=3000)
            except Exception:
                await _native_click(page, verify_btn)
        else:
            await page.keyboard.press("Enter")

        await asyncio.sleep(2)

        # 6. Verify modal is dismissed
        if await sms_modal.count():
            try:
                await sms_modal.wait_for(state="hidden", timeout=5000)
                logger.info("Douyin SMS verification passed and modal dismissed!")
                verification_manager.complete_request(req.request_id)
                return True
            except Exception:
                pass

        logger.info("Douyin SMS verification submitted.")
        verification_manager.complete_request(req.request_id)
        return True

    except Exception as e:
        logger.warning(f"Error during SMS verification handling: {e}")
        return False


async def _handle_auto_video_cover(page) -> bool:
    """
    If Douyin prompts '请设置封面后再发布' or displays recommendCover cards, auto-select recommended cover.
    """
    try:
        has_prompt = False
        for ptext in ["请设置封面后再发布", "请选择封面", "设置封面"]:
            p = page.get_by_text(ptext).first
            if await p.count() and await p.is_visible():
                has_prompt = True
                break

        recommend_cover = page.locator('[class^="recommendCover-"], [class*="recommend-cover"]').first
        if has_prompt or (await recommend_cover.count() and await recommend_cover.is_visible()):
            logger.info("Handling Douyin video cover prompt, selecting first recommended cover...")
            if await recommend_cover.count():
                try:
                    await recommend_cover.click(timeout=4000)
                except Exception:
                    await _native_click(page, recommend_cover)
                await asyncio.sleep(1)

                confirm_modal = page.locator(".semi-modal-content, .semi-modal-body").first
                if await confirm_modal.count() and await confirm_modal.is_visible():
                    confirm_btn = confirm_modal.get_by_role("button", name="确定", exact=True).first
                    if not await confirm_btn.count():
                        confirm_btn = page.get_by_role("button", name="确定").first
                    if await confirm_btn.count() and await confirm_btn.is_visible():
                        try:
                            await confirm_btn.click(timeout=3000)
                        except Exception:
                            await _native_click(page, confirm_btn)
                        await asyncio.sleep(1)
                logger.info("Recommended video cover applied.")
                return True
    except Exception as e:
        logger.warning(f"Error handling auto video cover: {e}")
    return False


async def _apply_custom_cover(page, cover_path: str) -> None:
    """
    Upload custom video cover image targeting the actual frame slot without confusing AI reference slots.
    """
    if not cover_path or not Path(cover_path).exists():
        return
    logger.info(f"Setting custom video cover from {cover_path}...")
    try:
        await _clear_blocking_overlays(page)
        cover_area = page.locator('[class*="cover-"]').filter(has=page.locator("img")).first
        if not await cover_area.count():
            cover_area = page.locator('[class*="cover"]').first

        cover_modal_str = "div.dy-creator-content-modal"
        cover_modal = page.locator(cover_modal_str).first
        opened = False

        for attempt in range(4):
            trigger = None
            for txt in ["编辑封面", "选择封面", "设置封面", "更换封面"]:
                t = page.get_by_text(txt, exact=True).first
                if await t.count() and await t.is_visible():
                    trigger = t
                    break
            if trigger is None:
                trigger = cover_area
            await _native_click(page, trigger)
            try:
                await page.wait_for_selector(cover_modal_str, timeout=4000)
                opened = True
                break
            except Exception:
                continue

        if not opened:
            logger.warning("Could not open cover modal, continuing with default cover")
            return

        await asyncio.sleep(1)
        # Target actual cover upload input, not AI reference input
        cover_upload = cover_modal.locator(
            ".semi-upload:has(.semi-upload-drag-area-main-text) input.semi-upload-hidden-input"
        ).first
        if await cover_upload.count() == 0:
            cover_upload = cover_modal.locator('input[type="file"][accept*="image"]').first
        if await cover_upload.count() == 0:
            cover_upload = cover_modal.locator("input.semi-upload-hidden-input").last

        await cover_upload.set_input_files(str(Path(cover_path).resolve()))
        await asyncio.sleep(2)

        # Wait for "完成" button to be enabled
        finish_btn = cover_modal.get_by_role("button", name="完成", exact=True).first
        if not await finish_btn.count():
            finish_btn = cover_modal.locator("button.semi-button").filter(has_text="完成").first

        for _ in range(20):
            if await finish_btn.count():
                cls = await finish_btn.get_attribute("class") or ""
                if "disabled" not in cls:
                    break
            await asyncio.sleep(0.5)

        # Click finish
        if await finish_btn.count() and await finish_btn.is_visible():
            await _native_click(page, finish_btn)
            await asyncio.sleep(1)

        # Handle potential secondary confirm
        for cname in ["确定", "确认", "仍然完成", "仍要完成", "继续"]:
            confirm = page.locator(".semi-modal-content").get_by_role("button", name=cname, exact=True).first
            if await confirm.count() and await confirm.is_visible():
                await _native_click(page, confirm)
                await asyncio.sleep(1)
                break

        # Dismiss if still open
        if await cover_modal.count() > 0:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

        logger.info("Custom video cover applied successfully")
    except Exception as ce:
        logger.warning(f"Failed to set custom cover: {ce}")


async def _apply_collection(page, collection_name: str) -> bool:
    """
    Select Douyin collection/series for the video (Semi Design select component).
    """
    if not collection_name or not str(collection_name).strip():
        return True
    collection_name = str(collection_name).strip()
    logger.info(f"Applying Douyin collection: '{collection_name}'...")
    try:
        await _clear_blocking_overlays(page)
        trigger = page.locator('[class*="select-collection-"]').first
        if not await trigger.count():
            logger.warning("未找到「添加合集」下拉框，跳过合集归集")
            return False
        selection = trigger.locator(".semi-select-selection")
        try:
            await selection.click(timeout=5000)
        except Exception:
            await _clear_blocking_overlays(page)
            await _native_click(page, selection)
        await asyncio.sleep(0.8)

        option = page.locator(".semi-select-option.collection-option").filter(
            has=page.locator(f'[class*="option-title-"]:text-is("{collection_name}")')
        )
        if not await option.count():
            option = page.locator(".semi-select-option").filter(has_text=collection_name)

        if not await option.count():
            logger.warning(f"合集下拉框未找到「{collection_name}」，跳过合集归集，保持未选状态")
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            return False

        try:
            await option.first.click(timeout=5000)
        except Exception:
            await _native_click(page, option.first)
        await asyncio.sleep(0.5)
        logger.info(f"已选择合集: {collection_name}")
        return True
    except Exception as exc:
        logger.warning(f"选择合集失败，跳过合集归集: {exc}")
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return False


async def _set_location(page, location: str) -> bool:
    """
    Set Douyin location (POI).
    """
    if not location or not str(location).strip():
        return True
    location = str(location).strip()
    logger.info(f"Setting Douyin location: '{location}'...")
    try:
        await _clear_blocking_overlays(page)
        loc_trigger = page.locator(
            'div.semi-select span:has-text("输入地理位置"), span:has-text("输入地理位置"), div.semi-select:has-text("添加标签") span:has-text("位置")'
        ).first
        if not await loc_trigger.count():
            logger.warning("未找到「输入地理位置」入口，跳过位置设置")
            return False

        try:
            await loc_trigger.click(timeout=4000)
        except Exception:
            await _native_click(page, loc_trigger)
        await asyncio.sleep(0.5)

        await page.keyboard.press("Backspace")
        await page.keyboard.type(location)
        await asyncio.sleep(1.5)

        opt = page.locator('div[role="listbox"] [role="option"], .semi-select-option').first
        if await opt.count():
            try:
                await opt.click(timeout=4000)
            except Exception:
                await _native_click(page, opt)
            logger.info(f"已设置地理位置: {location}")
            return True
        else:
            logger.warning(f"未找到匹配的地理位置选项「{location}」")
            await page.keyboard.press("Escape")
            return False
    except Exception as exc:
        logger.warning(f"设置地理位置失败: {exc}")
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return False


async def _set_product_link(page, product_link: str, product_title: str) -> bool:
    """
    Set Douyin e-commerce product link and short title.
    """
    if not product_link or not str(product_link).strip():
        return True
    product_link = str(product_link).strip()
    product_title = (product_title or "")[:10].strip()
    logger.info(f"Setting Douyin product link: {product_link} (title: {product_title})...")
    try:
        dropdown = page.locator(".semi-select").filter(has_text="添加标签").first
        if not await dropdown.count():
            add_tag_btn = page.get_by_text("添加标签").first
            if await add_tag_btn.count():
                dropdown = add_tag_btn.locator("xpath=ancestor::*[contains(@class, 'semi-select')]").first
        if not await dropdown.count():
            dropdown = page.locator(".semi-select").first

        if not await dropdown.count():
            logger.warning("未找到标签下拉框，跳过商品设置")
            return False

        await _native_click(page, dropdown)
        await asyncio.sleep(0.5)

        cart_opt = page.locator('[role="option"]:has-text("购物车"), .semi-select-option:has-text("购物车")').first
        if not await cart_opt.count():
            logger.warning("下拉列表中无「购物车」选项（账号可能未开通带货权限）")
            await page.keyboard.press("Escape")
            return False

        await _native_click(page, cart_opt)
        await asyncio.sleep(0.8)

        input_field = page.locator('input[placeholder="粘贴商品链接"]').first
        if not await input_field.count():
            logger.warning("未找到商品链接输入框")
            return False

        await input_field.fill(product_link)
        await asyncio.sleep(0.5)

        add_btn = page.locator('span:has-text("添加链接"), button:has-text("添加链接")').first
        btn_class = await add_btn.get_attribute("class") or ""
        if "disable" in btn_class or "disabled" in btn_class:
            logger.warning("「添加链接」按钮处于禁用状态")
            return False

        await _native_click(page, add_btn)
        await asyncio.sleep(1.5)

        error_modal = page.locator("text=未搜索到对应商品")
        if await error_modal.count() and await error_modal.is_visible():
            confirm_btn = page.locator('button:has-text("确定")').first
            if await confirm_btn.count():
                await confirm_btn.click()
            logger.warning("商品链接无效或未搜索到商品")
            return False

        short_title_input = page.locator('input[placeholder="请输入商品短标题"]').first
        if await short_title_input.count() and await short_title_input.is_visible():
            if product_title:
                await short_title_input.fill(product_title)
                await asyncio.sleep(0.5)

            finish_btn = page.locator('button:has-text("完成编辑")').first
            if await finish_btn.count():
                btn_cls = await finish_btn.get_attribute("class") or ""
                if "disabled" not in btn_cls:
                    await _native_click(page, finish_btn)
                    await asyncio.sleep(1)
                    logger.info("商品短标题与编辑已完成")
                    return True
                else:
                    cancel_btn = page.locator('button:has-text("取消")').first
                    if await cancel_btn.count():
                        await cancel_btn.click()
                    return False
        return True
    except Exception as exc:
        logger.warning(f"设置商品链接时出错: {exc}")
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return False


class DouyinPublisher(BasePlatformPublisher):
    """
    Douyin Platform Publisher Adapter
    """

    platform = PlatformName.DOUYIN
    capabilities = PlatformCapabilities(
        platform_name=PlatformName.DOUYIN,
        display_name="抖音",
        icon="🎵",
        supports_video=True,
        supports_images=False,
        supports_scheduling=True,
        max_title_length=DouyinConstraints.MAX_TITLE_LENGTH,
        max_description_length=DouyinConstraints.MAX_DESCRIPTION_LENGTH,
        max_tags=DouyinConstraints.MAX_TAGS,
        required_credential_type=CredentialType.COOKIE,
        custom_params_schema={
            "declaration": {
                "type": "string",
                "label": "自主声明",
                "options": DouyinDeclaration.get_options_with_empty(),
                "default": "",
            },
            "collection_name": {
                "type": "string",
                "label": "添加合集",
                "description": "归集到指定合集/系列名称",
                "default": "",
            },
            "location": {
                "type": "string",
                "label": "地理位置 (POI)",
                "description": "添加地理位置",
                "default": "",
            },
            "product_link": {
                "type": "string",
                "label": "商品链接",
                "description": "抖音精选联盟/小店商品链接",
                "default": "",
            },
            "product_title": {
                "type": "string",
                "label": "商品短标题",
                "description": "商品短标题 (最多10字)",
                "default": "",
            },
            "visibility": {
                "type": "string",
                "label": "谁可以看",
                "options": DouyinVisibility.ALL_OPTIONS,
                "default": DouyinVisibility.DEFAULT,
            },
            "allow_download": {"type": "boolean", "label": "允许下载", "default": True},
        },
    )

    async def check_account(
        self,
        account: SocialAccount,
        credential: Optional[Credential],
    ) -> AccountCheckResult:
        """Verify Douyin account login state via headless browser inspection"""
        if not credential or not credential.data:
            return AccountCheckResult(is_valid=False, error_message="未配置抖音 Cookie/Session 凭据")

        try:
            async with BrowserManager.get_session(
                credential.data, platform="douyin", headless=True, timeout_ms=30000
            ) as session:
                page = session.page
                await page.goto(
                    "https://creator.douyin.com/creator-micro/content/upload",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                await page.wait_for_timeout(2500)

                # Check for login prompts
                has_login = (
                    await page.get_by_text("手机号登录").count() > 0
                    or await page.get_by_text("扫码登录").count() > 0
                )
                if "content/upload" in page.url and not has_login:
                    # Extract username if available
                    username = account.username or ""
                    try:
                        name_el = page.locator(".name-text, .user-name, [class*='avatar-name']").first
                        if await name_el.count():
                            username = (await name_el.inner_text()).strip()
                    except Exception:
                        pass

                    return AccountCheckResult(
                        is_valid=True,
                        username=username or account.username,
                        display_name=username or account.display_name,
                    )
                else:
                    return AccountCheckResult(
                        is_valid=False,
                        error_message="抖音登录状态已失效，需要重新登录",
                    )
        except Exception as e:
            logger.error(f"Error checking Douyin account {account.account_id}: {e}")
            return AccountCheckResult(is_valid=False, error_message=f"检查失败: {e}")

    async def publish_video(
        self,
        job: PublishJob,
        account: SocialAccount,
        credential: Optional[Credential],
    ) -> PublishResult:
        """Publish video to Douyin via automated browser actions"""
        # 1. Validation checks
        validation_error = self.validate_publish_request(job, credential)
        if validation_error:
            return validation_error

        video_path = Path(job.video_path)

        # Validate schedule time if specified
        schedule_dt: Optional[datetime] = None
        if job.scheduled_at:
            try:
                schedule_dt = datetime.fromisoformat(job.scheduled_at)
                min_schedule_time = datetime.now() + timedelta(hours=2)
                if schedule_dt <= min_schedule_time:
                    return PublishResult(
                        success=False,
                        error_message="[VALIDATION_ERROR] 抖音定时发布时间必须大于当前时间 2 小时",
                    )
            except Exception as e:
                return PublishResult(
                    success=False,
                    error_message=f"[VALIDATION_ERROR] 定时发布时间格式不正确: {e}",
                )

        # 2. Browser Automation Execution
        try:
            async with BrowserManager.get_session(
                credential.data, platform="douyin", headless=True, timeout_ms=240000
            ) as session:
                page = session.page

                logger.info(f"Navigating to Douyin creator upload page for job {job.job_id}...")
                await page.goto(
                    "https://creator.douyin.com/creator-micro/content/upload",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                await page.wait_for_timeout(2000)

                # Check auth
                has_login = (
                    await page.get_by_text("手机号登录").count() > 0
                    or await page.get_by_text("扫码登录").count() > 0
                )
                if has_login or "content/upload" not in page.url:
                    return PublishResult(
                        success=False,
                        error_message="[AUTH_ERROR] 抖音 Cookie 已失效，请重新扫码登录",
                    )

                # 3. Upload video file
                logger.info(f"Setting input video file: {video_path}...")
                upload_input = page.locator(
                    'div.progress-div [class^="upload-btn-input"], input.upload-btn-input, div[class^="container"] input[accept]'
                ).first
                if not await upload_input.count():
                    upload_input = page.locator(
                        'div[class^="container"] input[type="file"], input[type="file"]'
                    ).first

                await upload_input.wait_for(state="attached", timeout=30000)
                await upload_input.set_input_files(str(video_path.resolve()))

                # 4. Wait for form rendering
                logger.info("Waiting for form rendering (up to 120s)...")
                title_input = page.locator('input[placeholder*="填写作品标题"]').first
                await title_input.wait_for(state="visible", timeout=120000)

                # 5. Fill title (max 30 characters)
                formatted_title = self.sanitize_title(job.title)
                await title_input.fill(formatted_title)
                logger.info(f"Filled video title: {formatted_title}")

                # 6. Fill description and hashtags
                desc_editor = page.locator('div.zone-container[contenteditable="true"]').first
                if await desc_editor.count():
                    await desc_editor.click()
                    await page.keyboard.press("Control+KeyA")
                    await page.keyboard.press("Delete")

                    if job.description:
                        await page.keyboard.type(job.description.strip())

                    for tag in (job.tags or [])[:10]:
                        tag_clean = tag.lstrip("#").strip()
                        if tag_clean:
                            await page.keyboard.type(f" #{tag_clean} ")
                            await asyncio.sleep(0.2)

                    await _clear_blocking_overlays(page)

                # 7. Wait for video file upload completion in the background
                logger.info("Waiting for video upload processing to complete...")
                for _ in range(60):  # up to 120s
                    if await page.locator('div.progress-div > div:has-text("上传失败")').count():
                        return PublishResult(
                            success=False,
                            error_message="[UPLOAD_ERROR] 抖音视频上传失败（平台提示上传失败）",
                        )
                    reupload_btn = page.locator(
                        '[class^="long-card"] div:has-text("重新上传"), div:has-text("重新上传")'
                    ).first
                    if await reupload_btn.count() and await reupload_btn.is_visible():
                        logger.info("Douyin video upload completed (reupload button detected).")
                        break
                    await asyncio.sleep(2)

                # 8. Apply Self Declaration if configured
                declaration = (
                    job.platform_custom_params.get("declaration")
                    or account.settings.get("declaration")
                )
                if declaration:
                    await self._apply_declaration(page, declaration)

                # 9. Apply Collection if configured
                collection_name = (
                    job.platform_custom_params.get("collection_name")
                    or account.settings.get("collection_name")
                )
                if collection_name:
                    await _apply_collection(page, collection_name)

                # 10. Apply Location (POI) if configured
                location = (
                    job.platform_custom_params.get("location")
                    or account.settings.get("location")
                )
                if location:
                    await _set_location(page, location)

                # 11. Apply E-commerce Product Link if configured
                product_link = (
                    job.platform_custom_params.get("product_link")
                    or account.settings.get("product_link")
                )
                product_title = (
                    job.platform_custom_params.get("product_title")
                    or account.settings.get("product_title")
                    or ""
                )
                if product_link:
                    await _set_product_link(page, product_link, product_title)

                # 12. Handle Custom Cover Image (if explicitly provided)
                cover_path = job.cover
                if cover_path and Path(cover_path).exists():
                    await _apply_custom_cover(page, str(cover_path))

                # 13. Apply switch toggles (e.g. allow_download)
                allow_download = job.platform_custom_params.get("allow_download", True)
                if allow_download is False:
                    download_switch = page.locator('div.semi-switch:has(input[type="checkbox"])').first
                    if await download_switch.count():
                        cls = await download_switch.get_attribute("class") or ""
                        if "semi-switch-checked" in cls:
                            await _native_click(page, download_switch)
                            await asyncio.sleep(0.5)

                # 14. Set Schedule Time if configured
                if schedule_dt:
                    logger.info(f"Setting Douyin schedule time: {schedule_dt}...")
                    sched_radio = page.locator("[class^='radio']:has-text('定时发布')").first
                    if await sched_radio.count():
                        await _native_click(page, sched_radio)
                        await asyncio.sleep(1)
                        time_input = page.locator('.semi-input[placeholder="日期和时间"]').first
                        if await time_input.count():
                            await _native_click(page, time_input)
                            await page.keyboard.press("Control+KeyA")
                            await page.keyboard.type(schedule_dt.strftime("%Y-%m-%d %H:%M"))
                            await page.keyboard.press("Enter")
                            await asyncio.sleep(1)
                    await _clear_blocking_overlays(page)

                # 15. Active Publish and Redirection Polling Loop
                logger.info("Starting active Douyin publish submission loop...")
                publish_success = False
                start_time = time.time()
                max_publish_wait_seconds = 90

                while time.time() - start_time < max_publish_wait_seconds:
                    # 1. Clear any lingering popover overlays
                    await _clear_blocking_overlays(page)

                    # 2. Check if already redirected to content/manage
                    if "content/manage" in page.url:
                        logger.info("Douyin content/manage redirection detected!")
                        publish_success = True
                        break

                    # 3. Check and handle SMS Verification modal if present
                    sms_result = await _handle_sms_verification(page, job=job, account=account, max_wait_seconds=120)
                    if sms_result is False:
                        return PublishResult(
                            success=False,
                            error_message="[AUTH_ERROR] 触发抖音手机短信二次验证：已自动请求发送验证码，请在前端界面输入验证码后重试发布",
                        )
                    if sms_result is True:
                        logger.info("SMS verification completed, waiting for publish response...")
                        await asyncio.sleep(2)
                        if "content/manage" in page.url:
                            publish_success = True
                            break

                    # 4. Check for fatal error toast
                    err_locator = page.locator(".semi-toast-error").first
                    if await err_locator.count() and await err_locator.is_visible():
                        err_text = (await err_locator.inner_text()).strip()
                        if "发布失败" in err_text or "违规" in err_text:
                            return PublishResult(
                                success=False,
                                error_message=f"[UPLOAD_ERROR] 抖音发布失败: {err_text}",
                            )

                    # 5. Resolve cover prompts (e.g. "请设置封面后再发布")
                    await _handle_auto_video_cover(page)

                    # 6. Resolve secondary modal confirm buttons
                    modal_dialog = page.locator(".semi-modal-content, .semi-modal-body").first
                    if await modal_dialog.count() and await modal_dialog.is_visible():
                        modal_txt = await modal_dialog.inner_text()
                        if "短信验证码" not in modal_txt and "选择声明类型" not in modal_txt:
                            for cname in ["确定", "确认", "继续发布", "立即发布", "仍要发布", "我知道了"]:
                                confirm = modal_dialog.get_by_role("button", name=cname, exact=True).first
                                if await confirm.count() and await confirm.is_visible():
                                    logger.info(f"Clicking secondary modal button: {cname}")
                                    try:
                                        await confirm.click(timeout=3000)
                                    except Exception:
                                        await _native_click(page, confirm)
                                    await asyncio.sleep(1)
                                    break

                    # 7. Locate the REAL bottom publish button (exclude sidebar [+ 作品发布])
                    publish_btn = page.get_by_role("button", name="发布", exact=True).first
                    if not await publish_btn.count():
                        publish_btn = page.locator('button:text-is("发布")').last
                    if not await publish_btn.count():
                        publish_btn = page.locator(
                            'div[class*="footer"] button:has-text("发布"), '
                            'div[class*="content"] button:has-text("发布"), '
                            'button.button-primary:has-text("发布"), '
                            'button.semi-button-primary:has-text("发布"), '
                            'button:has-text("发布")'
                        ).filter(has_not_text="作品发布").last

                    if await publish_btn.count() and await publish_btn.is_visible():
                        btn_class = await publish_btn.get_attribute("class") or ""
                        aria_disabled = await publish_btn.get_attribute("aria-disabled") or ""
                        if "disabled" not in btn_class and aria_disabled != "true":
                            logger.info("Clicking Douyin bottom form publish button...")
                            try:
                                await publish_btn.scroll_into_view_if_needed(timeout=3000)
                            except Exception:
                                pass
                            try:
                                await publish_btn.click(force=True, timeout=5000)
                            except Exception:
                                await _native_click(page, publish_btn)

                    # 8. Wait for URL redirection to content/manage
                    try:
                        await page.wait_for_url("**/creator-micro/content/manage**", timeout=4000)
                        logger.info("Douyin content/manage redirection detected via wait_for_url!")
                        publish_success = True
                        break
                    except Exception:
                        pass

                    if "content/manage" in page.url:
                        publish_success = True
                        break

                    await asyncio.sleep(1.5)

                if not publish_success and "content/manage" not in page.url:
                    try:
                        Path("temp").mkdir(exist_ok=True)
                        screenshot_path = "temp/douyin_publish_failed.png"
                        await page.screenshot(path=screenshot_path, full_page=True)
                        logger.warning(f"Saved failure diagnostic screenshot to {screenshot_path}")
                    except Exception:
                        pass

                    err_locator = page.locator(
                        ".semi-toast-error, .semi-toast-warning, div:has-text('发布失败')"
                    ).first
                    if await err_locator.count() and await err_locator.is_visible():
                        err_text = (await err_locator.inner_text()).strip()
                        return PublishResult(
                            success=False,
                            error_message=f"[UPLOAD_ERROR] 抖音发布失败: {err_text}",
                        )
                    return PublishResult(
                        success=False,
                        error_message="[UPLOAD_ERROR] 抖音发布确认超时（页面未跳转至作品管理）",
                    )

                post_id = f"dy_{int(time.time())}_{account.account_id}"
                logger.info(f"Douyin video publish succeeded for job {job.job_id}")

                return PublishResult(
                    success=True,
                    platform_post_id=post_id,
                    post_url="https://creator.douyin.com/creator-micro/content/manage",
                    extra_info={"published_title": formatted_title},
                )

        except Exception as e:
            logger.error(f"Failed Douyin publishing execution for job {job.job_id}: {e}")
            return self.format_error(e, fallback_message="抖音发布失败")

    async def _apply_declaration(self, page, declaration: str) -> bool:
        """
        Select self-declaration option in Douyin form with keyword fuzzy matching
        and guaranteed modal dismissal so it never leaves a blocking overlay.
        """
        if not declaration or not str(declaration).strip():
            return True

        decl_str = str(declaration).strip()
        logger.info(f"Applying Douyin self-declaration: '{decl_str}'...")

        try:
            await _clear_blocking_overlays(page)

            # 1. Locate entry button to open modal
            entry = None
            for etext in ["请选择自主声明", "请选择声明类型", "添加自主声明", "自主声明", "作品声明"]:
                cand = page.get_by_text(etext).first
                if await cand.count():
                    entry = cand
                    break

            if entry is None:
                logger.warning("Could not find Douyin self-declaration entry button, skipping")
                return False

            try:
                await entry.scroll_into_view_if_needed(timeout=3000)
            except Exception:
                pass
            try:
                await entry.click(timeout=4000)
            except Exception:
                await _native_click(page, entry)

            await asyncio.sleep(1)

            # 2. Locate dialog container
            dialog = page.locator(".semi-modal-content").filter(has_text="请选择声明类型").first
            if await dialog.count() == 0:
                dialog = page.locator(".semi-modal-content, .semi-modal-body").first

            if await dialog.count() == 0:
                logger.warning("Douyin self-declaration modal dialog not opened, continuing")
                return False

            await dialog.wait_for(state="visible", timeout=6000)

            # 3. Fuzzy keyword mapping for Douyin standard declaration radio options
            keyword_map = [
                (["个人观点", "仅供参考", "观点", "见解"], "个人观点"),
                (["AI", "ai", "人工智能", "算法生成"], "AI生成"),
                (["转载", "网络", "取材"], "转载"),
                (["虚构", "娱乐", "演绎"], "虚构"),
            ]

            target_kw = decl_str
            for kw_list, mapped_val in keyword_map:
                if any(k in decl_str for k in kw_list):
                    target_kw = mapped_val
                    break

            # 4. Search and select matching radio option
            option = None
            # Try exact addon text
            exact_opt = dialog.locator("label.semi-radio").filter(
                has=page.locator(f'.semi-radio-addon:text-is("{decl_str}")')
            ).first
            if await exact_opt.count():
                option = exact_opt

            # Try has_text with decl_str
            if option is None:
                cand_opt = dialog.locator("label.semi-radio").filter(has_text=decl_str).first
                if await cand_opt.count():
                    option = cand_opt

            # Try has_text with target_kw
            if option is None and target_kw != decl_str:
                cand_opt = dialog.locator("label.semi-radio").filter(has_text=target_kw).first
                if await cand_opt.count():
                    option = cand_opt

            # Try iterating all radio options in the modal
            if option is None:
                radios = dialog.locator("label.semi-radio")
                count = await radios.count()
                for i in range(count):
                    r = radios.nth(i)
                    txt = await r.inner_text()
                    if decl_str in txt or target_kw in txt or any(k in txt for k in ["个人观点", "AI", "转载", "虚构"] if k in decl_str):
                        option = r
                        break

            if option is not None:
                try:
                    await option.click(timeout=4000)
                except Exception:
                    await _native_click(page, option)
                await asyncio.sleep(0.5)

                # 5. Click Confirm button
                confirm_btn = dialog.locator("button.semi-button-primary").filter(has_text="确定").first
                if await confirm_btn.count() == 0:
                    confirm_btn = dialog.get_by_role("button", name="确定").first
                if await confirm_btn.count():
                    try:
                        await confirm_btn.click(timeout=4000)
                    except Exception:
                        await _native_click(page, confirm_btn)

                # Wait for modal to be dismissed
                try:
                    await dialog.wait_for(state="hidden", timeout=4000)
                    logger.info(f"Douyin self-declaration '{decl_str}' selected and modal closed.")
                    return True
                except Exception:
                    pass

            # 6. Safety Dismissal: If option was not matched or modal failed to close, force dismiss modal
            logger.warning(
                f"Could not cleanly complete declaration for '{decl_str}', force closing modal to avoid blocking publish..."
            )
            try:
                close_btn = dialog.locator(".semi-modal-close").first
                if await close_btn.count():
                    await close_btn.click(timeout=2000)
            except Exception:
                pass
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            await asyncio.sleep(0.5)
            await _clear_blocking_overlays(page)
            return False

        except Exception as e:
            logger.warning(f"Error setting Douyin declaration: {e}")
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            await _clear_blocking_overlays(page)
            return False
