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
Research domain models

Defines standardized data models for search results and research contexts.
"""

from urllib.parse import urlparse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator


class SearchResult(BaseModel):
    """
    Standardized search result model
    """
    title: str = Field(default="", description="Result title")
    url: str = Field(default="", description="Result URL")
    domain: str = Field(default="", description="Website domain")
    snippet: str = Field(default="", description="Short summary / snippet")
    content: str = Field(default="", description="Main content or extended snippet")
    published_at: Optional[str] = Field(default=None, description="Publication timestamp/date")
    score: float = Field(default=0.0, description="Relevance score")
    raw_data: Optional[Dict[str, Any]] = Field(default=None, description="Raw provider data")

    @model_validator(mode="after")
    def _extract_domain(self) -> "SearchResult":
        if not self.domain and self.url:
            try:
                parsed = urlparse(self.url)
                self.domain = parsed.netloc.lower()
            except Exception:
                self.domain = ""
        return self


class ResearchContext(BaseModel):
    """
    Compiled research context for LLM background reference
    """
    topic: str = Field(description="Original topic/theme")
    queries: List[str] = Field(default_factory=list, description="Search queries executed")
    results: List[SearchResult] = Field(default_factory=list, description="Curated search results")
    formatted_text: str = Field(default="", description="Formatted context string for LLM")

    @property
    def is_empty(self) -> bool:
        """Check if research context contains any results"""
        return len(self.results) == 0 and not bool(self.formatted_text.strip())

    def format_for_prompt(self, max_length: int = 3000) -> str:
        """
        Format research findings into clean markdown reference text,
        bounded by max_length.
        """
        if self.formatted_text and len(self.formatted_text) <= max_length:
            return self.formatted_text

        if not self.results:
            return ""

        sections = [f"Topic: {self.topic}\n"]
        sections.append("Key Findings & Sources:")

        for i, item in enumerate(self.results, 1):
            source_label = f"[{item.title}]({item.url})" if item.url else item.title
            domain_info = f" ({item.domain})" if item.domain else ""
            
            # Prefer content if available, fallback to snippet
            text_body = (item.content or item.snippet or "").strip()
            if not text_body:
                continue
            
            # Clean up text body newlines
            text_body = " ".join(text_body.split())
            
            entry = f"{i}. {source_label}{domain_info}\n   {text_body}"
            sections.append(entry)

        full_text = "\n\n".join(sections)
        if len(full_text) > max_length:
            # Truncate cleanly
            truncated = full_text[:max_length]
            last_break = max(truncated.rfind("\n"), truncated.rfind(" "))
            if last_break > int(max_length * 0.7):
                full_text = truncated[:last_break] + "..."
            else:
                full_text = truncated + "..."

        return full_text
