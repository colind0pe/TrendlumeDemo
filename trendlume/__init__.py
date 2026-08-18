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
Trendlume - AI-powered video generator

Convention-based system with unified configuration management.

Usage:
    from trendlume import trendlume
    
    # Initialize
    await trendlume.initialize()
    
    # Use capabilities
    answer = await trendlume.llm("Explain atomic habits")
    audio = await trendlume.tts("Hello world")
    
    # Generate video with different pipelines
    # Standard pipeline (default)
    result = await trendlume.generate_video(
        text="如何提高学习效率",
        n_scenes=5
    )
    
    # Custom pipeline (template for your own logic)
    result = await trendlume.generate_video(
        text=your_content,
        pipeline="custom",
        custom_param_example="custom_value"
    )
    
    # Check available pipelines
    print(trendlume.pipelines.keys())  # dict_keys(['standard', 'custom'])
"""

from trendlume.service import TrendlumeCore, trendlume
from trendlume.config import config_manager

__version__ = "0.2.0"

__all__ = ["TrendlumeCore", "trendlume", "config_manager"]
