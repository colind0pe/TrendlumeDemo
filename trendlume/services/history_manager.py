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
History Manager Service (Legacy Compatibility Layer)

DEPRECATED: This service is maintained strictly for backward compatibility.
New code and UI workflows must use `TaskManager` and `ProjectManager`.
"""

from typing import Optional

from loguru import logger

from trendlume.services.persistence import PersistenceService
from trendlume.services.task_manager import TaskManager


class HistoryManager(TaskManager):
    """
    Legacy History Compatibility Layer
    
    Inherits from TaskManager to provide full backward compatibility for any
    external scripts, plugins, or legacy tests.
    """
    
    def __init__(self, persistence: PersistenceService):
        """
        Initialize history manager (Legacy Compatibility)
        
        Args:
            persistence: PersistenceService instance
        """
        super().__init__(persistence)
        logger.debug("HistoryManager initialized (Legacy Compatibility Layer)")

    # Legacy future stubs
    async def regenerate_frame(
        self,
        task_id: str,
        frame_index: int,
        **override_params
    ) -> Optional[str]:
        """Legacy stub for frame regeneration"""
        logger.warning("regenerate_frame is not implemented")
        return None

    async def export_task(self, task_id: str, export_path: str) -> Optional[str]:
        """Legacy stub for task packaging"""
        logger.warning("export_task is not implemented")
        return None
