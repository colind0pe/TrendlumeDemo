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

"""Compatibility config for migrated API provider clients.

This module keeps the old ``Config.X`` access pattern used by the copied
clients, while sourcing values from Trendlume's config manager first and
environment variables as a fallback.
"""

import os
from typing import Any


def _provider_config(provider: str) -> dict:
    try:
        from trendlume.config import config_manager

        config = config_manager.config.to_dict()
        return config.get("api_providers", {}).get(provider, {}) or {}
    except Exception:
        return {}


class _ConfigMeta(type):
    def __getattr__(cls, name: str) -> Any:
        mapping = {
            "PRINT_MODEL_INPUT": ("common", "print_model_input", False),
            "LOCAL_PROXY": ("common", "local_proxy", ""),
            "OPENAI_API_KEY": ("openai", "api_key", ""),
            "OPENAI_BASE_URL": ("openai", "base_url", ""),
            "DASHSCOPE_API_KEY": ("dashscope", "api_key", ""),
            "DASHSCOPE_BASE_URL": ("dashscope", "base_url", ""),
            "DEEPSEEK_API_KEY": ("deepseek", "api_key", ""),
            "DEEPSEEK_BASE_URL": ("deepseek", "base_url", ""),
            "GEMINI_API_KEY": ("gemini", "api_key", ""),
            "GOOGLE_GEMINI_BASE_URL": ("gemini", "base_url", ""),
            "ARK_API_KEY": ("ark", "api_key", ""),
            "ARK_BASE_URL": ("ark", "base_url", ""),
            "KLING_BASE_URL": ("kling", "base_url", ""),
            "KLING_ACCESS_KEY": ("kling", "access_key", ""),
            "KLING_SECRET_KEY": ("kling", "secret_key", ""),
        }

        if name not in mapping:
            raise AttributeError(name)

        provider, key, default = mapping[name]
        value = _provider_config(provider).get(key, default)
        env_value = os.getenv(name)
        if env_value is not None and env_value != "":
            return env_value
        return value


class Config(metaclass=_ConfigMeta):
    """Old-style config facade for migrated provider clients."""
