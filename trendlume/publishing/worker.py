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
Publishing Worker & Queue Engine

In-process background publish queue consumer with:
- Global concurrency limiter (Semaphore)
- Per-account mutex lock (prevents multi-tab session conflicts on same account)
- Scheduler integration & Exponential backoff retry
- Idempotency & Crash recovery
- Dedicated background worker thread with Proactor event loop
"""

import asyncio
import sys
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set

from loguru import logger

from trendlume.models.publishing import (
    AccountStatus,
    PublishJob,
    PublishJobStatus,
    SocialAccount,
)
from trendlume.publishing.base import PublishResult
from trendlume.publishing.logger import PublishLogger
from trendlume.publishing.registry import PublisherRegistry, publisher_registry
from trendlume.services.publishing_persistence import PublishingPersistenceService


class PublishingWorker:
    """
    Asynchronous publishing worker that processes queued and scheduled video publishing jobs.
    """

    def __init__(
        self,
        store: PublishingPersistenceService,
        registry: Optional[PublisherRegistry] = None,
        max_concurrent_browsers: int = 2,
        poll_interval_seconds: float = 5.0,
    ):
        self.store = store
        self.registry = registry or publisher_registry
        self.max_concurrent_browsers = max_concurrent_browsers
        self.poll_interval = poll_interval_seconds

        self._semaphore: Optional[asyncio.Semaphore] = None
        self._account_locks: Dict[str, asyncio.Lock] = {}
        self._is_running = False
        self._wakeup_event: Optional[asyncio.Event] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._in_flight_jobs: Set[str] = set()
        self._active_job_tasks: Set[asyncio.Task] = set()

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Lazily initialize semaphore on current event loop"""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent_browsers)
        return self._semaphore

    def _get_account_lock(self, account_id: str) -> asyncio.Lock:
        """Get or create mutex lock for a specific social account on current event loop"""
        if account_id not in self._account_locks:
            self._account_locks[account_id] = asyncio.Lock()
        return self._account_locks[account_id]

    def _get_wakeup_event(self) -> asyncio.Event:
        """Lazily initialize wakeup event on current event loop"""
        if self._wakeup_event is None:
            self._wakeup_event = asyncio.Event()
        return self._wakeup_event

    def start(self):
        """Start background queue polling worker in a dedicated worker thread"""
        if self._is_running:
            return

        self._is_running = True

        def _worker_thread_main():
            logger.info(
                f"PublishingWorker thread started (max_concurrent_browsers={self.max_concurrent_browsers}, poll_interval={self.poll_interval}s)"
            )
            if sys.platform == "win32":
                self._loop = asyncio.ProactorEventLoop()
            else:
                self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            # Reset loop-bound async objects for the new loop
            self._semaphore = None
            self._account_locks.clear()
            self._wakeup_event = None
            self._active_job_tasks.clear()

            try:
                self._loop.run_until_complete(self._run_loop())
            except Exception as e:
                logger.error(f"Error in PublishingWorker thread loop: {e}")
            finally:
                try:
                    # Cancel any active tasks
                    pending = [t for t in asyncio.all_tasks(self._loop) if not t.done()]
                    for t in pending:
                        t.cancel()
                    if pending:
                        self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception as ex:
                    logger.debug(f"Error during loop task cancellation: {ex}")
                try:
                    self._loop.close()
                except Exception:
                    pass
                self._loop = None

        self._worker_thread = threading.Thread(target=_worker_thread_main, daemon=True, name="PublishingWorker")
        self._worker_thread.start()

    def stop(self):
        """Stop background worker loop gracefully"""
        if not self._is_running:
            return
        self._is_running = False
        self.wakeup()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)
        self._worker_thread = None
        logger.info("PublishingWorker stopped")

    def wakeup(self):
        """Trigger immediate queue scan without waiting for poll interval"""
        if self._loop and self._loop.is_running() and self._wakeup_event:
            self._loop.call_soon_threadsafe(self._wakeup_event.set)
        elif self._wakeup_event:
            self._wakeup_event.set()

    async def recover_stale_jobs(self):
        """
        Crash recovery on startup: find jobs stuck in PUBLISHING and recover them safely.
        """
        stale_jobs = await self.store.list_jobs(status=PublishJobStatus.PUBLISHING, limit=1000)
        for job in stale_jobs:
            PublishLogger.warning(
                f"Recovering stale PUBLISHING job {job.job_id} after process restart",
                job_id=job.job_id,
                platform=job.platform,
                account_id=job.account_id,
            )
            if job.platform_post_id:
                job.status = PublishJobStatus.PUBLISHED
            elif job.attempt_count >= job.max_attempts:
                job.status = PublishJobStatus.FAILED
                job.error_message = "Execution interrupted by server restart"
            else:
                job.status = PublishJobStatus.QUEUED
                job.error_message = "Restarted after unexpected interruption"

            job.updated_at = datetime.now().isoformat()
            await self.store.save_job(job)

    async def get_due_jobs(self, now: Optional[datetime] = None) -> List[PublishJob]:
        """
        Fetch all jobs ready for execution:
        - status == QUEUED (and next_retry_at is None or next_retry_at <= now)
        - status == SCHEDULED and scheduled_at <= now
        """
        now_dt = now or datetime.now()

        def _is_due(ts: Optional[str]) -> bool:
            if not ts:
                return True
            try:
                return datetime.fromisoformat(ts) <= now_dt
            except Exception:
                return True

        queued = await self.store.list_jobs(status=PublishJobStatus.QUEUED, limit=1000)
        due_jobs = [j for j in queued if _is_due(j.next_retry_at)]

        scheduled = await self.store.list_jobs(status=PublishJobStatus.SCHEDULED, limit=1000)
        due_jobs.extend(j for j in scheduled if j.scheduled_at and _is_due(j.scheduled_at))

        return due_jobs

    async def _safe_process_job(self, job_id: str) -> PublishResult:
        """Wrapper around process_job to manage in-flight lock release"""
        try:
            return await self.process_job(job_id)
        finally:
            self._in_flight_jobs.discard(job_id)

    async def _run_loop(self):
        """Main queue consumer loop"""
        await self.recover_stale_jobs()
        wakeup_evt = self._get_wakeup_event()

        while self._is_running:
            try:
                if len(self._active_job_tasks) < self.max_concurrent_browsers:
                    due_jobs = await self.get_due_jobs()
                    for job in due_jobs:
                        if not self._is_running or len(self._active_job_tasks) >= self.max_concurrent_browsers:
                            break
                        # Avoid duplicate dispatch of already in-flight jobs
                        if job.job_id in self._in_flight_jobs:
                            continue
                        self._in_flight_jobs.add(job.job_id)
                        task = asyncio.create_task(self._safe_process_job(job.job_id))
                        self._active_job_tasks.add(task)
                        task.add_done_callback(self._active_job_tasks.discard)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in PublishingWorker loop: {e}")

            # Wait for next poll or wakeup
            try:
                await asyncio.wait_for(wakeup_evt.wait(), timeout=self.poll_interval)
                wakeup_evt.clear()
            except asyncio.TimeoutError:
                pass

    async def _handle_job_failure(
        self,
        job: PublishJob,
        account: SocialAccount,
        error_message: str,
        completed_iso: str,
    ) -> None:
        """Centralized failure handling, retry backoff calculation, and account health state updating"""
        job.error_message = error_message
        account.failed_count += 1
        account.updated_at = completed_iso

        if "[AUTH_ERROR]" in error_message:
            job.error_code = "AUTH_ERROR"
            job.status = PublishJobStatus.FAILED
            job.next_retry_at = None
            account.status = AccountStatus.EXPIRED
            PublishLogger.error(
                f"Authentication failed: {error_message}. Account marked EXPIRED. No auto-retry.",
                job_id=job.job_id,
                platform=job.platform,
                account_id=job.account_id,
            )
        elif "[VALIDATION_ERROR]" in error_message:
            job.error_code = "VALIDATION_ERROR"
            job.status = PublishJobStatus.FAILED
            job.next_retry_at = None
            PublishLogger.error(
                f"Validation failed: {error_message}. No auto-retry.",
                job_id=job.job_id,
                platform=job.platform,
                account_id=job.account_id,
            )
        elif job.attempt_count < job.max_attempts:
            job.error_code = "UPLOAD_ERROR"
            backoff_seconds = (2 ** (job.attempt_count - 1)) * 60
            job.next_retry_at = (datetime.now() + timedelta(seconds=backoff_seconds)).isoformat()
            job.status = PublishJobStatus.QUEUED
            PublishLogger.warning(
                f"Publish attempt failed: {error_message}. Next retry scheduled at {job.next_retry_at} (backoff: {backoff_seconds}s)",
                job_id=job.job_id,
                platform=job.platform,
                account_id=job.account_id,
                attempt=job.attempt_count,
                max_attempts=job.max_attempts,
            )
        else:
            job.error_code = "UPLOAD_ERROR"
            job.status = PublishJobStatus.FAILED
            job.next_retry_at = None
            PublishLogger.error(
                f"Max attempts ({job.max_attempts}) reached. Job marked FAILED: {error_message}",
                job_id=job.job_id,
                platform=job.platform,
                account_id=job.account_id,
            )

        await self.store.save_account(account)
        await self.store.save_job(job)

    async def process_job(self, job_id: str) -> PublishResult:
        """
        Execute a single publish job with idempotency checks, account lock, and semaphore limit.
        """
        job = await self.store.get_job(job_id)
        if not job:
            return PublishResult(success=False, error_message=f"Job {job_id} not found")

        # 1. Idempotency Check: if already published, skip
        if job.status == PublishJobStatus.PUBLISHED or job.platform_post_id:
            PublishLogger.info(
                f"Job already published (Post ID: {job.platform_post_id}), skipping duplicate execution.",
                job_id=job.job_id,
                platform=job.platform,
                account_id=job.account_id,
            )
            return PublishResult(
                success=True,
                platform_post_id=job.platform_post_id,
                error_message="Job is already published",
            )

        # 2. Acquire Global Concurrency Semaphore
        async with self._get_semaphore():
            # 3. Acquire Account Mutex Lock (ensures 1 job per account at a time)
            account_lock = self._get_account_lock(job.account_id)
            async with account_lock:
                # Reload job to verify status inside lock
                job = await self.store.get_job(job_id)
                if not job or job.status == PublishJobStatus.PUBLISHED:
                    return PublishResult(success=True, platform_post_id=job.platform_post_id if job else None)

                account = await self.store.get_account(job.account_id)
                async def _fail_job(error_code: str, error_message: str) -> PublishResult:
                    job.status = PublishJobStatus.FAILED
                    job.error_code = error_code
                    job.error_message = error_message
                    now_str = datetime.now().isoformat()
                    job.completed_at = now_str
                    job.updated_at = now_str
                    await self.store.save_job(job)
                    return PublishResult(success=False, error_message=error_message)

                if not account:
                    return await _fail_job("VALIDATION_ERROR", f"Account {job.account_id} not found")

                if account.status in [AccountStatus.DISABLED, AccountStatus.EXPIRED]:
                    return await _fail_job("AUTH_ERROR", f"Account {account.account_name} is {account.status}")

                credential = None
                if account.credential_id:
                    credential = await self.store.get_credential(account.credential_id)

                # Ensure video file exists
                if not job.video_path or not Path(job.video_path).exists():
                    return await _fail_job("VALIDATION_ERROR", f"Video file not found at path: {job.video_path}")

                # Transition to PUBLISHING
                now_iso = datetime.now().isoformat()
                job.status = PublishJobStatus.PUBLISHING
                job.attempt_count += 1
                job.started_at = now_iso
                job.lock_token = uuid.uuid4().hex
                job.updated_at = now_iso
                await self.store.save_job(job)

                PublishLogger.info(
                    f"Publishing video '{job.title}' to {job.platform.upper()}",
                    job_id=job.job_id,
                    platform=job.platform,
                    account_id=job.account_id,
                    attempt=job.attempt_count,
                    max_attempts=job.max_attempts,
                )

                # Execute Platform Publisher
                try:
                    publisher = self.registry.get_publisher(job.platform)
                    result = await publisher.publish_video(job, account, credential)

                    completed_iso = datetime.now().isoformat()
                    job.updated_at = completed_iso
                    job.completed_at = completed_iso

                    if result.success:
                        job.status = PublishJobStatus.PUBLISHED
                        job.platform_post_id = result.platform_post_id
                        job.published_at = completed_iso
                        job.error_message = None
                        job.error_code = None
                        job.next_retry_at = None
                        job.lock_token = None

                        # Update account publishing stats
                        account.published_count += 1
                        account.last_published_at = completed_iso
                        account.updated_at = completed_iso
                        await self.store.save_account(account)
                        await self.store.save_job(job)

                        PublishLogger.info(
                            f"Published successfully! Post ID: {result.platform_post_id}",
                            job_id=job.job_id,
                            platform=job.platform,
                            account_id=job.account_id,
                        )
                        return result
                    else:
                        err_msg = result.error_message or "Platform publish failed"
                        await self._handle_job_failure(job, account, err_msg, completed_iso)
                        return result

                except Exception as e:
                    completed_iso = datetime.now().isoformat()
                    err_str = str(e)
                    job.completed_at = completed_iso
                    job.updated_at = completed_iso
                    await self._handle_job_failure(job, account, err_str, completed_iso)
                    return PublishResult(success=False, error_message=err_str)
