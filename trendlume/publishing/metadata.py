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
Platform Metadata Generator

Uses LLM structured output to generate platform-specific publishing metadata
(e.g., Douyin title <= 30 chars, description, hashtags, declarations)
strictly based on the final generated script/narrations.
"""

from typing import Any, Dict, List, Optional, Type, Union

from loguru import logger

from trendlume.models.metadata import BasePlatformMetadata, DouyinDeclaration, DouyinMetadata
from trendlume.services.llm_service import LLMService

DOUYIN_METADATA_PROMPT_TEMPLATE = """# Role & Task
You are a viral social media growth expert specializing in short-form video platforms (Douyin / 抖音).
Your task is to generate high-retention, high-converting Douyin platform publishing metadata based on the provided video script and title.

# Video Content
Title: {title}
Script / Narrations:
{script}

{custom_instructions}

# Douyin Publishing Requirements
1. **Title (title)**:
   - MUST be catchy, suspenseful, or emotionally resonant (爆款短视频标题).
   - MUST NOT exceed 30 characters in total (严格限制在 30 个汉字/字符以内).
   - DO NOT include punctuation marks at the end of the title.
2. **Description (description)**:
   - Engaging caption summarizing the key takeaway or curiosity hook (1-3 punchy sentences).
   - End with an engaging interactive question or call to follow/like (引导评论点赞互动).
3. **Hashtags (tags)**:
   - Provide 3-8 relevant, high-traffic topic tags (e.g. "认知思维", "干货分享", "知识科普").
   - Output clean tag names without the '#' symbol.
4. **Self Declaration (declaration)**:
   - Select the most appropriate declaration: "内容由AI生成", "个人观点，仅供参考", "内容为个人观点或见解", "内容取材网络". Default is "内容由AI生成".
5. **Visibility (visibility)**:
   - "public"

You must output structured data strictly matching the requested schema.
"""


class PlatformMetadataGenerator:
    """
    Platform Metadata Generator
    
    Coordinates platform-specific metadata schema validation and LLM generation.
    """

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service
        self._schema_registry: Dict[str, Type[BasePlatformMetadata]] = {
            "douyin": DouyinMetadata,
        }

    def get_schema(self, platform: str) -> Type[BasePlatformMetadata]:
        """Get registered schema class for platform, fallback to BasePlatformMetadata"""
        return self._schema_registry.get(platform.lower().strip(), BasePlatformMetadata)

    async def generate_metadata(
        self,
        platform: str,
        script: Union[str, List[str]],
        title: Optional[str] = None,
        custom_instructions: Optional[str] = "",
        cover: Optional[str] = None,
        **kwargs,
    ) -> BasePlatformMetadata:
        """
        Generate platform-tailored metadata from final script content using structured LLM.
        
        Args:
            platform: Target platform identifier (e.g. 'douyin')
            script: Full script string or list of scene narration strings
            title: Determined video title (optional)
            custom_instructions: Extra instructions for LLM (optional)
            cover: Cover image path or URL (optional)
            
        Returns:
            Validated platform metadata instance (e.g. DouyinMetadata)
        """
        plat_key = platform.lower().strip()
        schema_cls = self.get_schema(plat_key)

        # Normalize script text
        if isinstance(script, list):
            script_text = "\n".join(f"- {s}" for s in script if s)
        else:
            script_text = str(script or "")

        resolved_title = title or (script_text[:20] if script_text else "未命名视频")
        extra_note = f"Custom Instructions:\n{custom_instructions}" if custom_instructions else ""

        # Build prompt
        prompt = DOUYIN_METADATA_PROMPT_TEMPLATE.format(
            title=resolved_title,
            script=script_text[:1500],  # Bound context length
            custom_instructions=extra_note,
        )

        try:
            logger.info(f"Generating platform metadata for '{plat_key}' using LLM structured output...")
            result = await self.llm(
                prompt=prompt,
                response_type=schema_cls,
                temperature=0.7,
                **kwargs,
            )

            if isinstance(result, BasePlatformMetadata):
                if cover and not result.cover:
                    result.cover = cover
                logger.info(
                    f"Successfully generated metadata for '{plat_key}': title='{result.title}', tags={result.tags}"
                )
                return result
            else:
                logger.warning(f"LLM returned unexpected type {type(result)}, building fallback model")
                return self._build_fallback(plat_key, resolved_title, script_text, cover=cover)

        except Exception as e:
            logger.warning(f"Failed to generate structured metadata via LLM ({e}), using safe fallback metadata")
            return self._build_fallback(plat_key, resolved_title, script_text, cover=cover)

    def normalize_metadata(
        self,
        platform: str,
        metadata_dict: Optional[Dict[str, Any]],
        fallback_title: str = "",
        fallback_script: str = "",
        cover: Optional[str] = None,
    ) -> BasePlatformMetadata:
        """
        Validate and normalize a metadata dictionary (e.g. from unified copywriting generation)
        into a validated BasePlatformMetadata instance. Falls back cleanly if dict is invalid/empty.
        """
        plat_key = platform.lower().strip()
        schema_cls = self.get_schema(plat_key)

        if not metadata_dict or not isinstance(metadata_dict, dict):
            return self._build_fallback(plat_key, fallback_title, fallback_script, cover=cover)

        try:
            data = dict(metadata_dict)
            if not data.get("title") and fallback_title:
                data["title"] = fallback_title[:30]
            if cover and not data.get("cover"):
                data["cover"] = cover
            validated = schema_cls.model_validate(data)
            return validated
        except Exception as e:
            logger.warning(f"Metadata dictionary validation failed for '{plat_key}' ({e}), using fallback")
            return self._build_fallback(plat_key, fallback_title, fallback_script, cover=cover)

    def _build_fallback(
        self,
        platform: str,
        title: str,
        script: str,
        cover: Optional[str] = None,
    ) -> BasePlatformMetadata:
        """Create a safe, deterministic metadata instance when LLM is unavailable"""
        clean_title = (title or "短视频分享").strip()
        if platform == "douyin":
            clean_title = clean_title[:30]
            clean_desc = (script[:100] + "...") if len(script) > 100 else script
            return DouyinMetadata(
                title=clean_title,
                description=clean_desc,
                tags=["短视频", "AI视频", "知识分享"],
                declaration=DouyinDeclaration.DEFAULT,
                visibility="public",
                allow_download=True,
                cover=cover,
            )
        else:
            return BasePlatformMetadata(
                title=clean_title,
                description=script[:200] if script else "",
                tags=["视频分享"],
                cover=cover,
            )

