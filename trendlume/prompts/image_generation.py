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
Image prompt generation template

For generating expressive, symbolic, and cinematic image prompts from narrations,
integrating visual storytelling, symbolic metaphors, style presets, and strict subject completeness.
"""

import json
from typing import List, Optional, Dict


# ==================== PRESET IMAGE STYLES ====================
# Predefined visual styles for different use cases

IMAGE_STYLE_PRESETS: Dict[str, Dict[str, str]] = {
    "stick_figure": {
        "name": "简约火柴人",
        "description": "Minimalist black ink stick figure line art, clean pure white background, hand-drawn sketch style, fully framed subject, zero clutter, no text",
        "use_case": "General explainer, conceptual, simple and intuitive"
    },
    "minimalist_line_art": {
        "name": "简笔画",
        "description": "Universal minimalist line art illustration, clean hand-drawn fluid contours, subtle flat color accents, strictly 1-3 focal elements, ample negative space, clear margins, no text",
        "use_case": "Versatile explainer, business insights, science concepts, daily life philosophy, emotional stories"
    },
    "chinese_ink": {
        "name": "中国水墨画",
        "description": "Traditional Chinese ink wash painting aesthetic, guochao style, elegant fluid brush strokes, poetic composition, ample harmonious negative space (留白), atmospheric mist, zen tranquility, no text",
        "use_case": "Eastern culture, humanities, Zen, philosophy, traditional history"
    },
    "cinematic_real": {
        "name": "电影写实",
        "description": "Cinematic 8k photograph, 35mm lens, shallow depth of field separating centered subject from soft uncluttered backdrop, dramatic chiaroscuro lighting, rich textures, no text",
        "use_case": "Realistic storytelling, historical, business, dramatic scenarios"
    },
    "animation": {
        "name": "动画",
        "description": "Vibrant clean animation art style, well-defined character silhouette centered in frame, smooth lighting, harmonious color palette, neat organized backdrop, no text",
        "use_case": "Engaging storytelling, warm narratives, creative explainers, accessible concepts"
    },
}

# Default preset
DEFAULT_IMAGE_STYLE = "stick_figure"


IMAGE_PROMPT_GENERATION_PROMPT = """# Role Definition
You are a master visual art director and creative designer, skilled at creating expressive, evocative, and symbolic image generation prompts (Midjourney / FLUX / DALL-E / SDXL) for video scripts, transforming narrative concepts into concrete, compelling visual scenes.

# Core Task
Based on the existing video script, create corresponding **English** image prompts for each storyboard's "narration content", ensuring visual scenes perfectly match the narrative content and enhance audience understanding and memory.

**Important: The input contains {narrations_count} narrations. You must generate one corresponding image prompt for each narration, totaling {narrations_count} image prompts.**

# Input Content (Narrations)
{narrations_json}

{style_hint_section}

# Output Requirements

## Image Prompt Specifications
- Language: **Must use English** (for AI image generation models)
- Description structure: `[Subject & Character Action]` + `[Scene / Environment & Context]` + `[Composition & Camera Framing]` + `[Lighting & Atmosphere]` + `[Symbolic Elements]`
- Description length: Ensure clear, complete, and creative descriptions (strictly **{min_words} to {max_words} English words** per prompt)

## Visual Creative Requirements
- Each image must accurately reflect the specific content and emotion of the corresponding narration
- **Use symbolic techniques to visualize abstract concepts** (e.g., use diverging paths to represent life choices, chains/cages to represent constraints, an hourglass/flowing water to represent time, ancient jade/bronze objects to represent cultural heritage, climbing stairs/mountain peaks to represent growth and breakthroughs)
- Scenes should express rich emotions and purposeful actions to enhance visual impact
- Highlight themes through composition and element arrangement; avoid overly literal word-for-word translation

## Key English Vocabulary Reference
- **Symbolic elements**: symbolic elements, metaphor, hourglass, crossroads, glowing compass, blooming flower, breaking chains, ancient manuscript
- **Expression & Emotion**: contemplative, determined, serene, intense, curious, awe-inspired, nostalgic
- **Action & Movement**: examining, holding gently, reaching forward, observing from afar, striding purposefully, standing resolute
- **Scene & Environment**: ancient wooden study, misty mountain peak, bustling modern metropolis, open horizon, minimalist gallery
- **Lighting & Atmosphere**: soft golden hour sunlight, dramatic chiaroscuro, cinematic rim lighting, serene ambient glow, misty atmospheric depth

## Visual and Copy Coordination Principles
- Images should serve the copy, becoming a visual extension of the copy content
- Avoid visual elements unrelated to or contradicting the copy content
- Choose visual presentation methods that best enhance the persuasiveness of the copy
- Ensure the audience can quickly understand the core viewpoint of the copy through images

## Creative Guidance
1. **Phenomenon Description Copy**: Use intuitive scenes to represent social phenomena
2. **Cause Analysis Copy**: Use visual metaphors of cause-and-effect relationships to represent internal logic
3. **Impact Argumentation Copy**: Use consequence scenes or contrast techniques to represent the degree of impact
4. **In-depth Discussion Copy**: Use concretization of abstract concepts to represent deep thinking
5. **Conclusion Inspiration Copy**: Use open-ended scenes or guiding elements to represent inspiration

## Core Rules & Prohibitions
1. **Subject Completeness**: Ensure the primary subject is **fully contained within the frame** with balanced breathing room around the edges. Avoid awkward cropping, cut-off heads, or severed limbs.
2. **Visual Restraint**: Limit each scene to **1 to 3 core focal elements** with clean negative space. Never overload the image with noisy, chaotic props or busy background debris.
3. **No Text / Watermark**: Strictly forbid any written words, letters, subtitles, signatures, watermarks, or logos in the image (always append `no text, no watermark`).
4. **Output Constraints**: Output ONLY a valid JSON object with key `"image_prompts"`.

# Expected JSON Output Format
```json
{{
  "image_prompts": [
    "A dramatic centered medium close-up of a contemplative young scholar holding a translucent jade pendant in an ancient wooden study, soft moonlight filtering through paper blinds, bronze incense burner on a desk, cinematic chiaroscuro lighting, ample negative space, fully framed, no text, no watermark",
    "A lone traveler standing on the crest of a golden sand dune overlooking an open horizon, warm sunrise lighting, vast sky with generous breathing room, centered silhouette, poetic peaceful atmosphere, fully framed, no text, no watermark"
  ]
}}
```

Now, please create {narrations_count} corresponding **English** image prompts for the above {narrations_count} narrations. Only output JSON, no other content."""


def build_image_prompt_prompt(
    narrations: List[str],
    min_words: int = 30,
    max_words: int = 60,
    style_preset: Optional[str] = None,
    custom_style_prefix: str = "",
) -> str:
    """
    Build prompt for generating image prompts from narrations with optional style preset
    
    Args:
        narrations: List of narration strings
        min_words: Minimum word count per prompt
        max_words: Maximum word count per prompt
        style_preset: Optional style preset key from IMAGE_STYLE_PRESETS
        custom_style_prefix: Optional custom prompt prefix
    
    Returns:
        Formatted prompt for LLM
    """
    narrations_json = json.dumps(
        {"narrations": narrations},
        ensure_ascii=False,
        indent=2
    )
    
    style_hint_section = ""
    if style_preset and style_preset in IMAGE_STYLE_PRESETS:
        preset = IMAGE_STYLE_PRESETS[style_preset]
        style_hint_section = f"# Target Visual Aesthetic ({preset['name']})\n{preset['description']}\n"
    elif custom_style_prefix and custom_style_prefix.strip():
        style_hint_section = f"# Target Visual Aesthetic\n{custom_style_prefix.strip()}\n"
    
    return IMAGE_PROMPT_GENERATION_PROMPT.format(
        narrations_json=narrations_json,
        narrations_count=len(narrations),
        min_words=min_words,
        max_words=max_words,
        style_hint_section=style_hint_section,
    ).strip()
