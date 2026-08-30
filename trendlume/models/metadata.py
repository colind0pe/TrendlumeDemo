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
Platform Metadata and Publishing Configuration Models
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class BasePlatformMetadata(BaseModel):
    """
    Base platform metadata model.
    Common fields shared across social publishing platforms.
    """
    title: str = Field(default="", description="Post / video title")
    description: str = Field(default="", description="Post caption / description")
    tags: List[str] = Field(default_factory=list, description="Topic hashtag list")
    cover: Optional[str] = Field(default=None, description="Cover image path or URL")
    platform_custom_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Platform-specific custom parameters",
    )


class DouyinConstraints:
    """Platform limits and validation constraints for Douyin"""
    MAX_TITLE_LENGTH: int = 30
    MAX_DESCRIPTION_LENGTH: int = 1000
    MAX_TAGS: int = 10


class DouyinVisibility:
    """Standard visibility presets for Douyin platform"""
    PUBLIC = "public"
    FRIEND = "friend"
    PRIVATE = "private"

    ALL_OPTIONS: List[str] = [PUBLIC, FRIEND, PRIVATE]
    DEFAULT: str = PUBLIC
    LABELS: Dict[str, str] = {
        PUBLIC: "公开 (所有人可见)",
        FRIEND: "好友可见",
        PRIVATE: "仅自己可见",
    }

    @classmethod
    def get_label(cls, visibility: str) -> str:
        return cls.LABELS.get(visibility, visibility)


class DouyinDeclaration:
    """
    Standard preset options for Douyin self-declaration (自主声明).
    Centralized canonical source of truth.
    """
    AI_GENERATED = "内容由AI生成"
    PERSONAL_OPINION_REF = "个人观点，仅供参考"
    PERSONAL_OPINION_VIEW = "内容为个人观点或见解"
    SOURCED_FROM_WEB = "内容取材网络"

    ALL_OPTIONS: List[str] = [
        AI_GENERATED,
        PERSONAL_OPINION_REF,
        PERSONAL_OPINION_VIEW,
        SOURCED_FROM_WEB,
    ]
    DEFAULT: str = AI_GENERATED

    @classmethod
    def get_options_with_empty(cls) -> List[str]:
        """Returns options list with empty string for optional selection in UI forms."""
        return ["", *cls.ALL_OPTIONS]


class DouyinMetadata(BasePlatformMetadata):
    """
    Douyin (抖音) specific metadata model.
    Validated according to Douyin platform specifications.
    """
    title: str = Field(
        default="",
        max_length=DouyinConstraints.MAX_TITLE_LENGTH,
        description=f"Douyin video title (max {DouyinConstraints.MAX_TITLE_LENGTH} characters)",
    )
    description: str = Field(
        default="",
        max_length=DouyinConstraints.MAX_DESCRIPTION_LENGTH,
        description=f"Douyin video caption/description (max {DouyinConstraints.MAX_DESCRIPTION_LENGTH} characters)",
    )
    tags: List[str] = Field(
        default_factory=list,
        description=f"Topic hashtags without # symbol (max {DouyinConstraints.MAX_TAGS} tags)",
    )
    declaration: Optional[str] = Field(
        default=DouyinDeclaration.DEFAULT,
        description=f"Self-declaration: {DouyinDeclaration.ALL_OPTIONS}",
    )
    location: Optional[str] = Field(
        default="",
        description="Geographic location / POI",
    )
    collection_name: Optional[str] = Field(
        default="",
        description="Collection / series name",
    )
    visibility: str = Field(
        default=DouyinVisibility.DEFAULT,
        description=f"Visibility: {DouyinVisibility.ALL_OPTIONS}",
    )
    allow_download: bool = Field(
        default=True,
        description="Whether download is allowed",
    )

    @field_validator("title", mode="before")
    @classmethod
    def sanitize_title(cls, v: Any) -> str:
        if v is None:
            return ""
        s = str(v).strip()
        return s[:DouyinConstraints.MAX_TITLE_LENGTH]

    @field_validator("tags", mode="before")
    @classmethod
    def sanitize_tags(cls, v: Any) -> List[str]:
        if not v:
            return []
        if isinstance(v, str):
            v = [t.strip() for t in v.split(",") if t.strip()]
        cleaned = [str(t).strip().lstrip("#") for t in v if str(t).strip()]
        return cleaned[:DouyinConstraints.MAX_TAGS]

    def model_post_init(self, __context: Any) -> None:
        """Populate platform_custom_params with Douyin-specific fields"""
        # Sync to platform_custom_params
        if not self.platform_custom_params:
            self.platform_custom_params = {}
        if self.declaration:
            self.platform_custom_params["declaration"] = self.declaration
        if self.location:
            self.platform_custom_params["location"] = self.location
        if self.collection_name:
            self.platform_custom_params["collection_name"] = self.collection_name
        self.platform_custom_params["visibility"] = self.visibility
        self.platform_custom_params["allow_download"] = self.allow_download


class PublishingMode:
    """Publishing trigger mode constants"""
    NONE = "none"
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"

    ALL_MODES: List[str] = [NONE, IMMEDIATE, SCHEDULED]
    DEFAULT: str = NONE

    LABELS: Dict[str, str] = {
        NONE: "🚫 不发布 (Don't Publish)",
        IMMEDIATE: "⚡ 生成完成后立即发布 (Publish Immediately)",
        SCHEDULED: "⏰ 定时发布 (Scheduled Publish)",
    }

    @classmethod
    def get_label(cls, mode: str) -> str:
        return cls.LABELS.get(mode, mode)


class PublishingConfig(BaseModel):
    """
    Publishing configuration attached to a video generation task.
    Defines auto-publishing behavior upon video completion.
    """
    mode: str = Field(
        default=PublishingMode.NONE,
        description=f"Publish mode: {PublishingMode.ALL_MODES}",
    )
    platform: str = Field(
        default="douyin",
        description="Target social platform (e.g. 'douyin')",
    )
    account_ids: List[str] = Field(
        default_factory=list,
        description="List of target SocialAccount IDs",
    )
    scheduled_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp for scheduled publication (if mode == 'scheduled')",
    )
    metadata_override: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional manual metadata override dict",
    )
