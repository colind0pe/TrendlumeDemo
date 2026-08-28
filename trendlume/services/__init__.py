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
Trendlume Services

Core services providing atomic capabilities.

Services:
- LLMService: LLM text generation
- TTSService: Text-to-speech
- MediaService: Media generation (image & video)
- VideoService: Video processing
- FrameProcessor: Frame processing orchestrator
- PersistenceService: Task metadata and storyboard persistence
- TaskManager: Individual task operations
- ProjectManager: Project lifecycle and task-project relationships
- HistoryManager: Legacy compatibility layer (subclass of TaskManager)
- HistoryMigrationService: Legacy history to project migration
- TaskScheduler: Lightweight scheduled task execution
- ComfyBaseService: Base class for ComfyUI-based services
"""

from trendlume.services.comfy_base_service import ComfyBaseService
from trendlume.services.llm_service import LLMService
from trendlume.services.tts_service import TTSService
from trendlume.services.media import MediaService
from trendlume.services.video import VideoService
from trendlume.services.frame_processor import FrameProcessor
from trendlume.services.persistence import PersistenceService
from trendlume.services.task_manager import TaskManager
from trendlume.services.history_manager import HistoryManager
from trendlume.services.project_manager import ProjectManager
from trendlume.services.history_migration import HistoryMigrationService, MigrationResult
from trendlume.services.task_scheduler import TaskScheduler

# Backward compatibility alias
ImageService = MediaService

__all__ = [
    "ComfyBaseService",
    "LLMService",
    "TTSService",
    "MediaService",
    "ImageService",  # Backward compatibility
    "VideoService",
    "FrameProcessor",
    "PersistenceService",
    "TaskManager",
    "HistoryManager",  # Legacy compatibility
    "ProjectManager",
    "HistoryMigrationService",
    "MigrationResult",
    "TaskScheduler",
]

