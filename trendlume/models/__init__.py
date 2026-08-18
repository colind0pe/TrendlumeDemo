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
Trendlume Data Models Package

Provides data structures for media results, progress tracking, and storyboards.
"""

from trendlume.models.media import MediaResult
from trendlume.models.progress import ProgressEvent
from trendlume.models.storyboard import (
    ContentMetadata,
    Storyboard,
    StoryboardConfig,
    StoryboardFrame,
    VideoGenerationResult,
)

__all__ = [
    "MediaResult",
    "ProgressEvent",
    "StoryboardConfig",
    "StoryboardFrame",
    "ContentMetadata",
    "Storyboard",
    "VideoGenerationResult",
]
