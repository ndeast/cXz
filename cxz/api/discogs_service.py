"""Discogs API service for searching vinyl records."""

import asyncio
import os
import time
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from pydantic import ValidationError

from cxz.models.record import DiscogsRelease, RecordQuery
from cxz.utils.discogs_query import build_discogs_search_params, build_fallback_query

load_dotenv()


class RateLimiter:
    """Simple rate limiter for API requests."""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute
        self.last_request_time = 0.0

    async def wait_if_needed(self):
        """Wait if necessary to respect rate limits."""
        now = time.time()
        time_since_last = now - self.last_request_time

        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            await asyncio.sleep(wait_time)

        self.last_request_time = time.time()


class DiscogsService:
    """Service for interacting with the Discogs API."""

    def __init__(
        self,
        user_token: Optional[str] = None,
        requests_per_minute: Optional[int] = None,
    ):
        """Initialize the Discogs service.

        Args:
            user_token: Discogs personal access token. If None, loads from environment.
            requests_per_minute: Rate limit. If None, loads from environment.
        """
        self.user_token = user_token or os.getenv("DISCOGS_USER_TOKEN")
        if not self.user_token:
            raise ValueError("DISCOGS_USER_TOKEN environment variable is required")

        rpm = requests_per_minute or int(os.getenv("DISCOGS_REQUESTS_PER_MINUTE", "60"))
        self.rate_limiter = RateLimiter(rpm)

        self.base_url = "https://api.discogs.com"
        self.headers = {
            "User-Agent": "cXz/0.1.0 +https://github.com/yourusername/cxz",
            "Authorization": f"Discogs token={self.user_token}",
        }

    async def search_releases(
        self, query: RecordQuery, max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """Search for releases using a structured query.

        Args:
            query: Parsed record query
            max_results: Maximum number of results to return

        Returns:
            List of Discogs search results

        Raises:
            ValueError: If the search fails or returns invalid data
            httpx.HTTPError: If there's an HTTP error
        """
        # Build search parameters from structured query
        params = build_discogs_search_params(query)
        # Override per_page from build_discogs_search_params with our preferred value
        params["per_page"] = min(max_results, 100)  # Discogs max is 100 per page
        params["page"] = 1

        try:
            results = await self._search_with_params(params)

            # If no results and we have a structured query, try fallback search
            if not results and any([query.artist, query.album, query.keywords]):
                fallback_query = build_fallback_query(query)
                fallback_params = {
                    "q": fallback_query,
                    "type": "release",
                    "per_page": min(max_results, 100),
                    "page": 1,
                }
                results = await self._search_with_params(fallback_params)

            return results[:max_results]

        except Exception as e:
            raise ValueError(f"Discogs search failed: {e}")

    async def _search_with_params(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Perform search with given parameters.

        Args:
            params: Search parameters for Discogs API

        Returns:
            List of search results
        """
        await self.rate_limiter.wait_if_needed()

        search_url = f"{self.base_url}/database/search"

        async with httpx.AsyncClient() as client:
            print(f"Making Discogs API request: {search_url}")
            print(f"Parameters: {params}")

            response = await client.get(
                search_url, params=params, headers=self.headers, timeout=30.0
            )

            print(f"Response status: {response.status_code}")

            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            # Log pagination info
            pagination = data.get("pagination", {})
            total_items = pagination.get("items", 0)

            print(
                f"Discogs API response: {total_items} total items, {len(results)} returned"
            )

            if total_items > 0:
                print(f"Found {total_items} total results, returning {len(results)}")
            else:
                print("No results found from Discogs API")
                print(f"Full response data: {data}")

            return results

    async def get_release_details(self, release_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific release.

        Args:
            release_id: Discogs release ID

        Returns:
            Detailed release information or None if not found
        """
        await self.rate_limiter.wait_if_needed()

        release_url = f"{self.base_url}/releases/{release_id}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    release_url, headers=self.headers, timeout=30.0
                )
                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def search_and_rank(
        self, description: str, llm_service, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for records and rank results using LLM.

        Args:
            description: Natural language description of the record
            llm_service: LLM service for parsing and ranking
            max_results: Maximum number of ranked results to return

        Returns:
            List of ranked results with relevance scores
        """
        # Parse the description into a structured query
        from cxz.utils.record_parser import parse_record_description

        query = parse_record_description(description, llm_service)

        # Search Discogs for matching releases
        search_results = await self.search_releases(
            query, max_results * 2
        )  # Get more for better ranking

        if not search_results:
            return []

        # Use LLM to rank the results
        ranked_results = llm_service.rank_results(query, search_results, description)

        return ranked_results[:max_results]

    def validate_credentials(self) -> bool:
        """Validate that the API credentials are working.

        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            # Make a simple request to test credentials
            import asyncio

            return asyncio.run(self._test_credentials())
        except:
            return False

    async def _test_credentials(self) -> bool:
        """Test API credentials asynchronously."""
        try:
            await self.rate_limiter.wait_if_needed()

            async with httpx.AsyncClient() as client:
                # Use a simple search to test credentials
                response = await client.get(
                    f"{self.base_url}/database/search",
                    params={"q": "test", "type": "release", "per_page": 1},
                    headers=self.headers,
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception as e:
            print(f"Credential test failed: {e}")
            return False

    async def add_to_collection(
        self, 
        release_id: int, 
        condition: str = "Mint (M)", 
        sleeve_condition: str = "Mint (M)"
    ) -> bool:
        """Add a release to the user's Discogs collection.

        Args:
            release_id: Discogs release ID
            condition: Media condition (Mint (M), Near Mint (NM), etc.)
            sleeve_condition: Sleeve condition

        Returns:
            True if successfully added, False otherwise
        """
        await self.rate_limiter.wait_if_needed()

        # Get user identity first
        user_info = await self._get_user_identity()
        if not user_info:
            print("Failed to get user identity for collection management")
            return False
            
        username = user_info.get("username")
        if not username:
            print("No username found in user identity")
            return False

        collection_url = f"{self.base_url}/users/{username}/collection/folders/1/releases/{release_id}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    collection_url,
                    json={
                        "condition": condition,
                        "sleeve_condition": sleeve_condition
                    },
                    headers=self.headers,
                    timeout=30.0,
                )
                
                if response.status_code == 201:
                    print(f"✅ Successfully added release {release_id} to collection")
                    return True
                elif response.status_code == 422:
                    print(f"ℹ️  Release {release_id} is already in collection")
                    return True
                else:
                    print(f"❌ Failed to add to collection: {response.status_code} - {response.text}")
                    return False

        except Exception as e:
            print(f"❌ Error adding to collection: {e}")
            return False

    async def _get_user_identity(self) -> Optional[Dict[str, Any]]:
        """Get the authenticated user's identity."""
        await self.rate_limiter.wait_if_needed()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/oauth/identity",
                    headers=self.headers,
                    timeout=10.0,
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Failed to get user identity: {response.status_code}")
                    return None

        except Exception as e:
            print(f"Error getting user identity: {e}")
            return None


async def search_vinyl_records(
    description: str, llm_service=None, max_results: int = 10
) -> List[Dict[str, Any]]:
    """Convenience function to search for vinyl records.

    Args:
        description: Natural language description
        llm_service: Optional LLM service instance
        max_results: Maximum results to return

    Returns:
        List of ranked search results
    """
    if llm_service is None:
        from cxz.api.llm_service import LLMService

        llm_service = LLMService()

    discogs_service = DiscogsService()
    return await discogs_service.search_and_rank(description, llm_service, max_results)
