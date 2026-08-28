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
Persistence Service

Handles task metadata and storyboard persistence to filesystem.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from trendlume.models.storyboard import (
    ContentMetadata,
    Storyboard,
    StoryboardConfig,
    StoryboardFrame,
)


class PersistenceService:
    """
    Task persistence service using filesystem (JSON)
    
    File structure:
        output/
        └── {task_id}/
            ├── metadata.json          # Task metadata (input, result, config)
            ├── storyboard.json        # Storyboard data (frames, prompts)
            ├── final.mp4
            └── frames/
                ├── 01_audio.mp3
                ├── 01_image.png
                └── ...
    
    Usage:
        persistence = PersistenceService()
        
        # Save metadata
        await persistence.save_task_metadata(task_id, metadata)
        
        # Save storyboard
        await persistence.save_storyboard(task_id, storyboard)
        
        # Load task
        metadata = await persistence.load_task_metadata(task_id)
        storyboard = await persistence.load_storyboard(task_id)
        
        # List all tasks
        tasks = await persistence.list_tasks(status="completed", limit=50)
    """
    
    def __init__(self, output_dir: str = "output"):
        """
        Initialize persistence service
        
        Args:
            output_dir: Base output directory (default: "output")
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Index file for fast listing
        self.index_file = self.output_dir / ".index.json"
        self._ensure_index()
    
    def get_task_dir(self, task_id: str) -> Path:
        """Get task directory path"""
        return self.output_dir / task_id
    
    def get_metadata_path(self, task_id: str) -> Path:
        """Get metadata.json path"""
        return self.get_task_dir(task_id) / "metadata.json"
    
    def get_storyboard_path(self, task_id: str) -> Path:
        """Get storyboard.json path"""
        return self.get_task_dir(task_id) / "storyboard.json"

    def get_task_final_video_path(self, task_id: str) -> Path:
        """Get final.mp4 path for a task"""
        return self.get_task_dir(task_id) / "final.mp4"
    
    def get_project_dir(self, project_id: str) -> Path:
        """Get project directory path"""
        return self.output_dir / "projects" / project_id

    def get_project_json_path(self, project_id: str) -> Path:
        """Get project.json path"""
        return self.get_project_dir(project_id) / "project.json"
    
    # ========================================================================
    # Metadata Operations
    # ========================================================================
    
    async def save_task_metadata(
        self,
        task_id: str,
        metadata: Dict[str, Any]
    ):
        """
        Save task metadata to filesystem
        
        Args:
            task_id: Task ID
            metadata: Metadata dict with structure:
                {
                    "task_id": str,
                    "created_at": str,
                    "completed_at": str (optional),
                    "status": str,
                    "input": dict,
                    "result": dict (optional),
                    "config": dict
                }
        """
        try:
            task_dir = self.get_task_dir(task_id)
            task_dir.mkdir(parents=True, exist_ok=True)
            
            metadata_path = self.get_metadata_path(task_id)
            
            # Ensure task_id is set
            metadata["task_id"] = task_id
            
            # Convert datetime objects to ISO format strings
            if "created_at" in metadata and isinstance(metadata["created_at"], datetime):
                metadata["created_at"] = metadata["created_at"].isoformat()
            if "completed_at" in metadata and isinstance(metadata["completed_at"], datetime):
                metadata["completed_at"] = metadata["completed_at"].isoformat()
            
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved task metadata: {task_id}")
            
            # Update index
            await self._update_index_for_task(task_id, metadata)
            
        except Exception as e:
            logger.error(f"Failed to save task metadata {task_id}: {e}")
            raise
    
    async def load_task_metadata(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Load task metadata from filesystem
        
        Args:
            task_id: Task ID
            
        Returns:
            Metadata dict or None if not found
        """
        try:
            metadata_path = self.get_metadata_path(task_id)
            
            if not metadata_path.exists():
                return None
            
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to load task metadata {task_id}: {e}")
            return None
    
    async def update_task_status(
        self,
        task_id: str,
        status: str,
        error: Optional[str] = None
    ):
        """
        Update task status in metadata
        
        Args:
            task_id: Task ID
            status: New status (pending, running, completed, failed, cancelled)
            error: Error message (optional, for failed status)
        """
        try:
            metadata = await self.load_task_metadata(task_id)
            if not metadata:
                logger.warning(f"Cannot update status: task {task_id} not found")
                return
            
            metadata["status"] = status
            
            if status in ["completed", "failed", "cancelled"]:
                metadata["completed_at"] = datetime.now().isoformat()
            
            if error:
                metadata["error"] = error
            
            await self.save_task_metadata(task_id, metadata)
            
        except Exception as e:
            logger.error(f"Failed to update task status {task_id}: {e}")
    
    # ========================================================================
    # Storyboard Operations
    # ========================================================================
    
    async def save_storyboard(
        self,
        task_id: str,
        storyboard: Storyboard
    ):
        """
        Save storyboard to filesystem
        
        Args:
            task_id: Task ID
            storyboard: Storyboard instance
        """
        try:
            task_dir = self.get_task_dir(task_id)
            task_dir.mkdir(parents=True, exist_ok=True)
            
            storyboard_path = self.get_storyboard_path(task_id)
            
            # Convert storyboard to dict
            storyboard_dict = self._storyboard_to_dict(storyboard)
            
            with open(storyboard_path, "w", encoding="utf-8") as f:
                json.dump(storyboard_dict, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved storyboard: {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to save storyboard {task_id}: {e}")
            raise
    
    async def load_storyboard(self, task_id: str) -> Optional[Storyboard]:
        """
        Load storyboard from filesystem
        
        Args:
            task_id: Task ID
            
        Returns:
            Storyboard instance or None if not found
        """
        try:
            storyboard_path = self.get_storyboard_path(task_id)
            
            if not storyboard_path.exists():
                return None
            
            with open(storyboard_path, "r", encoding="utf-8") as f:
                storyboard_dict = json.load(f)
            
            # Convert dict to storyboard
            storyboard = self._dict_to_storyboard(storyboard_dict)
            
            return storyboard
            
        except Exception as e:
            logger.error(f"Failed to load storyboard {task_id}: {e}")
            return None
    
    # ========================================================================
    # Task Listing & Querying
    # ========================================================================
    
    async def list_tasks(
        self,
        status: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List tasks with optional filtering
        
        Args:
            status: Filter by status (pending, running, completed, failed, cancelled)
            project_id: Filter by project_id (optional)
            limit: Maximum number of tasks to return
            offset: Number of tasks to skip
            
        Returns:
            List of metadata dicts, sorted by created_at descending
        """
        try:
            index = self._load_index()
            tasks = index.get("tasks", [])

            # Filter by status
            if status:
                tasks = [t for t in tasks if t.get("status") == status]

            # Filter by project_id
            if project_id is not None:
                tasks = [t for t in tasks if t.get("project_id") == project_id]

            # Sort by created_at descending
            tasks.sort(key=lambda t: t.get("created_at") or "", reverse=True)

            # Apply pagination
            return tasks[offset:offset + limit]

        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            return []
    
    async def task_exists(self, task_id: str) -> bool:
        """Check if task exists"""
        return self.get_task_dir(task_id).exists()

    # ========================================================================
    # Serialization Helpers
    # ========================================================================
    
    def _storyboard_to_dict(self, storyboard: Storyboard) -> Dict[str, Any]:
        """Convert Storyboard to dict for JSON serialization"""
        return {
            "title": storyboard.title,
            "config": self._config_to_dict(storyboard.config),
            "frames": [self._frame_to_dict(frame) for frame in storyboard.frames],
            "content_metadata": self._content_metadata_to_dict(storyboard.content_metadata) if storyboard.content_metadata else None,
            "final_video_path": storyboard.final_video_path,
            "total_duration": storyboard.total_duration,
            "created_at": storyboard.created_at.isoformat() if storyboard.created_at else None,
            "completed_at": storyboard.completed_at.isoformat() if storyboard.completed_at else None,
        }
    
    def _dict_to_storyboard(self, data: Dict[str, Any]) -> Storyboard:
        """Convert dict to Storyboard instance"""
        return Storyboard(
            title=data["title"],
            config=self._dict_to_config(data["config"]),
            frames=[self._dict_to_frame(frame_data) for frame_data in data["frames"]],
            content_metadata=self._dict_to_content_metadata(data["content_metadata"]) if data.get("content_metadata") else None,
            final_video_path=data.get("final_video_path"),
            total_duration=data.get("total_duration", 0.0),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )
    
    def _config_to_dict(self, config: StoryboardConfig) -> Dict[str, Any]:
        """Convert StoryboardConfig to dict"""
        return {
            "task_id": config.task_id,
            "n_storyboard": config.n_storyboard,
            "min_narration_words": config.min_narration_words,
            "max_narration_words": config.max_narration_words,
            "min_image_prompt_words": config.min_image_prompt_words,
            "max_image_prompt_words": config.max_image_prompt_words,
            "video_fps": config.video_fps,
            "tts_inference_mode": config.tts_inference_mode,
            "voice_id": config.voice_id,
            "tts_workflow": config.tts_workflow,
            "tts_speed": config.tts_speed,
            "ref_audio": config.ref_audio,
            "media_width": config.media_width,
            "media_height": config.media_height,
            "media_workflow": config.media_workflow,
            "frame_template": config.frame_template,
            "template_params": config.template_params,
        }
    
    def _dict_to_config(self, data: Dict[str, Any]) -> StoryboardConfig:
        """Convert dict to StoryboardConfig"""
        return StoryboardConfig(
            task_id=data.get("task_id"),
            n_storyboard=data.get("n_storyboard", 5),
            min_narration_words=data.get("min_narration_words", 5),
            max_narration_words=data.get("max_narration_words", 20),
            min_image_prompt_words=data.get("min_image_prompt_words", 30),
            max_image_prompt_words=data.get("max_image_prompt_words", 60),
            video_fps=data.get("video_fps", 30),
            tts_inference_mode=data.get("tts_inference_mode", "local"),
            voice_id=data.get("voice_id"),
            tts_workflow=data.get("tts_workflow"),
            tts_speed=data.get("tts_speed"),
            ref_audio=data.get("ref_audio"),
            media_width=data.get("media_width", data.get("image_width", 1024)),  # Backward compatibility
            media_height=data.get("media_height", data.get("image_height", 1024)),  # Backward compatibility
            media_workflow=data.get("media_workflow", data.get("image_workflow")),  # Backward compatibility
            frame_template=data.get("frame_template", "1080x1920/default.html"),
            template_params=data.get("template_params"),
        )
    
    def _frame_to_dict(self, frame: StoryboardFrame) -> Dict[str, Any]:
        """Convert StoryboardFrame to dict"""
        return {
            "index": frame.index,
            "narration": frame.narration,
            "image_prompt": frame.image_prompt,
            "audio_path": frame.audio_path,
            "media_type": frame.media_type,
            "image_path": frame.image_path,
            "video_path": frame.video_path,
            "composed_image_path": frame.composed_image_path,
            "video_segment_path": frame.video_segment_path,
            "duration": frame.duration,
            "created_at": frame.created_at.isoformat() if frame.created_at else None,
        }
    
    def _dict_to_frame(self, data: Dict[str, Any]) -> StoryboardFrame:
        """Convert dict to StoryboardFrame"""
        return StoryboardFrame(
            index=data["index"],
            narration=data["narration"],
            image_prompt=data["image_prompt"],
            audio_path=data.get("audio_path"),
            media_type=data.get("media_type"),
            image_path=data.get("image_path"),
            video_path=data.get("video_path"),
            composed_image_path=data.get("composed_image_path"),
            video_segment_path=data.get("video_segment_path"),
            duration=data.get("duration", 0.0),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
        )
    
    def _content_metadata_to_dict(self, metadata: ContentMetadata) -> Dict[str, Any]:
        """Convert ContentMetadata to dict"""
        return {
            "title": metadata.title,
            "author": metadata.author,
            "subtitle": metadata.subtitle,
            "genre": metadata.genre,
            "summary": metadata.summary,
            "publication_year": metadata.publication_year,
            "cover_url": metadata.cover_url,
        }
    
    def _dict_to_content_metadata(self, data: Dict[str, Any]) -> ContentMetadata:
        """Convert dict to ContentMetadata"""
        return ContentMetadata(
            title=data["title"],
            author=data.get("author"),
            subtitle=data.get("subtitle"),
            genre=data.get("genre"),
            summary=data.get("summary"),
            publication_year=data.get("publication_year"),
            cover_url=data.get("cover_url"),
        )
    
    # ========================================================================
    # Index Management (for fast listing)
    # ========================================================================
    
    def _ensure_index(self):
        """Ensure index file exists, create if not"""
        if not self.index_file.exists():
            self._save_index({"version": "1.0", "tasks": []})
    
    def _load_index(self) -> Dict[str, Any]:
        """Load index from file"""
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            return {"version": "1.0", "tasks": []}
    
    def _save_index(self, index_data: Dict[str, Any]):
        """Save index to file"""
        try:
            index_data["last_updated"] = datetime.now().isoformat()
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
    
    async def _resolve_task_title(self, task_id: str, metadata: Dict[str, Any]) -> str:
        """Resolve display title from metadata, storyboard, or input text."""
        title = metadata.get("title")
        inp = metadata.get("input") or {}
        if not title:
            title = inp.get("title")
        if not title or title == "":
            storyboard = await self.load_storyboard(task_id)
            if storyboard and storyboard.title:
                title = storyboard.title
            else:
                input_text = inp.get("text", "")
                if input_text:
                    title = input_text[:30] + ("..." if len(input_text) > 30 else "")
                else:
                    title = "Untitled"
        return title

    def _build_index_entry(self, task_id: str, metadata: Dict[str, Any], title: str) -> Dict[str, Any]:
        """Build a standardised index entry dict from task metadata."""
        res = metadata.get("result") or {}
        return {
            "task_id": task_id,
            "project_id": metadata.get("project_id"),
            "created_at": metadata.get("created_at"),
            "completed_at": metadata.get("completed_at"),
            "scheduled_at": metadata.get("scheduled_at"),
            "priority": metadata.get("priority", 0),
            "status": metadata.get("status", "unknown"),
            "title": title,
            "duration": res.get("duration", 0),
            "n_frames": res.get("n_frames", 0),
            "file_size": res.get("file_size", 0),
            "video_path": res.get("video_path"),
        }

    async def _update_index_for_task(self, task_id: str, metadata: Dict[str, Any]):
        """Update index entry for a specific task"""
        index = self._load_index()
        
        title = await self._resolve_task_title(task_id, metadata)
        index_entry = self._build_index_entry(task_id, metadata, title)
        
        # Update or append
        tasks = index.get("tasks", [])
        existing_idx = next((i for i, t in enumerate(tasks) if t["task_id"] == task_id), None)
        
        if existing_idx is not None:
            tasks[existing_idx] = index_entry
        else:
            tasks.append(index_entry)
        
        index["tasks"] = tasks
        self._save_index(index)
    
    async def rebuild_index(self):
        """Rebuild index by scanning all task directories"""
        logger.info("Rebuilding task index...")
        index = {"version": "1.0", "tasks": []}
        
        # Scan all directories
        for task_dir in self.output_dir.iterdir():
            if not task_dir.is_dir() or task_dir.name.startswith(".") or task_dir.name == "projects":
                continue
            
            task_id = task_dir.name
            metadata = await self.load_task_metadata(task_id)
            
            if metadata:
                title = await self._resolve_task_title(task_id, metadata)
                index["tasks"].append(self._build_index_entry(task_id, metadata, title))
        
        self._save_index(index)
        logger.info(f"Index rebuilt: {len(index['tasks'])} tasks")
    
    # ========================================================================
    # Paginated Listing
    # ========================================================================
    
    async def list_tasks_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        project_id: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """
        List tasks with pagination
        
        Args:
            page: Page number (1-based)
            page_size: Number of items per page
            status: Filter by status (optional)
            project_id: Filter by project_id (optional)
            sort_by: Sort field (created_at, completed_at, scheduled_at, priority, title, duration)
            sort_order: Sort order (asc, desc)
        
        Returns:
            {
                "tasks": [...],          # List of task summaries
                "total": 100,            # Total matching tasks
                "page": 1,               # Current page
                "page_size": 20,         # Items per page
                "total_pages": 5         # Total pages
            }
        """
        index = self._load_index()
        tasks = index.get("tasks", [])
        
        # Filter by status
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        
        # Filter by project_id
        if project_id is not None:
            tasks = [t for t in tasks if t.get("project_id") == project_id]
        
        # Sort
        reverse = (sort_order == "desc")
        if sort_by in ["created_at", "completed_at", "scheduled_at"]:
            tasks.sort(
                key=lambda t: datetime.fromisoformat(t.get(sort_by) or "1970-01-01T00:00:00"),
                reverse=reverse
            )
        elif sort_by == "priority":
            tasks.sort(key=lambda t: t.get("priority", 0), reverse=reverse)
        elif sort_by in ["title", "duration", "n_frames"]:
            tasks.sort(key=lambda t: str(t.get(sort_by) or ""), reverse=reverse)
        
        # Paginate
        total = len(tasks)
        total_pages = (total + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_tasks = tasks[start_idx:end_idx]
        
        return {
            "tasks": page_tasks,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    
    # ========================================================================
    # Statistics
    # ========================================================================
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about all tasks
        
        Returns:
            {
                "total_tasks": 100,
                "completed": 95,
                "failed": 5,
                "total_duration": 3600.5,  # seconds
                "total_size": 1024000000,  # bytes
            }
        """
        index = self._load_index()
        tasks = index.get("tasks", [])
        
        stats = {
            "total_tasks": len(tasks),
            "completed": len([t for t in tasks if t.get("status") == "completed"]),
            "failed": len([t for t in tasks if t.get("status") == "failed"]),
            "total_duration": sum(t.get("duration", 0) for t in tasks),
            "total_size": sum(t.get("file_size", 0) for t in tasks),
        }
        
        return stats
    
    # ========================================================================
    # Delete Task
    # ========================================================================
    
    async def delete_task(self, task_id: str) -> bool:
        """
        Delete a task and all its files
        
        Args:
            task_id: Task ID to delete
        
        Returns:
            True if successful, False otherwise
        """
        try:
            import shutil
            
            task_dir = self.get_task_dir(task_id)
            if task_dir.exists():
                shutil.rmtree(task_dir)
                logger.info(f"Deleted task directory: {task_dir}")
            
            # Update index
            index = self._load_index()
            tasks = index.get("tasks", [])
            tasks = [t for t in tasks if t["task_id"] != task_id]
            index["tasks"] = tasks
            self._save_index(index)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete task {task_id}: {e}")
            return False

    # ========================================================================
    # Project Operations
    # ========================================================================

    async def save_project(self, project_data: Dict[str, Any]) -> None:
        """
        Save project data to filesystem (output/projects/{project_id}/project.json)
        
        Args:
            project_data: Project dictionary containing project_id, name, etc.
        """
        try:
            project_id = project_data.get("project_id")
            if not project_id:
                raise ValueError("project_id is required to save project")
            
            project_dir = self.get_project_dir(project_id)
            project_dir.mkdir(parents=True, exist_ok=True)
            
            project_path = self.get_project_json_path(project_id)
            with open(project_path, "w", encoding="utf-8") as f:
                json.dump(project_data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved project: {project_id}")
        except Exception as e:
            logger.error(f"Failed to save project {project_data.get('project_id')}: {e}")
            raise

    async def load_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Load project data from filesystem
        
        Args:
            project_id: Project ID
            
        Returns:
            Project dict or None if not found
        """
        try:
            project_path = self.get_project_json_path(project_id)
            if not project_path.exists():
                return None
            
            with open(project_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load project {project_id}: {e}")
            return None

    async def list_projects(self) -> List[Dict[str, Any]]:
        """
        List all projects from filesystem
        
        Returns:
            List of project dicts, sorted by created_at descending
        """
        projects_dir = self.output_dir / "projects"
        if not projects_dir.exists():
            return []
        
        projects = []
        for p_dir in projects_dir.iterdir():
            if not p_dir.is_dir() or p_dir.name.startswith("."):
                continue
            project_file = p_dir / "project.json"
            if project_file.exists():
                try:
                    with open(project_file, "r", encoding="utf-8") as f:
                        projects.append(json.load(f))
                except Exception as e:
                    logger.warning(f"Failed to read project at {project_file}: {e}")
        
        projects.sort(key=lambda p: p.get("created_at", ""), reverse=True)
        return projects

    async def delete_project(self, project_id: str) -> bool:
        """
        Delete project directory (output/projects/{project_id})
        
        Args:
            project_id: Project ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import shutil
            project_dir = self.get_project_dir(project_id)
            if project_dir.exists():
                shutil.rmtree(project_dir)
                logger.info(f"Deleted project directory: {project_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete project {project_id}: {e}")
            return False

