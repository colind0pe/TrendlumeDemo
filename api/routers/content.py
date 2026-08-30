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
Content generation endpoints

Endpoints for generating narrations, image prompts, and titles.
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.dependencies import TrendlumeDep
from api.schemas.content import (
    NarrationGenerateRequest,
    NarrationGenerateResponse,
    ImagePromptGenerateRequest,
    ImagePromptGenerateResponse,
    VideoPromptGenerateRequest,
    VideoPromptGenerateResponse,
    TitleGenerateRequest,
    TitleGenerateResponse,
)
from trendlume.utils.content_generators import (
    generate_narrations_from_topic,
    generate_image_prompts,
    generate_video_prompts,
    generate_title,
)

router = APIRouter(prefix="/content", tags=["Content Generation"])


@router.post("/narration", response_model=NarrationGenerateResponse)
async def generate_narration(
    request: NarrationGenerateRequest,
    trendlume: TrendlumeDep
):
    """
    Generate narrations from text
    
    Uses LLM to break down text into multiple narration segments with golden hooks, multi-genre support,
    video title, and unified publishing platform metadata.
    
    - **text**: Source text
    - **n_scenes**: Number of narrations to generate
    - **min_words**: Minimum words per narration
    - **max_words**: Maximum words per narration
    - **genre**: Track/genre style
    - **hook_type**: Golden hook strategy
    - **custom_prompt**: Additional user guidance
    - **title**: Optional user-specified title
    - **target_platform**: Target platform (default: 'douyin')
    
    Returns list of narration strings, video title, and publishing metadata.
    """
    try:
        logger.info(f"Generating {request.n_scenes} narrations from text (genre={request.genre}, hook={request.hook_type}, platform={request.target_platform})")
        
        bundle = await generate_narrations_from_topic(
            llm_service=trendlume.llm,
            topic=request.text,
            n_scenes=request.n_scenes,
            min_words=request.min_words,
            max_words=request.max_words,
            genre=request.genre,
            hook_type=request.hook_type,
            custom_prompt=request.custom_prompt,
            research_service=getattr(trendlume, "research", None),
            enable_research=request.enable_research,
            title=request.title,
            target_platform=request.target_platform or "douyin",
            return_full=True,
        )
        
        return NarrationGenerateResponse(
            narrations=bundle.narrations,
            title=bundle.title or None,
            metadata=bundle.metadata,
        )
        
    except Exception as e:
        logger.error(f"Narration generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/image-prompt", response_model=ImagePromptGenerateResponse)
async def generate_image_prompt(
    request: ImagePromptGenerateRequest,
    trendlume: TrendlumeDep
):
    """
    Generate image prompts from narrations
    
    Uses LLM to create detailed image generation prompts with shot types and aesthetic presets.
    
    - **narrations**: List of narration texts
    - **min_words**: Minimum words per prompt
    - **max_words**: Maximum words per prompt
    - **style_preset**: Image style preset key
    - **custom_style_prefix**: Custom style prompt prefix
    
    Returns list of image prompts.
    """
    try:
        logger.info(f"Generating image prompts for {len(request.narrations)} narrations (style={request.style_preset})")
        
        image_prompts = await generate_image_prompts(
            llm_service=trendlume.llm,
            narrations=request.narrations,
            min_words=request.min_words,
            max_words=request.max_words,
            style_preset=request.style_preset,
            custom_style_prefix=request.custom_style_prefix,
        )
        
        return ImagePromptGenerateResponse(image_prompts=image_prompts)
        
    except Exception as e:
        logger.error(f"Image prompt generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/video-prompt", response_model=VideoPromptGenerateResponse)
async def generate_video_prompt(
    request: VideoPromptGenerateRequest,
    trendlume: TrendlumeDep
):
    """
    Generate video prompts from narrations
    
    Uses LLM to create dynamic video generation prompts with camera motions and dynamic physics.
    
    - **narrations**: List of narration texts
    - **min_words**: Minimum words per prompt
    - **max_words**: Maximum words per prompt
    - **custom_style_prefix**: Custom style prompt prefix
    
    Returns list of video prompts.
    """
    try:
        logger.info(f"Generating video prompts for {len(request.narrations)} narrations")
        
        video_prompts = await generate_video_prompts(
            llm_service=trendlume.llm,
            narrations=request.narrations,
            min_words=request.min_words,
            max_words=request.max_words,
            custom_style_prefix=request.custom_style_prefix,
        )
        
        return VideoPromptGenerateResponse(video_prompts=video_prompts)
        
    except Exception as e:
        logger.error(f"Video prompt generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/title", response_model=TitleGenerateResponse)
async def generate_title_endpoint(
    request: TitleGenerateRequest,
    trendlume: TrendlumeDep
):
    """
    Generate video title from text
    
    Uses LLM to create an engaging title.
    
    - **text**: Source text
    - **style**: Optional title style hint
    
    Returns generated title.
    """
    try:
        logger.info("Generating title from text")
        
        title = await generate_title(
            llm_service=trendlume.llm,
            content=request.text,
            strategy="llm"
        )
        
        return TitleGenerateResponse(title=title)
        
    except Exception as e:
        logger.error(f"Title generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
