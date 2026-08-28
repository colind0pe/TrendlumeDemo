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
Research Service

Orchestrates multi-query web search, result normalization, URL deduplication,
context synthesis, and safe fallback handling.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from loguru import logger

from trendlume.research.models import ResearchContext, SearchResult
from trendlume.research.provider import SearchProvider, TavilySearchProvider


class ResearchService:
    """
    Web Research service for augmenting narration generation.
    """

    def __init__(
        self,
        config: Optional[dict] = None,
        provider: Optional[SearchProvider] = None,
        llm_service: Optional[Any] = None,
    ):
        """
        Initialize Research Service
        """
        self._provider = provider
        self._llm_service = llm_service
        self._config_dict = config or {}

    def _get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get config value with hot-reload support.
        Priority: env var > config_manager (hot-reload) > fallback config dict > default
        """
        env_key_map = {
            "enabled": "RESEARCH_ENABLED",
            "tavily_api_key": "TAVILY_API_KEY",
            "max_queries": "RESEARCH_MAX_QUERIES",
            "max_results": "RESEARCH_MAX_RESULTS",
            "max_context": "RESEARCH_MAX_CONTEXT",
        }

        # 1. Check environment variables
        env_var = env_key_map.get(key)
        if env_var and env_var in os.environ:
            val = os.environ[env_var]
            if isinstance(default, bool) or key == "enabled":
                return str(val).lower() in ("true", "1", "yes", "on")
            if isinstance(default, int) or key in ("max_queries", "max_results", "max_context"):
                try:
                    return int(val)
                except ValueError:
                    pass
            return val

        # 2. Check explicit instance config dict (if provided at construction)
        if self._config_dict and "research" in self._config_dict:
            if key in self._config_dict["research"]:
                return self._config_dict["research"][key]

        # 3. Check global config_manager (supports hot-reload from UI / file)
        try:
            from trendlume.config import config_manager
            cfg_val = getattr(config_manager.config.research, key, None)
            if cfg_val is not None:
                return cfg_val
        except Exception:
            pass

        return default

    @property
    def is_configured(self) -> bool:
        """Check if research service has API key or provider configured"""
        if self._provider is not None:
            return True
        api_key = self._get_config_value("tavily_api_key", "")
        return bool(api_key and str(api_key).strip())

    def is_enabled(self, override: Optional[bool] = None) -> bool:
        """Check if research enhancement is enabled"""
        if override is not None:
            return bool(override)
        return bool(self._get_config_value("enabled", False))

    def _get_provider(self) -> SearchProvider:
        """Get or initialize the search provider (cached on first use)."""
        if self._provider is not None:
            return self._provider

        api_key = self._get_config_value("tavily_api_key", "")
        self._provider = TavilySearchProvider(api_key=api_key)
        return self._provider

    async def generate_search_queries(
        self,
        topic: str,
        max_queries: int = 3,
        llm_service: Optional[Any] = None,
    ) -> List[str]:
        """
        Generate multi-dimensional search queries from a topic.
        Dynamically adapts to any domain (tech, finance, health, social trends, tutorials, culture, etc.).
        """
        clean_topic = topic.strip()
        if not clean_topic:
            return []

        active_llm = llm_service or self._llm_service
        if active_llm is not None and max_queries > 1:
            try:
                from trendlume.utils.content_generators import _parse_json
                
                prompt = f"""# Role
You are an expert web research query generator for viral short videos and factual content.

# Task
Given the following video topic, generate up to {max_queries} diverse, high-value search queries covering different information dimensions (e.g. core facts, underlying mechanisms, key data/benchmarks, or practical takeaways).

# Input Topic
{clean_topic}

# Output Requirements
- Queries MUST be in the exact same language as the input topic.
- Queries MUST be concise, search-engine-friendly keyword combinations.
- Each query must target a distinct aspect of the topic.

# Expected Output Format
Strictly output in the following JSON format:

```json
{{
  "queries": [
    "<search keyword query 1>",
    "<search keyword query 2>",
    "<search keyword query 3>"
  ]
}}
```

Now output the JSON with the generated queries array."""
                response = await active_llm(prompt, temperature=0.3)
                data = _parse_json(response)
                raw_queries = data.get("queries", data.get("data", []))
                if isinstance(raw_queries, list):
                    queries = [str(q).strip() for q in raw_queries if str(q).strip()]
                    if queries:
                        logger.debug(f"LLM generated {len(queries)} search queries for '{clean_topic}': {queries}")
                        return queries[:max_queries]
            except Exception as e:
                logger.warning(f"LLM search query generation failed: {e}. Using heuristic fallback.")

        # Heuristic fallback if LLM is unavailable or failed
        return self._generate_heuristic_queries(clean_topic, max_queries)

    def _clean_topic_for_search(self, topic: str) -> str:
        """Strip punctuation and conversational prefixes to extract core keyword subject"""
        t = topic.strip().strip("？?！!。,.，；;：:")
        
        # Remove common Chinese conversational question prefixes
        prefixes_cn = ["为什么", "如何", "怎样", "怎么", "什么是", "为何", "深度解析", "聊聊"]
        for p in prefixes_cn:
            if t.startswith(p):
                t = t[len(p):].strip(" ，,：:的")
                break

        # Remove common English conversational question prefixes
        prefixes_en = [
            "why does", "why do", "why is", "why are", "why",
            "how to", "how do", "how does", "how can",
            "what is", "what are", "what makes"
        ]
        for p in prefixes_en:
            if t.lower().startswith(p):
                t = t[len(p):].strip(" ,:?-")
                break

        return t.strip() if t.strip() else topic.strip()

    def _generate_heuristic_queries(self, topic: str, max_queries: int) -> List[str]:
        """Generate rule-based queries covering versatile, search-friendly dimensions"""
        raw_topic = topic.strip()
        if not raw_topic:
            return []

        core_kw = self._clean_topic_for_search(raw_topic)
        is_chinese = any('\u4e00' <= char <= '\u9fff' for char in raw_topic)

        queries = [raw_topic]
        if max_queries <= 1:
            return queries

        if is_chinese:
            candidates = [
                f"{core_kw} 核心逻辑 与 原理解析",
                f"{core_kw} 关键数据 现状 与 案例",
                f"{core_kw} 最新进展 与 深度对比",
            ]
        else:
            candidates = [
                f"{core_kw} core mechanism and explanation",
                f"{core_kw} key data facts and case studies",
                f"{core_kw} latest trends and comprehensive overview",
            ]

        for cand in candidates:
            if len(queries) < max_queries and cand not in queries:
                queries.append(cand)

        return queries[:max_queries]

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication"""
        try:
            parsed = urlparse(url)
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            path = parsed.path.rstrip("/")
            return f"{scheme}://{netloc}{path}"
        except Exception:
            return url.strip().rstrip("/")

    def deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Deduplicate search results by normalized URL, keeping the highest scoring item.
        """
        seen_urls: Dict[str, SearchResult] = {}

        for item in results:
            if not item.url:
                continue
            norm_url = self._normalize_url(item.url)
            if norm_url not in seen_urls:
                seen_urls[norm_url] = item
            else:
                existing = seen_urls[norm_url]
                # Replace if current item has higher score or longer content
                if item.score > existing.score or len(item.content) > len(existing.content):
                    seen_urls[norm_url] = item

        deduped = list(seen_urls.values())
        # Sort by score descending
        deduped.sort(key=lambda x: x.score, reverse=True)
        return deduped

    async def conduct_research(
        self,
        topic: str,
        llm_service: Optional[Any] = None,
        max_queries: Optional[int] = None,
        max_results: Optional[int] = None,
        max_context: Optional[int] = None,
        enable_override: Optional[bool] = None,
    ) -> Optional[ResearchContext]:
        """
        Perform end-to-end web research for a topic.
        
        Returns:
            ResearchContext if search succeeded, or None if disabled/failed.
        """
        # 1. Check enabled switch
        if not self.is_enabled(enable_override):
            logger.debug("Research is disabled. Skipping web research.")
            return None

        # 2. Check API key
        if not self.is_configured:
            logger.warning("Research enabled but TAVILY_API_KEY is not set. Skipping web research.")
            return None

        try:
            # 3. Resolve limits
            limit_queries = max_queries or self._get_config_value("max_queries", 3)
            limit_results = max_results or self._get_config_value("max_results", 5)
            limit_context = max_context or self._get_config_value("max_context", 3000)

            # 4. Generate search queries
            queries = await self.generate_search_queries(
                topic=topic,
                max_queries=limit_queries,
                llm_service=llm_service,
            )

            if not queries:
                logger.warning(f"No search queries generated for topic: '{topic}'")
                return None

            logger.info(f"🔍 Executing {len(queries)} search queries for topic: '{topic}'")
            provider = self._get_provider()

            # 5. Concurrently search with bounded semaphore
            semaphore = asyncio.Semaphore(3)

            async def search_single(q: str) -> List[SearchResult]:
                async with semaphore:
                    try:
                        return await provider.search(query=q, max_results=limit_results)
                    except Exception as e:
                        logger.warning(f"Query '{q}' failed: {e}")
                        return []

            tasks = [search_single(q) for q in queries]
            search_batches = await asyncio.gather(*tasks, return_exceptions=True)

            # 6. Aggregate results
            all_results: List[SearchResult] = []
            for batch in search_batches:
                if isinstance(batch, list):
                    all_results.extend(batch)

            if not all_results:
                logger.warning(f"Web research returned 0 results for topic '{topic}'. Skipping research context.")
                return None

            # 7. Deduplicate & sort
            curated_results = self.deduplicate_results(all_results)
            logger.info(f"📊 Curated {len(curated_results)} unique sources (from {len(all_results)} total results)")

            # 8. Assemble ResearchContext
            context = ResearchContext(
                topic=topic,
                queries=queries,
                results=curated_results,
            )
            context.formatted_text = context.format_for_prompt(max_length=limit_context)

            return context

        except Exception as e:
            logger.warning(f"Research execution failed with exception: {e}. Falling back gracefully.")
            return None

    async def close(self):
        """Clean up provider resources"""
        if self._provider is not None:
            await self._provider.close()
