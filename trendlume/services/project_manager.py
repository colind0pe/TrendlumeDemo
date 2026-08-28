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
Project Manager Service

Business logic for managing Projects and Project-Task relationships.
"""

import os
import shutil
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from trendlume.models.project import Project, Task, TaskStatus
from trendlume.services.persistence import PersistenceService


class ProjectManager:
    """
    Project management service
    
    Provides business logic for:
    - Project lifecycle (create, get, list, update, delete)
    - Task-Project associations (add to project, remove from project, get project tasks)
    - Task Plans and Execution lifecycle (create plan, update plan, execute, schedule, retry)
    """
    
    def __init__(self, persistence: PersistenceService, core: Optional[Any] = None):
        """
        Initialize ProjectManager
        
        Args:
            persistence: PersistenceService instance
            core: Optional TrendlumeCore instance for pipeline execution
        """
        self.persistence = persistence
        self.core = core

    async def create_project(
        self,
        name: str,
        description: Optional[str] = "",
        cover: Optional[str] = None,
        tags: Optional[List[str]] = None,
        settings: Optional[Dict[str, Any]] = None,
        template: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
    ) -> Project:
        """
        Create a new Project
        
        Args:
            name: Project name
            description: Project description
            cover: Project cover image path or URL
            tags: List of tags
            settings: Project-level settings
            template: Default generation template configuration (optional)
            project_id: Custom project ID (optional, auto-generated if omitted)
            
        Returns:
            Created Project instance
        """
        if not project_id:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            short_id = uuid.uuid4().hex[:4]
            project_id = f"proj_{timestamp}_{short_id}"
        
        now = datetime.now().isoformat()
        project = Project(
            project_id=project_id,
            name=name,
            description=description or "",
            cover=cover,
            tags=tags or [],
            settings=settings or {},
            template=template,
            created_at=now,
            updated_at=now,
        )
        
        await self.persistence.save_project(project.model_dump())
        logger.info(f"Created project: {project_id} ({name})")
        return project

    async def get_project(self, project_id: str) -> Optional[Project]:
        """
        Get Project by ID
        
        Args:
            project_id: Project ID
            
        Returns:
            Project instance or None if not found
        """
        data = await self.persistence.load_project(project_id)
        if not data:
            return None
        return Project.model_validate(data)

    async def list_projects(self) -> List[Project]:
        """
        List all Projects, sorted by created_at descending
        
        Returns:
            List of Project instances
        """
        projects_data = await self.persistence.list_projects()
        return [Project.model_validate(p) for p in projects_data]

    async def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        cover: Optional[str] = None,
        tags: Optional[List[str]] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Optional[Project]:
        """
        Update an existing Project
        
        Args:
            project_id: Project ID
            name: New name (optional)
            description: New description (optional)
            cover: New cover (optional)
            tags: New tags (optional)
            settings: New settings (optional)
            
        Returns:
            Updated Project or None if not found
        """
        project = await self.get_project(project_id)
        if not project:
            logger.warning(f"Cannot update project: {project_id} not found")
            return None
        
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if cover is not None:
            project.cover = cover
        if tags is not None:
            project.tags = tags
        if settings is not None:
            project.settings = settings
        
        project.updated_at = datetime.now().isoformat()
        await self.persistence.save_project(project.model_dump())
        logger.info(f"Updated project: {project_id}")
        return project

    async def set_project_template(
        self,
        project_id: str,
        template_config: Dict[str, Any],
    ) -> Project:
        """
        Set or update the generation template for a project.
        Strips any runtime/task-specific fields (task_id, video, text, title, etc.)
        so the template only contains clean generation configuration.
        """
        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Sanitize template: only keep generation configuration
        clean_template = dict(template_config)
        forbidden_keys = [
            "task_id", "project_id", "text", "title", "video", "storyboard",
            "assets", "status", "result", "executions", "metadata", "created_at",
            "completed_at", "scheduled_at", "priority", "batch_mode",
            "progress_callback", "final_video_path",
        ]
        for key in forbidden_keys:
            clean_template.pop(key, None)

        project.template = clean_template
        project.updated_at = datetime.now().isoformat()
        await self.persistence.save_project(project.model_dump())
        logger.info(f"Set template for project {project_id} with {len(clean_template)} keys")
        return project

    async def get_project_template(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project generation template configuration"""
        project = await self.get_project(project_id)
        if not project:
            return None
        return project.template

    async def clear_project_template(self, project_id: str) -> Project:
        """Clear the project generation template (revert to system default)"""
        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        project.template = None
        project.updated_at = datetime.now().isoformat()
        await self.persistence.save_project(project.model_dump())
        logger.info(f"Cleared template for project {project_id}")
        return project

    async def delete_project(self, project_id: str, keep_tasks: bool = True) -> bool:
        """
        Delete a Project.
        By default, preserves existing tasks and unbinds project_id (decouple).
        
        Args:
            project_id: Project ID to delete
            keep_tasks: If True (default), decouple tasks by setting project_id=None.
            
        Returns:
            True if successful, False otherwise
        """
        project = await self.get_project(project_id)
        if not project:
            logger.warning(f"Cannot delete project: {project_id} not found")
            return False
        
        if keep_tasks:
            # Unbind all tasks associated with this project
            tasks = await self.get_project_tasks(project_id)
            for task in tasks:
                await self.remove_task_from_project(task.task_id)
            logger.info(f"Decoupled {len(tasks)} tasks from project {project_id}")
        else:
            # Delete all tasks associated with this project
            tasks = await self.get_project_tasks(project_id)
            for task in tasks:
                await self.persistence.delete_task(task.task_id)
            logger.info(f"Deleted {len(tasks)} tasks associated with project {project_id}")
        
        success = await self.persistence.delete_project(project_id)
        if success:
            logger.info(f"Deleted project: {project_id}")
        return success

    async def get_project_tasks(self, project_id: str) -> List[Task]:
        """
        Get all tasks belonging to a Project
        
        Args:
            project_id: Project ID
            
        Returns:
            List of Task instances
        """
        task_summaries = await self.persistence.list_tasks(project_id=project_id, limit=10000)
        tasks: List[Task] = []
        for summary in task_summaries:
            task_id = summary.get("task_id")
            if task_id:
                metadata = await self.persistence.load_task_metadata(task_id)
                if metadata:
                    tasks.append(Task.from_metadata_dict(metadata))
        return tasks

    async def add_task_to_project(self, task_id: str, project_id: str) -> bool:
        """
        Associate a Task with a Project
        
        Args:
            task_id: Task ID
            project_id: Project ID
            
        Returns:
            True if successful, False if task or project does not exist
        """
        project = await self.get_project(project_id)
        if not project:
            logger.warning(f"Cannot add task {task_id}: Project {project_id} does not exist")
            return False
        
        metadata = await self.persistence.load_task_metadata(task_id)
        if not metadata:
            logger.warning(f"Cannot add task {task_id}: Task does not exist")
            return False
        
        metadata["project_id"] = project_id
        await self.persistence.save_task_metadata(task_id, metadata)
        logger.info(f"Added task {task_id} to project {project_id}")
        return True

    async def remove_task_from_project(self, task_id: str) -> bool:
        """
        Disassociate a Task from its Project (sets project_id to None)
        
        Args:
            task_id: Task ID
            
        Returns:
            True if successful, False if task does not exist
        """
        metadata = await self.persistence.load_task_metadata(task_id)
        if not metadata:
            logger.warning(f"Cannot remove task {task_id}: Task does not exist")
            return False
        
        metadata["project_id"] = None
        await self.persistence.save_task_metadata(task_id, metadata)
        logger.info(f"Removed task {task_id} from project")
        return True

    async def migrate_legacy_tasks(self):
        """
        Migrate legacy history tasks into the 'Imported History' project.
        
        Returns:
            MigrationResult containing statistics and details
        """
        from trendlume.services.history_migration import HistoryMigrationService
        service = HistoryMigrationService(self.persistence, self)
        return await service.migrate()

    @staticmethod
    def _empty_stats() -> Dict[str, int]:
        """Return a zeroed stats dict."""
        return {
            "total": 0,
            "draft": 0,
            "scheduled": 0,
            "queued": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "pending": 0,
        }

    @staticmethod
    def _accumulate_task_status(stats: Dict[str, int], status: str) -> None:
        """Increment the appropriate counters in *stats* for a single task *status*."""
        stats["total"] += 1
        if status == TaskStatus.DRAFT:
            stats["draft"] += 1
        elif status == TaskStatus.SCHEDULED:
            stats["scheduled"] += 1
        elif status == TaskStatus.QUEUED:
            stats["queued"] += 1
            stats["scheduled"] += 1  # queued is a sub-state of scheduled
        elif status == TaskStatus.RUNNING:
            stats["running"] += 1
        elif status == TaskStatus.COMPLETED:
            stats["completed"] += 1
        elif status == TaskStatus.FAILED:
            stats["failed"] += 1
        elif status == TaskStatus.CANCELLED:
            stats["cancelled"] += 1
        if status in (TaskStatus.PENDING, TaskStatus.DRAFT, TaskStatus.SCHEDULED, TaskStatus.QUEUED):
            stats["pending"] += 1

    async def get_project_stats(self, project_id: str) -> Dict[str, int]:
        """
        Get aggregated task statistics for a Project
        
        Args:
            project_id: Project ID
            
        Returns:
            Dict containing total, completed, failed, running, pending, scheduled, draft counts
        """
        tasks = await self.persistence.list_tasks(project_id=project_id, limit=10000)
        stats = self._empty_stats()
        for t in tasks:
            self._accumulate_task_status(stats, t.get("status", ""))
        return stats

    async def get_all_projects_stats(self) -> Dict[str, Dict[str, int]]:
        """
        Get aggregated task statistics for all Projects in a single pass.
        Eliminates N+1 index loading during Projects list rendering.
        
        Returns:
            Dict mapping project_id -> {total, draft, scheduled, queued, running, completed, failed, cancelled, pending}
        """
        all_tasks = await self.persistence.list_tasks(limit=100000)
        stats_by_proj: Dict[str, Dict[str, int]] = {}
        
        for t in all_tasks:
            pid = t.get("project_id") or "_unassigned"
            if pid not in stats_by_proj:
                stats_by_proj[pid] = self._empty_stats()
            self._accumulate_task_status(stats_by_proj[pid], t.get("status", ""))
                
        return stats_by_proj

    # ========================================================================
    # Task Plan & Generation Lifecycle
    # ========================================================================

    async def create_task_plan(
        self,
        project_id: str,
        title: str,
        text: str,
        generation_config: Optional[Dict[str, Any]] = None,
        scheduled_at: Optional[str] = None,
        priority: int = 0,
        auto_generate: bool = False,
        task_id: Optional[str] = None,
        progress_callback: Optional[Any] = None,
    ) -> Task:
        """
        Create a new Task Plan within a project
        
        Args:
            project_id: Associated project ID
            title: Task title
            text: Video script or topic
            generation_config: Optional pipeline generation configuration
            scheduled_at: Optional scheduled ISO timestamp
            priority: Task priority (higher executes first)
            auto_generate: Whether to execute immediately
            task_id: Optional explicit task ID
            progress_callback: Optional callback for real-time progress events
            
        Returns:
            Created Task instance
        """
        if not task_id:
            now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            rand_suffix = uuid.uuid4().hex[:4]
            task_id = f"{now_str}_{rand_suffix}"
            
        status = TaskStatus.DRAFT
        if auto_generate:
            status = TaskStatus.QUEUED
        elif scheduled_at:
            status = TaskStatus.SCHEDULED
            
        now_iso = datetime.now().isoformat()
        cfg = dict(generation_config or {})
        
        input_data = {
            "title": title or "",
            "text": text or "",
        }
        if "input" in cfg and isinstance(cfg["input"], dict):
            input_data.update(cfg["input"])
            
        metadata = {
            "task_id": task_id,
            "project_id": project_id,
            "status": status,
            "title": title or "",
            "created_at": now_iso,
            "completed_at": None,
            "scheduled_at": scheduled_at,
            "priority": priority,
            "executions": [],
            "input": input_data,
            "config": cfg,
            "result": None,
            "metadata": {},
        }
        
        await self.persistence.save_task_metadata(task_id, metadata)
        logger.info(f"Created task plan: {task_id} in project {project_id} (status: {status})")
        
        task = Task.from_metadata_dict(metadata)
        if auto_generate:
            task = await self.execute_task(task_id, progress_callback=progress_callback)
            
        return task

    async def update_task_plan(
        self,
        task_id: str,
        title: Optional[str] = None,
        text: Optional[str] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        scheduled_at: Optional[str] = None,
        priority: Optional[int] = None,
        status: Optional[str] = None,
    ) -> Optional[Task]:
        """Update an existing task plan"""
        metadata = await self.persistence.load_task_metadata(task_id)
        if not metadata:
            return None
            
        if title is not None:
            metadata["title"] = title
            metadata.setdefault("input", {})["title"] = title
        if text is not None:
            metadata.setdefault("input", {})["text"] = text
        if generation_config is not None:
            metadata["config"] = generation_config
        if scheduled_at is not None:
            metadata["scheduled_at"] = scheduled_at
            if metadata.get("status") in [TaskStatus.DRAFT, TaskStatus.CANCELLED]:
                metadata["status"] = TaskStatus.SCHEDULED
        if priority is not None:
            metadata["priority"] = priority
        if status is not None:
            metadata["status"] = status
            
        await self.persistence.save_task_metadata(task_id, metadata)
        return Task.from_metadata_dict(metadata)

    async def execute_task(
        self,
        task_id: str,
        core: Optional[Any] = None,
        progress_callback: Optional[Any] = None,
    ) -> Task:
        """
        Execute generation for a Task using the existing pipeline.
        If the task already has a video, archives the previous video to avoid overwriting.
        """
        metadata = await self.persistence.load_task_metadata(task_id)
        if not metadata:
            raise ValueError(f"Task {task_id} not found")

        if metadata.get("status") == TaskStatus.RUNNING:
            logger.warning(f"Task {task_id} is already running; skipping duplicate execution")
            return Task.from_metadata_dict(metadata)
            
        core_instance = core or self.core
        if core_instance is None:
            from trendlume.service import trendlume
            core_instance = trendlume
            
        if not getattr(core_instance, "_initialized", False):
            await core_instance.initialize()
            
        # Non-destructive: Archive existing final.mp4 if this is a re-run
        is_reexecution = metadata.get("status") == TaskStatus.COMPLETED or metadata.get("completed_at") is not None
        res = metadata.get("result") or {}
        existing_video = res.get("video_path")
        if not existing_video and is_reexecution:
            default_video = self.persistence.get_task_final_video_path(task_id)
            if default_video.exists() and default_video.stat().st_size > 0:
                existing_video = str(default_video)
                
        if is_reexecution and existing_video and os.path.exists(existing_video):
            exec_dir = self.persistence.get_task_dir(task_id) / "executions"
            exec_dir.mkdir(parents=True, exist_ok=True)
            arch_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
            arch_path = exec_dir / f"final_{arch_id}.mp4"
            try:
                shutil.copy2(existing_video, arch_path)
                existing_execs = metadata.setdefault("executions", [])
                matched = False
                for ex in reversed(existing_execs):
                    if ex.get("video_path") == existing_video or (ex.get("status") == "completed" and not matched):
                        ex["video_path"] = str(arch_path)
                        matched = True
                        break
                if not matched:
                    existing_execs.append({
                        "execution_id": arch_id,
                        "created_at": metadata.get("completed_at") or datetime.now().isoformat(),
                        "status": "completed",
                        "video_path": str(arch_path),
                        "duration": res.get("duration", 0),
                        "n_frames": res.get("n_frames", 0),
                        "file_size": os.path.getsize(arch_path) if arch_path.exists() else 0,
                    })
                logger.info(f"Archived previous execution for task {task_id} to {arch_path}")
            except Exception as e:
                logger.warning(f"Failed to archive old video for task {task_id}: {e}")
                
        # Mark running
        metadata["status"] = TaskStatus.RUNNING
        await self.persistence.save_task_metadata(task_id, metadata)
        
        # Prepare pipeline params
        input_dict = dict(metadata.get("input", {}))
        input_text = input_dict.pop("text", "")
        cfg = dict(metadata.get("config", {}))
        
        # Merge input_dict into cfg so all parameters (TTS, template, workflow, BGM, etc.) are passed
        full_params = {**cfg, **input_dict}
        pipeline_name = full_params.pop("pipeline", "standard")
        full_params.setdefault("project_id", metadata.get("project_id"))
        full_params.setdefault("task_id", task_id)
        if metadata.get("title"):
            full_params.setdefault("title", metadata.get("title"))
        if progress_callback is not None:
            full_params["progress_callback"] = progress_callback
            
        try:
            result = await core_instance.generate_video(
                text=input_text,
                pipeline=pipeline_name,
                **full_params,
            )
            now_iso = datetime.now().isoformat()
            video_path = getattr(result, "final_video_path", None) or str(self.persistence.get_task_final_video_path(task_id))
            duration = getattr(result, "duration", 0)
            n_frames = getattr(result, "n_frames", 0)
            file_size = os.path.getsize(video_path) if video_path and os.path.exists(video_path) else 0
            
            # Reload fresh metadata to retain fields written by the pipeline (e.g. storyboard)
            fresh_metadata = await self.persistence.load_task_metadata(task_id)
            if fresh_metadata:
                metadata = fresh_metadata

            metadata["status"] = TaskStatus.COMPLETED
            metadata["completed_at"] = now_iso
            metadata["result"] = {
                "video_path": str(video_path),
                "duration": duration,
                "n_frames": n_frames,
                "file_size": file_size,
            }
            new_exec_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            metadata.setdefault("executions", []).append({
                "execution_id": new_exec_id,
                "created_at": now_iso,
                "status": "completed",
                "video_path": str(video_path),
                "duration": duration,
                "n_frames": n_frames,
                "file_size": file_size,
            })
            await self.persistence.save_task_metadata(task_id, metadata)
            logger.info(f"Task {task_id} generated successfully: {video_path}")
            return Task.from_metadata_dict(metadata)
            
        except Exception as e:
            logger.error(f"Task {task_id} generation failed: {e}")
            fresh_metadata = await self.persistence.load_task_metadata(task_id)
            if fresh_metadata:
                metadata = fresh_metadata
            metadata["status"] = TaskStatus.FAILED
            metadata.setdefault("metadata", {})["last_error"] = str(e)
            metadata.setdefault("executions", []).append({
                "execution_id": f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "created_at": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e),
            })
            await self.persistence.save_task_metadata(task_id, metadata)
            raise

    async def schedule_task(self, task_id: str, scheduled_at: str, priority: int = 0) -> Optional[Task]:
        """Schedule a task for future execution"""
        return await self.update_task_plan(
            task_id,
            scheduled_at=scheduled_at,
            priority=priority,
            status=TaskStatus.SCHEDULED,
        )

    async def cancel_task_schedule(self, task_id: str) -> Optional[Task]:
        """Cancel a scheduled or queued task"""
        return await self.update_task_plan(
            task_id,
            status=TaskStatus.CANCELLED,
        )

    async def retry_task(
        self,
        task_id: str,
        core: Optional[Any] = None,
        progress_callback: Optional[Any] = None,
    ) -> Task:
        """Retry or regenerate a task"""
        return await self.execute_task(task_id, core=core, progress_callback=progress_callback)
