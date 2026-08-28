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
Project and Task Data Models
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Project(BaseModel):
    """
    Project data model
    
    A project groups multiple generation tasks together.
    """
    project_id: str = Field(description="Unique project identifier")
    name: str = Field(description="Project name")
    description: Optional[str] = Field(default="", description="Project description")
    cover: Optional[str] = Field(default=None, description="Project cover image path or URL")
    tags: List[str] = Field(default_factory=list, description="Project tags")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Project-level default settings")
    template: Optional[Dict[str, Any]] = Field(default=None, description="Default generation configuration template for the project")
    created_at: str = Field(description="ISO timestamp of creation")
    updated_at: str = Field(description="ISO timestamp of last update")


class TaskStatus:
    """Standard unified task statuses"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    # Legacy alias
    PENDING = "pending"


class Task(BaseModel):
    """
    Task data model
    
    Represents a generation task that can optionally belong to a project.
    Can serve as a draft idea, a scheduled plan, or a container of generation executions.
    project_id is nullable to ensure backward compatibility with legacy tasks.
    """
    task_id: str = Field(description="Unique task identifier")
    project_id: Optional[str] = Field(default=None, description="Associated project ID, None for standalone tasks")
    status: str = Field(default=TaskStatus.DRAFT, description="Task status")
    title: Optional[str] = Field(default="", description="Task title")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp of creation")
    completed_at: Optional[str] = Field(default=None, description="ISO timestamp of completion")
    scheduled_at: Optional[str] = Field(default=None, description="ISO timestamp of scheduled execution")
    priority: int = Field(default=0, description="Execution priority (higher executes first)")
    input: Dict[str, Any] = Field(default_factory=dict, description="Task input parameters")
    config: Dict[str, Any] = Field(default_factory=dict, description="Configuration settings used")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Task execution results")
    executions: List[Dict[str, Any]] = Field(default_factory=list, description="Historical execution records")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional task metadata")

    @classmethod
    def from_metadata_dict(cls, data: Dict[str, Any]) -> "Task":
        """
        Build a Task instance from metadata dict (e.g. loaded from metadata.json).
        Extracts title from top-level or input.title gracefully.
        """
        raw = dict(data)
        task_id = raw.get("task_id", "")
        project_id = raw.get("project_id")
        status = raw.get("status", TaskStatus.DRAFT)
        
        # Try to resolve title
        title = raw.get("title")
        if not title:
            title = raw.get("input", {}).get("title", "")
        
        created_at = raw.get("created_at")
        completed_at = raw.get("completed_at")
        scheduled_at = raw.get("scheduled_at")
        priority = raw.get("priority", 0)
        executions = raw.get("executions", [])
        if not isinstance(executions, list):
            executions = []
            
        task_input = raw.get("input", {})
        task_config = raw.get("config", {})
        task_result = raw.get("result")
        
        # Extra metadata
        known_keys = {
            "task_id", "project_id", "status", "title", "created_at",
            "completed_at", "scheduled_at", "priority", "executions",
            "input", "config", "result", "metadata"
        }
        extra_metadata = raw.get("metadata", {})
        if not isinstance(extra_metadata, dict):
            extra_metadata = {}
        for k, v in raw.items():
            if k not in known_keys and k not in extra_metadata:
                extra_metadata[k] = v

        return cls(
            task_id=task_id,
            project_id=project_id,
            status=status,
            title=title,
            created_at=created_at,
            completed_at=completed_at,
            scheduled_at=scheduled_at,
            priority=priority,
            executions=executions,
            input=task_input,
            config=task_config,
            result=task_result,
            metadata=extra_metadata,
        )

    def to_metadata_dict(self) -> Dict[str, Any]:
        """Convert back to metadata dict for JSON persistence"""
        data = {
            "task_id": self.task_id,
            "project_id": self.project_id,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "scheduled_at": self.scheduled_at,
            "priority": self.priority,
            "executions": self.executions,
            "input": self.input,
            "config": self.config,
            "result": self.result,
        }
        data["title"] = self.title or ""
        if self.metadata:
            data["metadata"] = self.metadata
        return data
