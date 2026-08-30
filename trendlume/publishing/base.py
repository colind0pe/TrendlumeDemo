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
Platform Publisher Base Interface and Data Structures
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from trendlume.models.publishing import Credential, CredentialType, PublishJob, SocialAccount


@dataclass
class PlatformCapabilities:
    """Platform upload and publishing capabilities metadata"""
    platform_name: str
    display_name: str
    icon: str = "🌐"
    supports_video: bool = True
    supports_images: bool = False
    supports_scheduling: bool = True
    max_title_length: int = 100
    max_description_length: int = 1000
    max_tags: int = 10
    required_credential_type: str = CredentialType.COOKIE
    custom_params_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccountCheckResult:
    """Result of checking social account status / credentials"""
    is_valid: bool
    username: Optional[str] = None
    display_name: Optional[str] = None
    avatar: Optional[str] = None
    error_message: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PublishResult:
    """Result of executing a publish operation"""
    success: bool
    platform_post_id: Optional[str] = None
    post_url: Optional[str] = None
    error_message: Optional[str] = None
    extra_info: Dict[str, Any] = field(default_factory=dict)


class BasePlatformPublisher(ABC):
    """
    Unified abstract publisher interface for social platforms.
    Kept minimal, robust, and decoupled from platform-specific SDKs/browsers.
    """

    platform: str = ""
    capabilities: PlatformCapabilities

    @abstractmethod
    async def check_account(
        self,
        account: SocialAccount,
        credential: Optional[Credential],
    ) -> AccountCheckResult:
        """
        Check if the account credentials and login state are valid.
        """
        pass

    @abstractmethod
    async def publish_video(
        self,
        job: PublishJob,
        account: SocialAccount,
        credential: Optional[Credential],
    ) -> PublishResult:
        """
        Publish a video post to the target platform.
        """
        pass

    def validate_publish_request(
        self,
        job: PublishJob,
        credential: Optional[Credential],
    ) -> Optional[PublishResult]:
        """
        Standard validation for publish requests.
        Returns a PublishResult with success=False if validation fails, otherwise None.
        """
        if not credential or not credential.data:
            return PublishResult(success=False, error_message=f"[AUTH_ERROR] 缺少{self.capabilities.display_name}登录凭据")

        if not job.title or not job.title.strip():
            return PublishResult(success=False, error_message="[VALIDATION_ERROR] 视频标题不能为空")

        video_path = Path(job.video_path) if job.video_path else None
        if not video_path or not video_path.exists():
            return PublishResult(
                success=False,
                error_message=f"[VALIDATION_ERROR] 视频文件不存在: {job.video_path}",
            )
        
        return None

    def sanitize_title(self, title: str) -> str:
        """Trim and bound title length by platform capabilities"""
        clean = (title or "").strip()
        max_len = self.capabilities.max_title_length
        return clean[:max_len] if max_len else clean

    def format_error(self, error: Any, fallback_message: str = "") -> PublishResult:
        """Format an exception into a standardized PublishResult with AUTH_ERROR classification"""
        err_str = str(error) or fallback_message
        if "login" in err_str.lower() or "auth" in err_str.lower():
            return PublishResult(success=False, error_message=f"[AUTH_ERROR] {err_str}")
        return PublishResult(success=False, error_message=f"[UPLOAD_ERROR] {err_str}")
