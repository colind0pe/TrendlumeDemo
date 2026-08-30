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
Publishing Service Layer

Coordinates Social Accounts, Decoupled Credentials, Publish Jobs, and Platform Publishers.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger

from trendlume.models.metadata import (
    BasePlatformMetadata,
)
from trendlume.models.publishing import (
    AccountStatus,
    Credential,
    CredentialSummary,
    CredentialType,
    PublishJob,
    PublishJobStatus,
    PublishTemplate,
    SocialAccount,
)
from trendlume.publishing.auth import PlatformAuthService, auth_service
from trendlume.publishing.base import AccountCheckResult, PublishResult
from trendlume.publishing.metadata import PlatformMetadataGenerator
from trendlume.publishing.registry import PublisherRegistry, publisher_registry
from trendlume.publishing.verification import (
    VerificationManager,
    VerificationRequest,
    verification_manager,
)
from trendlume.publishing.worker import PublishingWorker
from trendlume.services.persistence import PersistenceService
from trendlume.services.publishing_persistence import PublishingPersistenceService


class PublishingService:
    """
    Publishing Service

    Unified business logic layer for:
    - Social account lifecycle and verification
    - Safe credential management
    - Publish job management (creation, inspection, retry, cancel)
    - Background queue & concurrency worker execution
    - Interactive verification code coordination
    - Platform Metadata generation & Task auto-publishing orchestration
    """

    def __init__(
        self,
        persistence: Optional[PersistenceService] = None,
        store: Optional[PublishingPersistenceService] = None,
        registry: Optional[PublisherRegistry] = None,
        auth: Optional[PlatformAuthService] = None,
        verification: Optional[VerificationManager] = None,
        max_concurrent_browsers: int = 2,
        core: Optional[Any] = None,
        llm_service: Optional[Any] = None,
    ):
        self.core = core
        self.persistence = persistence or PersistenceService()
        if store:
            self.store = store
        elif persistence:
            self.store = PublishingPersistenceService(output_dir=str(persistence.output_dir))
        else:
            self.store = PublishingPersistenceService()

        self.registry = registry or publisher_registry
        self.auth = auth or auth_service
        self.verification = verification or verification_manager
        self.worker = PublishingWorker(
            store=self.store,
            registry=self.registry,
            max_concurrent_browsers=max_concurrent_browsers,
        )
        self._llm = llm_service
        self._metadata_generator: Optional[PlatformMetadataGenerator] = None

    @property
    def metadata_generator(self) -> PlatformMetadataGenerator:
        """Lazily initialize PlatformMetadataGenerator with current LLM service"""
        if self._metadata_generator is None:
            llm = self._llm
            if not llm and self.core and hasattr(self.core, "llm") and self.core.llm:
                llm = self.core.llm
            if not llm:
                from trendlume.config import config_manager
                from trendlume.services.llm_service import LLMService

                llm = LLMService(config_manager.config.to_dict())
            self._metadata_generator = PlatformMetadataGenerator(llm_service=llm)
        return self._metadata_generator

    def start_worker(self):
        """Start background publish queue worker"""
        self.worker.start()

    def stop_worker(self):
        """Stop background publish queue worker"""
        self.worker.stop()

    def wakeup_worker(self):
        """Wake up worker for immediate processing"""
        self.worker.wakeup()

    # ========================================================================
    # Interactive QR Auth Session Management (Delegated to AuthService)
    # ========================================================================

    def start_qr_session(self, platform: str, headless: bool = True):
        """Start an interactive QR code login session for a platform"""
        return self.auth.start_qr_session(platform=platform, headless=headless)

    def get_qr_session(self, session_id: str):
        """Get the state of an active or recent QR login session"""
        return self.auth.get_qr_session(session_id)

    def cancel_qr_session(self, session_id: str) -> bool:
        """Cancel an ongoing QR login session"""
        return self.auth.cancel_qr_session(session_id)

    # ========================================================================
    # Interactive Verification Management (SMS / Captcha / 2FA)
    # ========================================================================

    def list_pending_verifications(self) -> List[VerificationRequest]:
        """List all pending interactive verification requests awaiting user code"""
        return self.verification.list_pending_requests()

    def get_verification_request(self, request_id: str) -> Optional[VerificationRequest]:
        """Get state of a specific verification request"""
        return self.verification.get_request(request_id)

    def submit_verification_code(self, request_id: str, code: str) -> bool:
        """Submit verification code entered by user in UI or API"""
        return self.verification.submit_code(request_id, code)

    def cancel_verification(self, request_id: str) -> bool:
        """Cancel an active verification request"""
        return self.verification.cancel_request(request_id)

    # ========================================================================
    # Social Account Management
    # ========================================================================

    async def create_account(
        self,
        platform: str,
        account_name: str,
        username: Optional[str] = "",
        display_name: Optional[str] = "",
        avatar: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
        credential_type: Optional[str] = None,
        credential_data: Optional[Dict[str, Any]] = None,
        account_id: Optional[str] = None,
    ) -> SocialAccount:
        """
        Create a new SocialAccount, optionally creating an associated Credential.
        """
        platform_clean = platform.lower().strip()
        now = datetime.now().isoformat()

        if not account_id:
            account_id = f"acc_{platform_clean}_{uuid.uuid4().hex[:6]}"

        credential_id = None
        if credential_data:
            credential_id = f"cred_{account_id}_{uuid.uuid4().hex[:4]}"
            cred = Credential(
                credential_id=credential_id,
                platform=platform_clean,
                credential_type=credential_type or CredentialType.COOKIE,
                data=credential_data,
                created_at=now,
                updated_at=now,
                is_valid=True,
            )
            await self.store.save_credential(cred)

        account = SocialAccount(
            account_id=account_id,
            platform=platform_clean,
            account_name=account_name,
            username=username or "",
            display_name=display_name or account_name,
            avatar=avatar,
            status=AccountStatus.ACTIVE,
            credential_id=credential_id,
            settings=settings or {},
            created_at=now,
            updated_at=now,
        )

        await self.store.save_account(account)
        logger.info(f"Created social account: {account_id} ({platform_clean} - {account_name})")
        return account

    async def get_account(self, account_id: str) -> Optional[SocialAccount]:
        """Get social account by ID"""
        return await self.store.get_account(account_id)

    async def list_accounts(
        self,
        platform: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[SocialAccount]:
        """List social accounts with optional platform and status filter"""
        return await self.store.list_accounts(platform=platform, status=status)

    async def update_account(
        self,
        account_id: str,
        account_name: Optional[str] = None,
        username: Optional[str] = None,
        display_name: Optional[str] = None,
        avatar: Optional[str] = None,
        status: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Optional[SocialAccount]:
        """Update existing social account metadata"""
        account = await self.store.get_account(account_id)
        if not account:
            return None

        if account_name is not None:
            account.account_name = account_name
        if username is not None:
            account.username = username
        if display_name is not None:
            account.display_name = display_name
        if avatar is not None:
            account.avatar = avatar
        if status is not None:
            account.status = status
        if settings is not None:
            account.settings = settings

        account.updated_at = datetime.now().isoformat()
        await self.store.save_account(account)
        logger.info(f"Updated social account: {account_id}")
        return account

    async def delete_account(self, account_id: str) -> bool:
        """Delete social account and its decoupled credential"""
        return await self.store.delete_account(account_id)

    async def check_account_status(self, account_id: str) -> AccountCheckResult:
        """
        Check account login/credential validity via platform publisher adapter.
        Updates account's last_checked_at and status accordingly.
        """
        account = await self.store.get_account(account_id)
        if not account:
            return AccountCheckResult(is_valid=False, error_message=f"Account {account_id} not found")

        credential = None
        if account.credential_id:
            credential = await self.store.get_credential(account.credential_id)

        try:
            publisher = self.registry.get_publisher(account.platform)
            result = await publisher.check_account(account, credential)

            # Update account check metadata
            account.last_checked_at = datetime.now().isoformat()
            if result.is_valid:
                account.status = AccountStatus.ACTIVE
                if result.username and not account.username:
                    account.username = result.username
                if result.display_name and not account.display_name:
                    account.display_name = result.display_name
                if result.avatar and not account.avatar:
                    account.avatar = result.avatar
            else:
                account.status = AccountStatus.ERROR

            account.updated_at = datetime.now().isoformat()
            await self.store.save_account(account)
            return result

        except Exception as e:
            logger.error(f"Error checking account status {account_id}: {e}")
            account.last_checked_at = datetime.now().isoformat()
            account.status = AccountStatus.ERROR
            await self.store.save_account(account)
            return AccountCheckResult(is_valid=False, error_message=str(e))

    # ========================================================================
    # Credential Management
    # ========================================================================

    async def set_credential(
        self,
        account_id: str,
        credential_type: str,
        data: Dict[str, Any],
        expires_at: Optional[str] = None,
    ) -> CredentialSummary:
        """
        Set or update credential for an account. Decoupled and safely stored.
        """
        account = await self.store.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        now = datetime.now().isoformat()
        credential_id = account.credential_id or f"cred_{account_id}_{uuid.uuid4().hex[:4]}"

        cred = Credential(
            credential_id=credential_id,
            platform=account.platform,
            credential_type=credential_type,
            data=data,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            is_valid=True,
        )

        await self.store.save_credential(cred)

        if account.credential_id != credential_id:
            account.credential_id = credential_id
            account.updated_at = now
            await self.store.save_account(account)

        logger.info(f"Set credential for account {account_id}")
        return cred.to_summary()

    async def get_credential(self, credential_id: str) -> Optional[Credential]:
        """Get internal credential object (backend service only)"""
        return await self.store.get_credential(credential_id)

    async def get_credential_summary(self, credential_id: str) -> Optional[CredentialSummary]:
        """Get sanitized summary of credential for API/UI"""
        cred = await self.store.get_credential(credential_id)
        if not cred:
            return None
        return cred.to_summary()

    async def delete_credential(self, credential_id: str) -> bool:
        """Delete credential"""
        return await self.store.delete_credential(credential_id)

    # ========================================================================
    # Publish Job Management
    # ========================================================================

    async def create_job(
        self,
        account_id: str,
        title: str = "",
        description: Optional[str] = "",
        tags: Optional[List[str]] = None,
        cover: Optional[str] = None,
        task_id: Optional[str] = None,
        video_id: Optional[str] = None,
        video_path: Optional[str] = None,
        scheduled_at: Optional[str] = None,
        platform_custom_params: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> PublishJob:
        """
        Create a new publish job.
        """
        account = await self.store.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        platform = account.platform
        now = datetime.now().isoformat()

        if not job_id:
            job_id = f"pub_{platform}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"

        # Resolve task metadata if task_id provided
        resolved_title = title
        resolved_desc = description
        resolved_video_path = video_path

        if task_id:
            task_metadata = await self.persistence.load_task_metadata(task_id)
            if task_metadata:
                if not resolved_title:
                    resolved_title = task_metadata.get("title") or task_metadata.get("input", {}).get("title", "")
                    if not resolved_title:
                        storyboard = await self.persistence.load_storyboard(task_id)
                        if storyboard and storyboard.title:
                            resolved_title = storyboard.title
                
                if resolved_desc == "":
                    resolved_desc = task_metadata.get("input", {}).get("text", "")

            if not resolved_video_path:
                task_video = self.persistence.get_task_final_video_path(task_id)
                if task_video.exists():
                    resolved_video_path = str(task_video.resolve())

        if not resolved_title:
            resolved_title = f"Trendlume Video {task_id or job_id[:8]}"

        # Determine initial status
        initial_status = status or PublishJobStatus.DRAFT
        if scheduled_at and initial_status == PublishJobStatus.DRAFT:
            initial_status = PublishJobStatus.SCHEDULED

        job = PublishJob(
            job_id=job_id,
            task_id=task_id,
            video_id=video_id,
            video_path=resolved_video_path,
            account_id=account_id,
            platform=platform,
            title=resolved_title,
            description=resolved_desc or "",
            tags=tags or [],
            cover=cover,
            scheduled_at=scheduled_at,
            status=initial_status,
            attempt_count=0,
            max_attempts=3,
            platform_custom_params=platform_custom_params or {},
            created_at=now,
            updated_at=now,
        )

        await self.store.save_job(job)
        logger.info(f"Created publish job: {job_id} for account {account_id} ({platform})")
        return job

    async def get_job(self, job_id: str) -> Optional[PublishJob]:
        """Get publish job by ID"""
        return await self.store.get_job(job_id)

    async def list_jobs(
        self,
        platform: Optional[str] = None,
        account_id: Optional[str] = None,
        status: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PublishJob]:
        """List publish jobs with filtering and pagination"""
        return await self.store.list_jobs(
            platform=platform,
            account_id=account_id,
            status=status,
            task_id=task_id,
            limit=limit,
            offset=offset,
        )

    async def update_job(
        self,
        job_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        cover: Optional[str] = None,
        scheduled_at: Optional[str] = None,
        status: Optional[str] = None,
        platform_custom_params: Optional[Dict[str, Any]] = None,
    ) -> Optional[PublishJob]:
        """Update publish job parameters"""
        job = await self.store.get_job(job_id)
        if not job:
            return None

        if title is not None:
            job.title = title
        if description is not None:
            job.description = description
        if tags is not None:
            job.tags = tags
        if cover is not None:
            job.cover = cover
        if scheduled_at is not None:
            job.scheduled_at = scheduled_at
        if status is not None:
            job.status = status
        if platform_custom_params is not None:
            job.platform_custom_params = platform_custom_params

        job.updated_at = datetime.now().isoformat()
        await self.store.save_job(job)
        return job

    async def delete_job(self, job_id: str) -> bool:
        """Delete publish job"""
        return await self.store.delete_job(job_id)

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued or scheduled publish job"""
        job = await self.store.get_job(job_id)
        if not job:
            return False

        if job.status in [PublishJobStatus.PUBLISHED, PublishJobStatus.CANCELLED]:
            return False

        job.status = PublishJobStatus.CANCELLED
        job.updated_at = datetime.now().isoformat()
        await self.store.save_job(job)
        logger.info(f"Cancelled publish job {job_id}")
        return True

    async def retry_job(self, job_id: str, force: bool = False) -> PublishJob:
        """Reset a failed or draft job back to queued for execution"""
        job = await self.store.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = PublishJobStatus.QUEUED
        job.error_message = None
        job.error_code = None
        job.next_retry_at = None
        if force:
            job.attempt_count = 0
        job.updated_at = datetime.now().isoformat()
        await self.store.save_job(job)
        self.wakeup_worker()
        return job

    # ========================================================================
    # Publishing Execution Pipeline
    # ========================================================================

    async def execute_job(self, job_id: str) -> PublishResult:
        """
        Execute a publish job via the PublishingWorker (ensuring account locks, concurrency limits, and retry policy).
        """
        return await self.worker.process_job(job_id)

    # ========================================================================
    # Due Jobs / Scheduler & Stats
    # ========================================================================

    async def get_due_jobs(self, now: Optional[datetime] = None) -> List[PublishJob]:
        """
        Get all publish jobs ready for execution (delegated to worker).
        """
        return await self.worker.get_due_jobs(now)

    async def get_queue_stats(self) -> Dict[str, int]:
        """Get aggregate counts for queue, scheduled, active accounts, etc."""
        accounts = await self.store.list_accounts()
        jobs = await self.store.list_jobs(limit=5000)

        active_accounts = sum(1 for a in accounts if a.status == AccountStatus.ACTIVE)
        expired_accounts = sum(1 for a in accounts if a.status == AccountStatus.EXPIRED)

        queued_jobs = sum(1 for j in jobs if j.status == PublishJobStatus.QUEUED)
        scheduled_jobs = sum(1 for j in jobs if j.status == PublishJobStatus.SCHEDULED)
        publishing_jobs = sum(1 for j in jobs if j.status == PublishJobStatus.PUBLISHING)
        published_jobs = sum(1 for j in jobs if j.status == PublishJobStatus.PUBLISHED)
        failed_jobs = sum(1 for j in jobs if j.status == PublishJobStatus.FAILED)
        cancelled_jobs = sum(1 for j in jobs if j.status == PublishJobStatus.CANCELLED)

        return {
            "total_accounts": len(accounts),
            "active_accounts": active_accounts,
            "expired_accounts": expired_accounts,
            "total_jobs": len(jobs),
            "queued_jobs": queued_jobs,
            "scheduled_jobs": scheduled_jobs,
            "publishing_jobs": publishing_jobs,
            "published_jobs": published_jobs,
            "failed_jobs": failed_jobs,
            "cancelled_jobs": cancelled_jobs,
        }

    # ========================================================================
    # Template & Content Adaptation Operations
    # ========================================================================

    async def create_template(
        self,
        template_name: str,
        description: Optional[str] = "",
        platform_configs: Optional[Dict[str, Any]] = None,
        template_id: Optional[str] = None,
    ) -> PublishTemplate:
        """Create a new publishing preset template"""
        now = datetime.now().isoformat()
        t_id = template_id or f"tpl_{uuid.uuid4().hex[:8]}"

        template = PublishTemplate(
            template_id=t_id,
            template_name=template_name,
            description=description or "",
            platform_configs=platform_configs or {},
            created_at=now,
            updated_at=now,
        )

        return await self.store.save_template(template)

    async def get_template(self, template_id: str) -> Optional[PublishTemplate]:
        """Get template by ID"""
        return await self.store.get_template(template_id)

    async def list_templates(self) -> List[PublishTemplate]:
        """List all publishing templates"""
        return await self.store.list_templates()

    async def delete_template(self, template_id: str) -> bool:
        """Delete publishing template"""
        return await self.store.delete_template(template_id)

    async def apply_template_to_content(
        self,
        template_id: str,
        base_title: str,
        base_description: str,
        base_tags: List[str],
        platform: str,
    ) -> Dict[str, Any]:
        """
        Apply a template to base content for a specific target platform.
        """
        template = await self.get_template(template_id)
        if not template:
            return {
                "title": base_title,
                "description": base_description,
                "tags": base_tags,
                "platform_custom_params": {},
            }

        plat_clean = platform.lower().strip()
        cfg = template.platform_configs.get(plat_clean)
        if not cfg:
            return {
                "title": base_title,
                "description": base_description,
                "tags": base_tags,
                "platform_custom_params": {},
            }

        adapted_title = base_title
        if cfg.title_template:
            adapted_title = cfg.title_template.replace("{title}", base_title)

        adapted_desc = base_description
        if cfg.description_template:
            adapted_desc = cfg.description_template.replace("{description}", base_description)

        combined_tags = list(base_tags)
        for t in cfg.tags:
            if t not in combined_tags:
                combined_tags.append(t)

        return {
            "title": adapted_title,
            "description": adapted_desc,
            "tags": combined_tags,
            "platform_custom_params": cfg.custom_params or {},
        }

    # ========================================================================
    # Multi-Video x Multi-Account Bulk Matrix Dispatcher
    # ========================================================================

    async def create_batch_jobs(
        self,
        account_ids: List[str],
        base_title: str,
        base_description: Optional[str] = "",
        base_tags: Optional[List[str]] = None,
        task_id: Optional[str] = None,
        video_path: Optional[str] = None,
        scheduled_at: Optional[str] = None,
        account_overrides: Optional[Dict[str, Any]] = None,
    ) -> List[PublishJob]:
        """
        Create publish jobs across multiple social accounts for a single video item.
        """
        video_items = [{
            "task_id": task_id,
            "video_path": video_path,
            "title": base_title,
            "description": base_description or "",
            "tags": base_tags or [],
        }]
        return await self.create_bulk_matrix_jobs(
            video_items=video_items,
            account_ids=account_ids,
            start_scheduled_at=scheduled_at,
            account_overrides=account_overrides,
        )

    async def create_bulk_matrix_jobs(
        self,
        video_items: List[Dict[str, Any]],
        account_ids: List[str],
        template_id: Optional[str] = None,
        base_title: Optional[str] = None,
        base_description: Optional[str] = None,
        base_tags: Optional[List[str]] = None,
        start_scheduled_at: Optional[str] = None,
        interval_minutes: int = 0,
        account_overrides: Optional[Dict[str, Any]] = None,
    ) -> List[PublishJob]:
        """
        Create an N (videos) x M (accounts) matrix of independent PublishJobs.
        Supports staggered interval scheduling and capability-driven content adaptation.
        """
        if not video_items or not account_ids:
            return []

        all_created_jobs: List[PublishJob] = []
        base_start_dt = None
        if start_scheduled_at:
            try:
                base_start_dt = datetime.fromisoformat(start_scheduled_at)
            except Exception:
                base_start_dt = None

        account_overrides = account_overrides or {}

        # Iterate each video item
        for v_idx, v_item in enumerate(video_items):
            v_task_id = v_item.get("task_id")
            v_path = v_item.get("video_path")
            v_title = v_item.get("title") or base_title or "未命名视频"
            v_desc = v_item.get("description") or base_description or ""
            v_tags = v_item.get("tags") or base_tags or []

            # Compute staggered schedule timestamp if interval is set
            video_sched_iso = None
            if base_start_dt:
                offset_mins = v_idx * interval_minutes
                video_sched_iso = (base_start_dt + timedelta(minutes=offset_mins)).isoformat()

            # For each account, generate an adapted PublishJob
            for acc_id in account_ids:
                account = await self.store.get_account(acc_id)
                if not account:
                    continue

                pub = self.registry.get_publisher(account.platform)
                caps = pub.capabilities

                # 1. Content adaptation (Template -> Overrides -> Capability limits)
                title = v_title
                desc = v_desc
                tags = list(v_tags)
                custom_params = {}

                # Apply template if present
                if template_id:
                    adapted = await self.apply_template_to_content(
                        template_id=template_id,
                        base_title=title,
                        base_description=desc,
                        base_tags=tags,
                        platform=account.platform,
                    )
                    title = adapted["title"]
                    desc = adapted["description"]
                    tags = adapted["tags"]
                    custom_params.update(adapted["platform_custom_params"])

                # Apply per-account manual overrides if any
                if acc_id in account_overrides:
                    ov = account_overrides[acc_id]
                    if ov.get("title"):
                        title = ov["title"]
                    if ov.get("description") is not None:
                        desc = ov["description"]
                    if ov.get("tags"):
                        tags = ov["tags"]
                    if ov.get("platform_custom_params"):
                        custom_params.update(ov["platform_custom_params"])

                # Enforce capability bounds
                if len(title) > caps.max_title_length:
                    title = title[: caps.max_title_length]
                tags = tags[: caps.max_tags]

                job = await self.create_job(
                    account_id=acc_id,
                    title=title,
                    description=desc,
                    tags=tags,
                    task_id=v_task_id,
                    video_path=v_path,
                    scheduled_at=video_sched_iso,
                    platform_custom_params=custom_params,
                    status=PublishJobStatus.SCHEDULED if video_sched_iso else PublishJobStatus.QUEUED,
                )
                all_created_jobs.append(job)

        if all_created_jobs:
            self.wakeup_worker()

        logger.info(
            f"Created {len(all_created_jobs)} matrix publish jobs ({len(video_items)} videos x {len(account_ids)} accounts)"
        )
        return all_created_jobs

    # ========================================================================
    # Analytics Summary Operations
    # ========================================================================

    async def get_analytics_summary(self) -> Dict[str, Any]:
        """
        Aggregate baseline publishing analytics and account performance.
        """
        accounts = await self.store.list_accounts()
        jobs = await self.store.list_jobs(limit=5000)

        total_published = sum(1 for j in jobs if j.status == PublishJobStatus.PUBLISHED)
        total_failed = sum(1 for j in jobs if j.status == PublishJobStatus.FAILED)

        # Platform distribution of published jobs
        platform_stats: Dict[str, Dict[str, int]] = {}
        for j in jobs:
            plat = j.platform
            if plat not in platform_stats:
                platform_stats[plat] = {"total": 0, "published": 0, "failed": 0}
            platform_stats[plat]["total"] += 1
            if j.status == PublishJobStatus.PUBLISHED:
                platform_stats[plat]["published"] += 1
            elif j.status == PublishJobStatus.FAILED:
                platform_stats[plat]["failed"] += 1

        account_leaderboard = []
        for acc in accounts:
            account_leaderboard.append({
                "account_id": acc.account_id,
                "account_name": acc.account_name,
                "platform": acc.platform,
                "status": acc.status,
                "published_count": acc.published_count,
                "failed_count": acc.failed_count,
                "last_published_at": acc.last_published_at,
            })

        account_leaderboard.sort(key=lambda a: a["published_count"], reverse=True)

        return {
            "total_published_jobs": total_published,
            "total_failed_jobs": total_failed,
            "platform_distribution": platform_stats,
            "account_leaderboard": account_leaderboard,
        }

    # ========================================================================
    # Automated Platform Metadata & Task Publishing Orchestration
    # ========================================================================

    async def generate_platform_metadata(
        self,
        platform: str,
        script: Any,
        title: Optional[str] = None,
        custom_instructions: Optional[str] = "",
        cover: Optional[str] = None,
        **kwargs,
    ) -> BasePlatformMetadata:
        """
        Generate platform-specific metadata (title, description, tags, custom params)
        using structured LLM output with platform constraint validation.
        """
        return await self.metadata_generator.generate_metadata(
            platform=platform,
            script=script,
            title=title,
            custom_instructions=custom_instructions,
            cover=cover,
            **kwargs,
        )

    async def regenerate_task_metadata(
        self,
        task_id: str,
        platform: str = "douyin",
        custom_instructions: Optional[str] = "",
    ) -> Optional[BasePlatformMetadata]:
        """
        Regenerate platform metadata for an existing task from its script without re-rendering video.
        """
        task_meta = await self.persistence.load_task_metadata(task_id)
        if not task_meta:
            raise ValueError(f"Task {task_id} not found")

        # Resolve script
        script = ""
        storyboard = await self.persistence.load_storyboard(task_id)
        if storyboard and storyboard.frames:
            script = "\n".join(f.narration for f in storyboard.frames if f.narration)
        if not script:
            script = task_meta.get("input", {}).get("text") or task_meta.get("input", {}).get("prompt") or ""

        # Resolve title
        title = task_meta.get("title") or task_meta.get("input", {}).get("title") or ""
        if not title and storyboard and storyboard.title:
            title = storyboard.title

        # Resolve cover
        cover = task_meta.get("metadata", {}).get("cover")

        meta = await self.generate_platform_metadata(
            platform=platform,
            script=script,
            title=title,
            custom_instructions=custom_instructions,
            cover=cover,
        )

        task_meta.setdefault("metadata", {}).setdefault("platform_metadata", {})[platform] = meta.model_dump()
        await self.persistence.save_task_metadata(task_id, task_meta)
        logger.info(f"Regenerated '{platform}' metadata for task {task_id}: {meta.title}")
        return meta

    async def update_task_metadata(
        self,
        task_id: str,
        platform: str,
        metadata_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update platform metadata for a task with manual edits.
        """
        task_meta = await self.persistence.load_task_metadata(task_id)
        if not task_meta:
            raise ValueError(f"Task {task_id} not found")

        plat_key = platform.lower().strip()
        schema_cls = self.metadata_generator.get_schema(plat_key)
        validated = schema_cls.model_validate(metadata_dict)

        task_meta.setdefault("metadata", {}).setdefault("platform_metadata", {})[plat_key] = validated.model_dump()
        await self.persistence.save_task_metadata(task_id, task_meta)
        logger.info(f"Updated '{plat_key}' metadata for task {task_id}")
        return validated.model_dump()

    async def create_jobs_for_task(
        self,
        task_id: str,
        account_ids: List[str],
        platform: Optional[str] = None,
        scheduled_at: Optional[str] = None,
        metadata_override: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
    ) -> List[PublishJob]:
        """
        Idempotently create PublishJobs for a task across target social accounts
        using the platform metadata snapshot.
        """
        if not account_ids:
            return []

        task_meta = await self.persistence.load_task_metadata(task_id)
        if not task_meta:
            raise ValueError(f"Task {task_id} not found")

        # Resolve video path
        res = task_meta.get("result") or {}
        video_path = res.get("video_path")
        if not video_path:
            vfile = self.persistence.get_task_final_video_path(task_id)
            if vfile.exists():
                video_path = str(vfile.resolve())

        existing_jobs = await self.store.list_jobs(task_id=task_id, limit=100)
        existing_by_account = {
            j.account_id: j
            for j in existing_jobs
            if j.status in [
                PublishJobStatus.QUEUED,
                PublishJobStatus.PUBLISHING,
                PublishJobStatus.PUBLISHED,
                PublishJobStatus.SCHEDULED,
            ]
        }

        created_jobs: List[PublishJob] = []

        for acc_id in account_ids:
            account = await self.store.get_account(acc_id)
            if not account:
                logger.warning(f"Account {acc_id} not found, skipping job creation for task {task_id}")
                continue

            acc_platform = account.platform
            if platform and acc_platform != platform:
                continue

            # Idempotency check: if active job exists for account, reuse
            if acc_id in existing_by_account:
                logger.info(
                    f"Task {task_id} already has active PublishJob ({existing_by_account[acc_id].job_id}) for account {acc_id}"
                )
                created_jobs.append(existing_by_account[acc_id])
                continue

            # Resolve metadata snapshot
            # 1. Check override
            meta_dict = metadata_override or {}
            # 2. Check stored platform metadata
            if not meta_dict:
                plat_meta_map = task_meta.get("metadata", {}).get("platform_metadata", {})
                meta_dict = plat_meta_map.get(acc_platform) or {}

            # 3. Fallback to task title/description
            job_title = (
                meta_dict.get("title")
                or task_meta.get("title")
                or task_meta.get("input", {}).get("title")
                or f"Trendlume Video {task_id[:8]}"
            )
            job_desc = meta_dict.get("description") or task_meta.get("input", {}).get("text") or ""
            job_tags = meta_dict.get("tags") or []
            job_cover = meta_dict.get("cover")
            custom_params = dict(meta_dict.get("platform_custom_params") or {})

            # Enforce publisher capabilities limit on snapshot
            pub = self.registry.get_publisher(acc_platform)
            caps = pub.capabilities
            if len(job_title) > caps.max_title_length:
                job_title = job_title[: caps.max_title_length]
            job_tags = job_tags[: caps.max_tags]

            initial_status = status or (
                PublishJobStatus.SCHEDULED if scheduled_at else PublishJobStatus.QUEUED
            )

            job = await self.create_job(
                account_id=acc_id,
                title=job_title,
                description=job_desc,
                tags=job_tags,
                cover=job_cover,
                task_id=task_id,
                video_path=video_path,
                scheduled_at=scheduled_at,
                platform_custom_params=custom_params,
                status=initial_status,
            )
            created_jobs.append(job)

        # Update task metadata with job IDs and publishing status
        all_task_job_ids = list(
            set(
                task_meta.get("metadata", {}).get("publish_job_ids", [])
                + [j.job_id for j in created_jobs]
            )
        )
        task_meta.setdefault("metadata", {})["publish_job_ids"] = all_task_job_ids
        if any(j.status == PublishJobStatus.QUEUED for j in created_jobs):
            task_meta["metadata"]["publishing_status"] = PublishJobStatus.QUEUED
        elif any(j.status == PublishJobStatus.SCHEDULED for j in created_jobs):
            task_meta["metadata"]["publishing_status"] = PublishJobStatus.SCHEDULED
        elif any(j.status == PublishJobStatus.PUBLISHED for j in created_jobs):
            task_meta["metadata"]["publishing_status"] = PublishJobStatus.PUBLISHED

        await self.persistence.save_task_metadata(task_id, task_meta)

        if any(j.status == PublishJobStatus.QUEUED for j in created_jobs):
            self.wakeup_worker()

        return created_jobs
