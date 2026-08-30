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
Task Platform Metadata & Publishing Status Component

Provides metadata inspection/editing, LLM regeneration, and real-time PublishJob tracking
for video generation outputs and task detail views.
"""

from datetime import datetime, timedelta
from typing import Any

import streamlit as st

from trendlume.models.metadata import (
    DouyinConstraints,
    DouyinDeclaration,
    PublishingMode,
)
from trendlume.models.publishing import (
    AccountStatus,
    PlatformName,
    PublishJobStatus,
)
from web.i18n import tr
from web.utils.async_helpers import run_async


def get_job_status_badge(status: str) -> str:
    """Return status label with emoji using canonical model definitions"""
    return PublishJobStatus.get_badge(status)


def render_task_publishing_section(
    trendlume: Any,
    task_id: str,
    key_prefix: str = "tp_",
):
    """
    Render complete Platform Metadata and Publishing Status cards for a task.
    """
    task_meta = run_async(trendlume.persistence.load_task_metadata(task_id))
    if not task_meta:
        return

    st.markdown("---")
    st.markdown(f"### 📢 {tr('publishing.task_section_title', fallback='平台元数据与自动发布')}")

    # ========================================================================
    # 1. Platform Metadata Card
    # ========================================================================
    plat_meta_map = task_meta.get("metadata", {}).get("platform_metadata", {})
    douyin_meta = plat_meta_map.get("douyin")

    with st.container(border=True):
        m_head_col1, m_head_col2 = st.columns([3, 2])
        with m_head_col1:
            st.markdown("#### 🎵 抖音平台元数据 (Douyin Metadata)")
        with m_head_col2:
            regen_btn = st.button(
                "🔄 重新生成元数据",
                key=f"{key_prefix}regen_meta_{task_id}",
                help="仅使用大模型基于视频文案重新生成抖音标题与标签，无需重新渲染视频",
                use_container_width=True,
            )

        if regen_btn:
            with st.spinner("正在使用大模型生成抖音专属元数据..."):
                try:
                    run_async(trendlume.publishing.regenerate_task_metadata(task_id, platform=PlatformName.DOUYIN))
                    st.success("✅ 平台元数据重新生成成功！")
                    st.rerun()
                except Exception as me:
                    st.error(f"生成元数据失败: {me}")

        if douyin_meta:
            title_val = douyin_meta.get("title", "")
            desc_val = douyin_meta.get("description", "")
            tags_val = douyin_meta.get("tags", [])
            custom_params = douyin_meta.get("platform_custom_params", {})
            decl_val = custom_params.get("declaration") or douyin_meta.get("declaration", DouyinDeclaration.DEFAULT)

            col_t, col_d = st.columns([1, 1])
            with col_t:
                st.markdown(f"**📌 抖音标题:** `{title_val}`")
                tags_formatted = " ".join(f"`#{t}`" for t in tags_val) if tags_val else "无"
                st.markdown(f"**🏷️ 话题标签:** {tags_formatted}")
                st.markdown(f"**🛡️ 自主声明:** `{decl_val}`")
            with col_d:
                st.markdown("**📝 视频描述/正文:**")
                st.info(desc_val if desc_val else "（暂无描述）")

            # Inline Metadata Editor
            with st.expander("✏️ 编辑平台元数据 (Edit Metadata)", expanded=False):
                with st.form(f"{key_prefix}edit_meta_form_{task_id}"):
                    edit_title = st.text_input(
                        f"视频标题 (最多{DouyinConstraints.MAX_TITLE_LENGTH}字)",
                        value=title_val,
                        max_chars=DouyinConstraints.MAX_TITLE_LENGTH,
                    )
                    edit_desc = st.text_area(
                        f"视频文案/简介 (最多{DouyinConstraints.MAX_DESCRIPTION_LENGTH}字)",
                        value=desc_val,
                        height=80,
                        max_chars=DouyinConstraints.MAX_DESCRIPTION_LENGTH,
                    )
                    edit_tags_str = st.text_input(
                        f"话题标签 (以英文逗号分隔，最多{DouyinConstraints.MAX_TAGS}个)",
                        value=", ".join(tags_val),
                    )
                    decl_options = DouyinDeclaration.ALL_OPTIONS
                    try:
                        decl_idx = decl_options.index(decl_val)
                    except ValueError:
                        decl_idx = 0
                    edit_decl = st.selectbox(
                        "自主声明",
                        options=decl_options,
                        index=decl_idx,
                    )

                    submitted = st.form_submit_button("💾 保存元数据修改", use_container_width=True)
                    if submitted:
                        cleaned_tags = [t.strip().lstrip("#") for t in edit_tags_str.split(",") if t.strip()][:DouyinConstraints.MAX_TAGS]
                        updated_dict = {
                            "title": edit_title.strip()[:DouyinConstraints.MAX_TITLE_LENGTH],
                            "description": edit_desc.strip(),
                            "tags": cleaned_tags,
                            "declaration": edit_decl,
                            "platform_custom_params": {
                                **custom_params,
                                "declaration": edit_decl,
                            },
                        }
                        run_async(trendlume.publishing.update_task_metadata(task_id, PlatformName.DOUYIN, updated_dict))
                        st.success("✅ 元数据已更新！")
                        st.rerun()
        else:
            st.info("💡 尚未生成抖音专属元数据。您可以点击上方按钮由 AI 自动提取生成。")

    # ========================================================================
    # 2. Publishing Status & Job Management Card
    # ========================================================================
    jobs = run_async(trendlume.publishing.list_jobs(task_id=task_id, limit=50))

    with st.container(border=True):
        st.markdown("#### 🚀 发布任务状态 (Publishing Jobs)")

        if jobs:
            for job in jobs:
                account = run_async(trendlume.publishing.store.get_account(job.account_id))
                acc_name = account.account_name if account else job.account_id
                acc_handle = f" (@{account.username})" if account and account.username else ""

                with st.container(border=True):
                    j_col1, j_col2, j_col3 = st.columns([2, 2, 1])
                    with j_col1:
                        st.markdown(f"**👤 账号:** `{acc_name}{acc_handle}`")
                        st.caption(f"Job ID: `{job.job_id}` | 平台: `抖音`")
                    with j_col2:
                        st.markdown(f"**状态:** {get_job_status_badge(job.status)}")
                        if job.status == PublishJobStatus.SCHEDULED and job.scheduled_at:
                            st.caption(f"⏰ 计划发布时间: `{job.scheduled_at.replace('T', ' ')[:16]}`")
                        elif job.status == PublishJobStatus.PUBLISHED and job.published_at:
                            st.caption(f"✅ 发布时间: `{job.published_at.replace('T', ' ')[:16]}`")
                        elif job.error_message:
                            st.caption(f"⚠️ 错误信息: `{job.error_message}`")
                    with j_col3:
                        if job.status == PublishJobStatus.FAILED:
                            if st.button("🔄 重试", key=f"{key_prefix}retry_job_{job.job_id}", use_container_width=True):
                                run_async(trendlume.publishing.retry_job(job.job_id, force=True))
                                st.success("已加入重试队列！")
                                st.rerun()
                        elif job.status in [PublishJobStatus.SCHEDULED, PublishJobStatus.QUEUED]:
                            if st.button("🚫 取消", key=f"{key_prefix}cancel_job_{job.job_id}", use_container_width=True):
                                run_async(trendlume.publishing.cancel_job(job.job_id))
                                st.success("已取消发布任务！")
                                st.rerun()
                        elif job.status == PublishJobStatus.PUBLISHED:
                            st.markdown("✅ [查看作品](https://creator.douyin.com/creator-micro/content/manage)")
        else:
            st.info("💡 当前视频尚未分发至任何社交账号。您可以立即创建发布任务：")

            # Quick Dispatch Form
            with st.form(f"{key_prefix}quick_dispatch_form_{task_id}"):
                all_accs = run_async(trendlume.publishing.list_accounts(platform=PlatformName.DOUYIN))
                active_accs = [a for a in all_accs if a.status != AccountStatus.DISABLED]

                if not active_accs:
                    st.warning("⚠️ 暂无可用抖音账号。请前往「📢 发布中心」添加账号。")
                    dispatch_submitted = False
                else:
                    acc_map = {a.account_id: f"{a.account_name} ({a.display_name or a.username or '抖音'})" for a in active_accs}
                    sel_accs = st.multiselect(
                        "选择发布目标账号",
                        options=list(acc_map.keys()),
                        default=[active_accs[0].account_id],
                        format_func=lambda x: acc_map.get(x, str(x)),
                    )

                    q_mode = st.radio(
                        "发布方式",
                        options=[PublishingMode.IMMEDIATE, PublishingMode.SCHEDULED],
                        format_func=lambda x: PublishingMode.get_label(x),
                        horizontal=True,
                    )

                    q_sched_iso = None
                    if q_mode == PublishingMode.SCHEDULED:
                        c1, c2 = st.columns(2)
                        with c1:
                            qd = st.date_input("计划发布日期", value=datetime.now().date())
                        with c2:
                            qt = st.time_input("计划发布时间", value=(datetime.now() + timedelta(hours=1)).time())
                        q_sched_iso = datetime.combine(qd, qt).isoformat()

                    dispatch_submitted = st.form_submit_button("🚀 立即创建发布任务", use_container_width=True)

                    if dispatch_submitted:
                        if not sel_accs:
                            st.error("请选择至少一个目标账号！")
                        else:
                            created = run_async(
                                trendlume.publishing.create_jobs_for_task(
                                    task_id=task_id,
                                    account_ids=sel_accs,
                                    platform=PlatformName.DOUYIN,
                                    scheduled_at=q_sched_iso,
                                )
                            )
                            st.success(f"已创建 {len(created)} 个发布任务！")
                            st.rerun()
