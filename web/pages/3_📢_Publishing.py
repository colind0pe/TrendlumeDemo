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
Publishing Center - Multi-platform Content Matrix, Queuing & Video Publishing
Tabs:
1. 📊 概览与发布 (Overview & Quick Dispatch)
2. 📦 批量矩阵发布 (Bulk Matrix Dispatch)
3. 📑 模板库 (Publishing Templates)
4. 👥 账号管理 (Accounts & QR Login)
5. 📋 队列与历史 (Queue & History)
"""
# ruff: noqa: E402

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to sys.path
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from trendlume.models.metadata import (
    DouyinConstraints,
    DouyinDeclaration,
    DouyinVisibility,
)
from trendlume.models.publishing import (
    AccountStatus,
    CredentialType,
    PlatformName,
    PublishJobStatus,
)
from trendlume.publishing.base import PlatformCapabilities
from trendlume.publishing.cookie_helper import normalize_storage_state
from web.components.header import render_header
from web.state.session import get_trendlume, init_i18n, init_session_state
from web.utils.async_helpers import run_async

# Page config
st.set_page_config(
    page_title="Publishing Center - Trendlume",
    page_icon="📢",
    layout="wide",
)


def get_status_badge(status: str) -> str:
    """Return colored markdown badge for status using model definitions"""
    if status in PublishJobStatus.LABELS:
        return PublishJobStatus.get_badge(status)
    if status in AccountStatus.LABELS:
        return AccountStatus.get_badge(status)
    return f"⚪ {status}"


def get_platform_icon(platform: str) -> str:
    """Return platform emoji or tag"""
    return PlatformName.get_display_name(platform)


def render_capability_form(
    caps: PlatformCapabilities,
    key_prefix: str,
    default_title: str = "",
    default_desc: str = "",
    default_tags: Optional[List[str]] = None,
    default_custom_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Capability-Driven Dynamic Form Engine.
    Dynamically renders title, description, tags, and custom metadata inputs purely based on PlatformCapabilities.
    Zero hardcoded 'if platform == ...' branches.
    """
    default_tags = default_tags or []
    default_custom_params = default_custom_params or {}

    # 1. Title Input bounded by max_title_length
    title_label = f"标题 (最大 {caps.max_title_length} 字)"
    initial_title = default_title[: caps.max_title_length]
    title = st.text_input(
        title_label,
        value=initial_title,
        max_chars=caps.max_title_length,
        key=f"{key_prefix}_title",
    )

    # 2. Description Input bounded by max_description_length
    desc_label = f"正文/简介 (最大 {caps.max_description_length} 字)"
    description = st.text_area(
        desc_label,
        value=default_desc[: caps.max_description_length],
        max_chars=caps.max_description_length,
        key=f"{key_prefix}_desc",
        height=90,
    )

    # 3. Tags Input bounded by max_tags
    tags_str = ", ".join(default_tags[: caps.max_tags])
    raw_tags = st.text_input(
        f"话题标签 (最多 {caps.max_tags} 个，以英文逗号分隔)",
        value=tags_str,
        key=f"{key_prefix}_tags",
    )
    parsed_tags = [t.strip().lstrip("#") for t in raw_tags.split(",") if t.strip()][: caps.max_tags]

    # 4. Custom Parameters from custom_params_schema
    custom_params: Dict[str, Any] = {}
    if caps.custom_params_schema:
        st.markdown(f"**🔧 {caps.display_name} 平台专属参数**")
        c_cols = st.columns(min(len(caps.custom_params_schema), 3))
        for idx, (param_key, param_spec) in enumerate(caps.custom_params_schema.items()):
            col = c_cols[idx % len(c_cols)]
            with col:
                p_type = param_spec.get("type", "string")
                p_label = param_spec.get("label", param_key)
                p_options = param_spec.get("options")
                p_default = default_custom_params.get(param_key, param_spec.get("default"))

                if p_options and isinstance(p_options, list):
                    def_idx = p_options.index(p_default) if p_default in p_options else 0
                    val = st.selectbox(p_label, options=p_options, index=def_idx, key=f"{key_prefix}_cp_{param_key}")
                    custom_params[param_key] = val
                elif p_type == "boolean":
                    val = st.checkbox(p_label, value=bool(p_default), key=f"{key_prefix}_cp_{param_key}")
                    custom_params[param_key] = val
                else:
                    val = st.text_input(p_label, value=str(p_default or ""), key=f"{key_prefix}_cp_{param_key}")
                    custom_params[param_key] = val

    return {
        "title": title,
        "description": description,
        "tags": parsed_tags,
        "custom_params": custom_params,
    }


# ============================================================================
# Tab 1: Publishing Console (Unified Single/Bulk Dispatch)
# ============================================================================

def render_publishing_console_tab(trendlume):
    """Tab 1: High level KPI summary and unified multi-video x multi-account publisher"""
    st.subheader("🚀 发布控制台 (Publishing Console)")
    st.markdown("支持勾选一个或多个视频，分发到一个或多个社交账号。")

    accounts = run_async(trendlume.publishing.list_accounts())
    active_accounts = [a for a in accounts if a.status == AccountStatus.ACTIVE]
    templates = run_async(trendlume.publishing.list_templates())
    tasks = run_async(trendlume.tasks.list_tasks(limit=50))
    completed_tasks = [t for t in tasks if t.status == "completed" and t.video_path]

    if not active_accounts:
        st.warning("⚠️ 当前暂无处于【正常】状态的社交账号。请前往【👥 账号管理】标签页扫码登录或导入 Cookie。")

    # 1. Source Video Selection
    st.markdown("##### 1️⃣ 选择要发布的视频")
    if not completed_tasks:
        st.info("💡 暂无已完成的生成视频任务，可在下方输入本地视频路径。")
    
    selected_videos = []
    
    v_cols = st.columns(2)
    for idx, t in enumerate(completed_tasks):
        col = v_cols[idx % 2]
        with col:
            chk = st.checkbox(
                f"🎬 **{t.title or '未命名视频'}** (`{t.task_id[:8]}`)",
                value=False,
                key=f"bulk_v_{t.task_id}",
            )
            if chk:
                selected_videos.append({
                    "task_id": t.task_id,
                    "video_path": t.video_path,
                    "title": t.title or "智能创作优质视频",
                    "description": getattr(t, "narration_text", "") or "",
                    "tags": ["AI创作", "爆款视频"],
                })
                
    st.markdown("###### 或添加本地视频")
    local_video = st.text_input("本地视频绝对路径", value="", placeholder="D:/Videos/my_video.mp4")
    if local_video:
        selected_videos.append({
            "task_id": None,
            "video_path": local_video,
            "title": "本地上传视频",
            "description": "",
            "tags": ["本地视频"],
        })

    if not selected_videos:
        st.info("👉 请至少选择一个视频。")
        return

    # 2. Template Selector
    st.markdown("##### 2️⃣ 选择发布模板与错峰策略")
    col_tpl, col_stg, col_sch = st.columns([1, 1, 1.5])
    
    selected_template_id = None
    with col_tpl:
        if templates:
            tpl_options = {"(不使用模板)": None}
            for t in templates:
                tpl_options[f"📑 {t.template_name} ({t.description or '无描述'})"] = t.template_id
            tpl_choice = st.selectbox("应用发布模板", list(tpl_options.keys()))
            selected_template_id = tpl_options[tpl_choice]
            
    with col_stg:
        interval_mins = st.number_input("视频错峰间隔 (分钟)", min_value=0, max_value=1440, value=15, step=5)
        
    scheduled_iso = None
    with col_sch:
        use_sched = st.checkbox("定时发布", value=False)
        if use_sched:
            default_sched = datetime.now() + timedelta(hours=2)
            c1, c2 = st.columns(2)
            sched_date = c1.date_input("日期", value=default_sched.date())
            sched_time = c2.time_input("时间", value=default_sched.time())
            combined = datetime.combine(sched_date, sched_time)
            scheduled_iso = combined.isoformat()

    # 3. Target Accounts Selection
    st.markdown("##### 3️⃣ 选择目标账号矩阵")
    if not active_accounts:
        st.error("没有可用的激活账号，请先添加账号。")
        return

    selected_acc_ids = []
    acc_cols = st.columns(min(len(active_accounts), 4) or 1)
    for idx, acc in enumerate(active_accounts):
        col = acc_cols[idx % len(acc_cols)]
        with col:
            is_checked = st.checkbox(
                f"{get_platform_icon(acc.platform)}\n\n**{acc.account_name}** ({acc.display_name or acc.username or '创作者'})",
                value=False,
                key=f"acc_sel_{acc.account_id}",
            )
            if is_checked:
                selected_acc_ids.append(acc.account_id)

    if not selected_acc_ids:
        st.info("👉 请勾选上方至少一个发布目标账号。")
        return

    # 4. Dynamic Form Overrides for Selected Accounts
    st.markdown("##### 📝 各平台文案与参数微调")
    account_overrides: Dict[str, Any] = {}
    
    # Use the first selected video as base for previewing overrides
    base_video = selected_videos[0]

    for acc_id in selected_acc_ids:
        acc = next(a for a in active_accounts if a.account_id == acc_id)
        pub = trendlume.publishing.registry.get_publisher(acc.platform)
        caps = pub.capabilities

        cur_title = base_video["title"]
        cur_desc = base_video["description"]
        cur_tags = list(base_video["tags"])
        cur_cp = {}

        if selected_template_id:
            adapted = run_async(
                trendlume.publishing.apply_template_to_content(
                    template_id=selected_template_id,
                    base_title=cur_title,
                    base_description=cur_desc,
                    base_tags=cur_tags,
                    platform=acc.platform,
                )
            )
            cur_title = adapted["title"]
            cur_desc = adapted["description"]
            cur_tags = adapted["tags"]
            cur_cp = adapted["platform_custom_params"]

        with st.expander(f"{get_platform_icon(acc.platform)} - {acc.account_name} (参数覆盖)", expanded=False):
            form_res = render_capability_form(
                caps=caps,
                key_prefix=f"ov_{acc.account_id}",
                default_title=cur_title,
                default_desc=cur_desc,
                default_tags=cur_tags,
                default_custom_params=cur_cp,
            )
            account_overrides[acc.account_id] = {
                "title": form_res["title"],
                "description": form_res["description"],
                "tags": form_res["tags"],
                "platform_custom_params": form_res["custom_params"],
            }

    # 5. Submit Batch Dispatch Button
    total_matrix_jobs = len(selected_videos) * len(selected_acc_ids)
    st.info(f"📊 矩阵计算: 已选 **{len(selected_videos)}** 个视频 $\\times$ **{len(selected_acc_ids)}** 个账号 = **{total_matrix_jobs}** 个独立发布任务。")
    
    if st.button("🚀 启动发布 (Dispatch)", type="primary", use_container_width=True, disabled=(total_matrix_jobs == 0)):
        try:
            created_jobs = run_async(
                trendlume.publishing.create_bulk_matrix_jobs(
                    video_items=selected_videos,
                    account_ids=selected_acc_ids,
                    template_id=selected_template_id,
                    start_scheduled_at=scheduled_iso,
                    interval_minutes=interval_mins,
                    account_overrides=account_overrides,
                )
            )
            st.success(f"🎉 成功创建 {len(created_jobs)} 个发布任务并加入后台调度队列！")
            st.balloons()
        except Exception as e:
            st.error(f"创建发布任务失败: {e}")


# ============================================================================
# Tab 3: Templates Management
# ============================================================================

def render_templates_tab(trendlume):
    """Tab 3: Publish Templates Management"""
    st.subheader("📑 发布模板库 (Publishing Templates)")
    st.markdown("创建与管理跨平台文案预设，自动为不同平台适配标题前缀/后缀、话题标签与分类。")

    templates = run_async(trendlume.publishing.list_templates())

    with st.expander("➕ 新建发布模板 (Create New Template)", expanded=len(templates) == 0):
        t_name = st.text_input("模板名称", placeholder="例如: 东方美学国风系列 / 科技硬核拆解")
        t_desc = st.text_area("模板说明", placeholder="适用于国风文化类短视频分发")

        st.markdown("###### 🎵 抖音发布预设规则")
        configs: Dict[str, Any] = {}

        dy_title = st.text_input("抖音标题模板 (可用 {title} 占位符, <=30字)", value="{title} #国风 #传统文化", key="tpl_dy_t")
        dy_desc = st.text_area("抖音正文/描述", value="{description}", key="tpl_dy_d")
        dy_tags = st.text_input("抖音默认标签 (逗号分隔, 最多10个)", value="国风, 东方美学, AI视觉", key="tpl_dy_tags")

        col_cp1, col_cp2 = st.columns(2)
        with col_cp1:
            dy_decl = st.selectbox(
                "自主声明预设",
                DouyinDeclaration.get_options_with_empty(),
                key="tpl_dy_decl",
            )
            dy_collection = st.text_input("默认归集合集/系列名称", placeholder="例如: 国风动画合集 (留空则不归集)", key="tpl_dy_col")
            dy_prod_link = st.text_input("默认商品链接 (选填)", placeholder="抖音商品分享链接", key="tpl_dy_plink")
        with col_cp2:
            dy_vis = st.selectbox(
                "可见范围预设",
                DouyinVisibility.ALL_OPTIONS,
                format_func=DouyinVisibility.get_label,
                key="tpl_dy_vis",
            )
            dy_location = st.text_input("默认地理位置 POI", placeholder="例如: 北京·故宫博物院", key="tpl_dy_loc")
            dy_prod_title = st.text_input("默认商品短标题 (<=10字)", placeholder="商品短标题", key="tpl_dy_ptitle")

        configs[PlatformName.DOUYIN] = {
            "title_template": dy_title,
            "description_template": dy_desc,
            "tags": [t.strip() for t in dy_tags.split(",") if t.strip()],
            "platform_custom_params": {
                "declaration": dy_decl,
                "visibility": dy_vis,
                "collection_name": dy_collection,
                "location": dy_location,
                "product_link": dy_prod_link,
                "product_title": dy_prod_title,
            },
        }

        if st.button("💾 保存模板 (Save Template)", type="primary"):
            if not t_name:
                st.error("请输入模板名称！")
            else:
                try:
                    run_async(
                        trendlume.publishing.create_template(
                            template_name=t_name,
                            description=t_desc,
                            platform_configs=configs,
                        )
                    )
                    st.success(f"模板【{t_name}】保存成功！")
                    st.rerun()
                except Exception as e:
                    st.error(f"保存模板失败: {e}")

    # Existing Templates List
    if not templates:
        st.info("💡 暂无发布模板，点击上方展开新建。")
        return

    st.markdown("##### 📚 现有模板列表")
    for tpl in templates:
        with st.container(border=True):
            col_t1, col_t2 = st.columns([4, 1])
            with col_t1:
                st.markdown(f"#### 📑 {tpl.template_name}")
                st.caption(f"ID: `{tpl.template_id}` | 创建于: {tpl.created_at[:19]} | 说明: {tpl.description or '无'}")
                st.markdown(f"**支持平台配置**: {', '.join(get_platform_icon(p) for p in tpl.platform_configs.keys())}")
            with col_t2:
                if st.button("🗑️ 删除", key=f"del_tpl_{tpl.template_id}", type="secondary"):
                    run_async(trendlume.publishing.delete_template(tpl.template_id))
                    st.rerun()


@st.fragment(run_every=2)
def render_pending_verifications_banner(trendlume):
    """Auto-refreshing banner for pending SMS/2FA verification requests across active publishing jobs"""
    try:
        pending = trendlume.publishing.list_pending_verifications()
    except Exception:
        pending = []

    if not pending:
        return

    for req in pending:
        with st.container(border=True):
            st.markdown("#### 📱 短信验证码确认 (SMS Verification Required)")
            st.warning(
                f"⚠️ 任务 **{req.title or req.job_id}**（平台: **{get_platform_icon(req.platform)}** | 账号: **{req.account_name or req.account_id}**）"
                f"在发布过程中触发了手机短信二次安全验证。\n\n"
                f"**短信验证码已自动发送至绑定的手机号，请在下方输入验证码并点击提交：**"
            )

            c_inp, c_sub, c_can = st.columns([3, 1.2, 1])
            with c_inp:
                code_val = st.text_input(
                    "短信验证码",
                    key=f"sms_code_in_{req.request_id}",
                    placeholder="请输入 4~6 位手机短信验证码 (如 123456)",
                    label_visibility="collapsed",
                )
            with c_sub:
                rem = req.remaining_seconds
                st.caption(f"⏳ 有效期剩余: **{rem}** 秒")
                if st.button("✅ 提交验证码", type="primary", key=f"btn_sub_code_{req.request_id}", use_container_width=True):
                    if not code_val or len(code_val.strip()) < 4:
                        st.error("请输入至少 4 位有效验证码！")
                    else:
                        ok = trendlume.publishing.submit_verification_code(req.request_id, code_val.strip())
                        if ok:
                            st.success("🎉 验证码已提交！后台正在自动填入并完成发布验证...")
                            st.rerun()
                        else:
                            st.error("验证码提交失败或会话已过期，请重试。")
            with c_can:
                if st.button("🚫 取消验证", type="secondary", key=f"btn_can_code_{req.request_id}", use_container_width=True):
                    trendlume.publishing.cancel_verification(req.request_id)
                    st.info("已取消验证请求。")
                    st.rerun()


@st.fragment(run_every=2)
def render_qr_session_card(trendlume, sess_id: str):
    """Auto-polling QR code session component"""
    sess_state = trendlume.publishing.get_qr_session(sess_id)
    if not sess_state:
        st.info("会话已失效或已关闭。")
        if st.button("关闭", key=f"close_empty_{sess_id}"):
            st.session_state.pop("active_qr_session", None)
            st.rerun()
        return

    st.markdown(f"**当前登录状态**: `{sess_state.status}`")

    if sess_state.status == "initializing":
        st.spinner("🚀 正在启动浏览器并获取二维码，请稍候...")
        st.caption("🔄 正在加载二维码 (约 3~5 秒)...")
    elif sess_state.qrcode_data_url:
        st.image(sess_state.qrcode_data_url, caption="请使用对应手机 App 扫码登录", width=220)

    if sess_state.status == "success":
        st.success("🎉 扫码登录成功！凭证已安全保存。")
        if st.button("✅ 绑定并完成账号注册", type="primary", key=f"bind_acc_{sess_id}"):
            alias = st.session_state.get("qr_account_alias") or "My Account"
            run_async(
                trendlume.publishing.create_account(
                    platform=sess_state.platform,
                    account_name=alias,
                    username=sess_state.user_info.get("username", ""),
                    display_name=sess_state.user_info.get("display_name", alias),
                    credential_type=CredentialType.STORAGE_STATE,
                    credential_data=sess_state.storage_state,
                )
            )
            st.session_state.pop("active_qr_session", None)
            st.rerun()
    elif sess_state.status in ["error", "timeout"]:
        st.error(f"登录失败: {sess_state.error_message}")
        if st.button("关闭会话", key=f"close_err_{sess_id}"):
            st.session_state.pop("active_qr_session", None)
            st.rerun()
    else:
        st.caption("🔄 等待手机扫码确认... (每 2 秒自动刷新状态)")
        if st.button("🚫 取消扫码会话", key=f"cancel_qr_{sess_id}", type="secondary"):
            trendlume.publishing.cancel_qr_session(sess_id)
            st.session_state.pop("active_qr_session", None)
            st.rerun()


# ============================================================================
# Tab 4: Accounts Management & Live QR Login
# ============================================================================

def render_accounts_tab(trendlume):
    """Tab 4: Full Account management with QR login and stats"""
    st.subheader("👥 社交账号管理 (Social Accounts)")

    accounts = run_async(trendlume.publishing.list_accounts())

    # Add Account Actions
    col_act1, col_act2 = st.columns([1, 1])

    with col_act1:
        with st.expander("📱 扫码授权添加新账号 (QR Login)", expanded=True):
            target_platform = st.selectbox(
                "选择平台",
                PlatformName.ALL_PLATFORMS,
                format_func=get_platform_icon,
                key="qr_plat_sel",
            )
            account_alias = st.text_input("账号自定义别名", value=f"{target_platform.capitalize()}_Main", key="qr_alias")

            if st.button("🚀 启动扫码登录会话", type="primary", key="btn_start_qr"):
                try:
                    session = trendlume.publishing.start_qr_session(target_platform)
                    st.session_state["active_qr_session"] = session.session_id
                    st.session_state["qr_account_alias"] = account_alias
                    st.success(f"已创建扫码会话 `{session.session_id}`，正在加载二维码...")
                    st.rerun()
                except Exception as e:
                    st.error(f"启动失败: {e}")

            # Active QR Code Display & Auto-Refreshing Status Poller
            if "active_qr_session" in st.session_state:
                sess_id = st.session_state["active_qr_session"]
                render_qr_session_card(trendlume, sess_id)

    with col_act2:
        with st.expander("🔑 手动导入 Cookie / Storage State", expanded=False):
            imp_plat = st.selectbox(
                "导入平台",
                PlatformName.ALL_PLATFORMS,
                format_func=get_platform_icon,
                key="imp_plat_sel",
            )
            imp_alias = st.text_input("账号名称", value=f"{imp_plat.capitalize()}_Cookie", key="imp_alias")
            raw_cookie = st.text_area("Cookie 字符串或 Storage State JSON", height=130, key="imp_cookie")

            if st.button("💾 验证并保存 Cookie", key="btn_save_cookie"):
                if not raw_cookie:
                    st.error("Cookie 不能为空！")
                else:
                    try:
                        normalized = normalize_storage_state(raw_cookie, platform=imp_plat)
                        run_async(
                            trendlume.publishing.create_account(
                                platform=imp_plat,
                                account_name=imp_alias,
                                credential_type=CredentialType.STORAGE_STATE,
                                credential_data=normalized,
                            )
                        )
                        st.success("账号与 Cookie 保存成功！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"导入失败: {e}")

    # Accounts List & Health Check
    st.markdown("##### 📋 已授权社交账号矩阵")
    if not accounts:
        st.info("暂无绑定的社交账号。")
        return

    for acc in accounts:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([2.5, 2, 2, 1.5])
            with col1:
                st.markdown(f"**{get_platform_icon(acc.platform)}** - **{acc.account_name}**")
                st.caption(f"ID: `{acc.account_id}` | 昵称: {acc.display_name or acc.username or '未获取'}")
            with col2:
                st.markdown(f"**状态**: {get_status_badge(acc.status)}")
                st.caption(f"已发布: **{acc.published_count}** | 失败: **{acc.failed_count}**")
            with col3:
                last_chk = acc.last_checked_at[:19] if acc.last_checked_at else "未检查"
                st.caption(f"最后检查: {last_chk}")
                last_pub = acc.last_published_at[:19] if acc.last_published_at else "暂无发布"
                st.caption(f"最后发布: {last_pub}")
            with col4:
                if st.button("🔍 检查登录", key=f"chk_{acc.account_id}"):
                    res = run_async(trendlume.publishing.check_account_status(acc.account_id))
                    if res.is_valid:
                        st.success("登录凭证有效！")
                    else:
                        st.error(f"失效: {res.error_message}")
                    st.rerun()

                if st.button("🗑️ 删除", key=f"del_{acc.account_id}", type="secondary"):
                    run_async(trendlume.publishing.delete_account(acc.account_id))
                    st.rerun()


# ============================================================================
# Tab 5: Queue & History Monitor
# ============================================================================

def render_queue_history_tab(trendlume):
    """Tab 5: Real-time Queue and historical logs"""
    st.subheader("📋 发布队列与历史 (Queue & History)")

    stats = run_async(trendlume.publishing.get_queue_stats())
    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
    col_m1.metric("排队中 (Queued)", stats["queued_jobs"])
    col_m2.metric("执行中 (Publishing)", stats["publishing_jobs"])
    col_m3.metric("定时中 (Scheduled)", stats["scheduled_jobs"])
    col_m4.metric("已成功 (Published)", stats["published_jobs"])
    col_m5.metric("已失败 (Failed)", stats["failed_jobs"])

    jobs = run_async(trendlume.publishing.list_jobs(limit=100))

    tab_active, tab_archived = st.tabs(["🚀 当前活跃队列 (Active Queue)", "📜 历史归档 (History)"])

    active_jobs = [j for j in jobs if j.status in [PublishJobStatus.QUEUED, PublishJobStatus.SCHEDULED, PublishJobStatus.PUBLISHING]]
    archived_jobs = [j for j in jobs if j.status in [PublishJobStatus.PUBLISHED, PublishJobStatus.FAILED, PublishJobStatus.CANCELLED]]

    with tab_active:
        if not active_jobs:
            st.info("💡 当前队列为空，暂无排队或执行中的任务。")
        for job in active_jobs:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 1.5])
                with c1:
                    st.markdown(f"**{get_platform_icon(job.platform)}** - **{job.title}**")
                    st.caption(f"Job ID: `{job.job_id}` | 关联任务: `{job.task_id or '手动'}`")
                with c2:
                    st.markdown(f"**状态**: {get_status_badge(job.status)}")
                    st.caption(f"尝试次数: {job.attempt_count} / {job.max_attempts}")
                with c3:
                    if job.scheduled_at:
                        st.caption(f"🕒 定时: {job.scheduled_at[:19]}")
                    if job.next_retry_at:
                        st.caption(f"🔄 计划重试: {job.next_retry_at[:19]}")
                with c4:
                    if st.button("⚡ 立即发布", key=f"force_pub_{job.job_id}"):
                        run_async(trendlume.publishing.execute_job(job.job_id))
                        st.rerun()
                    if st.button("🚫 取消", key=f"cancel_{job.job_id}"):
                        run_async(trendlume.publishing.cancel_job(job.job_id))
                        st.rerun()

    with tab_archived:
        if not archived_jobs:
            st.info("💡 暂无历史归档发布记录。")
        for job in archived_jobs:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 1.5])
                with c1:
                    st.markdown(f"**{get_platform_icon(job.platform)}** - **{job.title}**")
                    st.caption(f"Job ID: `{job.job_id}` | 平台作品 ID: `{job.platform_post_id or '无'}`")
                with c2:
                    st.markdown(f"**结果**: {get_status_badge(job.status)}")
                    if job.error_message:
                        st.caption(f"❌ 错误: `{job.error_message[:40]}`")
                with c3:
                    pub_at = job.published_at[:19] if job.published_at else (job.completed_at[:19] if job.completed_at else job.created_at[:19])
                    st.caption(f"完成时间: {pub_at}")
                with c4:
                    if job.status == PublishJobStatus.FAILED:
                        if st.button("🔄 重试", key=f"retry_{job.job_id}"):
                            run_async(trendlume.publishing.retry_job(job.job_id, force=True))
                            st.rerun()
                    if st.button("🗑️ 删除", key=f"del_job_{job.job_id}", type="secondary"):
                        run_async(trendlume.publishing.delete_job(job.job_id))
                        st.rerun()


# ============================================================================
# Main Page Entry Point
# ============================================================================

def main():
    init_session_state()
    init_i18n()
    trendlume = get_trendlume()

    render_header()

    # Dynamic Pending Verification Banner (Auto-refreshing SMS / 2FA verification prompt)
    render_pending_verifications_banner(trendlume)

    tab1, tab2, tab3, tab4 = st.tabs([
        "🚀 发布控制台",
        "📑 发布模板库",
        "👥 账号管理",
        "📋 队列与历史",
    ])

    with tab1:
        render_publishing_console_tab(trendlume)

    with tab2:
        render_templates_tab(trendlume)

    with tab3:
        render_accounts_tab(trendlume)

    with tab4:
        render_queue_history_tab(trendlume)


if __name__ == "__main__":
    main()
