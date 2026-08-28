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
Unified Generation Form Components & Configuration Helpers

Provides shared Project selection, default generation configuration,
and template extraction logic reused across both the Generation Studio
and Project New Task workflows.
"""

from typing import Any, Dict, Optional

import streamlit as st

from web.i18n import tr
from web.utils.async_helpers import run_async


def get_default_generation_config() -> Dict[str, Any]:
    """
    Get system default generation configuration values.
    Used when a project does not define its own template.
    """
    return {
        "pipeline": "standard",
        "mode": "generate",
        "n_scenes": 5,
        "split_mode": "paragraph",
        "genre": "auto",
        "tts_inference_mode": "local",
        "tts_voice": "zh-CN-YunjianNeural",
        "tts_speed": 1.0,
        "tts_workflow": None,
        "ref_audio": None,
        "frame_template": "1080x1920/image_default.html",
        "template_params": {},
        "media_workflow": "image/flux_schnell",
        "prompt_prefix": "",
        "style_preset": None,
        "bgm_path": "default.mp3",
        "bgm_volume": 0.2,
        "media_width": 1080,
        "media_height": 1920,
    }


def clean_template_config(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize raw generation parameters to extract clean template configuration.
    Strictly strips task-specific runtime data (text, title, task_id, video, etc.).
    """
    clean = dict(raw_config)
    forbidden_keys = [
        "task_id", "project_id", "text", "title", "video", "storyboard",
        "assets", "status", "result", "executions", "metadata", "created_at",
        "completed_at", "scheduled_at", "priority", "batch_mode",
        "progress_callback", "final_video_path",
    ]
    for key in forbidden_keys:
        clean.pop(key, None)
    return clean


def render_project_selector(
    trendlume: Any,
    default_project_id: Optional[str] = None,
    disabled: bool = False,
    key: str = "generation_project_selector",
) -> Optional[str]:
    """
    Render a project selector dropdown for video generation workflows.
    
    Args:
        trendlume: TrendlumeCore service instance
        default_project_id: Initially selected project ID
        disabled: If True, locks selection to default_project_id (for Project -> New Task)
        key: Streamlit widget key
        
    Returns:
        Selected project_id or None
    """
    projects = run_async(trendlume.projects.list_projects())

    if disabled:
        # Fixed Project Mode (Project -> New Task)
        selected_proj = next((p for p in projects if p.project_id == default_project_id), None)
        proj_name = selected_proj.name if selected_proj else (default_project_id or "Current Project")
        st.markdown(f"**📁 {tr('project.selector.title')}:** `{proj_name}` 🔒")
        return default_project_id

    # Interactive Project Selection (Studio Generation Page)
    options = [None] + [p.project_id for p in projects]
    names = {None: tr("project.selector.no_project")}
    for p in projects:
        names[p.project_id] = f"📁 {p.name}"

    default_idx = 0
    if default_project_id and default_project_id in options:
        default_idx = options.index(default_project_id)

    # Ensure session_state does not contain an invalid option (e.g., deleted project)
    if key in st.session_state and st.session_state[key] not in options:
        del st.session_state[key]

    selected = st.selectbox(
        tr("project.selector.label"),
        options=options,
        index=default_idx,
        format_func=lambda x: names.get(x, str(x)),
        key=key,
        help=tr("project.selector.help"),
    )
    return selected


def create_progress_tracker():
    """
    Create a unified progress bar and status text tracker matching Home page behavior.
    Returns:
        progress_bar: st.progress element
        status_text: st.empty element
        update_progress: callable(event: Any) to pass to video generation pipeline
        finish_progress: callable() to set 100% and success message
    """
    progress_bar = st.progress(0)
    status_text = st.empty()

    def update_progress(event: Any):
        if hasattr(event, "event_type"):
            if event.event_type == "frame_step":
                action_key = f"progress.step_{event.action}"
                action_text = tr(action_key)
                message = tr(
                    "progress.frame_step",
                    current=event.frame_current,
                    total=event.frame_total,
                    step=event.step,
                    action=action_text
                )
            elif event.event_type == "processing_frame":
                message = tr(
                    "progress.frame",
                    current=event.frame_current,
                    total=event.frame_total
                )
            else:
                message = tr(f"progress.{event.event_type}")

            if getattr(event, "extra_info", None):
                message = f"{message} - {event.extra_info}"

            status_text.text(message)
            if hasattr(event, "progress"):
                progress_bar.progress(min(int(event.progress * 100), 99))
        else:
            status_text.text(str(event))

    def finish_progress():
        progress_bar.progress(100)
        status_text.text(tr("status.success"))

    return progress_bar, status_text, update_progress, finish_progress
