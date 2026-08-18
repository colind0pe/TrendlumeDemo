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
FastAPI Dependencies

Provides dependency injection for TrendlumeCore and other services.
"""

from typing import Annotated
from fastapi import Depends
from loguru import logger

from trendlume.service import TrendlumeCore


# Global Trendlume instance
_trendlume_instance: TrendlumeCore = None


async def get_trendlume() -> TrendlumeCore:
    """
    Get Trendlume core instance (dependency injection)
    
    Returns:
        TrendlumeCore instance
    """
    global _trendlume_instance
    
    if _trendlume_instance is None:
        _trendlume_instance = TrendlumeCore()
        await _trendlume_instance.initialize()
        logger.info("✅ Trendlume initialized for API")
    
    return _trendlume_instance


async def shutdown_trendlume():
    """Shutdown Trendlume instance and cleanup resources"""
    global _trendlume_instance
    if _trendlume_instance:
        logger.info("Shutting down Trendlume...")
        await _trendlume_instance.cleanup()
        _trendlume_instance = None
    
    from trendlume.services.frame_html import HTMLFrameGenerator
    await HTMLFrameGenerator.close_browser()


# Type alias for dependency injection
TrendlumeDep = Annotated[TrendlumeCore, Depends(get_trendlume)]

