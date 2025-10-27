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
import asyncio
import logging

logger = logging.getLogger(__name__)


class PromptService:
    """Service for fetching and caching prompts from external API"""

    def __init__(
        self,
        api_base_url: str,
        cache_ttl_seconds: int = 3600,
        fallback_dir: str = "prompts",
        max_retries: int = 3,
        timeout: float = 30.0
    ):
        """
        Initialize the PromptService

        Args:
            api_base_url: Base URL for the prompt API (e.g., https://example.com)
            cache_ttl_seconds: Time-to-live for cached prompts in seconds (default: 1 hour)
            fallback_dir: Directory containing local fallback prompt files
            max_retries: Maximum number of retry attempts for API calls (default: 3)
            timeout: HTTP request timeout in seconds (default: 30.0)
        """
        self.api_base_url = api_base_url.rstrip('/')
        self.cache_ttl_seconds = cache_ttl_seconds
        self.fallback_dir = fallback_dir
        self.max_retries = max_retries
        self.timeout = timeout

        # Cache structure: {prompt_id: {"prompt": str, "fetched_at": float, "source": str}}
        self._cache: Dict[str, Dict] = {}

        # HTTP client with connection pooling and timeouts optimized for Lambda
        # Use limits to prevent connection pool exhaustion
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            follow_redirects=True
        )

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
            logger.info(f"✅ Using cached prompt (id={prompt_id}, source={cached['source']}, age={int(time.time() - cached['fetched_at'])}s)")
            print(f"✅ Using cached prompt (id={prompt_id}, source={cached['source']}, age={int(time.time() - cached['fetched_at'])}s)")
            return cached["prompt"]

        # Try fetching from API
        try:
            logger.info(f"Fetching prompt {prompt_id} from API: {self.api_base_url}")
            prompt = await self._fetch_from_api(prompt_id)
            logger.info(f"Prompt : {prompt}")
            self._cache[cache_key] = {
                "prompt": prompt,
                "fetched_at": time.time(),
                "source": "api"
            }
            logger.info(f"✅ Fetched prompt from API (id={prompt_id}, length={len(prompt)} chars)")
            print(f"✅ Fetched prompt from API (id={prompt_id})")
            return prompt

        except Exception as api_error:
            logger.error(f"⚠️  Failed to fetch prompt from API (id={prompt_id}): {api_error}", exc_info=True)
            print(f"⚠️  Failed to fetch prompt from API (id={prompt_id}): {api_error}")

            # Try local file fallback
            if fallback_filename:
                try:
                    logger.info(f"Attempting to load fallback file: {fallback_filename}")
                    prompt = self._load_from_file(fallback_filename)
                    self._cache[cache_key] = {
                        "prompt": prompt,
                        "fetched_at": time.time(),
                        "source": "file"
                    }
                    logger.info(f"✅ Using local fallback prompt: {fallback_filename} (length={len(prompt)} chars)")
                    print(f"✅ Using local fallback prompt: {fallback_filename}")
                    return prompt

                except Exception as file_error:
                    logger.error(f"❌ Failed to load fallback file {fallback_filename}: {file_error}", exc_info=True)
                    print(f"❌ Failed to load fallback file {fallback_filename}: {file_error}")
                    raise Exception(f"Failed to fetch prompt from API and fallback file: API error: {api_error}, File error: {file_error}")
            else:
                logger.error(f"No fallback file specified for prompt {prompt_id}")
                raise Exception(f"Failed to fetch prompt from API and no fallback file specified: {api_error}")

    async def _fetch_from_api(self, prompt_id: int) -> str:
        """
        Fetch prompt from external API with retry logic

        Args:
            prompt_id: The numeric ID of the prompt

        Returns:
            The prompt text

        Raises:
            Exception: If API call fails after all retries
        """
        url = f"{self.api_base_url}/api/cmn/get_prompt"
        params = {"id": prompt_id}

        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Attempting to fetch prompt {prompt_id} (attempt {attempt + 1}/{self.max_retries})")

                response = await self.client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                if "prompt" not in data:
                    raise Exception(f"API response missing 'prompt' field: {data}")

                logger.info(f"Successfully fetched prompt {prompt_id} on attempt {attempt + 1}")
                return data["prompt"]

            except httpx.TimeoutException as e:
                last_error = f"Timeout error: {e}"
                logger.warning(f"Timeout fetching prompt {prompt_id} on attempt {attempt + 1}: {e}")

            except httpx.ConnectError as e:
                last_error = f"Connection error: {e}"
                logger.warning(f"Connection error fetching prompt {prompt_id} on attempt {attempt + 1}: {e}")

            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}: {e}"
                logger.warning(f"HTTP error fetching prompt {prompt_id} on attempt {attempt + 1}: {e}")
                # Don't retry on 4xx errors (client errors)
                if 400 <= e.response.status_code < 500:
                    raise Exception(last_error)

            except Exception as e:
                last_error = f"Unexpected error: {e}"
                logger.warning(f"Error fetching prompt {prompt_id} on attempt {attempt + 1}: {e}")

            # Exponential backoff: wait 1s, 2s, 4s between retries
            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt
                logger.info(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

        # All retries exhausted
        error_msg = f"Failed to fetch prompt {prompt_id} after {self.max_retries} attempts. Last error: {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)

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

    async def refresh_client(self):
        """
        Refresh the HTTP client (useful for Lambda to avoid stale connections)

        This closes the existing client and creates a new one with fresh connections.
        Call this periodically in Lambda environments to prevent connection issues.
        """
        try:
            await self.client.aclose()
            logger.info("Closed existing HTTP client")
        except Exception as e:
            logger.warning(f"Error closing HTTP client: {e}")

        # Create a new client with the same configuration
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            follow_redirects=True
        )
        logger.info("Created fresh HTTP client")

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
        logger.info("HTTP client closed")
