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
Publishing Configuration Component for Generation Workflows

Provides seamless publishing configuration (mode, platform, multi-account selection, scheduled time)
for Studio generation and Project Task creation.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import streamlit as st

from trendlume.models.metadata import PublishingMode
from trendlume.models.publishing import AccountStatus, PlatformName
from web.i18n import tr
from web.utils.async_helpers import run_async


def render_publishing_config(
    trendlume: Any,
    initial_values: Optional[Dict[str, Any]] = None,
    key_prefix: str = "",
) -> Dict[str, Any]:
    """
    Render publishing settings accordion/section.
    
    Args:
        trendlume: TrendlumeCore instance
        initial_values: Optional initial dictionary containing 'publishing' config
        key_prefix: Unique widget key prefix
        
    Returns:
        Dict with 'publishing': {'mode': str, 'platform': str, 'account_ids': List[str], 'scheduled_at': Optional[str]}
    """
    initial_values = initial_values or {}
    pub_init = initial_values.get("publishing", {})

    with st.container(border=True):
        st.markdown(f"**📢 {tr('publishing.config_title', fallback='社交平台发布设置 (Publishing Settings)')}**")

        mode_options = PublishingMode.LABELS

        default_mode = pub_init.get("mode", PublishingMode.DEFAULT)
        if default_mode not in mode_options:
            default_mode = PublishingMode.DEFAULT

        mode_keys = PublishingMode.ALL_MODES
        default_mode_idx = mode_keys.index(default_mode)

        selected_mode = st.radio(
            "发布方式 (Publish Mode)",
            options=mode_keys,
            index=default_mode_idx,
            format_func=lambda m: mode_options.get(m, m),
            key=f"{key_prefix}pub_mode",
            horizontal=False,
            label_visibility="collapsed",
        )

        if selected_mode == PublishingMode.NONE:
            return {
                "publishing": {
                    "mode": PublishingMode.NONE,
                    "platform": PlatformName.DOUYIN,
                    "account_ids": [],
                    "scheduled_at": None,
                }
            }

        # Platform Selection
        platform = PlatformName.DOUYIN

        p_col1, p_col2 = st.columns([1, 2])
        with p_col1:
            st.selectbox(
                "目标平台 (Platform)",
                options=PlatformName.ALL_PLATFORMS,
                format_func=lambda x: PlatformName.get_display_name(x),
                index=0,
                key=f"{key_prefix}pub_platform",
            )

        # Accounts Selection
        all_accounts = run_async(trendlume.publishing.list_accounts(platform=platform))
        active_accounts = [a for a in all_accounts if a.status != AccountStatus.DISABLED]

        with p_col2:
            if not active_accounts:
                st.warning("⚠️ 暂无可用抖音账号。请先前往「📢 发布中心」扫码或导入 Cookie 登录账号。")
                account_ids = []
            else:
                account_map = {
                    a.account_id: f"{a.account_name} ({a.display_name or a.username or '抖音账号'})"
                    for a in active_accounts
                }
                default_accounts = [
                    aid for aid in pub_init.get("account_ids", []) if aid in account_map
                ]
                if not default_accounts and active_accounts:
                    default_accounts = [active_accounts[0].account_id]

                account_ids = st.multiselect(
                    "选择发布账号 (可多选)",
                    options=list(account_map.keys()),
                    default=default_accounts,
                    format_func=lambda x: account_map.get(x, str(x)),
                    key=f"{key_prefix}pub_accounts",
                    help="同一个视频将自动适配生成平台元数据并独立分发至所选账号",
                )

        scheduled_iso = None
        if selected_mode == "scheduled":
            st.markdown("🕒 **设定发布时间**")
            t_col1, t_col2 = st.columns(2)
            with t_col1:
                sched_date = st.date_input(
                    "发布日期",
                    value=datetime.now().date(),
                    key=f"{key_prefix}pub_sched_date",
                )
            with t_col2:
                sched_time = st.time_input(
                    "发布时间",
                    value=(datetime.now() + timedelta(hours=1)).time(),
                    key=f"{key_prefix}pub_sched_time",
                )
            dt = datetime.combine(sched_date, sched_time)
            scheduled_iso = dt.isoformat()
            st.caption(f"📌 将于 `{dt.strftime('%Y-%m-%d %H:%M')}` 自动调度发布")

        return {
            "publishing": {
                "mode": selected_mode,
                "platform": platform,
                "account_ids": account_ids,
                "scheduled_at": scheduled_iso,
            }
        }
