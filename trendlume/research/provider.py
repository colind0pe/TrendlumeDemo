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
Search Providers

Defines the abstract SearchProvider base class and concrete implementations (e.g. Tavily).
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import httpx
from loguru import logger

from trendlume.research.models import SearchResult


class SearchProvider(ABC):
    """
    Abstract search provider interface.
    Allows easy extension to other search backends (e.g., Google, Bing, DuckDuckGo, Serper).
    """

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Execute a search query asynchronously and return standardized SearchResult list.
        
        Args:
            query: The search query string
            max_results: Maximum number of results to fetch
            
        Returns:
            List of SearchResult objects
        """
        pass

    async def close(self):
        """Close underlying client connections if any"""
        pass


class TavilySearchProvider(SearchProvider):
    """
    Tavily search provider implementation using Tavily REST API via httpx.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.tavily.com",
        timeout: float = 10.0,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.api_key = api_key.strip() if api_key else ""
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._external_client = client is not None
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Execute search on Tavily API
        """
        if not self.api_key:
            logger.warning("Tavily search skipped: TAVILY_API_KEY is not configured.")
            return []

        clean_query = query.strip()
        if not clean_query:
            return []

        endpoint = f"{self.base_url}/search"
        payload = {
            "api_key": self.api_key,
            "query": clean_query,
            "search_depth": "basic",
            "max_results": max(1, max_results),
            "include_answer": False,
            "include_raw_content": False,
        }

        try:
            client = await self._get_client()
            response = await client.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

            raw_results = data.get("results", [])
            results: List[SearchResult] = []

            for item in raw_results:
                title = str(item.get("title") or "").strip()
                url = str(item.get("url") or "").strip()
                content = str(item.get("content") or "").strip()
                published_at = item.get("published_date")
                score = float(item.get("score") or 0.0)

                # Formulate snippet from content (first 200 chars or whole snippet)
                snippet = content[:200] if len(content) > 200 else content

                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        content=content,
                        published_at=str(published_at) if published_at else None,
                        score=score,
                        raw_data=item,
                    )
                )

            logger.debug(f"Tavily search for '{clean_query}' returned {len(results)} results")
            return results

        except httpx.HTTPStatusError as e:
            logger.warning(
                f"Tavily API HTTP {e.response.status_code} error for query '{clean_query}': {e.response.text[:200]}"
            )
            return []
        except httpx.TimeoutException:
            logger.warning(f"Tavily API request timed out ({self.timeout}s) for query '{clean_query}'")
            return []
        except Exception as e:
            logger.warning(f"Tavily search error for query '{clean_query}': {e}")
            return []

    async def close(self):
        """Close HTTP client if created internally"""
        if not self._external_client and self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
