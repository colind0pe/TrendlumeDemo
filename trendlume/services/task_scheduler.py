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
Task Scheduler Service

Provides a lightweight, dependency-free scheduling abstraction:
- Detect due tasks (get_due_tasks)
- Execute due tasks (execute_due_task / run_pending)
- Background polling loop (start_polling / stop_polling)
"""

import asyncio
import sys
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from trendlume.models.project import Task, TaskStatus
from trendlume.services.persistence import PersistenceService
from trendlume.services.project_manager import ProjectManager


class TaskScheduler:
    """
    Lightweight task scheduler service.
    
    No external message broker (Celery/Redis/RabbitMQ) required.
    Operates directly on task metadata and persistence layer.
    """
    
    def __init__(
        self,
        persistence: PersistenceService,
        project_manager: ProjectManager,
        core: Optional[Any] = None,
    ):
        self.persistence = persistence
        self.project_manager = project_manager
        self.core = core
        self._polling_task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        self._stop_event = threading.Event()
        self._polling_thread: Optional[threading.Thread] = None

    async def get_due_tasks(
        self,
        project_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> List[Task]:
        """
        Get all tasks that are scheduled and due for execution.
        
        Args:
            project_id: Optional project filter
            now: Current reference datetime (defaults to datetime.now())
            
        Returns:
            List of Task instances ordered by priority (descending) and scheduled_at (ascending)
        """
        if now is None:
            now = datetime.now()
            
        index_tasks = await self.persistence.list_tasks(
            project_id=project_id,
            limit=10000,
        )
        
        due_tasks: List[Task] = []
        for t_summary in index_tasks:
            status = t_summary.get("status")
            if status not in [TaskStatus.SCHEDULED, TaskStatus.QUEUED]:
                continue
                
            task_id = t_summary["task_id"]
            metadata = await self.persistence.load_task_metadata(task_id)
            if not metadata:
                continue
                
            # If queued, it's immediately due
            if metadata.get("status") == TaskStatus.QUEUED:
                due_tasks.append(Task.from_metadata_dict(metadata))
                continue
                
            # If scheduled, check if scheduled_at <= now
            scheduled_at = metadata.get("scheduled_at")
            if not scheduled_at:
                continue
                
            try:
                sched_dt = datetime.fromisoformat(scheduled_at)
                if sched_dt <= now:
                    due_tasks.append(Task.from_metadata_dict(metadata))
            except Exception as e:
                logger.warning(f"Invalid scheduled_at timestamp on task {task_id}: {scheduled_at} ({e})")
                
        # Sort by priority desc, then scheduled_at asc
        due_tasks.sort(
            key=lambda t: (
                -t.priority,
                t.scheduled_at or "9999-12-31"
            )
        )
        return due_tasks

    async def execute_due_task(self, task_id: str) -> bool:
        """
        Execute a single due task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if execution succeeded, False otherwise
        """
        try:
            logger.info(f"Executing due task: {task_id}")
            task = await self.project_manager.execute_task(task_id, core=self.core)
            return task.status == TaskStatus.COMPLETED
        except Exception as e:
            logger.error(f"Failed to execute due task {task_id}: {e}")
            return False

    async def run_pending(self) -> List[Dict[str, Any]]:
        """
        Scan and execute all currently due tasks.
        
        Returns:
            List of results with task_id and success status
        """
        due_tasks = await self.get_due_tasks()
        results = []
        for task in due_tasks:
            success = await self.execute_due_task(task.task_id)
            results.append({"task_id": task.task_id, "success": success})
        return results

    def start_polling(self, interval_seconds: float = 30):
        """Start background polling loop for due tasks"""
        if self._is_running:
            logger.warning("Scheduler polling is already running")
            return
            
        self._is_running = True
        self._stop_event.clear()
        
        def _poll_thread():
            logger.info(f"TaskScheduler polling started (interval: {interval_seconds}s)")
            while self._is_running and not self._stop_event.is_set():
                try:
                    if sys.platform == "win32":
                        loop = asyncio.ProactorEventLoop()
                        try:
                            loop.run_until_complete(self.run_pending())
                        finally:
                            loop.close()
                    else:
                        asyncio.run(self.run_pending())
                except Exception as e:
                    logger.error(f"Error in scheduler poll loop: {e}")
                self._stop_event.wait(timeout=interval_seconds)
                
        self._polling_thread = threading.Thread(target=_poll_thread, daemon=True)
        self._polling_thread.start()

    def stop_polling(self):
        """Stop background polling loop"""
        self._is_running = False
        self._stop_event.set()
        if self._polling_thread and self._polling_thread.is_alive():
            self._polling_thread.join(timeout=2.0)
        self._polling_thread = None
        logger.info("TaskScheduler polling stopped")
