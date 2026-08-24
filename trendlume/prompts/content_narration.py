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
Content narration generation prompt

For extracting, refining, and restructuring user-provided content into
high-retention, spoken-style short video narration scripts.
"""

from typing import Optional


CONTENT_NARRATION_TEMPLATE = """# Mandatory Language Rule (CRITICAL & HIGHEST PRIORITY)
First, identify the exact language of the source content.
You MUST write and output ALL {n_storyboard} storyboard narrations in the EXACT SAME LANGUAGE as the source content.
- If the source content is in Chinese (中文), you MUST output all narrations in 100% fluent, natural Chinese (严禁输出英文).
- If the source content is in English, you MUST output all narrations in English.

# Role Definition
You are a master short-video script editor. You excel at extracting core insights from source text and restructuring them into punchy, spoken-style short video scripts with high viewer retention and coherent narrative flow.

# Core Task
The user will provide source content. Distill and restructure it into {n_storyboard} scene-by-scene narrations for TTS voiceover generation.

# Source Content
{content}

{genre_section}
{custom_prompt_section}

# Narrative Arc & Logical Progression Guidelines
1. **Scene 1 (The 3-Second Golden Hook)**: Extract the most captivating conclusion, counter-intuitive insight, or core dilemma from the content as a piercing 3-second opening hook.
2. **Intermediate Scenes (Coherent Logic & Punchy Elaboration)**: 
   - Ensure seamless logical transitions from scene to scene, creating a continuous narrative chain.
   - Unpack key arguments and core mechanisms step-by-step, removing written fluff while maintaining high information density and spoken cadence.
3. **Final Scene (Summary & Follow CTA)**: 
   - Summarize the core essence into an actionable takeaway or memorable cognitive payoff.
   - **MANDATORY**: The final narration **MUST end with 1-2 natural, authentic sentences prompting the viewer to follow/subscribe**.

# Spoken Rhythm & Short-Video Retention Requirements
- **Language Consistency (STRICT)**: Output copy MUST match the language of the source content.
- **Word Count**: Strictly control each narration between {min_words} and {max_words} words (minimum {min_words} words).
- **Spoken Punctuation**: Use natural punctuation (, 。 ? ! ……) to control voiceover breathing, pauses, and cadence. Do NOT end narrations with dangling commas.
- **Tone & Delivery**: Accessible, sincere, crisp, and conversational. Reject academic jargon and bureaucratic phrasing.
- **Prohibitions**: No markdown headers, no scene labels in narration text, no URLs, no emoji in voiceover, no numbering.

# Output Format
Strictly output in the following JSON format, without any surrounding commentary:

```json
{{
  "narrations": [
    "First narration (Scene 1: 3-Second Golden Hook)",
    "Second narration (Scene 2: Core Context & Problem)",
    "Third narration (Scene 3: Deep Insight & Key Point)",
    "Fourth narration (Scene 4: Elaboration & Impact)",
    "Fifth narration (Scene 5: Summary + Natural Follow CTA in the last 1-2 sentences)"
  ]
}}
```

**CRITICAL**: Return ONLY the valid JSON object containing exactly {n_storyboard} string elements in the "narrations" array.
"""



def build_content_narration_prompt(
    content: str,
    n_storyboard: int = 5,
    min_words: int = 5,
    max_words: int = 20,
    genre: str = "general",
    custom_prompt: str = "",
) -> str:
    """
    Build content refinement narration prompt
    
    Args:
        content: User-provided content
        n_storyboard: Number of storyboard frames (default: 5)
        min_words: Minimum word count per narration
        max_words: Maximum word count per narration
        genre: Genre style hint (default: 'general')
        custom_prompt: Additional user guidance or specific requirements
    
    Returns:
        Formatted prompt
    """
    genre_section = ""
    if genre and genre not in ("general", "auto"):
        from trendlume.prompts.topic_narration import GENRE_INSTRUCTIONS
        if genre in GENRE_INSTRUCTIONS:
            genre_section = f"# Track / Genre Style Guide ({genre})\n{GENRE_INSTRUCTIONS[genre]}\n"

    if custom_prompt and custom_prompt.strip():
        custom_prompt_section = f"# Additional User Requirements\n{custom_prompt.strip()}\n"
    else:
        custom_prompt_section = ""
        
    return CONTENT_NARRATION_TEMPLATE.format(
        content=content.strip(),
        n_storyboard=n_storyboard,
        min_words=min_words,
        max_words=max_words,
        genre_section=genre_section,
        custom_prompt_section=custom_prompt_section,
    ).strip()


