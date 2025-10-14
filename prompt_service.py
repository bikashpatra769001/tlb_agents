"""
Prompt Service Module

Fetches prompts from an external API with local file fallback and caching.
Supports dynamic prompt updates without requiring application redeployment.
"""

import os
import time
from typing import Optional, Dict
import httpx
from datetime import datetime


class PromptService:
    """Service for fetching and caching prompts from external API"""

    def __init__(
        self,
        api_base_url: str,
        cache_ttl_seconds: int = 3600,
        fallback_dir: str = "prompts"
    ):
        """
        Initialize the PromptService

        Args:
            api_base_url: Base URL for the prompt API (e.g., https://example.com)
            cache_ttl_seconds: Time-to-live for cached prompts in seconds (default: 1 hour)
            fallback_dir: Directory containing local fallback prompt files
        """
        self.api_base_url = api_base_url.rstrip('/')
        self.cache_ttl_seconds = cache_ttl_seconds
        self.fallback_dir = fallback_dir

        # Cache structure: {prompt_id: {"prompt": str, "fetched_at": float, "source": str}}
        self._cache: Dict[str, Dict] = {}

        # HTTP client with reasonable timeouts
        self.client = httpx.AsyncClient(timeout=10.0)

    async def get_prompt(
        self,
        prompt_id: int,
        fallback_filename: Optional[str] = None,
        force_refresh: bool = False
    ) -> str:
        """
        Get a prompt by ID, using cache, API, or local file fallback

        Args:
            prompt_id: The numeric ID of the prompt to fetch
            fallback_filename: Optional local filename to use as fallback (e.g., "ror_summary.txt")
            force_refresh: If True, bypass cache and fetch fresh from API

        Returns:
            The prompt text

        Raises:
            Exception: If all methods (API + fallback) fail
        """
        cache_key = str(prompt_id)

        # Check cache first (unless force refresh)
        if not force_refresh and self._is_cache_valid(cache_key):
            cached = self._cache[cache_key]
            print(f"✅ Using cached prompt (id={prompt_id}, source={cached['source']}, age={int(time.time() - cached['fetched_at'])}s)")
            return cached["prompt"]

        # Try fetching from API
        try:
            prompt = await self._fetch_from_api(prompt_id)
            self._cache[cache_key] = {
                "prompt": prompt,
                "fetched_at": time.time(),
                "source": "api"
            }
            print(f"✅ Fetched prompt from API (id={prompt_id})")
            return prompt

        except Exception as api_error:
            print(f"⚠️  Failed to fetch prompt from API (id={prompt_id}): {api_error}")

            # Try local file fallback
            if fallback_filename:
                try:
                    prompt = self._load_from_file(fallback_filename)
                    self._cache[cache_key] = {
                        "prompt": prompt,
                        "fetched_at": time.time(),
                        "source": "file"
                    }
                    print(f"✅ Using local fallback prompt: {fallback_filename}")
                    return prompt

                except Exception as file_error:
                    print(f"❌ Failed to load fallback file {fallback_filename}: {file_error}")
                    raise Exception(f"Failed to fetch prompt from API and fallback file: API error: {api_error}, File error: {file_error}")
            else:
                raise Exception(f"Failed to fetch prompt from API and no fallback file specified: {api_error}")

    async def _fetch_from_api(self, prompt_id: int) -> str:
        """
        Fetch prompt from external API

        Args:
            prompt_id: The numeric ID of the prompt

        Returns:
            The prompt text

        Raises:
            Exception: If API call fails
        """
        url = f"{self.api_base_url}/api/cmn/get_prompt"
        params = {"id": prompt_id}

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        if "prompt" not in data:
            raise Exception(f"API response missing 'prompt' field: {data}")

        return data["prompt"]

    def _load_from_file(self, filename: str) -> str:
        """
        Load prompt from local file

        Args:
            filename: Name of the file in the fallback directory

        Returns:
            The prompt text

        Raises:
            Exception: If file cannot be read
        """
        file_path = os.path.join(
            os.path.dirname(__file__),
            self.fallback_dir,
            filename
        )

        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()

    def _is_cache_valid(self, cache_key: str) -> bool:
        """
        Check if cached prompt is still valid based on TTL

        Args:
            cache_key: The cache key to check

        Returns:
            True if cache is valid, False otherwise
        """
        if cache_key not in self._cache:
            return False

        cached = self._cache[cache_key]
        age = time.time() - cached["fetched_at"]

        return age < self.cache_ttl_seconds

    def clear_cache(self, prompt_id: Optional[int] = None):
        """
        Clear cache for a specific prompt or all prompts

        Args:
            prompt_id: Optional specific prompt ID to clear, or None to clear all
        """
        if prompt_id is not None:
            cache_key = str(prompt_id)
            if cache_key in self._cache:
                del self._cache[cache_key]
                print(f"🗑️  Cleared cache for prompt id={prompt_id}")
        else:
            self._cache.clear()
            print("🗑️  Cleared all prompt cache")

    def get_cache_stats(self) -> Dict:
        """
        Get statistics about the cache

        Returns:
            Dictionary with cache statistics
        """
        stats = {
            "total_cached": len(self._cache),
            "prompts": []
        }

        current_time = time.time()
        for cache_key, cached in self._cache.items():
            age_seconds = int(current_time - cached["fetched_at"])
            stats["prompts"].append({
                "id": cache_key,
                "source": cached["source"],
                "age_seconds": age_seconds,
                "valid": age_seconds < self.cache_ttl_seconds
            })

        return stats

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
