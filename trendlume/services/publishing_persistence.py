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
Publishing Persistence Service

Handles filesystem persistence for Social Accounts, Credentials, Publish Jobs, and Templates.
"""

import json
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional

from loguru import logger

from trendlume.models.publishing import (
    Credential,
    PublishJob,
    PublishTemplate,
    SocialAccount,
)


class PublishingPersistenceService:
    """
    Persistence service for publishing infrastructure using JSON files.

    Directory structure:
        output/
        └── publishing/
            ├── accounts.json
            ├── credentials.json
            ├── jobs.json
            └── templates.json
    """

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.publishing_dir = self.output_dir / "publishing"
        self.publishing_dir.mkdir(parents=True, exist_ok=True)

        self.accounts_file = self.publishing_dir / "accounts.json"
        self.credentials_file = self.publishing_dir / "credentials.json"
        self.jobs_file = self.publishing_dir / "jobs.json"
        self.templates_file = self.publishing_dir / "templates.json"

        self._lock = threading.RLock()
        self._ensure_storage()

    def _ensure_storage(self):
        """Ensure json storage files exist"""
        for file_path in [self.accounts_file, self.credentials_file, self.jobs_file, self.templates_file]:
            if not file_path.exists():
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump({}, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"Failed to initialize storage file {file_path}: {e}")

    def _read_json(self, file_path: Path) -> Dict[str, Any]:
        """Safely read JSON dictionary from file"""
        if not file_path.exists():
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading JSON from {file_path}: {e}")
            return {}

    def _write_json(self, file_path: Path, data: Dict[str, Any]):
        """Safely write JSON dictionary to file"""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error writing JSON to {file_path}: {e}")
            raise

    # ========================================================================
    # SocialAccount Operations
    # ========================================================================

    async def save_account(self, account: SocialAccount) -> SocialAccount:
        """Create or update a SocialAccount"""
        with self._lock:
            accounts = self._read_json(self.accounts_file)
            accounts[account.account_id] = account.model_dump()
            self._write_json(self.accounts_file, accounts)
        logger.debug(f"Saved social account: {account.account_id} ({account.account_name})")
        return account

    async def get_account(self, account_id: str) -> Optional[SocialAccount]:
        """Get a SocialAccount by account_id"""
        with self._lock:
            accounts = self._read_json(self.accounts_file)
            raw = accounts.get(account_id)
        if raw:
            try:
                return SocialAccount(**raw)
            except Exception as e:
                logger.error(f"Failed to parse account {account_id}: {e}")
        return None

    async def list_accounts(
        self,
        platform: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[SocialAccount]:
        """List SocialAccounts with optional platform/status filter"""
        with self._lock:
            accounts_dict = self._read_json(self.accounts_file)
        result: List[SocialAccount] = []
        for raw in accounts_dict.values():
            try:
                acc = SocialAccount(**raw)
                if platform and acc.platform != platform:
                    continue
                if status and acc.status != status:
                    continue
                result.append(acc)
            except Exception as e:
                logger.warning(f"Failed to parse account: {e}")

        result.sort(key=lambda a: a.created_at, reverse=True)
        return result

    async def delete_account(self, account_id: str) -> bool:
        """Delete a SocialAccount and its associated credential"""
        with self._lock:
            accounts = self._read_json(self.accounts_file)
            if account_id in accounts:
                acc_data = accounts.pop(account_id)
                self._write_json(self.accounts_file, accounts)

                # Also delete linked credential if any
                cred_id = acc_data.get("credential_id")
                if cred_id:
                    creds = self._read_json(self.credentials_file)
                    if cred_id in creds:
                        del creds[cred_id]
                        self._write_json(self.credentials_file, creds)
                        logger.info(f"Deleted credential: {cred_id}")

                logger.info(f"Deleted social account: {account_id}")
                return True
            return False

    # ========================================================================
    # Credential Operations
    # ========================================================================

    async def save_credential(self, credential: Credential) -> Credential:
        """Create or update a Credential"""
        with self._lock:
            creds = self._read_json(self.credentials_file)
            creds[credential.credential_id] = credential.model_dump()
            self._write_json(self.credentials_file, creds)
        logger.debug(f"Saved credential: {credential.credential_id} ({credential.platform})")
        return credential

    async def get_credential(self, credential_id: str) -> Optional[Credential]:
        """Get a Credential by credential_id"""
        with self._lock:
            creds = self._read_json(self.credentials_file)
            raw = creds.get(credential_id)
        if raw:
            try:
                return Credential(**raw)
            except Exception as e:
                logger.error(f"Failed to parse credential {credential_id}: {e}")
        return None

    async def delete_credential(self, credential_id: str) -> bool:
        """Delete a Credential by credential_id"""
        with self._lock:
            creds = self._read_json(self.credentials_file)
            if credential_id in creds:
                del creds[credential_id]
                self._write_json(self.credentials_file, creds)
                logger.info(f"Deleted credential: {credential_id}")
                return True
            return False

    # ========================================================================
    # PublishJob Operations
    # ========================================================================

    async def save_job(self, job: PublishJob) -> PublishJob:
        """Create or update a PublishJob"""
        with self._lock:
            jobs = self._read_json(self.jobs_file)
            jobs[job.job_id] = job.model_dump()
            self._write_json(self.jobs_file, jobs)
        logger.debug(f"Saved publish job: {job.job_id} (status: {job.status})")
        return job

    async def get_job(self, job_id: str) -> Optional[PublishJob]:
        """Get a PublishJob by job_id"""
        with self._lock:
            jobs = self._read_json(self.jobs_file)
            raw = jobs.get(job_id)
        if raw:
            try:
                return PublishJob(**raw)
            except Exception as e:
                logger.error(f"Failed to parse job {job_id}: {e}")
        return None

    async def list_jobs(
        self,
        platform: Optional[str] = None,
        account_id: Optional[str] = None,
        status: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PublishJob]:
        """List PublishJobs with filtering and pagination"""
        with self._lock:
            jobs_dict = self._read_json(self.jobs_file)
        result: List[PublishJob] = []
        for raw in jobs_dict.values():
            try:
                job = PublishJob(**raw)
                if platform and job.platform != platform:
                    continue
                if account_id and job.account_id != account_id:
                    continue
                if status and job.status != status:
                    continue
                if task_id and job.task_id != task_id:
                    continue
                result.append(job)
            except Exception as e:
                logger.warning(f"Failed to parse job: {e}")

        result.sort(key=lambda j: j.created_at, reverse=True)
        return result[offset : offset + limit]

    async def delete_job(self, job_id: str) -> bool:
        """Delete a PublishJob by job_id"""
        with self._lock:
            jobs = self._read_json(self.jobs_file)
            if job_id in jobs:
                del jobs[job_id]
                self._write_json(self.jobs_file, jobs)
                logger.info(f"Deleted publish job: {job_id}")
                return True
            return False

    # ========================================================================
    # PublishTemplate Operations
    # ========================================================================

    async def save_template(self, template: PublishTemplate) -> PublishTemplate:
        """Create or update a PublishTemplate"""
        with self._lock:
            templates = self._read_json(self.templates_file)
            templates[template.template_id] = template.model_dump()
            self._write_json(self.templates_file, templates)
        logger.debug(f"Saved publish template: {template.template_id} ({template.template_name})")
        return template

    async def get_template(self, template_id: str) -> Optional[PublishTemplate]:
        """Get a PublishTemplate by template_id"""
        with self._lock:
            templates = self._read_json(self.templates_file)
            raw = templates.get(template_id)
        if raw:
            try:
                return PublishTemplate(**raw)
            except Exception as e:
                logger.error(f"Failed to parse template {template_id}: {e}")
        return None

    async def list_templates(self) -> List[PublishTemplate]:
        """List all PublishTemplates"""
        with self._lock:
            templates_dict = self._read_json(self.templates_file)
        result: List[PublishTemplate] = []
        for raw in templates_dict.values():
            try:
                result.append(PublishTemplate(**raw))
            except Exception as e:
                logger.warning(f"Failed to parse template: {e}")

        result.sort(key=lambda t: t.created_at, reverse=True)
        return result

    async def delete_template(self, template_id: str) -> bool:
        """Delete a PublishTemplate by template_id"""
        with self._lock:
            templates = self._read_json(self.templates_file)
            if template_id in templates:
                del templates[template_id]
                self._write_json(self.templates_file, templates)
                logger.info(f"Deleted publish template: {template_id}")
                return True
            return False
