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
Publishing & Social Account Management API Endpoints
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from api.dependencies import TrendlumeDep
from api.schemas.base import BaseResponse
from api.schemas.publishing import (
    AccountCheckResponse,
    BulkMatrixPublishRequest,
    CredentialSetRequest,
    ManualCookieImportRequest,
    MetadataGenerateRequest,
    MetadataGenerateResponse,
    PlatformCapabilityResponse,
    PublishExecuteResponse,
    PublishingAnalyticsSummaryResponse,
    PublishJobCreateRequest,
    PublishJobResponse,
    PublishJobUpdateRequest,
    PublishQueueStatsResponse,
    PublishTemplateCreateRequest,
    PublishTemplateResponse,
    QRCompleteRequest,
    QRStartRequest,
    QRStartResponse,
    QRStatusResponse,
    SocialAccountCreateRequest,
    SocialAccountResponse,
    SocialAccountUpdateRequest,
    TaskMetadataUpdateRequest,
    TaskPublishRequest,
    VerificationCancelRequest,
    VerificationRequestResponse,
    VerificationSubmitRequest,
)
from trendlume.models.publishing import CredentialSummary, CredentialType
from trendlume.publishing.cookie_helper import normalize_storage_state

router = APIRouter(prefix="/publishing", tags=["Publishing"])


# ============================================================================
# Helper Functions
# ============================================================================

async def _build_account_response(trendlume, account) -> SocialAccountResponse:
    """Helper to convert SocialAccount model to safe SocialAccountResponse"""
    cred_summary: Optional[CredentialSummary] = None
    if account.credential_id:
        cred_summary = await trendlume.publishing.get_credential_summary(account.credential_id)

    return SocialAccountResponse(
        account_id=account.account_id,
        platform=account.platform,
        account_name=account.account_name,
        username=account.username,
        display_name=account.display_name,
        avatar=account.avatar,
        status=account.status,
        has_credential=bool(account.credential_id),
        credential_summary=cred_summary,
        settings=account.settings,
        last_checked_at=account.last_checked_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


# ============================================================================
# Platform Info Endpoints
# ============================================================================

@router.get("/platforms", response_model=List[PlatformCapabilityResponse])
async def list_platforms(trendlume: TrendlumeDep):
    """
    List all supported social platforms and their capabilities.
    """
    try:
        platforms_meta = trendlume.publishing.registry.list_supported_platforms()
        return [PlatformCapabilityResponse(**p) for p in platforms_meta]
    except Exception as e:
        logger.error(f"Error listing platforms: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Social Account Endpoints
# ============================================================================

@router.get("/accounts", response_model=List[SocialAccountResponse])
async def list_accounts(
    trendlume: TrendlumeDep,
    platform: Optional[str] = Query(None, description="Filter by platform"),
    status: Optional[str] = Query(None, description="Filter by status (active/disabled/error)"),
):
    """
    List connected social accounts with credential summary.
    """
    try:
        accounts = await trendlume.publishing.list_accounts(platform=platform, status=status)
        responses = []
        for acc in accounts:
            responses.append(await _build_account_response(trendlume, acc))
        return responses
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts", response_model=SocialAccountResponse)
async def create_account(
    request: SocialAccountCreateRequest,
    trendlume: TrendlumeDep,
):
    """
    Create a new social account, optionally providing initial credentials.
    """
    try:
        account = await trendlume.publishing.create_account(
            platform=request.platform,
            account_name=request.account_name,
            username=request.username,
            display_name=request.display_name,
            avatar=request.avatar,
            settings=request.settings,
            credential_type=request.credential_type,
            credential_data=request.credential_data,
        )
        return await _build_account_response(trendlume, account)
    except Exception as e:
        logger.error(f"Error creating account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}", response_model=SocialAccountResponse)
async def get_account(
    account_id: str,
    trendlume: TrendlumeDep,
):
    """
    Get detailed information about a specific social account.
    """
    account = await trendlume.publishing.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
    return await _build_account_response(trendlume, account)


@router.put("/accounts/{account_id}", response_model=SocialAccountResponse)
async def update_account(
    account_id: str,
    request: SocialAccountUpdateRequest,
    trendlume: TrendlumeDep,
):
    """
    Update an existing social account's metadata.
    """
    account = await trendlume.publishing.update_account(
        account_id=account_id,
        account_name=request.account_name,
        username=request.username,
        display_name=request.display_name,
        avatar=request.avatar,
        status=request.status,
        settings=request.settings,
    )
    if not account:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
    return await _build_account_response(trendlume, account)


@router.delete("/accounts/{account_id}", response_model=BaseResponse)
async def delete_account(
    account_id: str,
    trendlume: TrendlumeDep,
):
    """
    Delete a social account and its decoupled credentials.
    """
    success = await trendlume.publishing.delete_account(account_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
    return BaseResponse(success=True, message=f"Account {account_id} deleted successfully")


@router.post("/accounts/{account_id}/check", response_model=AccountCheckResponse)
async def check_account_status(
    account_id: str,
    trendlume: TrendlumeDep,
):
    """
    Trigger a health/login validity check for the given account.
    """
    account = await trendlume.publishing.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    result = await trendlume.publishing.check_account_status(account_id)
    return AccountCheckResponse(
        account_id=account_id,
        is_valid=result.is_valid,
        username=result.username,
        display_name=result.display_name,
        avatar=result.avatar,
        error_message=result.error_message,
        checked_at=datetime.now().isoformat(),
    )


@router.post("/accounts/{account_id}/credentials", response_model=CredentialSummary)
async def set_account_credential(
    account_id: str,
    request: CredentialSetRequest,
    trendlume: TrendlumeDep,
):
    """
    Set or update authentication credentials (cookie, token, etc.) for an account.
    """
    try:
        summary = await trendlume.publishing.set_credential(
            account_id=account_id,
            credential_type=request.credential_type,
            data=request.data,
            expires_at=request.expires_at,
        )
        return summary
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error setting credential: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Publish Job Endpoints
# ============================================================================

@router.get("/jobs", response_model=List[PublishJobResponse])
async def list_jobs(
    trendlume: TrendlumeDep,
    platform: Optional[str] = Query(None, description="Filter by platform"),
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    status: Optional[str] = Query(None, description="Filter by job status"),
    task_id: Optional[str] = Query(None, description="Filter by associated Task ID"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    List publish jobs with filtering and pagination.
    """
    try:
        jobs = await trendlume.publishing.list_jobs(
            platform=platform,
            account_id=account_id,
            status=status,
            task_id=task_id,
            limit=limit,
            offset=offset,
        )
        return [PublishJobResponse(**j.model_dump()) for j in jobs]
    except Exception as e:
        logger.error(f"Error listing publish jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs", response_model=PublishJobResponse)
async def create_job(
    request: PublishJobCreateRequest,
    trendlume: TrendlumeDep,
):
    """
    Create a new publish job.
    """
    try:
        job = await trendlume.publishing.create_job(
            account_id=request.account_id,
            title=request.title,
            description=request.description,
            tags=request.tags,
            cover=request.cover,
            task_id=request.task_id,
            video_id=request.video_id,
            video_path=request.video_path,
            scheduled_at=request.scheduled_at,
            platform_custom_params=request.platform_custom_params,
            status=request.status,
        )
        return PublishJobResponse(**job.model_dump())
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error creating publish job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=PublishJobResponse)
async def get_job(
    job_id: str,
    trendlume: TrendlumeDep,
):
    """
    Get detailed information about a specific publish job.
    """
    job = await trendlume.publishing.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return PublishJobResponse(**job.model_dump())


@router.put("/jobs/{job_id}", response_model=PublishJobResponse)
async def update_job(
    job_id: str,
    request: PublishJobUpdateRequest,
    trendlume: TrendlumeDep,
):
    """
    Update publish job parameters.
    """
    job = await trendlume.publishing.update_job(
        job_id=job_id,
        title=request.title,
        description=request.description,
        tags=request.tags,
        cover=request.cover,
        scheduled_at=request.scheduled_at,
        status=request.status,
        platform_custom_params=request.platform_custom_params,
    )
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return PublishJobResponse(**job.model_dump())


@router.delete("/jobs/{job_id}", response_model=BaseResponse)
async def delete_job(
    job_id: str,
    trendlume: TrendlumeDep,
):
    """
    Delete a publish job.
    """
    success = await trendlume.publishing.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return BaseResponse(success=True, message=f"Job {job_id} deleted successfully")


@router.get("/queue/stats", response_model=PublishQueueStatsResponse)
async def get_queue_stats(
    trendlume: TrendlumeDep,
):
    """
    Get real-time aggregate statistics for publishing queue and accounts.
    """
    stats = await trendlume.publishing.get_queue_stats()
    return PublishQueueStatsResponse(**stats)


@router.post("/jobs/{job_id}/publish", response_model=PublishExecuteResponse)
async def execute_job(
    job_id: str,
    trendlume: TrendlumeDep,
    background: bool = False,
):
    """
    Trigger execution of a publish job (enqueue to background worker by default).
    """
    job = await trendlume.publishing.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if background:
        job = await trendlume.publishing.retry_job(job_id)
        return PublishExecuteResponse(
            job_id=job_id,
            success=True,
            status=job.status,
            platform_post_id=job.platform_post_id,
            post_url=None,
            error_message=None,
        )
    else:
        result = await trendlume.publishing.execute_job(job_id)
        refreshed_job = await trendlume.publishing.get_job(job_id)
        return PublishExecuteResponse(
            job_id=job_id,
            success=result.success,
            status=refreshed_job.status if refreshed_job else "unknown",
            platform_post_id=result.platform_post_id,
            post_url=result.post_url,
            error_message=result.error_message,
        )


@router.post("/jobs/{job_id}/cancel", response_model=BaseResponse)
async def cancel_job(
    job_id: str,
    trendlume: TrendlumeDep,
):
    """
    Cancel a queued or scheduled publish job.
    """
    success = await trendlume.publishing.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Cannot cancel job {job_id}")
    return BaseResponse(success=True, message=f"Job {job_id} cancelled")


@router.post("/jobs/{job_id}/retry", response_model=PublishJobResponse)
async def retry_job(
    job_id: str,
    trendlume: TrendlumeDep,
    force: bool = False,
):
    """
    Reset a failed publish job back to queued for re-execution.
    """
    try:
        job = await trendlume.publishing.retry_job(job_id, force=force)
        return PublishJobResponse(**job.model_dump())
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error retrying job: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================================
# Interactive Authentication Endpoints
# ============================================================================

@router.post("/auth/qr/start", response_model=QRStartResponse)
async def start_qr_auth(
    request: QRStartRequest,
    trendlume: TrendlumeDep,
):
    """
    Start an interactive QR code login session for a platform (douyin, mock).
    """
    try:
        session = trendlume.publishing.auth.start_qr_session(
            platform=request.platform,
            headless=request.headless,
        )
        return QRStartResponse(
            session_id=session.session_id,
            platform=session.platform,
            status=session.status,
            qrcode_data_url=session.qrcode_data_url,
        )
    except Exception as e:
        logger.error(f"Error starting QR auth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/qr/status/{session_id}", response_model=QRStatusResponse)
async def get_qr_auth_status(
    session_id: str,
    trendlume: TrendlumeDep,
):
    """
    Get live scanning status of a QR login session.
    """
    session = trendlume.publishing.auth.get_qr_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"QR session {session_id} not found")

    return QRStatusResponse(
        session_id=session.session_id,
        platform=session.platform,
        status=session.status,
        qrcode_data_url=session.qrcode_data_url,
        is_logged_in=(session.status == "success"),
        error_message=session.error_message,
    )


@router.post("/auth/qr/complete", response_model=SocialAccountResponse)
async def complete_qr_auth(
    request: QRCompleteRequest,
    trendlume: TrendlumeDep,
):
    """
    Finalize QR login by saving the captured session as a Credential and creating a SocialAccount.
    """
    session = trendlume.publishing.auth.get_qr_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"QR session {request.session_id} not found")

    if session.status != "success" or not session.storage_state:
        raise HTTPException(
            status_code=400,
            detail=f"QR session is not in 'success' state (current: {session.status})",
        )

    user_info = session.user_info or {}
    username = request.username or user_info.get("username", "")
    display_name = request.display_name or user_info.get("display_name", username)

    account = await trendlume.publishing.create_account(
        platform=session.platform,
        account_name=request.account_name,
        username=username,
        display_name=display_name,
        credential_type=CredentialType.STORAGE_STATE,
        credential_data=session.storage_state,
    )

    return await _build_account_response(trendlume, account)


@router.post("/auth/cookie/import", response_model=SocialAccountResponse)
async def import_manual_cookie(
    request: ManualCookieImportRequest,
    trendlume: TrendlumeDep,
):
    """
    Import raw cookie string or storage_state JSON, normalize it, and create/update SocialAccount.
    """
    try:
        normalized = normalize_storage_state(request.cookie_string, platform=request.platform)
        if not normalized or not normalized.get("cookies"):
            raise HTTPException(status_code=400, detail="Invalid cookie string or empty cookies parsed")

        account = await trendlume.publishing.create_account(
            platform=request.platform,
            account_name=request.account_name,
            username=request.username or "",
            display_name=request.display_name or request.account_name,
            credential_type=CredentialType.COOKIE,
            credential_data=normalized,
        )

        return await _build_account_response(trendlume, account)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing manual cookie: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ========================================================================
# Publishing Templates Endpoints
# ========================================================================

@router.get("/templates", response_model=List[PublishTemplateResponse])
async def list_publish_templates(
    trendlume: TrendlumeDep,
):
    """List all publishing preset templates"""
    templates = await trendlume.publishing.list_templates()
    return [
        PublishTemplateResponse(
            template_id=t.template_id,
            template_name=t.template_name,
            description=t.description,
            platform_configs={k: v.model_dump() for k, v in t.platform_configs.items()},
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in templates
    ]


@router.post("/templates", response_model=PublishTemplateResponse)
async def create_publish_template(
    request: PublishTemplateCreateRequest,
    trendlume: TrendlumeDep,
):
    """Create a new publishing preset template"""
    try:
        tpl = await trendlume.publishing.create_template(
            template_name=request.template_name,
            description=request.description,
            platform_configs=request.platform_configs,
        )
        return PublishTemplateResponse(
            template_id=tpl.template_id,
            template_name=tpl.template_name,
            description=tpl.description,
            platform_configs={k: v.model_dump() for k, v in tpl.platform_configs.items()},
            created_at=tpl.created_at,
            updated_at=tpl.updated_at,
        )
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/templates/{template_id}", response_model=PublishTemplateResponse)
async def get_publish_template(
    template_id: str,
    trendlume: TrendlumeDep,
):
    """Get a publishing template by ID"""
    tpl = await trendlume.publishing.get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
    return PublishTemplateResponse(
        template_id=tpl.template_id,
        template_name=tpl.template_name,
        description=tpl.description,
        platform_configs={k: v.model_dump() for k, v in tpl.platform_configs.items()},
        created_at=tpl.created_at,
        updated_at=tpl.updated_at,
    )


@router.delete("/templates/{template_id}", response_model=BaseResponse)
async def delete_publish_template(
    template_id: str,
    trendlume: TrendlumeDep,
):
    """Delete a publishing template"""
    deleted = await trendlume.publishing.delete_template(template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
    return BaseResponse(message=f"Template {template_id} deleted successfully")


# ========================================================================
# Bulk Matrix Video Publishing
# ========================================================================

@router.post("/jobs/bulk-matrix", response_model=List[PublishJobResponse])
async def create_bulk_matrix_jobs(
    request: BulkMatrixPublishRequest,
    trendlume: TrendlumeDep,
):
    """
    Create a bulk N (videos) x M (accounts) matrix of independent publish jobs.
    """
    try:
        created_jobs = await trendlume.publishing.create_bulk_matrix_jobs(
            video_items=request.video_items,
            account_ids=request.account_ids,
            template_id=request.template_id,
            base_title=request.base_title,
            base_description=request.base_description,
            base_tags=request.base_tags,
            start_scheduled_at=request.start_scheduled_at,
            interval_minutes=request.interval_minutes,
            account_overrides=request.account_overrides,
        )
        return [PublishJobResponse(**j.model_dump()) for j in created_jobs]
    except Exception as e:
        logger.error(f"Error creating bulk matrix jobs: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ========================================================================
# Analytics Overview
# ========================================================================

@router.get("/analytics/summary", response_model=PublishingAnalyticsSummaryResponse)
async def get_publishing_analytics_summary(
    trendlume: TrendlumeDep,
):
    """Get baseline publishing analytics and account performance summary"""
    stats = await trendlume.publishing.get_analytics_summary()
    return PublishingAnalyticsSummaryResponse(**stats)


# ========================================================================
# Interactive Verification Endpoints (SMS / 2FA / Captcha)
# ========================================================================

@router.get("/verification/pending", response_model=List[VerificationRequestResponse])
async def list_pending_verifications(
    trendlume: TrendlumeDep,
):
    """
    List all currently pending interactive verification requests awaiting user code.
    """
    pending = trendlume.publishing.list_pending_verifications()
    return [
        VerificationRequestResponse(
            request_id=req.request_id,
            job_id=req.job_id,
            account_id=req.account_id,
            account_name=req.account_name,
            title=req.title,
            platform=req.platform,
            prompt=req.prompt,
            status=req.status,
            remaining_seconds=req.remaining_seconds,
            timeout_seconds=req.timeout_seconds,
            created_at=req.created_at,
            error_message=req.error_message,
        )
        for req in pending
    ]


@router.post("/verification/submit", response_model=BaseResponse)
async def submit_verification_code(
    request: VerificationSubmitRequest,
    trendlume: TrendlumeDep,
):
    """
    Submit a verification code (e.g. SMS code) entered by user for an active job.
    """
    success = trendlume.publishing.submit_verification_code(
        request_id=request.request_id,
        code=request.code,
    )
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Verification request {request.request_id} not found, already expired, or not in pending state",
        )
    return BaseResponse(success=True, message=f"Verification code submitted for {request.request_id}")


@router.post("/verification/cancel", response_model=BaseResponse)
async def cancel_verification(
    request: VerificationCancelRequest,
    trendlume: TrendlumeDep,
):
    """
    Cancel an active verification request.
    """
    success = trendlume.publishing.cancel_verification(request.request_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Verification request {request.request_id} not found",
        )
    return BaseResponse(success=True, message=f"Verification {request.request_id} cancelled")


# ============================================================================
# Platform Metadata & Task Publishing Endpoints
# ============================================================================

@router.post("/metadata/generate", response_model=MetadataGenerateResponse)
async def generate_metadata(
    request: MetadataGenerateRequest,
    trendlume: TrendlumeDep,
):
    """
    Generate platform-optimized metadata from text or script using structured LLM.
    """
    try:
        meta = await trendlume.publishing.generate_platform_metadata(
            platform=request.platform,
            script=request.script,
            title=request.title,
            custom_instructions=request.custom_instructions,
            cover=request.cover,
        )
        return MetadataGenerateResponse(
            platform=request.platform,
            title=meta.title,
            description=meta.description,
            tags=meta.tags,
            cover=meta.cover,
            platform_custom_params=meta.platform_custom_params,
        )
    except Exception as e:
        logger.error(f"Error generating platform metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/metadata/regenerate", response_model=MetadataGenerateResponse)
async def regenerate_task_metadata(
    task_id: str,
    trendlume: TrendlumeDep,
    platform: str = Query("douyin", description="Platform identifier"),
    custom_instructions: Optional[str] = Query("", description="Custom prompt instructions"),
):
    """
    Regenerate platform metadata for an existing task from its script without re-rendering video.
    """
    try:
        meta = await trendlume.publishing.regenerate_task_metadata(
            task_id=task_id,
            platform=platform,
            custom_instructions=custom_instructions,
        )
        if not meta:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        return MetadataGenerateResponse(
            platform=platform,
            title=meta.title,
            description=meta.description,
            tags=meta.tags,
            cover=meta.cover,
            platform_custom_params=meta.platform_custom_params,
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error regenerating task metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/tasks/{task_id}/metadata", response_model=MetadataGenerateResponse)
async def update_task_metadata(
    task_id: str,
    request: TaskMetadataUpdateRequest,
    trendlume: TrendlumeDep,
):
    """
    Update stored platform metadata for a task with manual edits.
    """
    try:
        updated = await trendlume.publishing.update_task_metadata(
            task_id=task_id,
            platform=request.platform,
            metadata_dict=request.model_dump(exclude_unset=True),
        )
        return MetadataGenerateResponse(
            platform=request.platform,
            title=updated.get("title", ""),
            description=updated.get("description", ""),
            tags=updated.get("tags", []),
            cover=updated.get("cover"),
            platform_custom_params=updated.get("platform_custom_params", {}),
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error updating task metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/publish", response_model=List[PublishJobResponse])
async def publish_task(
    task_id: str,
    request: TaskPublishRequest,
    trendlume: TrendlumeDep,
):
    """
    Create and dispatch PublishJobs for an existing task across target social accounts.
    """
    try:
        jobs = await trendlume.publishing.create_jobs_for_task(
            task_id=task_id,
            account_ids=request.account_ids,
            platform=request.platform,
            scheduled_at=request.scheduled_at,
            metadata_override=request.metadata_override,
        )
        return [PublishJobResponse(**j.model_dump()) for j in jobs]
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error publishing task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


