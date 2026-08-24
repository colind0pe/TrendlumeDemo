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
Video prompt generation template

For generating dynamic, motion-rich, and expressive English video generation prompts
(Wan 2.1, Kling, Hunyuan, LTX-Video, Minimax) from narrations, integrating explicit camera
movement, physical dynamics, symbolic visual storytelling, and temporal continuity.
"""

import json
from typing import List, Optional


VIDEO_PROMPT_GENERATION_PROMPT = """# Role Definition
You are a master AI video creative designer and motion director (specializing in AI video models like Wan 2.1, Kling, Hunyuan, LTX-Video, Minimax). You excel at transforming narrative scripts into dynamic, expressive, and visually fluid English video prompts with purposeful camera motions.

# Core Task
Based on the existing video script, create corresponding **English** video generation prompts for each storyboard's "narration content", ensuring video scenes perfectly match the narrative content and enhance audience understanding and memory through dynamic visuals.

**Important: The input contains {narrations_count} narrations. You must generate one corresponding video prompt for each narration, totaling {narrations_count} video prompts.**

# Input Content (Narrations)
{narrations_json}

{style_hint_section}

# Output Requirements

## Video Prompt Specifications
- Language: **Must use English** (for AI video generation models)
- Description structure: `[Continuous Subject Action & Physical Dynamics]` + `[Explicit Camera Movement & Speed]` + `[Lighting Progression & Atmosphere]` + `[Cinematic Motion Quality Details]`
- Description length: Ensure clear, complete, and creative descriptions (strictly **{min_words} to {max_words} English words** per prompt)
- Dynamic elements: Emphasize continuous actions, movements, temporal evolution, and physical effects

## Visual Creative Requirements
- Each video must accurately reflect the specific content and emotion of the corresponding narration
- **Highlight visual dynamics**: character actions, object movements, camera movements, physical interactions, environmental changes
- **Use symbolic techniques to visualize abstract concepts** (e.g., use flowing water/streaming sand to represent the passage of time, rising stairs/mountain climbs to represent progress and breakthrough, parting clouds for revelation, diverging paths for crucial life decisions)
- Scenes should express rich emotions and purposeful actions to enhance visual impact
- Enhance expressiveness through deliberate camera language (push, pull, pan, tilt, tracking, orbital) and temporal rhythm

## Key English Vocabulary Reference
- **Actions & Dynamics**: moving, running, flowing, transforming, growing, falling, surging forward, drifting gently, striding purposefully, spinning, accelerating
- **Camera Movement**: slow push-in, slow pull-out, smooth tracking pan, zoom in, zoom out, dynamic tilt-up, aerial view, orbital shot, low-angle follow
- **Transitions & Temporal Evolution**: lighting shifting, shadows moving, sunlight streaming, volumetric beams parting, gradual particle dispersal
- **Atmosphere & Mood**: dynamic, energetic, peaceful, dramatic, mysterious, reflective, awe-inspiring
- **Lighting & Physics**: shifting volumetric light, fluid ripple dynamics, drifting smoke, soft atmospheric glow, high motion fluidity

## Video and Copy Coordination Principles
- Videos should serve the copy, becoming a dynamic visual extension of the copy content
- Avoid visual elements unrelated to or contradicting the copy content
- Choose dynamic presentation methods that best enhance the persuasiveness of the copy
- Ensure the audience can quickly understand the core viewpoint of the copy through video dynamics

## Creative Guidance
1. **Phenomenon Description Copy**: Use dynamic scenes to represent the occurrence process of social phenomena
2. **Cause Analysis Copy**: Use dynamic evolution of cause-and-effect relationships to represent internal logic
3. **Impact Argumentation Copy**: Use dynamic unfolding of consequence scenes or contrasts to represent the degree of impact
4. **In-depth Discussion Copy**: Use dynamic concretization of abstract concepts to represent deep thinking
5. **Conclusion Inspiration Copy**: Use open-ended dynamic scenes or guiding movements to represent inspiration

## Video-Specific Considerations
- **Emphasize dynamics**: Each video prompt must include obvious actions, motion speed, or continuous physical progression (avoid static descriptions).
- **Camera language**: Purposefully use camera techniques (e.g. slow push-in for focus/tension, pull-out for context/reflection, tracking pan for journey).
- **Duration & Fluidity**: Videos should describe a coherent dynamic process with natural physical fluidity.
- **No Text or Subtitles**: Do NOT include instructions for subtitles, voiceover text, signatures, or on-screen letters.
- **Exact Match**: The output array MUST contain exactly {narrations_count} elements corresponding one-to-one with the input narrations.

# Expected JSON Output Format
```json
{{
  "video_prompts": [
    "A glowing golden hourglass with luminous sand streaming rapidly downwards, camera slowly pushes in towards the narrowing glass neck, volumetric light beams shifting, dark cinematic studio atmosphere, fluid 60fps motion",
    "A lone wanderer walks briskly through an open misty mountain path, camera tracks smoothly from a low side angle, gentle breeze rustles leaves, warm sunrise lighting breaking through clouds, cinematic motion fluidity"
  ]
}}
```

Now, please create {narrations_count} corresponding **English** video prompts for the above {narrations_count} narrations. Only output JSON, no other content."""


def build_video_prompt_prompt(
    narrations: List[str],
    min_words: int = 30,
    max_words: int = 60,
    custom_style_prefix: str = "",
) -> str:
    """
    Build video prompt generation prompt with camera motions and dynamic physics guidelines.
    
    Args:
        narrations: List of narration strings
        min_words: Minimum word count per prompt
        max_words: Maximum word count per prompt
        custom_style_prefix: Optional custom prompt prefix or style hint
    
    Returns:
        Formatted prompt for LLM
    """
    narrations_json = json.dumps(
        {"narrations": narrations},
        ensure_ascii=False,
        indent=2
    )
    
    style_hint_section = ""
    if custom_style_prefix and custom_style_prefix.strip():
        style_hint_section = f"# Target Visual & Motion Style\n{custom_style_prefix.strip()}\n"
    
    return VIDEO_PROMPT_GENERATION_PROMPT.format(
        narrations_json=narrations_json,
        narrations_count=len(narrations),
        min_words=min_words,
        max_words=max_words,
        style_hint_section=style_hint_section,
    ).strip()
