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
Platform Publisher Registry & Factory

Maintains registered platform publishers and resolves the appropriate adapter for jobs.
"""

from typing import Any, Dict, List, Optional, Type

from loguru import logger

from trendlume.publishing.base import BasePlatformPublisher, PlatformCapabilities
from trendlume.publishing.mock import MockPlatformPublisher
from trendlume.publishing.platforms import DouyinPublisher


class PublisherRegistry:
    """
    Registry and factory for Platform Publisher adapters.
    Decouples core business logic from concrete platform implementations.
    """

    def __init__(self):
        self._registry: Dict[str, Type[BasePlatformPublisher]] = {}
        self._instances: Dict[str, BasePlatformPublisher] = {}
        self._register_builtins()

    def _register_builtins(self):
        """Register built-in publishers"""
        self.register("mock", MockPlatformPublisher)
        self.register("douyin", DouyinPublisher)

    def register(self, platform: str, publisher: Any) -> None:
        """
        Register a publisher class or instance for a specific platform.
        """
        platform_key = platform.lower().strip()
        if isinstance(publisher, BasePlatformPublisher):
            self._registry[platform_key] = type(publisher)
            self._instances[platform_key] = publisher
            logger.debug(f"Registered platform publisher instance: {platform_key} -> {type(publisher).__name__}")
        else:
            self._registry[platform_key] = publisher
            self._instances.pop(platform_key, None)
            logger.debug(f"Registered platform publisher class: {platform_key} -> {publisher.__name__}")

    def get_publisher(self, platform: str) -> BasePlatformPublisher:
        """
        Get or instantiate a publisher instance for the given platform.
        Raises ValueError if platform is not registered.
        """
        platform_key = platform.lower().strip()
        if platform_key in self._instances:
            return self._instances[platform_key]

        publisher_cls = self._registry.get(platform_key)
        if not publisher_cls:
            raise ValueError(
                f"Unsupported platform: '{platform}'. "
                f"Supported platforms: {', '.join(sorted(self._registry.keys()))}"
            )

        instance = publisher_cls()
        self._instances[platform_key] = instance
        return instance

    def list_supported_platforms(self) -> List[Dict[str, Any]]:
        """
        List metadata of all supported platforms and their capabilities.
        """
        platforms: List[Dict[str, Any]] = []
        seen_platforms = set()
        for platform_key in sorted(self._registry.keys()):
            try:
                pub = self.get_publisher(platform_key)
                cap = pub.capabilities
                if cap.platform_name in seen_platforms:
                    continue
                seen_platforms.add(cap.platform_name)
                platforms.append(
                    {
                        "platform": cap.platform_name,
                        "display_name": cap.display_name,
                        "icon": cap.icon,
                        "supports_video": cap.supports_video,
                        "supports_images": cap.supports_images,
                        "supports_scheduling": cap.supports_scheduling,
                        "max_title_length": cap.max_title_length,
                        "max_description_length": cap.max_description_length,
                        "max_tags": cap.max_tags,
                        "required_credential_type": cap.required_credential_type,
                        "custom_params_schema": cap.custom_params_schema,
                    }
                )
            except Exception as e:
                logger.warning(f"Error inspecting capabilities for {platform_key}: {e}")

        return platforms


# Global registry singleton
publisher_registry = PublisherRegistry()
