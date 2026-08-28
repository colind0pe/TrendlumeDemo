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
Standard Pipeline UI

Implements the classic 3-column layout for the Standard Pipeline.
"""

from typing import Any

import streamlit as st

# Import components
from web.components.content_input import (
    render_bgm_section,
    render_content_input,
    render_version_info,
)
from web.components.generation_form import render_project_selector
from web.components.output_preview import render_output_preview
from web.i18n import tr
from web.pipelines.base import PipelineUI, register_pipeline_ui
from web.utils.async_helpers import run_async


class StandardPipelineUI(PipelineUI):
    """
    UI for the Standard Video Generation Pipeline.
    Implements the classic 3-column layout.
    """
    name = "quick_create"
    icon = "⚡"
    
    @property
    def display_name(self):
        return tr("pipeline.quick_create.name")
    
    @property
    def description(self):
        return tr("pipeline.quick_create.description")
    
    def render(self, trendlume: Any):
        # Three-column layout
        left_col, middle_col, right_col = st.columns([1, 1, 1])
        
        # Check for applied template from project
        applied_template = st.session_state.get("studio_applied_template", None)

        # ====================================================================
        # Left Column: Project Selector, Content Input & BGM
        # ====================================================================
        with left_col:
            # Project Selector (Attribution)
            with st.container(border=True):
                # Consume target_project_id if set from navigation
                if "target_project_id" in st.session_state:
                    target_pid = st.session_state.pop("target_project_id")
                    if target_pid:
                        st.session_state["studio_project_selector"] = target_pid

                selected_project_id = render_project_selector(
                    trendlume,
                    default_project_id=st.session_state.get("studio_project_selector"),
                    key="studio_project_selector"
                )
                if selected_project_id:
                    proj = run_async(trendlume.projects.get_project(selected_project_id))
                    if proj and proj.template:
                        st.caption(f"💡 {tr('project.template.has_template_hint')}")
                        if st.button(tr('project.template.apply_button'), key="apply_proj_template_studio", use_container_width=True):
                            st.session_state["studio_applied_template"] = proj.template
                            clear_keys = [
                                "style_preset_selector", "prompt_prefix_input", "_active_style_preset",
                                "processing_mode", "input_text", "input_split_mode", "input_title",
                                "input_n_scenes", "batch_mode", "bgm_select_dropdown", "bgm_volume_slider",
                                "tts_inference_mode", "tts_local_voice", "tts_local_speed", "tts_workflow_select",
                                "ref_audio_upload", "selected_template", "template_type_selector",
                                "standard_image_workflow_source", "standard_video_workflow_source",
                            ]
                            for k in clear_keys:
                                st.session_state.pop(k, None)
                            st.rerun()

            # Content input (mode, text, title, n_scenes)
            content_params = render_content_input(initial_values=applied_template)
            
            # BGM selection (bgm_path, bgm_volume)
            bgm_params = render_bgm_section(initial_values=applied_template)
            
            # Version info & GitHub link
            render_version_info()
        
        # ====================================================================
        # Middle Column: Style Configuration
        # ====================================================================
        with middle_col:
            # Style configuration (TTS, template, workflow, etc.)
            from web.components.style_config import render_style_config
            style_params = render_style_config(trendlume, initial_values=applied_template)
        
        # ====================================================================
        # Right Column: Output Preview
        # ====================================================================
        with right_col:
            # Combine all parameters including project attribution
            video_params = {
                "pipeline": self.name,
                "project_id": selected_project_id,
                **content_params,
                **bgm_params,
                **style_params
            }
            
            # Render output preview (generate button, progress, video preview)
            render_output_preview(trendlume, video_params)


# Register self
register_pipeline_ui(StandardPipelineUI)
