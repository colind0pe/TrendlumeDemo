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
Cookie & Storage State Helper Utilities

Normalizes cookies and session payloads across different formats for Playwright browser automation.
"""

import json
from typing import Any, Dict, List
from urllib.parse import unquote


def get_default_domain_for_platform(platform: str) -> str:
    """Return default root cookie domain for a platform"""
    domain_map = {
        "douyin": ".douyin.com",
        "mock": ".mock.com",
    }
    return domain_map.get(platform.lower().strip(), "")


def parse_cookie_string(cookie_str: str, default_domain: str = "") -> List[Dict[str, Any]]:
    """
    Parse a standard Cookie header string into Playwright cookie objects.
    Example: "sessionid=abc123; sid_guard=xyz" -> [{"name": "sessionid", "value": "abc123", ...}]
    """
    cookies: List[Dict[str, Any]] = []
    if not cookie_str or not isinstance(cookie_str, str):
        return cookies

    for part in cookie_str.strip().split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, val = part.split("=", 1)
        name = key.strip()
        if not name:
            continue

        cookie_dict: Dict[str, Any] = {
            "name": name,
            "value": unquote(val.strip()),
            "path": "/",
        }
        if default_domain:
            cookie_dict["domain"] = default_domain
        cookies.append(cookie_dict)

    return cookies


def _sanitize_cookie_list(raw_cookies: List[Any], default_domain: str) -> List[Dict[str, Any]]:
    """Sanitize and ensure required domain and path fields on cookie dictionaries."""
    sanitized: List[Dict[str, Any]] = []
    for c in raw_cookies:
        if isinstance(c, dict) and "name" in c and "value" in c:
            item = dict(c)
            dom = item.get("domain") or default_domain
            if dom:
                item["domain"] = dom
                if not item.get("path"):
                    item["path"] = "/"
                sanitized.append(item)
    return sanitized


def normalize_storage_state(credential_data: Any, platform: str = "") -> Dict[str, Any]:
    """
    Normalize any credential format (raw string, cookie list, dict, JSON string) into Playwright storage_state format:
    {
        "cookies": [...],
        "origins": [...]
    }
    """
    default_domain = get_default_domain_for_platform(platform)
    if not credential_data:
        return {"cookies": [], "origins": []}

    # JSON string handling
    if isinstance(credential_data, str):
        trimmed = credential_data.strip()
        if (trimmed.startswith("{") and trimmed.endswith("}")) or (trimmed.startswith("[") and trimmed.endswith("]")):
            try:
                return normalize_storage_state(json.loads(trimmed), platform=platform)
            except Exception:
                pass
        return {"cookies": parse_cookie_string(trimmed, default_domain=default_domain), "origins": []}

    # Dict format handling
    if isinstance(credential_data, dict):
        if "cookies" in credential_data and isinstance(credential_data["cookies"], list):
            return {
                "cookies": _sanitize_cookie_list(credential_data["cookies"], default_domain),
                "origins": credential_data.get("origins", []),
            }
        raw_cookie = credential_data.get("cookie") or credential_data.get("raw")
        if isinstance(raw_cookie, str):
            return {"cookies": parse_cookie_string(raw_cookie, default_domain=default_domain), "origins": []}
        # Key-value mapping
        kv_cookies = [
            {"name": str(k), "value": str(v), "path": "/", **({"domain": default_domain} if default_domain else {})}
            for k, v in credential_data.items()
            if isinstance(v, (str, int, float, bool))
        ]
        return {"cookies": kv_cookies, "origins": []}

    # List format handling
    if isinstance(credential_data, list):
        return {"cookies": _sanitize_cookie_list(credential_data, default_domain), "origins": []}

    return {"cookies": [], "origins": []}
