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
Projects Page - Manage projects, video generation plans, and scheduled generation tasks.
"""
# ruff: noqa: E402

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add project root to sys.path
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from trendlume.models.project import TaskStatus
from web.components.content_input import render_bgm_section, render_content_input
from web.components.generation_form import (
    clean_template_config,
    create_progress_tracker,
    get_default_generation_config,
    render_project_selector,
)
from web.components.header import render_header
from web.i18n import tr
from web.state.session import get_trendlume, init_i18n, init_session_state
from web.utils.async_helpers import run_async

# Page config
st.set_page_config(
    page_title="Projects - Trendlume",
    page_icon="📁",
    layout="wide",
)


# ============================================================================
# Formatting Helpers
# ============================================================================

def format_duration(seconds: float) -> str:
    """Format duration in seconds to readable string"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"


def format_file_size(bytes_size: int) -> str:
    """Format file size in bytes to readable string"""
    if bytes_size < 1024:
        return f"{bytes_size}B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f}KB"
    elif bytes_size < 1024 * 1024 * 1024:
        return f"{bytes_size / 1024 / 1024:.1f}MB"
    else:
        return f"{bytes_size / 1024 / 1024 / 1024:.2f}GB"


def sanitize_filename(name: str) -> str:
    """Sanitize string for safe file downloading across platforms"""
    cleaned = "".join(c for c in name if c.isalnum() or c in " _-").strip()
    return cleaned[:50] or "video"


def format_datetime(iso_string: str) -> str:
    """Format ISO datetime string to readable format"""
    if not iso_string:
        return ""
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_string


def truncate_text(text: str, max_length: int = 60) -> str:
    """Truncate text to max length"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def get_status_badge(status: str) -> str:
    """Return status emoji and label"""
    status_map = {
        TaskStatus.DRAFT: ("📝", tr("project.task.status_draft")),
        TaskStatus.SCHEDULED: ("⏰", tr("project.task.status_scheduled")),
        TaskStatus.QUEUED: ("⏳", tr("project.task.status_queued")),
        TaskStatus.RUNNING: ("🏃", tr("project.task.status_running")),
        TaskStatus.COMPLETED: ("✅", tr("project.task.status_completed")),
        TaskStatus.FAILED: ("❌", tr("project.task.status_failed")),
        TaskStatus.CANCELLED: ("🚫", tr("project.task.status_cancelled")),
    }
    emoji, text = status_map.get(status, ("❓", status))
    return f"{emoji} {text}"


# ============================================================================
# Task Card Component
# ============================================================================

def render_grid_task_card(task: dict, trendlume):
    """Render an actionable grid task card supporting all 8 operations"""
    task_id = task["task_id"]
    title = task.get("title") or "Untitled"
    status = task.get("status", TaskStatus.DRAFT)
    created_at = task.get("created_at", "")
    scheduled_at = task.get("scheduled_at")
    priority = task.get("priority", 0)
    duration = task.get("duration", 0)
    n_frames = task.get("n_frames", 0)
    video_path = task.get("video_path", "")

    with st.container(border=True):
        # 1. Preview Area
        if video_path and os.path.exists(video_path):
            st.video(video_path, autoplay=False, loop=False, muted=False)
        else:
            placeholder_icon = "⏰" if status == TaskStatus.SCHEDULED else "📝"
            st.markdown(
                f"<div style='background: #f4f4f5; height: 140px; display: flex; align-items: center; "
                f"justify-content: center; border-radius: 6px; font-size: 38px;'>{placeholder_icon}</div>",
                unsafe_allow_html=True,
            )

        # 2. Title & Status Badge
        p_badge = "🔥 " if priority > 0 else ("💤 " if priority < 0 else "")
        st.markdown(f"**{get_status_badge(status)} {p_badge}{truncate_text(title, 35)}**")

        # 3. Time & Meta Info
        if status == TaskStatus.SCHEDULED and scheduled_at:
            st.caption(f"⏰ {tr('project.task.scheduled_at')}: {format_datetime(scheduled_at)}")
        elif duration > 0:
            st.caption(f"⏱️ {format_duration(duration)} | 🎬 {n_frames} frames")
        else:
            st.caption(f"🕒 {format_datetime(created_at)}")

        st.divider()

        # 4. Action Buttons (Row 1: Primary Actions)
        b_col1, b_col2, b_col3 = st.columns(3)
        with b_col1:
            if st.button("👁️", key=f"view_{task_id}", help=tr("project.task.view_detail"), use_container_width=True):
                st.session_state.selected_task_id = task_id
                st.rerun()

        with b_col2:
            if status in [TaskStatus.DRAFT, TaskStatus.SCHEDULED, TaskStatus.CANCELLED, TaskStatus.FAILED]:
                if st.button("⚡", key=f"gen_{task_id}", help=tr("project.task.run_now"), use_container_width=True):
                    progress_bar, status_text, update_progress, finish_progress = create_progress_tracker()
                    try:
                        run_async(trendlume.projects.execute_task(task_id, progress_callback=update_progress))
                        finish_progress()
                    except Exception as e:
                        st.error(f"Generation failed: {e}")
                    st.rerun()
            elif status == TaskStatus.COMPLETED:
                if st.button("🔄", key=f"retry_{task_id}", help=tr("project.task.retry"), use_container_width=True):
                    progress_bar, status_text, update_progress, finish_progress = create_progress_tracker()
                    try:
                        run_async(trendlume.projects.retry_task(task_id, progress_callback=update_progress))
                        finish_progress()
                    except Exception as e:
                        st.error(f"Retry failed: {e}")
                    st.rerun()
            else:
                st.button("⏳", key=f"disabled_gen_{task_id}", disabled=True, use_container_width=True)

        with b_col3:
            if video_path and os.path.exists(video_path):
                with open(video_path, "rb") as f:
                    st.download_button(
                        "⬇️",
                        data=f,
                        file_name=f"{sanitize_filename(title)}.mp4",
                        mime="video/mp4",
                        key=f"download_{task_id}",
                        help=tr("project.task.download"),
                        use_container_width=True,
                    )
            else:
                st.button("⬇️", key=f"download_disabled_{task_id}", disabled=True, use_container_width=True)

        # Row 2: Secondary Actions (Edit, Schedule/Cancel, Delete)
        s_col1, s_col2, s_col3 = st.columns(3)
        with s_col1:
            if st.button("✏️", key=f"edit_task_{task_id}", help=tr("project.task.edit_plan_title"), use_container_width=True):
                st.session_state.editing_task_id = task_id
                st.rerun()

        with s_col2:
            if status == TaskStatus.SCHEDULED:
                if st.button("🚫", key=f"cancel_sched_{task_id}", help=tr("project.task.cancel_schedule"), use_container_width=True):
                    run_async(trendlume.projects.cancel_task_schedule(task_id))
                    st.success(tr("project.task.schedule_cancelled"))
                    st.rerun()
            else:
                if st.button("⏰", key=f"sched_task_{task_id}", help=tr("project.task.schedule"), use_container_width=True):
                    st.session_state.scheduling_task_id = task_id
                    st.rerun()

        with s_col3:
            if st.button("🗑️", key=f"delete_{task_id}", help=tr("project.task.delete"), use_container_width=True):
                st.session_state[f"confirm_delete_task_{task_id}"] = True
                st.rerun()

        # Delete confirmation
        if st.session_state.get(f"confirm_delete_task_{task_id}", False):
            st.warning(tr("project.task.delete_confirm"))
            dcol1, dcol2 = st.columns(2)
            with dcol1:
                if st.button("✅", key=f"confirm_yes_task_{task_id}", use_container_width=True):
                    try:
                        success = run_async(trendlume.tasks.delete_task(task_id))
                        if success:
                            st.success(tr("project.task.delete_success"))
                            st.session_state[f"confirm_delete_task_{task_id}"] = False
                            st.rerun()
                        else:
                            st.error(tr("history.action.delete_failed", error=""))
                    except Exception as e:
                        st.error(tr("history.action.delete_failed", error=str(e)))
            with dcol2:
                if st.button("❌", key=f"confirm_no_task_{task_id}", use_container_width=True):
                    st.session_state[f"confirm_delete_task_{task_id}"] = False
                    st.rerun()


# ============================================================================
# Task Detail Component (Reused 3-Column Layout with Executions)
# ============================================================================

def render_task_detail_view(task_id: str, project_id: str, trendlume):
    """Render full task detail in three-column layout with historical executions"""
    col_back, col_actions = st.columns([2, 2])
    with col_back:
        if st.button(tr("project.back_to_tasks"), key="back_to_tasks_btn"):
            st.session_state.selected_task_id = None
            st.rerun()

    detail = run_async(trendlume.tasks.get_task_detail(task_id))
    if not detail:
        st.error(tr("status.error", error="Task not found"))
        if st.button(tr("project.back_to_tasks")):
            st.session_state.selected_task_id = None
            st.rerun()
        return

    metadata = detail.get("metadata") or {}
    storyboard = detail.get("storyboard")
    status = metadata.get("status", TaskStatus.DRAFT)
    input_params = metadata.get("input") or {}
    config_params = metadata.get("config") or {}
    result_data = metadata.get("result") or {}
    executions = metadata.get("executions") or []

    task_title = input_params.get("title") or metadata.get("title") or task_id
    st.markdown(f"### 📋 {task_title}")
    st.caption(f"Status: **{get_status_badge(status)}** | Task ID: `{task_id}` | Project: `{project_id}`")
    progress_placeholder = st.container()

    with col_actions:
        btn1, btn2 = st.columns(2)
        with btn1:
            if status in [TaskStatus.DRAFT, TaskStatus.SCHEDULED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                if st.button(f"⚡ {tr('project.task.run_now')}", key=f"detail_run_{task_id}", type="primary", use_container_width=True):
                    with progress_placeholder:
                        progress_bar, status_text, update_progress, finish_progress = create_progress_tracker()
                        try:
                            run_async(trendlume.projects.execute_task(task_id, progress_callback=update_progress))
                            finish_progress()
                        except Exception as e:
                            st.error(f"Generation failed: {e}")
                        st.rerun()
            elif status == TaskStatus.COMPLETED:
                if st.button(f"🔄 {tr('project.task.retry')}", key=f"detail_retry_{task_id}", type="primary", use_container_width=True):
                    with progress_placeholder:
                        progress_bar, status_text, update_progress, finish_progress = create_progress_tracker()
                        try:
                            run_async(trendlume.projects.retry_task(task_id, progress_callback=update_progress))
                            finish_progress()
                        except Exception as e:
                            st.error(f"Retry failed: {e}")
                        st.rerun()
        with btn2:
            if st.button(f"✏️ {tr('project.task.edit_plan_title')}", key=f"detail_edit_{task_id}", use_container_width=True):
                st.session_state.editing_task_id = task_id
                st.rerun()

    col_input, col_storyboard, col_video = st.columns([1, 1, 1])

    # Left column: Input and config
    with col_input:
        st.markdown(f"**📝 {tr('project.detail.input_params')}**")
        mode_val = input_params.get("mode") or config_params.get("mode", "N/A")
        scenes_val = input_params.get("n_scenes") or config_params.get("n_scenes", "N/A")
        tts_mode_val = input_params.get("tts_inference_mode") or config_params.get("tts_inference_mode", "N/A")
        voice_val = input_params.get("tts_voice") or config_params.get("tts_voice", "N/A")

        st.markdown(f"**{tr('project.detail.mode')}:** {mode_val}")
        st.markdown(f"**{tr('project.detail.n_scenes')}:** {scenes_val}")
        st.markdown(f"**{tr('project.detail.tts_mode')}:** {tts_mode_val}")
        st.markdown(f"**{tr('project.detail.voice')}:** {voice_val}")
        if metadata.get("scheduled_at"):
            st.markdown(f"**{tr('project.task.scheduled_at')}:** {format_datetime(metadata.get('scheduled_at'))}")

        with st.expander(tr("project.detail.text"), expanded=True):
            text_val = input_params.get("text") or metadata.get("text") or "N/A"
            st.text_area(
                "Input Text",
                value=text_val,
                height=200,
                disabled=True,
                label_visibility="collapsed",
            )

    # Middle column: Storyboard frames
    with col_storyboard:
        st.markdown(f"**🎬 {tr('project.detail.storyboard')}**")
        if storyboard and hasattr(storyboard, "frames") and storyboard.frames:
            for frame in storyboard.frames:
                with st.expander(
                    f"{tr('project.detail.frame')} {frame.index + 1}",
                    expanded=False,
                ):
                    st.markdown(f"**{tr('project.detail.narration')}:**")
                    st.caption(frame.narration)

                    if frame.image_prompt:
                        st.markdown(f"**{tr('project.detail.image_prompt')}:**")
                        st.caption(frame.image_prompt)

                    col1, col2 = st.columns(2)
                    with col1:
                        if frame.composed_image_path and os.path.exists(frame.composed_image_path):
                            st.image(frame.composed_image_path)
                        elif frame.image_path and os.path.exists(frame.image_path):
                            st.image(frame.image_path)
                    with col2:
                        if frame.video_segment_path and os.path.exists(frame.video_segment_path):
                            st.video(frame.video_segment_path)

                    if frame.audio_path and os.path.exists(frame.audio_path):
                        st.audio(frame.audio_path)
        else:
            if status == TaskStatus.RUNNING:
                st.info("⏳ 正在生成分镜与画面...")
            elif status in [TaskStatus.DRAFT, TaskStatus.SCHEDULED, TaskStatus.QUEUED]:
                st.info("ℹ️ 任务尚未开始生成，暂无分镜数据。")
            else:
                st.info("No storyboard data yet. Task has not been generated.")

    # Right column: Final video & Executions
    with col_video:
        st.markdown(f"**🎥 {tr('project.detail.video_info')}**")
        video_path = result_data.get("video_path")
        if video_path and os.path.exists(video_path):
            st.video(video_path)
            st.markdown(f"**{tr('project.detail.duration')}:** {format_duration(result_data.get('duration', 0))}")
            st.markdown(f"**{tr('project.detail.frames')}:** {result_data.get('n_frames', 0)}")
            st.markdown(f"**{tr('project.detail.file_size')}:** {format_file_size(result_data.get('file_size', 0))}")

            with open(video_path, "rb") as f:
                title = input_params.get("title") or metadata.get("title") or "video"
                st.download_button(
                    tr("project.detail.download_video"),
                    data=f,
                    file_name=f"{sanitize_filename(title)}.mp4",
                    mime="video/mp4",
                    use_container_width=True,
                )
        else:
            if status == TaskStatus.RUNNING:
                st.info("⏳ 视频正在生成中，成片渲染完成后将自动显示在此处。")
            elif status == TaskStatus.QUEUED:
                st.info("⏳ 任务排队中，等待调度执行生成...")
            elif status == TaskStatus.SCHEDULED:
                sched_time_str = format_datetime(metadata.get('scheduled_at', '')) if metadata.get('scheduled_at') else ''
                st.info(f"⏰ 定时计划任务（排期：{sched_time_str}），尚未执行生成。")
            elif status == TaskStatus.FAILED:
                st.error(f"❌ {tr('history.task_card.status_failed')}，{tr('project.task.retry')}")
            else:
                st.info("ℹ️ 当前任务为草稿计划，尚未生成成片。点击上方“立即生成”开始创作。")

        # Non-destructive historical executions list
        if executions:
            with st.expander(f"{tr('project.task.executions')} ({len(executions)})", expanded=False):
                for i, ex in enumerate(reversed(executions)):
                    ex_id = ex.get("execution_id", f"exec_{i}")
                    ex_time = format_datetime(ex.get("created_at", ""))
                    ex_path = ex.get("video_path", "")
                    ex_status = ex.get("status", "completed")
                    st.markdown(f"**#{len(executions) - i} {ex_id}** (`{ex_status}`)")
                    st.caption(f"🕒 {ex_time}")
                    if ex_path and os.path.exists(ex_path):
                        st.video(ex_path)
                    st.divider()


# ============================================================================
# Upcoming Tasks Component (Requirement 8)
# ============================================================================

def render_upcoming_tasks_section(project_id: str, trendlume):
    """Render Upcoming / Scheduled tasks at top of Project Detail"""
    all_project_tasks = run_async(trendlume.persistence.list_tasks(project_id=project_id, limit=1000))
    upcoming = [t for t in all_project_tasks if t.get("status") in [TaskStatus.SCHEDULED, TaskStatus.QUEUED]]

    if not upcoming:
        return

    # Sort upcoming by priority descending and scheduled_at ascending
    upcoming.sort(key=lambda t: (-t.get("priority", 0), t.get("scheduled_at") or "9999-12-31"))

    with st.expander(f"{tr('project.task.upcoming')} ({len(upcoming)})", expanded=True):
        for t in upcoming:
            t_id = t["task_id"]
            p_badge = "🔥 " if t.get("priority", 0) > 0 else ""
            c_info, c_action1, c_action2 = st.columns([3, 1, 1])
            with c_info:
                sched_str = format_datetime(t.get("scheduled_at", ""))
                st.markdown(f"**{p_badge}{t.get('title', 'Untitled')}** (`{t.get('status')}`)")
                st.caption(f"⏰ {tr('project.task.scheduled_at')}: {sched_str} | ID: `{t_id}`")
            with c_action1:
                if st.button(f"⚡ {tr('project.task.run_now')}", key=f"upcoming_run_{t_id}", use_container_width=True):
                    with st.spinner("Generating..."):
                        try:
                            run_async(trendlume.projects.execute_task(t_id))
                        except Exception as e:
                            st.error(f"Generation failed: {e}")
                        st.rerun()
            with c_action2:
                if st.button(f"🚫 {tr('project.task.cancel_schedule')}", key=f"upcoming_cancel_{t_id}", use_container_width=True):
                    run_async(trendlume.projects.cancel_task_schedule(t_id))
                    st.rerun()
            st.divider()


# ============================================================================
# Task Plan Modals (Create, Edit, Schedule)
# ============================================================================

def render_task_plan_modals(project_id: str, trendlume):
    """Render modal forms for creating, editing, and scheduling task plans"""
    # 2. Edit Task Plan Modal
    editing_task_id = st.session_state.get("editing_task_id")
    if editing_task_id:
        detail = run_async(trendlume.tasks.get_task_detail(editing_task_id))
        if detail and detail.get("metadata"):
            meta = detail["metadata"]
            with st.expander(f"✏️ {tr('project.task.edit_plan_title')}: {editing_task_id}", expanded=True):
                with st.form(f"edit_task_form_{editing_task_id}"):
                    meta_inp = meta.get("input") or {}
                    curr_title = meta.get("title") or meta_inp.get("title", "")
                    curr_text = meta_inp.get("text") or meta.get("text", "")
                    curr_priority = meta.get("priority", 0)

                    new_title = st.text_input(tr("project.task.sort_title", fallback="Title"), value=curr_title)
                    new_text = st.text_area(tr("project.detail.text", fallback="Text Content"), value=curr_text, height=120)
                    new_priority = st.selectbox(
                        tr("project.task.priority"),
                        options=[1, 0, -1],
                        index=0 if curr_priority == 1 else (2 if curr_priority == -1 else 1),
                        format_func=lambda x: tr("project.task.priority_high") if x == 1 else (tr("project.task.priority_normal") if x == 0 else tr("project.task.priority_low")),
                    )

                    c_sub, c_can = st.columns(2)
                    with c_sub:
                        submitted = st.form_submit_button(tr("project.save"), use_container_width=True)
                    with c_can:
                        cancelled = st.form_submit_button(tr("project.cancel"), use_container_width=True)

                    if submitted:
                        run_async(
                            trendlume.projects.update_task_plan(
                                task_id=editing_task_id,
                                title=new_title.strip(),
                                text=new_text.strip(),
                                priority=new_priority,
                            )
                        )
                        st.success(tr("project.task.plan_updated"))
                        st.session_state.editing_task_id = None
                        st.rerun()

                    if cancelled:
                        st.session_state.editing_task_id = None
                        st.rerun()

    # 3. Schedule Task Modal
    sched_task_id = st.session_state.get("scheduling_task_id")
    if sched_task_id:
        with st.expander(f"⏰ {tr('project.task.schedule')}: {sched_task_id}", expanded=True):
            with st.form(f"schedule_task_form_{sched_task_id}"):
                col_d, col_t = st.columns(2)
                with col_d:
                    s_date = st.date_input(tr("project.task.date", fallback="Date"), value=datetime.now().date())
                with col_t:
                    s_time = st.time_input(tr("project.task.time", fallback="Time"), value=(datetime.now() + timedelta(hours=1)).time())
                s_prio = st.selectbox(tr("project.task.priority", fallback="Priority"), options=[1, 0, -1], index=1)

                c_sub, c_can = st.columns(2)
                with c_sub:
                    submitted = st.form_submit_button(tr("project.task.save_schedule"), use_container_width=True)
                with c_can:
                    cancelled = st.form_submit_button(tr("project.cancel"), use_container_width=True)

                if submitted:
                    s_dt = datetime.combine(s_date, s_time)
                    run_async(trendlume.projects.schedule_task(sched_task_id, scheduled_at=s_dt.isoformat(), priority=s_prio))
                    st.success(tr("project.task.plan_updated"))
                    st.session_state.scheduling_task_id = None
                    st.rerun()

                if cancelled:
                    st.session_state.scheduling_task_id = None
                    st.rerun()


# ============================================================================
# Project New Task Generation Workspace (Full Options & Template)
# ============================================================================

def render_new_task_generation_view(project_id: str, trendlume: Any):
    """
    Render full video generation workspace for creating a new Task inside a Project.
    Reuses the exact same content input, BGM, and style configuration components.
    Automatically loads the Project Template (if present) or system defaults.
    Ensures the task strictly belongs to project_id.
    """
    project = run_async(trendlume.projects.get_project(project_id))
    if not project:
        st.error(tr("status.error", error="Project not found"))
        if st.button(tr("project.back_to_projects")):
            st.session_state.creating_task_in_project_id = None
            st.rerun()
        return

    # 1. Navigation Header
    h_col1, h_col2 = st.columns([1, 4])
    with h_col1:
        if st.button(tr('project.back_to_tasks'), use_container_width=True):
            st.session_state.creating_task_in_project_id = None
            st.session_state.pop("active_pnt_template", None)
            st.rerun()
    with h_col2:
        st.markdown(f"### {tr('project.task.new_task')} — 📁 {project.name}")

    # 2. Template Status & Quick Actions Banner
    with st.container(border=True):
        bcol1, bcol2, bcol3 = st.columns([3, 1, 1])
        with bcol1:
            if project.template:
                st.markdown(f"**{tr('project.template.active')}**")
                st.caption(f"{tr('project.template.has_template_hint')}")
            else:
                st.markdown(f"**{tr('project.template.none')}**")
                st.caption(tr("project.template.none_hint", fallback="Currently using system default configuration. You can configure parameters below and save as a project template."))
        with bcol2:
            if project.template:
                if st.button(tr('project.template.apply_button'), use_container_width=True, key="btn_apply_template_pnt"):
                    st.session_state["active_pnt_template"] = dict(project.template)
                    for k in list(st.session_state.keys()):
                        if k.startswith("pnt_") and k != "btn_apply_template_pnt":
                            del st.session_state[k]
                    st.rerun()
        with bcol3:
            if project.template:
                if st.button(tr('project.template.clear_button'), use_container_width=True, key="btn_clear_template_pnt"):
                    run_async(trendlume.projects.clear_project_template(project.project_id))
                    st.session_state.pop("active_pnt_template", None)
                    for k in list(st.session_state.keys()):
                        if k.startswith("pnt_"):
                            del st.session_state[k]
                    st.success(tr("project.template.cleared_success"))
                    st.rerun()

    # Active template config
    if "active_pnt_template" in st.session_state:
        initial_cfg = st.session_state["active_pnt_template"]
    elif project.template:
        initial_cfg = project.template
    else:
        initial_cfg = get_default_generation_config()

    # 3. Three-Column Generation Layout (Reusing components)
    col_left, col_mid, col_right = st.columns([1, 1, 1])

    # Left Column: Project Attribution & Content Input & BGM
    with col_left:
        with st.container(border=True):
            render_project_selector(trendlume, default_project_id=project.project_id, disabled=True)
        content_params = render_content_input(initial_values=initial_cfg, key_prefix="pnt_")
        bgm_params = render_bgm_section(key_prefix="pnt_", initial_values=initial_cfg)

    # Middle Column: Style Configuration
    with col_mid:
        from web.components.style_config import render_style_config
        style_params = render_style_config(trendlume, initial_values=initial_cfg, key_prefix="pnt_")

    # Right Column: Task Planning & Execution Actions
    with col_right:
        with st.container(border=True):
            st.markdown(f"**⚙️ {tr('project.task.plan_settings')}**")

            priority = st.selectbox(
                tr("project.task.priority"),
                options=[1, 0, -1],
                index=1,
                format_func=lambda x: tr("project.task.priority_high") if x == 1 else (tr("project.task.priority_normal") if x == 0 else tr("project.task.priority_low")),
                key="pnt_priority"
            )

            st.markdown(f"**⏰ {tr('project.task.scheduled_at')} {tr('label.optional', fallback='(Optional)')}**")
            sc_date, sc_time = st.columns(2)
            with sc_date:
                sched_date = st.date_input(tr("project.task.date", fallback="Date"), value=datetime.now().date(), key="pnt_sched_date")
            with sc_time:
                sched_time = st.time_input(tr("project.task.time", fallback="Time"), value=(datetime.now() + timedelta(hours=1)).time(), key="pnt_sched_time")
            enable_schedule = st.checkbox(tr("project.task.enable_schedule", fallback="启用定时生成"), value=False, key="pnt_enable_sched")

            st.divider()

            # Compile generation configuration
            full_params = {
                "pipeline": "standard",
                "project_id": project.project_id,
                **content_params,
                **bgm_params,
                **style_params,
            }
            clean_cfg = clean_template_config(full_params)

            # Actions
            btn_gen = st.button(tr('project.task.save_and_generate'), type="primary", use_container_width=True, key="pnt_btn_gen")
            btn_draft = st.button(tr('project.task.save_draft'), use_container_width=True, key="pnt_btn_draft")
            btn_sched = st.button(tr('project.task.save_schedule'), use_container_width=True, key="pnt_btn_sched")

            text_val = content_params.get("text", "").strip()
            title_val = content_params.get("title", "").strip()

            if btn_gen or btn_draft or btn_sched:
                if not text_val and not title_val:
                    st.error(tr("error.input_required"))
                else:
                    scheduled_iso = None
                    if btn_sched or enable_schedule:
                        dt = datetime.combine(sched_date, sched_time)
                        scheduled_iso = dt.isoformat()

                    auto_gen = bool(btn_gen)
                    created_task = None
                    if auto_gen:
                        progress_bar, status_text, update_progress, finish_progress = create_progress_tracker()
                        try:
                            created_task = run_async(
                                trendlume.projects.create_task_plan(
                                    project_id=project.project_id,
                                    title=title_val,
                                    text=text_val,
                                    generation_config=clean_cfg,
                                    scheduled_at=scheduled_iso,
                                    priority=priority,
                                    auto_generate=True,
                                    progress_callback=update_progress,
                                )
                            )
                            finish_progress()
                        except Exception as e:
                            st.error(f"Generation failed: {e}")
                    else:
                        with st.spinner("正在创建任务计划..."):
                            created_task = run_async(
                                trendlume.projects.create_task_plan(
                                    project_id=project.project_id,
                                    title=title_val,
                                    text=text_val,
                                    generation_config=clean_cfg,
                                    scheduled_at=scheduled_iso,
                                    priority=priority,
                                    auto_generate=False,
                                )
                            )
                    if created_task:
                        st.session_state.selected_project_id = project.project_id
                        st.session_state.selected_task_id = created_task.task_id
                        st.session_state.creating_task_in_project_id = None
                        st.session_state.pop("active_pnt_template", None)
                        st.success(tr("project.task.plan_created"))
                        st.rerun()

            st.divider()

            # Template Management
            st.markdown(f"**🛠️ {tr('project.template.title')}**")
            if st.button(tr('project.template.save_button'), use_container_width=True, key="pnt_btn_save_template"):
                run_async(trendlume.projects.set_project_template(project.project_id, clean_cfg))
                st.session_state["active_pnt_template"] = clean_cfg
                st.success(tr("project.template.saved_success"))
                st.rerun()


# ============================================================================
# Project Card Component
# ============================================================================

def render_project_card(project, stats: dict, trendlume):
    """Render a clean, modern Project card with complete task statistics"""
    with st.container(border=True):
        st.markdown(f"### 📁 {project.name}")
        if project.description:
            st.caption(truncate_text(project.description, 80))
        else:
            st.caption("No description")

        if project.tags:
            tag_badges = " ".join([f"`#{tag}`" for tag in project.tags])
            st.markdown(tag_badges)

        st.divider()

        # Stats metrics
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric(tr("project.task.title"), stats.get("total", 0))
        with c2:
            st.metric(tr("project.task.status_scheduled"), stats.get("scheduled", 0))
        with c3:
            st.metric(tr("project.task.status_completed"), stats.get("completed", 0))
        with c4:
            st.metric(tr("project.task.status_failed"), stats.get("failed", 0))

        st.caption(f"🕒 {tr('project.updated_at', time=format_datetime(project.updated_at))}")

        st.divider()

        # Actions
        btn_col1, btn_col2, btn_col3 = st.columns(3)
        with btn_col1:
            if st.button(
                f"📂 {tr('project.open')}",
                key=f"open_proj_{project.project_id}",
                use_container_width=True,
            ):
                st.session_state.selected_project_id = project.project_id
                st.session_state.selected_task_id = None
                st.session_state.project_task_page = 1
                st.rerun()

        with btn_col2:
            if st.button(
                f"✏️ {tr('project.edit')}",
                key=f"edit_proj_{project.project_id}",
                use_container_width=True,
            ):
                st.session_state.editing_project_id = project.project_id
                st.rerun()

        with btn_col3:
            if st.button(
                f"🗑️ {tr('project.delete')}",
                key=f"del_proj_{project.project_id}",
                use_container_width=True,
            ):
                st.session_state.confirm_delete_project_id = project.project_id
                st.rerun()


# ============================================================================
# Project Creation / Edit / Delete Modals
# ============================================================================

def render_project_modals(trendlume):
    """Handle Project Create, Edit, and Delete forms"""
    if st.session_state.get("show_new_project_modal", False):
        with st.expander(f"➕ {tr('project.create_title')}", expanded=True):
            with st.form("new_project_form"):
                name = st.text_input(
                    tr("project.name") + " *",
                    placeholder=tr("project.name_placeholder"),
                )
                description = st.text_area(
                    tr("project.description"),
                    placeholder=tr("project.description_placeholder"),
                )
                cover = st.text_input(
                    tr("project.cover"),
                    placeholder=tr("project.cover_placeholder"),
                )
                tags_str = st.text_input(
                    tr("project.tags"),
                    placeholder=tr("project.tags_placeholder"),
                )

                col_sub, col_can = st.columns([1, 1])
                with col_sub:
                    submitted = st.form_submit_button(tr("project.save"), use_container_width=True)
                with col_can:
                    cancelled = st.form_submit_button(tr("project.cancel"), use_container_width=True)

                if submitted:
                    if not name.strip():
                        st.error(tr("project.name_required"))
                    else:
                        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                        new_proj = run_async(
                            trendlume.projects.create_project(
                                name=name.strip(),
                                description=description.strip(),
                                cover=cover.strip() if cover else None,
                                tags=tags,
                            )
                        )
                        st.success(tr("project.action.create_success"))
                        st.session_state.show_new_project_modal = False
                        st.session_state.selected_project_id = new_proj.project_id
                        st.rerun()

                if cancelled:
                    st.session_state.show_new_project_modal = False
                    st.rerun()

    editing_id = st.session_state.get("editing_project_id")
    if editing_id:
        project = run_async(trendlume.projects.get_project(editing_id))
        if project:
            with st.expander(f"✏️ {tr('project.edit_title')}: {project.name}", expanded=True):
                with st.form(f"edit_project_form_{editing_id}"):
                    name = st.text_input(tr("project.name") + " *", value=project.name)
                    description = st.text_area(tr("project.description"), value=project.description or "")
                    cover = st.text_input(tr("project.cover"), value=project.cover or "")
                    tags_str = st.text_input(tr("project.tags"), value=", ".join(project.tags))

                    col_sub, col_can = st.columns([1, 1])
                    with col_sub:
                        submitted = st.form_submit_button(tr("project.save"), use_container_width=True)
                    with col_can:
                        cancelled = st.form_submit_button(tr("project.cancel"), use_container_width=True)

                    if submitted:
                        if not name.strip():
                            st.error(tr("project.name_required"))
                        else:
                            tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                            run_async(
                                trendlume.projects.update_project(
                                    editing_id,
                                    name=name.strip(),
                                    description=description.strip(),
                                    cover=cover.strip() if cover else None,
                                    tags=tags,
                                )
                            )
                            st.success(tr("project.action.update_success"))
                            st.session_state.editing_project_id = None
                            st.rerun()

                    if cancelled:
                        st.session_state.editing_project_id = None
                        st.rerun()

    del_id = st.session_state.get("confirm_delete_project_id")
    if del_id:
        project = run_async(trendlume.projects.get_project(del_id))
        if project:
            stats = run_async(trendlume.projects.get_project_stats(del_id))
            st.warning(
                tr(
                    "project.delete.warning",
                    count=stats.get("total", 0),
                    name=project.name,
                )
            )
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button(
                    f"⚠️ {tr('project.delete.confirm_btn')}",
                    key="confirm_del_proj_yes",
                    use_container_width=True,
                ):
                    run_async(trendlume.projects.delete_project(del_id, keep_tasks=True))
                    st.success(tr("project.delete.success"))
                    st.session_state.confirm_delete_project_id = None
                    if st.session_state.get("selected_project_id") == del_id:
                        st.session_state.selected_project_id = None
                    st.rerun()
            with col_no:
                if st.button(
                    tr("project.cancel"),
                    key="confirm_del_proj_no",
                    use_container_width=True,
                ):
                    st.session_state.confirm_delete_project_id = None
                    st.rerun()


# ============================================================================
# Project Detail View
# ============================================================================

def render_project_detail_view(project_id: str, trendlume):
    """Render the tasks and details of a single Project with generation plan & schedule capabilities"""
    project = run_async(trendlume.projects.get_project(project_id))
    if not project:
        st.error(tr("status.error", error="Project not found"))
        st.session_state.selected_project_id = None
        st.rerun()
        return

    # Back to project list
    if st.button(tr("project.back_to_projects"), key="back_to_projects_top"):
        st.session_state.selected_project_id = None
        st.session_state.selected_task_id = None
        st.rerun()

    # Project Header
    header_col, action_col = st.columns([3, 2])
    with header_col:
        st.markdown(f"## 📁 {project.name}")
        if project.description:
            st.markdown(f"> {project.description}")
        if project.tags:
            tag_badges = " ".join([f"`#{t}`" for t in project.tags])
            st.markdown(tag_badges)

    with action_col:
        btn_act1, btn_act2 = st.columns(2)
        with btn_act1:
            if st.button(
                tr("project.task.new_task"),
                key="btn_open_new_task_plan",
                use_container_width=True,
                type="primary",
            ):
                st.session_state.creating_task_in_project_id = project.project_id
                st.rerun()
        with btn_act2:
            if st.button(
                tr("project.generate_video"),
                key="proj_generate_video_btn",
                use_container_width=True,
            ):
                st.session_state["target_project_id"] = project.project_id
                st.switch_page("pages/1_🎬_Home.py")

        c_edit, c_del = st.columns(2)
        with c_edit:
            if st.button(f"✏️ {tr('project.edit')}", key="btn_edit_proj_header", use_container_width=True):
                st.session_state.editing_project_id = project.project_id
                st.rerun()
        with c_del:
            if st.button(f"🗑️ {tr('project.delete')}", key="btn_del_proj_header", use_container_width=True):
                st.session_state.confirm_delete_project_id = project.project_id
                st.rerun()

    # Render Project Modals
    render_project_modals(trendlume)
    render_task_plan_modals(project_id, trendlume)

    # Project Stats Dashboard (Requirement 8)
    stats = run_async(trendlume.projects.get_project_stats(project_id))
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric(tr("project.task.title"), stats.get("total", 0))
    with m2:
        st.metric(tr("project.task.status_scheduled"), stats.get("scheduled", 0))
    with m3:
        st.metric(tr("project.task.status_running"), stats.get("running", 0))
    with m4:
        st.metric(tr("project.task.status_completed"), stats.get("completed", 0))
    with m5:
        st.metric(tr("project.task.status_failed"), stats.get("failed", 0))

    st.divider()

    # Upcoming Tasks Section (Requirement 8)
    render_upcoming_tasks_section(project_id, trendlume)

    # Sidebar Filter Controls
    with st.sidebar:
        st.markdown(f"**🔍 {tr('project.task.status_all')}**")
        status_options = {
            "all": tr("project.task.status_all"),
            TaskStatus.DRAFT: tr("project.task.status_draft"),
            TaskStatus.SCHEDULED: tr("project.task.status_scheduled"),
            TaskStatus.RUNNING: tr("project.task.status_running"),
            TaskStatus.COMPLETED: tr("project.task.status_completed"),
            TaskStatus.FAILED: tr("project.task.status_failed"),
            TaskStatus.CANCELLED: tr("project.task.status_cancelled"),
        }
        selected_status = st.selectbox(
            "Filter Status",
            options=list(status_options.keys()),
            format_func=lambda x: status_options[x],
            key="proj_filter_status",
            label_visibility="collapsed",
        )
        filter_status = None if selected_status == "all" else selected_status

        st.markdown(f"**📊 {tr('project.task.sort_by')}**")
        sort_options = {
            "created_at": tr("project.task.sort_created"),
            "completed_at": tr("project.task.sort_completed"),
            "scheduled_at": tr("project.task.scheduled_at"),
            "priority": tr("project.task.priority"),
            "title": tr("project.task.sort_title"),
            "duration": tr("project.task.sort_duration"),
        }
        sort_by = st.selectbox(
            "Sort By",
            options=list(sort_options.keys()),
            format_func=lambda x: sort_options[x],
            key="proj_sort_by",
            label_visibility="collapsed",
        )

        sort_order_options = {
            "desc": tr("project.task.sort_desc"),
            "asc": tr("project.task.sort_asc"),
        }
        sort_order = st.radio(
            "Sort Order",
            options=list(sort_order_options.keys()),
            format_func=lambda x: sort_order_options[x],
            key="proj_sort_order",
            label_visibility="collapsed",
            horizontal=True,
        )

        page_size = st.selectbox(
            tr("project.task.page_size"),
            options=[16, 32, 64],
            index=0,
            key="proj_page_size",
        )

    # Initialize task pagination
    if "project_task_page" not in st.session_state:
        st.session_state.project_task_page = 1

    # Load tasks paginated
    result = run_async(
        trendlume.persistence.list_tasks_paginated(
            page=st.session_state.project_task_page,
            page_size=page_size,
            status=filter_status,
            project_id=project_id,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    )

    tasks = result["tasks"]
    total = result["total"]
    total_pages = result["total_pages"]

    st.markdown(f"#### 🎬 {tr('project.task.title')} ({total})")

    if not tasks:
        st.info(tr("project.empty.tasks"))
    else:
        CARDS_PER_ROW = 4
        for i in range(0, len(tasks), CARDS_PER_ROW):
            cols = st.columns(CARDS_PER_ROW)
            for j in range(CARDS_PER_ROW):
                task_idx = i + j
                if task_idx < len(tasks):
                    with cols[j]:
                        render_grid_task_card(tasks[task_idx], trendlume)

    # Pagination
    if total_pages > 1:
        st.divider()
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button(
                "⬅️ Previous",
                disabled=st.session_state.project_task_page == 1,
                use_container_width=True,
                key="prev_page_btn",
            ):
                st.session_state.project_task_page -= 1
                st.rerun()
        with col2:
            st.markdown(
                f"<div style='text-align: center; padding-top: 8px;'>"
                f"{tr('project.task.page_info', page=st.session_state.project_task_page, total_pages=total_pages)}"
                f"</div>",
                unsafe_allow_html=True,
            )
        with col3:
            if st.button(
                "Next ➡️",
                disabled=st.session_state.project_task_page == total_pages,
                use_container_width=True,
                key="next_page_btn",
            ):
                st.session_state.project_task_page += 1
                st.rerun()


# ============================================================================
# Project List View
# ============================================================================

def render_project_list_view(trendlume):
    """Render top-level list of Projects"""
    col_title, col_new = st.columns([3, 1])
    with col_title:
        st.markdown(f"## 📁 {tr('project.page_title')}")
    with col_new:
        if st.button(
            tr("project.new_button"),
            key="open_new_proj_modal_btn",
            use_container_width=True,
            type="primary",
        ):
            st.session_state.show_new_project_modal = True
            st.rerun()

    # Render modals
    render_project_modals(trendlume)

    # Load all projects and pre-aggregate stats in a single pass (O(1) lookup per card)
    projects = run_async(trendlume.projects.list_projects())
    all_proj_stats = run_async(trendlume.projects.get_all_projects_stats())

    # Render statistics in sidebar
    with st.sidebar:
        st.markdown(f"**📊 {tr('project.page_title')}**")
        st.metric(tr("project.page_title"), len(projects))
        all_stats = run_async(trendlume.tasks.get_statistics())
        sc1, sc2 = st.columns(2)
        with sc1:
            st.metric(tr("project.task.status_completed"), all_stats.get("completed", 0))
        with sc2:
            st.metric(tr("project.task.status_failed"), all_stats.get("failed", 0))

    if not projects:
        st.info(tr("project.empty.projects"))
        return

    # Render projects in a grid of 2 columns
    CARDS_PER_ROW = 2
    for i in range(0, len(projects), CARDS_PER_ROW):
        cols = st.columns(CARDS_PER_ROW)
        for j in range(CARDS_PER_ROW):
            idx = i + j
            if idx < len(projects):
                proj = projects[idx]
                stats = all_proj_stats.get(proj.project_id, {"total": 0, "scheduled": 0, "completed": 0, "failed": 0})
                with cols[j]:
                    render_project_card(proj, stats, trendlume)


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for Projects page"""
    init_session_state()
    init_i18n()
    render_header()
    trendlume = get_trendlume()

    selected_project_id = st.session_state.get("selected_project_id")
    selected_task_id = st.session_state.get("selected_task_id")
    creating_task_in_project_id = st.session_state.get("creating_task_in_project_id")

    if selected_project_id and selected_task_id:
        render_task_detail_view(selected_task_id, selected_project_id, trendlume)
    elif creating_task_in_project_id:
        render_new_task_generation_view(creating_task_in_project_id, trendlume)
    elif selected_project_id:
        render_project_detail_view(selected_project_id, trendlume)
    else:
        render_project_list_view(trendlume)


if __name__ == "__main__":
    main()
