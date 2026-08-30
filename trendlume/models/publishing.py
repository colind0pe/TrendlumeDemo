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
Social Account, Credential, Publish Job, and Template Data Models
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PlatformName:
    """Supported social platform identifiers and display metadata"""
    DOUYIN = "douyin"
    MOCK = "mock"

    ALL_PLATFORMS: List[str] = [DOUYIN]
    DISPLAY_NAMES: Dict[str, str] = {
        DOUYIN: "🎵 抖音 (Douyin)",
        MOCK: "🧪 模拟平台 (Mock)",
    }
    ICONS: Dict[str, str] = {
        DOUYIN: "🎵",
        MOCK: "🧪",
    }

    @classmethod
    def get_display_name(cls, platform: str) -> str:
        plat = str(platform).lower().strip()
        return cls.DISPLAY_NAMES.get(plat, f"🌐 {platform.capitalize()}")


class AccountStatus:
    """Status options for SocialAccount"""
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPIRED = "expired"
    ERROR = "error"

    ALL_STATUSES: List[str] = [ACTIVE, DISABLED, EXPIRED, ERROR]
    LABELS: Dict[str, str] = {
        ACTIVE: "🟢 正常 (Active)",
        DISABLED: "⚪ 已禁用 (Disabled)",
        ERROR: "🔴 异常 (Error)",
        EXPIRED: "🟠 已过期 (Expired)",
    }

    @classmethod
    def get_badge(cls, status: str) -> str:
        return cls.LABELS.get(status, f"⚪ {status}")


class CredentialType:
    """Supported credential types"""
    COOKIE = "cookie"
    STORAGE_STATE = "storage_state"
    TOKEN = "token"
    SESSION = "session"
    API_KEY = "api_key"


class PublishJobStatus:
    """Standard lifecycle statuses for PublishJob"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"

    ALL_STATUSES: List[str] = [
        DRAFT,
        SCHEDULED,
        QUEUED,
        PUBLISHING,
        PUBLISHED,
        FAILED,
        CANCELLED,
    ]
    LABELS: Dict[str, str] = {
        PUBLISHED: "🟢 已发布 (Published)",
        PUBLISHING: "🔄 发布中 (Publishing...)",
        QUEUED: "🟡 排队中 (Queued)",
        SCHEDULED: "🕒 定时中 (Scheduled)",
        DRAFT: "⚪ 草稿 (Draft)",
        FAILED: "🔴 失败 (Failed)",
        CANCELLED: "⚫ 已取消 (Cancelled)",
    }

    @classmethod
    def get_badge(cls, status: str) -> str:
        return cls.LABELS.get(status, f"⚪ {status}")


class CredentialSummary(BaseModel):
    """
    Sanitized, safe representation of Credential for public API / UI exposure.
    Sensitive data is masked.
    """
    credential_id: str = Field(description="Credential unique identifier")
    platform: str = Field(description="Platform identifier (e.g. douyin)")
    credential_type: str = Field(default=CredentialType.COOKIE, description="Type of authentication data")
    has_data: bool = Field(default=True, description="Whether credential payload is present")
    masked_preview: str = Field(default="", description="Masked preview of the credential")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="ISO timestamp of creation")
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="ISO timestamp of last update")
    expires_at: Optional[str] = Field(default=None, description="ISO timestamp of credential expiry if known")
    is_valid: bool = Field(default=True, description="Whether credential is currently considered valid")


class Credential(BaseModel):
    """
    Authentication credential entity, decoupled from SocialAccount.
    Contains actual sensitive payload (cookies/tokens), stored safely in backend persistence.
    """
    credential_id: str = Field(default_factory=lambda: f"cred_{uuid.uuid4().hex[:8]}", description="Credential unique identifier")
    platform: str = Field(description="Platform identifier")
    credential_type: str = Field(default=CredentialType.COOKIE, description="Type of credential")
    data: Dict[str, Any] = Field(default_factory=dict, description="Sensitive credential payload")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="ISO timestamp of creation")
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="ISO timestamp of last update")
    expires_at: Optional[str] = Field(default=None, description="ISO timestamp of expiry")
    is_valid: bool = Field(default=True, description="Whether the credential passed recent validation")

    def to_summary(self) -> CredentialSummary:
        """Create a sanitized summary with masked preview for safe exposure."""
        preview = ""
        if self.credential_type in [CredentialType.COOKIE, CredentialType.STORAGE_STATE]:
            cookie_val = self.data.get("cookie") or self.data.get("raw") or ""
            if isinstance(cookie_val, str) and cookie_val:
                preview = f"{cookie_val[:6]}...{cookie_val[-4:]}" if len(cookie_val) > 10 else "***"
            elif isinstance(self.data.get("cookies"), list):
                preview = f"{len(self.data['cookies'])} cookies stored"
            elif isinstance(cookie_val, list):
                preview = f"{len(cookie_val)} cookies stored"
            else:
                preview = "Session/Cookie configured"
        elif self.credential_type == CredentialType.TOKEN:
            token = str(self.data.get("token") or self.data.get("access_token") or "")
            preview = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "***"
        elif self.credential_type == CredentialType.API_KEY:
            key = str(self.data.get("api_key") or self.data.get("key") or "")
            preview = f"{key[:3]}...{key[-3:]}" if len(key) > 6 else "***"
        else:
            preview = f"{self.credential_type} session configured"

        return CredentialSummary(
            credential_id=self.credential_id,
            platform=self.platform,
            credential_type=self.credential_type,
            has_data=bool(self.data),
            masked_preview=preview,
            created_at=self.created_at,
            updated_at=self.updated_at,
            expires_at=self.expires_at,
            is_valid=self.is_valid,
        )


class SocialAccount(BaseModel):
    """
    Social Account entity representing a creator identity on a specific platform.
    Decoupled from Credential entity via credential_id reference.
    """
    account_id: str = Field(default_factory=lambda: f"acc_{uuid.uuid4().hex[:8]}", description="Unique account identifier")
    platform: str = Field(description="Platform identifier (e.g. douyin)")
    account_name: str = Field(description="User-assigned alias/name for the account")
    username: Optional[str] = Field(default="", description="Platform-native user handle or ID")
    display_name: Optional[str] = Field(default="", description="Platform display nickname")
    avatar: Optional[str] = Field(default=None, description="Avatar image URL or local path")
    status: str = Field(default=AccountStatus.ACTIVE, description="Account status")
    credential_id: Optional[str] = Field(default=None, description="Reference to associated Credential")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Platform-specific default account settings")
    published_count: int = Field(default=0, description="Total successful published videos")
    failed_count: int = Field(default=0, description="Total failed publishing attempts")
    last_published_at: Optional[str] = Field(default=None, description="ISO timestamp of last successful publication")
    last_checked_at: Optional[str] = Field(default=None, description="ISO timestamp of last health/login check")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="ISO timestamp of creation")
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="ISO timestamp of last update")


class PublishJob(BaseModel):
    """
    Independent publish job entity linking generated videos/tasks to target social accounts.
    Separates common publishing metadata from platform-specific custom parameters.
    """
    job_id: str = Field(default_factory=lambda: f"job_{uuid.uuid4().hex[:8]}", description="Unique publish job identifier")
    task_id: Optional[str] = Field(default=None, description="Associated Trendlume Task ID")
    video_id: Optional[str] = Field(default=None, description="Associated Video ID (if separate from task)")
    video_path: Optional[str] = Field(default=None, description="Filesystem path to video file")
    account_id: str = Field(description="Target SocialAccount ID")
    platform: str = Field(description="Target platform identifier")
    title: str = Field(default="", description="Post / video title")
    description: Optional[str] = Field(default="", description="Post description / caption")
    tags: List[str] = Field(default_factory=list, description="List of topic tags")
    cover: Optional[str] = Field(default=None, description="Cover image path or URL")
    scheduled_at: Optional[str] = Field(default=None, description="ISO timestamp for scheduled publishing")
    status: str = Field(default=PublishJobStatus.DRAFT, description="Publish job status")
    attempt_count: int = Field(default=0, description="Number of execution attempts")
    max_attempts: int = Field(default=3, description="Maximum retry attempts")
    error_message: Optional[str] = Field(default=None, description="Last error message if failed")
    error_code: Optional[str] = Field(default=None, description="Error category code (e.g. AUTH_ERROR, NETWORK_ERROR)")
    next_retry_at: Optional[str] = Field(default=None, description="ISO timestamp for next scheduled retry execution")
    platform_post_id: Optional[str] = Field(default=None, description="Post/video ID returned by the platform")
    platform_custom_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Platform-specific parameters (e.g. Douyin declaration, location, visibility)",
    )
    started_at: Optional[str] = Field(default=None, description="ISO timestamp when execution started")
    completed_at: Optional[str] = Field(default=None, description="ISO timestamp when execution finished")
    published_at: Optional[str] = Field(default=None, description="ISO timestamp of successful publication")
    analytics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Baseline analytics stubs (e.g. view_count, like_count, comment_count, share_count)",
    )
    lock_token: Optional[str] = Field(default=None, description="Idempotency execution lock token")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="ISO timestamp of creation")
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="ISO timestamp of last update")


class PlatformTemplateConfig(BaseModel):
    """Platform-specific publishing template presets"""
    title_template: Optional[str] = Field(default=None, description="Title template with placeholders like {title}")
    description_template: Optional[str] = Field(default=None, description="Description template with placeholders like {description}")
    tags: List[str] = Field(default_factory=list, description="Default tags for this platform")
    custom_params: Dict[str, Any] = Field(default_factory=dict, description="Platform specific parameters preset (e.g. category, declaration)")


class PublishTemplate(BaseModel):
    """
    Publishing Template for recurring cross-platform content adaptation.
    """
    template_id: str = Field(default_factory=lambda: f"tpl_{uuid.uuid4().hex[:8]}", description="Unique template identifier")
    template_name: str = Field(description="User-facing template name (e.g. 东方美学风, 科技解说)")
    description: Optional[str] = Field(default="", description="Template description")
    platform_configs: Dict[str, PlatformTemplateConfig] = Field(
        default_factory=dict,
        description="Map of platform_name -> PlatformTemplateConfig",
    )
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="ISO timestamp of creation")
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="ISO timestamp of last update")
