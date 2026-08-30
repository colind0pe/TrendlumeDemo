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
Content generation API schemas
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Narration Generation
# ============================================================================

class NarrationGenerateRequest(BaseModel):
    """Narration generation request"""
    text: str = Field(..., description="Source text to generate narrations from")
    n_scenes: int = Field(5, ge=1, le=20, description="Number of scenes")
    min_words: int = Field(5, ge=1, le=100, description="Minimum words per narration")
    max_words: int = Field(20, ge=1, le=200, description="Maximum words per narration")
    genre: str = Field("auto", description="Track/genre style (default: 'auto' for intelligent autonomous matching, or 'science_tech', 'business_wealth', etc.)")
    hook_type: Optional[str] = Field(None, description="Golden hook strategy override (e.g., 'bold_claim', 'curiosity_gap', 'mistake_warning', 'story_twist', 'pain_point')")
    custom_prompt: str = Field("", description="Additional user guidance or specific prompt requirements")
    enable_research: Optional[bool] = Field(None, description="Optional override to enable/disable web research")
    title: Optional[str] = Field(None, description="Optional user-specified video title")
    target_platform: Optional[str] = Field("douyin", description="Target social platform for metadata (e.g. 'douyin')")
    
    model_config = {"json_schema_extra": {"example": {
        "text": "Atomic Habits is about making small changes that lead to remarkable results.",
        "n_scenes": 5, "min_words": 5, "max_words": 20,
        "genre": "auto", "hook_type": None, "custom_prompt": "", "enable_research": False,
        "title": "The Power of Atomic Habits", "target_platform": "douyin",
    }}}


class NarrationGenerateResponse(BaseModel):
    """Narration generation response"""
    success: bool = True
    message: str = "Success"
    narrations: List[str] = Field(..., description="Generated narrations")
    title: Optional[str] = Field(None, description="Generated or resolved video title")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Generated platform publishing metadata")


# ============================================================================
# Image Prompt Generation
# ============================================================================

class ImagePromptGenerateRequest(BaseModel):
    """Image prompt generation request"""
    narrations: List[str] = Field(..., description="List of narrations")
    min_words: int = Field(30, ge=10, le=100, description="Minimum words per prompt")
    max_words: int = Field(60, ge=10, le=200, description="Maximum words per prompt")
    style_preset: Optional[str] = Field(None, description="Image style preset (e.g., 'stick_figure', 'cinematic_real', 'chinese_ink', '3d_animation')")
    custom_style_prefix: str = Field("", description="Custom style prompt prefix")
    
    model_config = {"json_schema_extra": {"example": {
        "narrations": ["Small habits compound over time", "Focus on systems, not goals"],
        "min_words": 30, "max_words": 60,
        "style_preset": "stick_figure", "custom_style_prefix": "",
    }}}


class ImagePromptGenerateResponse(BaseModel):
    """Image prompt generation response"""
    success: bool = True
    message: str = "Success"
    image_prompts: List[str] = Field(..., description="Generated image prompts")


# ============================================================================
# Video Prompt Generation
# ============================================================================

class VideoPromptGenerateRequest(BaseModel):
    """Video prompt generation request"""
    narrations: List[str] = Field(..., description="List of narrations")
    min_words: int = Field(30, ge=10, le=100, description="Minimum words per prompt")
    max_words: int = Field(60, ge=10, le=200, description="Maximum words per prompt")
    custom_style_prefix: str = Field("", description="Custom style / camera motion prefix")
    
    model_config = {"json_schema_extra": {"example": {
        "narrations": ["Small habits compound over time", "Focus on systems, not goals"],
        "min_words": 30, "max_words": 60, "custom_style_prefix": "",
    }}}


class VideoPromptGenerateResponse(BaseModel):
    """Video prompt generation response"""
    success: bool = True
    message: str = "Success"
    video_prompts: List[str] = Field(..., description="Generated video prompts")


# ============================================================================
# Title Generation
# ============================================================================

class TitleGenerateRequest(BaseModel):
    """Title generation request"""
    text: str = Field(..., description="Source text")
    style: Optional[str] = Field(None, description="Title style (e.g., 'engaging', 'formal')")
    
    model_config = {"json_schema_extra": {"example": {
        "text": "Atomic Habits is about making small changes that lead to remarkable results.",
        "style": "engaging",
    }}}


class TitleGenerateResponse(BaseModel):
    """Title generation response"""
    success: bool = True
    message: str = "Success"
    title: str = Field(..., description="Generated title")
