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
History Migration Service

Safely migrates legacy generation tasks into the Project system.
Guarantees:
- Zero data loss (no file deletion, no file moving, no file copying)
- Complete idempotency (no duplicate projects, no duplicate task assignments)
- High fault tolerance (corrupted/missing metadata handled gracefully without blocking)
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger
from pydantic import BaseModel, Field

from trendlume.models.project import Project
from trendlume.services.persistence import PersistenceService
from trendlume.services.project_manager import ProjectManager

IMPORTED_HISTORY_PROJECT_ID = "proj_imported_history"
IMPORTED_HISTORY_NAME = "Imported History"


class MigrationResult(BaseModel):
    """Result summary of a history migration execution"""
    project_id: str = Field(description="Target Project ID for legacy tasks")
    project_name: str = Field(description="Target Project name")
    total_scanned: int = Field(default=0, description="Total directories scanned in output")
    migrated: int = Field(default=0, description="Tasks successfully migrated in this run")
    already_migrated: int = Field(default=0, description="Tasks that already belonged to a project")
    skipped_incomplete: int = Field(default=0, description="Directories skipped due to missing metadata.json")
    failed: int = Field(default=0, description="Directories skipped due to corrupted/unparseable metadata")
    details: List[Dict[str, Any]] = Field(default_factory=list, description="Per-task migration details")


class HistoryMigrationService:
    """
    Service responsible for safely discovering and migrating legacy tasks into Projects.
    """

    def __init__(self, persistence: PersistenceService, project_manager: ProjectManager):
        self.persistence = persistence
        self.project_manager = project_manager

    async def get_or_create_imported_history_project(self) -> Project:
        """
        Get or create the logical 'Imported History' Project.
        Guarantees idempotency by reusing any existing project with matching ID or Name.
        """
        # 1. Look up by deterministic ID
        project = await self.project_manager.get_project(IMPORTED_HISTORY_PROJECT_ID)
        if project:
            return project

        # 2. Look up by Name across all projects
        projects = await self.project_manager.list_projects()
        for p in projects:
            if p.name == IMPORTED_HISTORY_NAME:
                return p

        # 3. Create if does not exist
        project = await self.project_manager.create_project(
            name=IMPORTED_HISTORY_NAME,
            description="Auto-imported legacy generation tasks from history",
            tags=["imported", "legacy", "history"],
            project_id=IMPORTED_HISTORY_PROJECT_ID,
        )
        logger.info(f"Created '{IMPORTED_HISTORY_NAME}' project: {project.project_id}")
        return project

    async def migrate(self) -> MigrationResult:
        """
        Execute the migration process.
        
        Scans output/ directory:
        - Identifies valid legacy tasks without project_id
        - Assigns them to 'Imported History' project
        - Gracefully skips incomplete or corrupted directories with warning logs
        - Leaves all videos, audio, and directory structures 100% in place
        
        Returns:
            MigrationResult with statistics and per-item details
        """
        project = await self.get_or_create_imported_history_project()

        result = MigrationResult(
            project_id=project.project_id,
            project_name=project.name,
        )

        output_dir = self.persistence.output_dir
        if not output_dir.exists():
            logger.warning(f"Output directory does not exist: {output_dir}")
            return result

        # Scan directories
        for entry in sorted(output_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith(".") or entry.name == "projects":
                continue

            task_id = entry.name
            result.total_scanned += 1
            metadata_path = self.persistence.get_metadata_path(task_id)

            # Check 1: metadata.json existence
            if not metadata_path.exists():
                logger.warning(
                    f"Skipping task directory '{task_id}': metadata.json not found (incomplete task)"
                )
                result.skipped_incomplete += 1
                result.details.append({
                    "task_id": task_id,
                    "status": "skipped_incomplete",
                    "reason": "metadata.json not found",
                })
                continue

            # Check 2: Parse metadata.json
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception as e:
                logger.warning(
                    f"Skipping task directory '{task_id}': corrupted or unparseable metadata.json: {e}"
                )
                result.failed += 1
                result.details.append({
                    "task_id": task_id,
                    "status": "failed",
                    "reason": f"Corrupted JSON: {e}",
                })
                continue

            if not isinstance(metadata, dict):
                logger.warning(
                    f"Skipping task directory '{task_id}': metadata.json is not a valid JSON object"
                )
                result.failed += 1
                result.details.append({
                    "task_id": task_id,
                    "status": "failed",
                    "reason": "Metadata is not a JSON object",
                })
                continue

            # Check 3: Check if already associated with a project (Idempotency)
            existing_project_id = metadata.get("project_id")
            if existing_project_id:
                result.already_migrated += 1
                result.details.append({
                    "task_id": task_id,
                    "status": "already_migrated",
                    "project_id": existing_project_id,
                })
                continue

            # Check 4: Video existence check (warning only, do not block)
            result_info = metadata.get("result", {})
            video_path = result_info.get("video_path") if isinstance(result_info, dict) else None
            has_video = False
            if video_path and Path(video_path).exists():
                has_video = True
            elif (entry / "final.mp4").exists():
                has_video = True

            if not has_video:
                logger.warning(
                    f"Task '{task_id}' has valid metadata but video file is missing"
                )

            # Perform safe in-place assignment
            metadata["project_id"] = project.project_id
            try:
                await self.persistence.save_task_metadata(task_id, metadata)
                result.migrated += 1
                title = (
                    metadata.get("input", {}).get("title")
                    if isinstance(metadata.get("input"), dict)
                    else None
                ) or metadata.get("title", "")
                result.details.append({
                    "task_id": task_id,
                    "status": "migrated",
                    "project_id": project.project_id,
                    "title": title,
                    "has_video": has_video,
                })
                logger.info(f"Migrated legacy task '{task_id}' -> '{project.name}'")
            except Exception as e:
                logger.error(f"Failed to save metadata for task '{task_id}': {e}")
                result.failed += 1
                result.details.append({
                    "task_id": task_id,
                    "status": "failed",
                    "reason": f"Save error: {e}",
                })

        # Rebuild index to guarantee consistency across all tasks and projects
        await self.persistence.rebuild_index()

        logger.info(
            f"Migration completed: {result.migrated} migrated, "
            f"{result.already_migrated} already migrated, "
            f"{result.skipped_incomplete} incomplete, {result.failed} failed "
            f"(Total scanned: {result.total_scanned})"
        )
        return result
