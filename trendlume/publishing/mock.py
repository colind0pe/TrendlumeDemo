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
Mock Platform Publisher for Testing and Dry-Run Verification
"""

import time
from typing import Optional

from trendlume.models.publishing import Credential, CredentialType, PublishJob, SocialAccount
from trendlume.publishing.base import (
    AccountCheckResult,
    BasePlatformPublisher,
    PlatformCapabilities,
    PublishResult,
)


class MockPlatformPublisher(BasePlatformPublisher):
    """
    Mock publisher used for unit testing, dry-runs, and local development.
    Validates input parameters and returns simulated successful publish results.
    """

    platform = "mock"
    capabilities = PlatformCapabilities(
        platform_name="mock",
        display_name="Mock Platform",
        icon="🧪",
        supports_video=True,
        supports_images=True,
        supports_scheduling=True,
        max_title_length=200,
        max_description_length=2000,
        max_tags=20,
        required_credential_type=CredentialType.COOKIE,
        custom_params_schema={
            "mock_mode": {"type": "string", "default": "success", "enum": ["success", "fail"]},
        },
    )

    async def check_account(
        self,
        account: SocialAccount,
        credential: Optional[Credential],
    ) -> AccountCheckResult:
        """Simulate checking account status"""
        if not credential or not credential.data:
            return AccountCheckResult(
                is_valid=False,
                error_message="Credential missing or empty for mock account",
            )

        if credential.data.get("mock_invalid"):
            return AccountCheckResult(
                is_valid=False,
                error_message="Simulated expired credential",
            )

        return AccountCheckResult(
            is_valid=True,
            username=account.username or "mock_user",
            display_name=account.display_name or "Mock Creator",
            avatar="https://api.dicebear.com/7.x/bottts/svg?seed=mock",
        )

    async def publish_video(
        self,
        job: PublishJob,
        account: SocialAccount,
        credential: Optional[Credential],
    ) -> PublishResult:
        """Simulate publishing a video"""
        if not job.title:
            return PublishResult(success=False, error_message="Video title cannot be empty")

        mode = job.platform_custom_params.get("mock_mode", "success")
        if mode == "fail":
            return PublishResult(
                success=False,
                error_message="Simulated mock publisher failure",
            )

        post_id = f"mock_post_{int(time.time())}"
        return PublishResult(
            success=True,
            platform_post_id=post_id,
            post_url=f"https://example.com/posts/{post_id}",
            extra_info={"simulated": True, "account": account.account_name},
        )
