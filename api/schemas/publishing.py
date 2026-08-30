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
Publishing API Schemas

Request and Response models for Social Accounts, Credentials, and Publish Jobs.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from trendlume.models.publishing import CredentialSummary

# ============================================================================
# Platform Info Schemas
# ============================================================================

class PlatformCapabilityResponse(BaseModel):
    """Platform capabilities and schema information"""
    platform: str
    display_name: str
    icon: str
    supports_video: bool
    supports_images: bool
    supports_scheduling: bool
    max_title_length: int
    max_description_length: int
    max_tags: int
    required_credential_type: str
    custom_params_schema: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Social Account Schemas
# ============================================================================

class SocialAccountCreateRequest(BaseModel):
    """Request payload for creating a new social account"""
    platform: str = Field(..., description="Platform identifier (e.g. douyin)")
    account_name: str = Field(..., description="User-friendly name or alias")
    username: Optional[str] = Field("", description="Platform account username or ID")
    display_name: Optional[str] = Field("", description="Display nickname")
    avatar: Optional[str] = Field(None, description="Avatar image URL or local path")
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Platform custom settings")
    credential_type: Optional[str] = Field(None, description="Credential type (cookie, token, etc.)")
    credential_data: Optional[Dict[str, Any]] = Field(None, description="Credential payload data")


class SocialAccountUpdateRequest(BaseModel):
    """Request payload for updating an existing social account"""
    account_name: Optional[str] = Field(None, description="Updated user-friendly alias")
    username: Optional[str] = Field(None, description="Platform account username")
    display_name: Optional[str] = Field(None, description="Display nickname")
    avatar: Optional[str] = Field(None, description="Avatar URL or path")
    status: Optional[str] = Field(None, description="Account status (active, disabled)")
    settings: Optional[Dict[str, Any]] = Field(None, description="Platform settings")


class SocialAccountResponse(BaseModel):
    """Safe response for social account data without raw credentials"""
    account_id: str
    platform: str
    account_name: str
    username: Optional[str] = ""
    display_name: Optional[str] = ""
    avatar: Optional[str] = None
    status: str
    has_credential: bool = False
    credential_summary: Optional[CredentialSummary] = None
    settings: Dict[str, Any] = Field(default_factory=dict)
    last_checked_at: Optional[str] = None
    created_at: str
    updated_at: str


class AccountCheckResponse(BaseModel):
    """Response of checking social account login / credential status"""
    account_id: str
    is_valid: bool
    username: Optional[str] = None
    display_name: Optional[str] = None
    avatar: Optional[str] = None
    error_message: Optional[str] = None
    checked_at: str


# ============================================================================
# Credential Schemas
# ============================================================================

class CredentialSetRequest(BaseModel):
    """Request payload for setting/updating an account's credential"""
    credential_type: str = Field("cookie", description="Type: cookie, token, session, api_key")
    data: Dict[str, Any] = Field(..., description="Credential payload dictionary")
    expires_at: Optional[str] = Field(None, description="Optional ISO expiration timestamp")


# ============================================================================
# Publish Job Schemas
# ============================================================================

class PublishJobCreateRequest(BaseModel):
    """Request payload for creating a publish job"""
    account_id: str = Field(..., description="Target SocialAccount ID")
    title: str = Field(..., description="Post title")
    description: Optional[str] = Field("", description="Post description / caption")
    tags: Optional[List[str]] = Field(default_factory=list, description="Topic tags")
    cover: Optional[str] = Field(None, description="Cover image path or URL")
    task_id: Optional[str] = Field(None, description="Associated Trendlume Task ID")
    video_id: Optional[str] = Field(None, description="Associated Video ID")
    video_path: Optional[str] = Field(None, description="Direct filesystem video path")
    scheduled_at: Optional[str] = Field(None, description="Optional scheduled execution ISO timestamp")
    platform_custom_params: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Platform specific parameters (e.g. Douyin location, privacy, XHS topics)",
    )
    status: Optional[str] = Field(None, description="Initial status (e.g. draft, queued)")


class PublishJobUpdateRequest(BaseModel):
    """Request payload for updating a publish job"""
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    cover: Optional[str] = None
    scheduled_at: Optional[str] = None
    status: Optional[str] = None
    platform_custom_params: Optional[Dict[str, Any]] = None


class PublishJobResponse(BaseModel):
    """Full response model for a publish job"""
    job_id: str
    task_id: Optional[str] = None
    video_id: Optional[str] = None
    video_path: Optional[str] = None
    account_id: str
    platform: str
    title: str
    description: Optional[str] = ""
    tags: List[str] = Field(default_factory=list)
    cover: Optional[str] = None
    scheduled_at: Optional[str] = None
    status: str
    attempt_count: int = 0
    max_attempts: int = 3
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    next_retry_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    platform_post_id: Optional[str] = None
    platform_custom_params: Dict[str, Any] = Field(default_factory=dict)
    published_at: Optional[str] = None
    created_at: str
    updated_at: str


class PublishExecuteResponse(BaseModel):
    """Response of executing a publish job"""
    job_id: str
    success: bool
    status: str
    platform_post_id: Optional[str] = None
    post_url: Optional[str] = None
    error_message: Optional[str] = None


class PublishQueueStatsResponse(BaseModel):
    """Aggregate queue statistics response"""
    total_accounts: int
    active_accounts: int
    expired_accounts: int
    total_jobs: int
    queued_jobs: int
    scheduled_jobs: int
    publishing_jobs: int
    published_jobs: int
    failed_jobs: int
    cancelled_jobs: int


class PublishTemplateCreateRequest(BaseModel):
    """Request model for creating/updating a publishing template"""
    template_name: str = Field(description="Name of the template")
    description: Optional[str] = Field(default="", description="Template description")
    platform_configs: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Dictionary of platform_name -> config",
    )


class PublishTemplateResponse(BaseModel):
    """Response model for a publishing template"""
    template_id: str
    template_name: str
    description: Optional[str] = ""
    platform_configs: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class BulkMatrixPublishRequest(BaseModel):
    """Request model for bulk matrix video publishing"""
    video_items: List[Dict[str, Any]] = Field(description="List of video objects with task_id/video_path/title/tags")
    account_ids: List[str] = Field(description="List of target account IDs")
    template_id: Optional[str] = Field(default=None, description="Optional template ID to apply")
    base_title: Optional[str] = Field(default=None, description="Fallback base title")
    base_description: Optional[str] = Field(default=None, description="Fallback base description")
    base_tags: Optional[List[str]] = Field(default=None, description="Fallback base tags")
    start_scheduled_at: Optional[str] = Field(default=None, description="Start scheduled timestamp in ISO format")
    interval_minutes: int = Field(default=0, description="Staggered interval in minutes between successive videos")
    account_overrides: Optional[Dict[str, Any]] = Field(default=None, description="Per-account overrides")


class PublishingAnalyticsSummaryResponse(BaseModel):
    """Response model for analytics overview"""
    total_published_jobs: int
    total_failed_jobs: int
    platform_distribution: Dict[str, Dict[str, int]]
    account_leaderboard: List[Dict[str, Any]]


# ============================================================================
# Interactive QR & Auth Schemas
# ============================================================================

class QRStartRequest(BaseModel):
    """Request to initiate an interactive QR code login session"""
    platform: str = Field(..., description="Target platform (douyin, mock)")
    headless: bool = Field(True, description="Run browser in headless mode")


class QRStartResponse(BaseModel):
    """Initial response of started QR login session"""
    session_id: str
    platform: str
    status: str
    qrcode_data_url: Optional[str] = None


class QRStatusResponse(BaseModel):
    """Real-time status of QR code scanning and login progress"""
    session_id: str
    platform: str
    status: str
    qrcode_data_url: Optional[str] = None
    is_logged_in: bool = False
    error_message: Optional[str] = None


class QRCompleteRequest(BaseModel):
    """Request to finalize account creation from a successful QR session"""
    session_id: str = Field(..., description="QR session ID that achieved 'success' status")
    account_name: str = Field(..., description="User-assigned alias for the new account")
    username: Optional[str] = Field(None, description="Optional override username")
    display_name: Optional[str] = Field(None, description="Optional override display name")


class ManualCookieImportRequest(BaseModel):
    """Request to import cookies directly for an account"""
    platform: str = Field(..., description="Target platform (douyin, mock)")
    account_name: str = Field(..., description="Account alias")
    cookie_string: str = Field(..., description="Raw cookie header string or storage_state JSON")
    username: Optional[str] = Field("", description="Optional platform username")
    display_name: Optional[str] = Field("", description="Optional display nickname")


# ============================================================================
# Interactive Verification Schemas (SMS / 2FA / Captcha)
# ============================================================================

class VerificationRequestResponse(BaseModel):
    """Model representing an active verification code request"""
    request_id: str
    job_id: str
    account_id: str
    account_name: Optional[str] = ""
    title: Optional[str] = ""
    platform: str
    prompt: str
    status: str
    remaining_seconds: int
    timeout_seconds: float
    created_at: float
    error_message: Optional[str] = None


class VerificationSubmitRequest(BaseModel):
    """Payload for submitting an interactive verification code"""
    request_id: str = Field(..., description="Active verification request ID")
    code: str = Field(..., min_length=1, description="Verification code (e.g. 6-digit SMS code)")


class VerificationCancelRequest(BaseModel):
    """Payload for cancelling a pending verification request"""
    request_id: str = Field(..., description="Active verification request ID to cancel")


# ============================================================================
# Platform Metadata & Auto-Publishing Workflow Schemas
# ============================================================================

class PublishingConfigRequest(BaseModel):
    """Publishing configuration for automated generation -> publishing pipeline"""
    mode: str = Field("none", description="Publish mode: 'none', 'immediate', 'scheduled'")
    platform: str = Field("douyin", description="Target platform (e.g. douyin)")
    account_ids: List[str] = Field(default_factory=list, description="Target SocialAccount IDs")
    scheduled_at: Optional[str] = Field(None, description="ISO timestamp if scheduled")
    metadata_override: Optional[Dict[str, Any]] = Field(None, description="Optional manual metadata override")


class MetadataGenerateRequest(BaseModel):
    """Request payload for generating platform metadata from text/script"""
    platform: str = Field("douyin", description="Target platform (e.g. douyin)")
    script: str = Field(..., description="Video script or narrations")
    title: Optional[str] = Field(None, description="Video title")
    custom_instructions: Optional[str] = Field("", description="Custom generation instructions")
    cover: Optional[str] = Field(None, description="Cover image path or URL")


class MetadataGenerateResponse(BaseModel):
    """Response containing generated platform metadata"""
    platform: str
    title: str
    description: str
    tags: List[str] = Field(default_factory=list)
    cover: Optional[str] = None
    platform_custom_params: Dict[str, Any] = Field(default_factory=dict)


class TaskMetadataUpdateRequest(BaseModel):
    """Request payload to update stored platform metadata for a task"""
    platform: str = Field("douyin", description="Platform identifier (e.g. douyin)")
    title: Optional[str] = Field(None, description="Video title")
    description: Optional[str] = Field(None, description="Video description")
    tags: Optional[List[str]] = Field(None, description="Tags list")
    cover: Optional[str] = Field(None, description="Cover image")
    platform_custom_params: Optional[Dict[str, Any]] = Field(None, description="Custom platform parameters")


class TaskPublishRequest(BaseModel):
    """Request to create and trigger publish jobs for an existing completed task"""
    account_ids: List[str] = Field(..., description="Target SocialAccount IDs")
    platform: Optional[str] = Field("douyin", description="Target platform")
    scheduled_at: Optional[str] = Field(None, description="Scheduled ISO timestamp (None for immediate)")
    metadata_override: Optional[Dict[str, Any]] = Field(None, description="Optional metadata override")

