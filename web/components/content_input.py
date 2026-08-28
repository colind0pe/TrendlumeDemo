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
Content input components for web UI (left column)
"""

import streamlit as st

from web.i18n import tr
from web.utils.async_helpers import get_project_version


def render_content_input(initial_values: dict = None, key_prefix: str = ""):
    """Render content input section (left column) with batch support"""
    initial = initial_values or {}
    with st.container(border=True):
        st.markdown(f"**{tr('section.content_input')}**")
        
        # ====================================================================
        # Step 1: Batch mode toggle (highest priority)
        # ====================================================================
        batch_mode = st.checkbox(
            tr("batch.mode_label"),
            value=initial.get("batch_mode", False),
            help=tr("batch.mode_help"),
            key=f"{key_prefix}batch_mode",
        )
        
        if not batch_mode:
            # ================================================================
            # Single task mode (original logic, unchanged)
            # ================================================================
            # Processing mode selection
            initial_mode = initial.get("mode", "generate")
            mode = st.radio(
                "Processing Mode",
                ["generate", "fixed"],
                horizontal=True,
                index=0 if initial_mode == "generate" else 1,
                format_func=lambda x: tr(f"mode.{x}"),
                label_visibility="collapsed",
                key=f"{key_prefix}processing_mode",
            )
            
            # Text input (unified for both modes)
            text_placeholder = tr("input.topic_placeholder") if mode == "generate" else tr("input.content_placeholder")
            text_height = 120 if mode == "generate" else 200
            text_help = tr("input.text_help_generate") if mode == "generate" else tr("input.text_help_fixed")
            
            text = st.text_area(
                tr("input.text"),
                value=initial.get("text", ""),
                placeholder=text_placeholder,
                height=text_height,
                help=text_help,
                key=f"{key_prefix}input_text",
            )
            
            # Split mode selector (only show in fixed mode)
            if mode == "fixed":
                split_mode_options = {
                    "paragraph": tr("split.mode_paragraph"),
                    "line": tr("split.mode_line"),
                    "sentence": tr("split.mode_sentence"),
                }
                init_split = initial.get("split_mode", "paragraph")
                split_keys = list(split_mode_options.keys())
                split_idx = split_keys.index(init_split) if init_split in split_keys else 0
                split_mode = st.selectbox(
                    tr("split.mode_label"),
                    options=split_keys,
                    format_func=lambda x: split_mode_options[x],
                    index=split_idx,
                    help=tr("split.mode_help"),
                    key=f"{key_prefix}input_split_mode",
                )
            else:
                split_mode = "paragraph"  # Default for generate mode (not used)
            
            # Title input (optional for both modes)
            title = st.text_input(
                tr("input.title"),
                value=initial.get("title", ""),
                placeholder=tr("input.title_placeholder"),
                help=tr("input.title_help"),
                key=f"{key_prefix}input_title",
            )
            
            # Number of scenes (only show in generate mode)
            if mode == "generate":
                init_scenes = int(initial.get("n_scenes", 5))
                init_scenes = max(3, min(30, init_scenes))
                n_scenes = st.slider(
                    tr("video.frames"),
                    min_value=3,
                    max_value=30,
                    value=init_scenes,
                    help=tr("video.frames_help"),
                    label_visibility="collapsed",
                    key=f"{key_prefix}input_n_scenes",
                )
                st.caption(tr("video.frames_label", n=n_scenes))
            else:
                # Fixed mode: n_scenes is ignored, set default value
                n_scenes = 5
                st.info(tr("video.frames_fixed_mode_hint"))
            
            return {
                "batch_mode": False,
                "mode": mode,
                "text": text,
                "title": title,
                "n_scenes": n_scenes,
                "split_mode": split_mode,
                "genre": initial.get("genre", "auto"),
                "hook_type": initial.get("hook_type", None),
                "custom_prompt": initial.get("custom_prompt", ""),
            }


        
        else:
            # ================================================================
            # Batch mode (simplified YAGNI version)
            # ================================================================
            st.markdown(f"**{tr('batch.section_title')}**")
            
            # Batch rules info
            st.info(f"""
**{tr('batch.rules_title')}**
- ✅ {tr('batch.rule_1')}
- ✅ {tr('batch.rule_2')}
- ✅ {tr('batch.rule_3')}
            """)
            
            # Batch input method
            batch_input_method = st.radio(
                "Batch Input Method",
                ["text", "file"],
                horizontal=True,
                label_visibility="collapsed"
            )
            
            if batch_input_method == "text":
                topics_text = st.text_area(
                    tr("batch.topics_label"),
                    placeholder=tr("batch.topics_placeholder"),
                    height=180,
                    help=tr("batch.topics_help")
                )
                if topics_text:
                    from web.utils.batch_manager import parse_topics_from_text
                    topics = parse_topics_from_text(topics_text)
                    if len(topics) > 10:
                        st.error(tr("batch.count_error", count=len(topics)))
                        topics = []
                    else:
                        st.success(tr("batch.count_success", count=len(topics)))
                        
                        # Preview topics list
                        with st.expander(tr("batch.preview_title"), expanded=False):
                            for i, topic in enumerate(topics, 1):
                                st.markdown(f"`{i}.` {topic}")
                else:
                    topics = []
            else:
                topics = []
            
            st.markdown("---")
            
            # Title prefix (optional)
            title_prefix = st.text_input(
                tr("batch.title_prefix_label"),
                placeholder=tr("batch.title_prefix_placeholder"),
                help=tr("batch.title_prefix_help")
            )
            
            # Number of scenes (unified for all videos)
            n_scenes = st.slider(
                tr("batch.n_scenes_label"),
                min_value=3,
                max_value=30,
                value=5,
                help=tr("batch.n_scenes_help")
            )
            st.caption(tr("batch.n_scenes_caption", n=n_scenes))
            
            # Config info
            st.info(f"📌 {tr('batch.config_info')}")
            
            return {
                "batch_mode": True,
                "topics": topics,
                "mode": "generate",  # Fixed to AI generate content
                "title_prefix": title_prefix,
                "n_scenes": n_scenes,
                "genre": "auto",
                "hook_type": None,
                "custom_prompt": "",
            }


def render_bgm_section(key_prefix="", initial_values: dict = None):
    """Render BGM selection section"""
    initial = initial_values or {}
    with st.container(border=True):
        st.markdown(f"**{tr('section.bgm')}**")
        
        with st.expander(tr("help.feature_description"), expanded=False):
            st.markdown(f"**{tr('help.what')}**")
            st.markdown(tr("bgm.what"))
            st.markdown(f"**{tr('help.how')}**")
            st.markdown(tr("bgm.how"))
        
        # Dynamically scan bgm folder for music files (merged from bgm/ and data/bgm/)
        from trendlume.utils.os_util import list_resource_files
        
        try:
            all_files = list_resource_files("bgm")
            # Filter to audio files only
            audio_extensions = ('.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg')
            bgm_files = sorted([f for f in all_files if f.lower().endswith(audio_extensions)])
        except Exception as e:
            st.warning(f"Failed to load BGM files: {e}")
            bgm_files = []
        
        # Add special "None" option
        bgm_options = [tr("bgm.none")] + bgm_files
        
        # Default to configured initial value or "default.mp3" if exists, otherwise first option
        init_bgm = initial.get("bgm_path")
        default_index = 0
        if init_bgm and init_bgm in bgm_options:
            default_index = bgm_options.index(init_bgm)
        elif init_bgm is None and "default.mp3" in bgm_files:
            default_index = bgm_options.index("default.mp3")
        
        bgm_choice = st.selectbox(
            "BGM",
            bgm_options,
            index=default_index,
            label_visibility="collapsed",
            key=f"{key_prefix}bgm_selector"
        )
        
        # BGM volume slider (only show when BGM is selected)
        if bgm_choice != tr("bgm.none"):
            init_vol = float(initial.get("bgm_volume", 0.2))
            init_vol = max(0.0, min(0.5, init_vol))
            bgm_volume = st.slider(
                tr("bgm.volume"),
                min_value=0.0,
                max_value=0.5,
                value=init_vol,
                step=0.01,
                format="%.2f",
                key=f"{key_prefix}bgm_volume_slider",
                help=tr("bgm.volume_help")
            )
        else:
            bgm_volume = 0.2  # Default value when no BGM selected
        
        # BGM preview button (only if BGM is not "None")
        if bgm_choice != tr("bgm.none"):
            if st.button(tr("bgm.preview"), key=f"{key_prefix}preview_bgm", use_container_width=True):
                from trendlume.utils.os_util import get_resource_path, resource_exists
                try:
                    if resource_exists("bgm", bgm_choice):
                        bgm_file_path = get_resource_path("bgm", bgm_choice)
                        st.audio(bgm_file_path)
                    else:
                        st.error(tr("bgm.preview_failed", file=bgm_choice))
                except Exception as e:
                    st.error(f"{tr('bgm.preview_failed', file=bgm_choice)}: {e}")
        
        # Use full filename for bgm_path (including extension)
        bgm_path = None if bgm_choice == tr("bgm.none") else bgm_choice
    
    return {
        "bgm_path": bgm_path,
        "bgm_volume": bgm_volume
    }


def render_version_info():
    """Render version info"""
    with st.container(border=True):
        st.markdown(f"**{tr('version.title')}**")
        version = get_project_version()
        st.markdown(f"{tr('version.current')}: `{version}`", unsafe_allow_html=True)

