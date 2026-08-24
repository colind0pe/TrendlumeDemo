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
Content generation utility functions

Pure/stateless functions for generating content using LLM.
These functions are reusable across different pipelines.
"""

import json
import re
from typing import List, Optional, Literal, Any, Callable

from loguru import logger


_CODE_FENCE_RE = re.compile(
    r"^```[a-zA-Z0-9_-]*\r?\n([\s\S]*?)\r?\n```\s*$"
)


def _strip_code_fence(text: str) -> str:
    """
    Strip surrounding markdown code fence from an LLM response.
    Uses anchored regex to avoid matching nested code blocks.
    """
    t = (text or "").strip()
    m = _CODE_FENCE_RE.match(t)
    if m:
        return m.group(1).strip()
    return t


async def generate_title(
    llm_service,
    content: str,
    strategy: Literal["auto", "direct", "llm"] = "auto",
    max_length: int = 15
) -> str:
    """
    Generate title from content
    
    Args:
        llm_service: LLM service instance
        content: Source content (topic or script)
        strategy: Generation strategy
            - "auto": Auto-decide based on content length (default)
            - "direct": Use content directly (truncated if needed)
            - "llm": Always use LLM to generate title
        max_length: Maximum title length (default: 15)
    
    Returns:
        Generated title
    """
    if strategy == "direct":
        content = content.strip()
        return content[:max_length] if len(content) > max_length else content
    
    if strategy == "auto":
        if len(content.strip()) <= 15:
            return content.strip()
        # Fall through to LLM
    
    # Use LLM to generate title
    from trendlume.prompts import build_title_generation_prompt
    
    # Pass max_length to prompt so LLM knows the character limit
    prompt = build_title_generation_prompt(content, max_length=max_length)
    response = await llm_service(prompt, temperature=0.7, max_tokens=8192)
    
    # Clean up response
    title = response.strip()
    
    # Remove quotes if present
    if title.startswith('"') and title.endswith('"'):
        title = title[1:-1]
    if title.startswith("'") and title.endswith("'"):
        title = title[1:-1]
    
    # Remove trailing punctuation
    title = title.rstrip('.,!?;:\'"')
    
    # Safety: if still over limit, truncate smartly
    if len(title) > max_length:
        # Try to truncate at word boundary
        truncated = title[:max_length]
        last_space = truncated.rfind(' ')
        
        # Only use word boundary if it's not too far back (at least 60% of max_length)
        if last_space > max_length * 0.6:
            title = truncated[:last_space]
        else:
            title = truncated
        
        # Remove any trailing punctuation after truncation
        title = title.rstrip('.,!?;:\'"')
    
    logger.debug(f"Generated title: '{title}' (length: {len(title)})")
    return title


async def generate_narrations_from_topic(
    llm_service,
    topic: str,
    n_scenes: int = 5,
    min_words: int = 5,
    max_words: int = 20,
    genre: str = "auto",
    hook_type: Optional[str] = None,
    custom_prompt: str = "",
    custom_system_prompt: str = "",
    research_service: Optional[Any] = None,
    enable_research: Optional[bool] = None,
) -> List[str]:
    """
    Generate narrations from topic using LLM with 3-second golden hook, multi-genre support,
    and optional web research context.
    
    Args:
        llm_service: LLM service instance
        topic: Topic/theme to generate narrations from
        n_scenes: Number of narrations to generate
        min_words: Minimum narration length
        max_words: Maximum narration length
        genre: Track style ('general', 'science_tech', 'business_wealth', 'emotion_growth', 'culture_history', 'humor_meme', 'product_review')
        hook_type: Golden hook strategy ('bold_claim', 'curiosity_gap', 'mistake_warning', 'story_twist', 'pain_point')
        custom_prompt: Additional user guidance or specific requirements
        custom_system_prompt: Custom system role override
        research_service: Optional ResearchService instance (must be pre-created)
        enable_research: Optional override to enable/disable research (defaults to config)
    
    Returns:
        List of narration texts
    """
    from trendlume.prompts import build_topic_narration_prompt
    
    logger.info(f"Generating {n_scenes} narrations from topic: '{topic}' (genre={genre}, hook={hook_type})")
    
    # 1. Execute Web Research if a research_service was provided and enabled
    research_context_text = None
    if research_service is not None:
        try:
            if research_service.is_enabled(override=enable_research):
                logger.info(f"🔍 Performing web research for topic: '{topic}'")
                context = await research_service.conduct_research(
                    topic=topic,
                    llm_service=llm_service,
                    enable_override=enable_research,
                )
                if context and not context.is_empty:
                    research_context_text = context.formatted_text
                    logger.info(f"✅ Web research completed ({len(context.results)} sources found)")
                else:
                    logger.info("ℹ️ Web research completed with no additional context")
        except Exception as e:
            logger.warning(f"Research step failed, proceeding with standard generation: {e}")
            research_context_text = None


    # 2. Build prompt
    prompt = build_topic_narration_prompt(
        topic=topic,
        n_storyboard=n_scenes,
        min_words=min_words,
        max_words=max_words,
        genre=genre,
        hook_type=hook_type,
        custom_prompt=custom_prompt,
        custom_system_prompt=custom_system_prompt,
        research_context=research_context_text,
    )
    
    response = await llm_service(
        prompt=prompt,
        temperature=0.8,
        max_tokens=8192
    )
    
    logger.debug(f"LLM response: {response[:200]}...")
    
    # Parse JSON
    result = _parse_json(response)
    
    if "narrations" not in result:
        raise ValueError("Invalid response format: missing 'narrations' key")
    
    narrations = result["narrations"]
    
    # Validate count
    if len(narrations) > n_scenes:
        logger.warning(f"Got {len(narrations)} narrations, taking first {n_scenes}")
        narrations = narrations[:n_scenes]
    elif len(narrations) < n_scenes:
        raise ValueError(f"Expected {n_scenes} narrations, got only {len(narrations)}")
    
    logger.info(f"Generated {len(narrations)} narrations successfully")
    return narrations



async def generate_narrations_from_content(
    llm_service,
    content: str,
    n_scenes: int = 5,
    min_words: int = 5,
    max_words: int = 20,
    genre: str = "general",
    custom_prompt: str = "",
) -> List[str]:
    """
    Generate narrations from user-provided content using LLM with retention-optimized structuring.
    
    Args:
        llm_service: LLM service instance
        content: User-provided content
        n_scenes: Number of narrations to generate
        min_words: Minimum narration length
        max_words: Maximum narration length
        genre: Genre style hint (default: 'general')
        custom_prompt: Additional user guidance or specific requirements
    
    Returns:
        List of narration texts
    """
    from trendlume.prompts import build_content_narration_prompt
    
    logger.info(f"Generating {n_scenes} narrations from content ({len(content)} chars)")
    
    prompt = build_content_narration_prompt(
        content=content,
        n_storyboard=n_scenes,
        min_words=min_words,
        max_words=max_words,
        genre=genre,
        custom_prompt=custom_prompt,
    )
    
    response = await llm_service(
        prompt=prompt,
        temperature=0.8,
        max_tokens=8192
    )
    
    # Parse JSON
    result = _parse_json(response)
    
    if "narrations" not in result:
        raise ValueError("Invalid response format: missing 'narrations' key")
    
    narrations = result["narrations"]
    
    # Validate count
    if len(narrations) > n_scenes:
        logger.warning(f"Got {len(narrations)} narrations, taking first {n_scenes}")
        narrations = narrations[:n_scenes]
    elif len(narrations) < n_scenes:
        raise ValueError(f"Expected {n_scenes} narrations, got only {len(narrations)}")
    
    logger.info(f"Generated {len(narrations)} narrations successfully")
    return narrations


async def split_narration_script(
    script: str,
    split_mode: Literal["paragraph", "line", "sentence"] = "paragraph",
) -> List[str]:
    """
    Split user-provided narration script into segments
    
    Args:
        script: Fixed narration script
        split_mode: Splitting strategy
            - "paragraph": Split by double newline (\\n\\n), preserve single newlines within paragraphs
            - "line": Split by single newline (\\n), each line is a segment
            - "sentence": Split by sentence-ending punctuation (。.!?！？)
    
    Returns:
        List of narration segments
    """
    logger.info(f"Splitting script (mode={split_mode}, length={len(script)} chars)")
    
    narrations = []
    
    if split_mode == "paragraph":
        # Split by double newline (paragraph mode)
        # Preserve single newlines within paragraphs
        paragraphs = re.split(r'\n\s*\n', script)
        for para in paragraphs:
            # Only strip leading/trailing whitespace, preserve internal newlines
            cleaned = para.strip()
            if cleaned:
                narrations.append(para)
        logger.info(f"✅ Split script into {len(narrations)} segments (by paragraph)")
    
    elif split_mode == "line":
        # Split by single newline (original behavior)
        narrations = [line.strip() for line in script.split('\n') if line.strip()]
        logger.info(f"✅ Split script into {len(narrations)} segments (by line)")
    
    elif split_mode == "sentence":
        # Split by sentence-ending punctuation
        # Supports Chinese (。！？) and English (.!?)
        # Use regex to split while keeping sentences intact
        cleaned = re.sub(r'\s+', ' ', script.strip())
        # Split on sentence-ending punctuation, keeping the punctuation with the sentence
        sentences = re.split(r'(?<=[。.!?！？])\s*', cleaned)
        narrations = [s.strip() for s in sentences if s.strip()]
        logger.info(f"✅ Split script into {len(narrations)} segments (by sentence)")
    
    else:
        # Fallback to line mode
        logger.warning(f"Unknown split_mode '{split_mode}', falling back to 'line'")
        narrations = [line.strip() for line in script.split('\n') if line.strip()]
    
    # Log statistics
    if narrations:
        lengths = [len(s) for s in narrations]
        logger.info(f"   Min: {min(lengths)} chars, Max: {max(lengths)} chars, Avg: {sum(lengths)//len(lengths)} chars")
    
    return narrations


async def _batch_generate_prompts(
    llm_service,
    narrations: List[str],
    prompt_builder: Callable,
    response_key: str,
    *,
    label: str = "prompts",
    batch_size: int = 10,
    max_retries: int = 3,
    progress_callback: Optional[callable] = None,
    **builder_kwargs,
) -> List[str]:
    """
    Generic batched LLM prompt generation with retry.
    
    Args:
        llm_service: LLM service instance
        narrations: List of narrations to generate prompts for
        prompt_builder: Callable that builds the LLM prompt (must accept `narrations` kwarg)
        response_key: JSON key to extract results from LLM response (e.g. 'image_prompts')
        label: Human-readable label for logging (default: 'prompts')
        batch_size: Max narrations per batch (default: 10)
        max_retries: Max retry attempts per batch (default: 3)
        progress_callback: Optional callback(completed, total, message) for progress updates
        **builder_kwargs: Additional keyword arguments passed to prompt_builder
    
    Returns:
        List of generated prompts
    """
    logger.info(f"Generating {label} for {len(narrations)} narrations (batch_size={batch_size})")
    
    batches = [narrations[i:i + batch_size] for i in range(0, len(narrations), batch_size)]
    logger.info(f"Split into {len(batches)} batches")
    
    all_prompts = []
    
    for batch_idx, batch_narrations in enumerate(batches, 1):
        logger.info(f"Processing batch {batch_idx}/{len(batches)} ({len(batch_narrations)} narrations)")
        
        for attempt in range(1, max_retries + 1):
            try:
                prompt = prompt_builder(
                    narrations=batch_narrations,
                    **builder_kwargs,
                )
                
                response = await llm_service(
                    prompt=prompt,
                    temperature=0.7,
                    max_tokens=8192
                )
                
                logger.debug(f"Batch {batch_idx} attempt {attempt}: LLM response length: {len(response)} chars")
                
                result = _parse_json(response)
                
                if response_key not in result:
                    raise KeyError(f"Invalid response format: missing '{response_key}'")
                
                batch_prompts = result[response_key]
                
                if len(batch_prompts) != len(batch_narrations):
                    error_msg = (
                        f"Batch {batch_idx} {label} count mismatch (attempt {attempt}/{max_retries}): "
                        f"expected {len(batch_narrations)}, got {len(batch_prompts)}"
                    )
                    if attempt < max_retries:
                        logger.warning(error_msg)
                        continue
                    raise ValueError(error_msg)
                
                all_prompts.extend(batch_prompts)
                logger.info(f"✅ Batch {batch_idx} completed ({len(batch_prompts)} {label})")
                
                if progress_callback:
                    progress_callback(
                        len(all_prompts),
                        len(narrations),
                        f"Batch {batch_idx}/{len(batches)} completed"
                    )
                break
                
            except json.JSONDecodeError as e:
                logger.error(f"Batch {batch_idx} JSON parse error (attempt {attempt}/{max_retries}): {e}")
                if attempt >= max_retries:
                    raise
            except (KeyError, ValueError):
                if attempt >= max_retries:
                    raise
            
            logger.info(f"Retrying batch {batch_idx}...")
    
    logger.info(f"✅ Generated {len(all_prompts)} {label}")
    return all_prompts


async def generate_image_prompts(
    llm_service,
    narrations: List[str],
    min_words: int = 30,
    max_words: int = 60,
    batch_size: int = 10,
    max_retries: int = 3,
    progress_callback: Optional[callable] = None,
    style_preset: Optional[str] = None,
    custom_style_prefix: str = "",
) -> List[str]:
    """
    Generate image prompts from narrations (with batching, retry, shot framing and style presets)
    """
    from trendlume.prompts import build_image_prompt_prompt
    
    logger.info(f"Image prompt generation: style_preset={style_preset}")
    return await _batch_generate_prompts(
        llm_service=llm_service,
        narrations=narrations,
        prompt_builder=build_image_prompt_prompt,
        response_key="image_prompts",
        label="image prompts",
        batch_size=batch_size,
        max_retries=max_retries,
        progress_callback=progress_callback,
        min_words=min_words,
        max_words=max_words,
        style_preset=style_preset,
        custom_style_prefix=custom_style_prefix,
    )


async def generate_video_prompts(
    llm_service,
    narrations: List[str],
    min_words: int = 30,
    max_words: int = 60,
    batch_size: int = 10,
    max_retries: int = 3,
    progress_callback: Optional[callable] = None,
    custom_style_prefix: str = "",
) -> List[str]:
    """
    Generate video prompts from narrations (with batching, retry, and camera motion guidelines)
    """
    from trendlume.prompts.video_generation import build_video_prompt_prompt
    
    return await _batch_generate_prompts(
        llm_service=llm_service,
        narrations=narrations,
        prompt_builder=build_video_prompt_prompt,
        response_key="video_prompts",
        label="video prompts",
        batch_size=batch_size,
        max_retries=max_retries,
        progress_callback=progress_callback,
        min_words=min_words,
        max_words=max_words,
        custom_style_prefix=custom_style_prefix,
    )


def _normalize_parsed_json(data) -> dict:
    """
    Ensure parsed JSON is always a dict.
    If the LLM returned a raw array, wrap it under a 'data' key.
    Callers should check for their specific expected key.
    """
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {"data": data}
    raise ValueError(f"Unexpected JSON type: {type(data).__name__}")


def _parse_json(text: str) -> dict:
    """
    Parse JSON from text, with fallback to extract JSON from markdown code blocks
    and raw JSON objects/arrays.
    
    Args:
        text: Text containing JSON
        
    Returns:
        Parsed JSON dict
        
    Raises:
        ValueError: If text is empty or missing
        json.JSONDecodeError: If no valid JSON found
    """
    if not text or not text.strip():
        raise ValueError("LLM returned empty content.")
    
    target_text = text.strip()
    
    # 1. Strip surrounding markdown code fence and try direct parsing
    stripped_fence_text = _strip_code_fence(target_text)
    for candidate in (stripped_fence_text, target_text):
        try:
            return _normalize_parsed_json(json.loads(candidate))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    
    # 2. Try extracting from markdown code block via regex
    code_block_match = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', target_text, re.DOTALL)
    if code_block_match:
        try:
            return _normalize_parsed_json(json.loads(code_block_match.group(1).strip()))
        except (json.JSONDecodeError, ValueError):
            pass
    
    # 3. Try finding JSON object with expected keys
    key_pattern = r'\{[^{}]*(?:"narrations"|"image_prompts"|"video_prompts"|"queries")\s*:\s*\[[^\]]*\][^{}]*\}'
    key_match = re.search(key_pattern, target_text, re.DOTALL)
    if key_match:
        try:
            return _normalize_parsed_json(json.loads(key_match.group(0)))
        except (json.JSONDecodeError, ValueError):
            pass
    
    # 4. Broader search for any JSON object (outermost curly braces)
    brace_start = target_text.find('{')
    brace_end = target_text.rfind('}')
    if brace_start != -1 and brace_end > brace_start:
        try:
            return _normalize_parsed_json(json.loads(target_text[brace_start:brace_end + 1]))
        except (json.JSONDecodeError, ValueError):
            pass
    
    # 5. Array fallback if the LLM returned a plain JSON array [ ... ]
    bracket_start = target_text.find('[')
    bracket_end = target_text.rfind(']')
    if bracket_start != -1 and bracket_end > bracket_start:
        try:
            return _normalize_parsed_json(json.loads(target_text[bracket_start:bracket_end + 1]))
        except (json.JSONDecodeError, ValueError):
            pass
    
    raise json.JSONDecodeError("No valid JSON found in LLM response", text, 0)

