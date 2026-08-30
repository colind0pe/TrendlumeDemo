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
Publishing Structured Logger with Credential Masking

Logs publishing lifecycle events with context (job_id, platform, account_id, attempt)
while strictly scrubbing and masking all sensitive credentials, cookies, and tokens.
"""

import re
from typing import Optional

from loguru import logger

# Regex patterns matching sensitive cookie and token values
SECRET_PATTERNS = [
    re.compile(r'(sessionid=)([^;\s]+)', re.IGNORECASE),
    re.compile(r'(sid_guard=)([^;\s]+)', re.IGNORECASE),
    re.compile(r'(passport_csrf_token=)([^;\s]+)', re.IGNORECASE),
    re.compile(r'(SESSDATA=)([^;\s]+)', re.IGNORECASE),
    re.compile(r'(bili_jct=)([^;\s]+)', re.IGNORECASE),
    re.compile(r'(web_session=)([^;\s]+)', re.IGNORECASE),
    re.compile(r'(token["\']?\s*[:=]\s*["\']?)([^"\'\s;,]+)', re.IGNORECASE),
    re.compile(r'(access_token["\']?\s*[:=]\s*["\']?)([^"\'\s;,]+)', re.IGNORECASE),
    re.compile(r'(authorization["\']?\s*[:=]\s*["\']?bearer\s+)([^"\'\s;,]+)', re.IGNORECASE),
    re.compile(r'(cookie["\']?\s*[:=]\s*["\']?)([^"\']{15,})', re.IGNORECASE),
]


def mask_sensitive_data(text: str) -> str:
    """Scrub sensitive credentials from a log text"""
    if not text or not isinstance(text, str):
        return text

    scrubbed = text
    for pattern in SECRET_PATTERNS:
        scrubbed = pattern.sub(r'\1***MASKED***', scrubbed)

    return scrubbed


class PublishLogger:
    """
    Structured context-aware logger for the publishing subsystem.
    """

    @classmethod
    def _format_prefix(
        cls,
        job_id: Optional[str] = None,
        platform: Optional[str] = None,
        account_id: Optional[str] = None,
        attempt: Optional[int] = None,
        max_attempts: Optional[int] = None,
    ) -> str:
        parts = ["[PUBLISH]"]
        if job_id:
            parts.append(f"[job={job_id[:12]}]")
        if platform:
            parts.append(f"[{platform}]")
        if account_id:
            parts.append(f"[acc={account_id[:10]}]")
        if attempt is not None:
            max_str = f"/{max_attempts}" if max_attempts else ""
            parts.append(f"[attempt={attempt}{max_str}]")
        return "".join(parts)

    @classmethod
    def _log(cls, level: str, message: str, **kwargs):
        prefix = cls._format_prefix(**kwargs)
        safe_msg = mask_sensitive_data(message)
        getattr(logger, level)(f"{prefix} {safe_msg}")

    @classmethod
    def info(cls, message: str, **kwargs):
        cls._log("info", message, **kwargs)

    @classmethod
    def warning(cls, message: str, **kwargs):
        cls._log("warning", message, **kwargs)

    @classmethod
    def error(cls, message: str, **kwargs):
        cls._log("error", message, **kwargs)

    @classmethod
    def debug(cls, message: str, **kwargs):
        cls._log("debug", message, **kwargs)

