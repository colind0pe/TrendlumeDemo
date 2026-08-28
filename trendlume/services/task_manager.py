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
Task Manager Service

Provides business logic for individual Task operations, decoupled from Projects.
Core service alongside ProjectManager and PersistenceService.
"""

from typing import Any, Dict, Optional

from loguru import logger

from trendlume.models.project import Task
from trendlume.services.persistence import PersistenceService


class TaskManager:
    """
    Task management service
    
    Provides business logic for:
    - Task retrieval and conversion to Task models
    - Detailed task inspection (metadata + storyboard)
    - Paginated listing and filtering
    - Task deletion (clean filesystem removal)
    - Task parameter duplication
    - Global task statistics
    """
    
    def __init__(self, persistence: PersistenceService):
        """
        Initialize task manager
        
        Args:
            persistence: PersistenceService instance
        """
        self.persistence = persistence

    async def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get a Task model by task_id
        
        Args:
            task_id: Task ID
            
        Returns:
            Task instance or None if not found
        """
        metadata = await self.persistence.load_task_metadata(task_id)
        if not metadata:
            return None
        return Task.from_metadata_dict(metadata)

    async def get_task_detail(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full task detail including storyboard
        
        Args:
            task_id: Task ID
        
        Returns:
            {
                "metadata": {...},      # Task metadata dict
                "storyboard": {...}     # Storyboard object (if available)
            }
            or None if task not found
        """
        metadata = await self.persistence.load_task_metadata(task_id)
        if not metadata:
            return None
        
        storyboard = await self.persistence.load_storyboard(task_id)
        return {
            "metadata": metadata,
            "storyboard": storyboard,
        }

    async def get_task_list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        project_id: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """
        Get paginated task list
        
        Args:
            page: Page number (1-indexed)
            page_size: Items per page
            status: Filter by status (optional)
            project_id: Filter by project ID (optional)
            sort_by: Sort field (created_at, completed_at, scheduled_at, priority, title, duration)
            sort_order: Sort order (asc, desc)
        
        Returns:
            {
                "tasks": [...],
                "total": int,
                "page": int,
                "page_size": int,
                "total_pages": int
            }
        """
        return await self.persistence.list_tasks_paginated(
            page=page,
            page_size=page_size,
            status=status,
            project_id=project_id,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    async def delete_task(self, task_id: str) -> bool:
        """
        Delete a task and all its associated files
        
        Args:
            task_id: Task ID to delete
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Deleting task: {task_id}")
        return await self.persistence.delete_task(task_id)

    async def duplicate_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Duplicate a task's input configuration parameters
        
        Args:
            task_id: Task ID to duplicate
        
        Returns:
            Input parameters dictionary or None if task not found
        """
        metadata = await self.persistence.load_task_metadata(task_id)
        if not metadata:
            logger.warning(f"Task {task_id} not found for duplication")
            return None
        
        input_params = metadata.get("input", {})
        logger.info(f"Duplicated task {task_id} parameters")
        return input_params

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about all tasks across the system
        
        Returns:
            Dict containing total_tasks, completed, failed, total_duration, total_size
        """
        return await self.persistence.get_statistics()

    async def rebuild_index(self) -> None:
        """Rebuild task index from filesystem"""
        await self.persistence.rebuild_index()
