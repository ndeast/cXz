"""Tests for Discogs API integration."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from cxz.api.discogs_service import DiscogsService, RateLimiter
from cxz.models.record import RecordQuery, VariantDescriptors


class TestRateLimiter:
    """Tests for the rate limiter."""

    @pytest.mark.asyncio
    async def test_rate_limiter_waits(self):
        """Test that rate limiter waits appropriately."""
        # Very low rate limit for testing
        limiter = RateLimiter(requests_per_minute=2)  # 30 second intervals

        start_time = asyncio.get_event_loop().time()

        # First request should not wait
        await limiter.wait_if_needed()
        first_time = asyncio.get_event_loop().time()

        # Second request should wait
        await limiter.wait_if_needed()
        second_time = asyncio.get_event_loop().time()

        # Should have waited close to the minimum interval
        wait_time = second_time - first_time
        assert wait_time >= limiter.min_interval * 0.9  # Allow some timing variance


class TestDiscogsService:
    """Tests for the Discogs API service."""

    def test_init_requires_token(self):
        """Test that initialization requires a token."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="DISCOGS_USER_TOKEN"):
                DiscogsService()

    def test_init_with_token(self):
        """Test successful initialization with token."""
        service = DiscogsService(user_token="test_token")
        assert service.user_token == "test_token"
        assert "Discogs token=test_token" in service.headers["Authorization"]

    @pytest.mark.asyncio
    async def test_search_releases_basic(self):
        """Test basic search functionality."""
        service = DiscogsService(user_token="test_token")

        # Mock the HTTP client
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Pink Floyd - Dark Side Of The Moon",
                    "year": "1973",
                    "formats": [{"name": "Vinyl", "descriptions": ["LP"]}],
                }
            ],
            "pagination": {"items": 1},
        }
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            query = RecordQuery(artist="Pink Floyd", album="Dark Side of the Moon")
            results = await service.search_releases(query)

            assert len(results) == 1
            assert "Pink Floyd" in results[0]["title"]

    @pytest.mark.asyncio
    async def test_search_with_fallback(self):
        """Test fallback search when initial search fails."""
        service = DiscogsService(user_token="test_token")

        # Mock empty first response, then successful fallback
        empty_response = Mock()
        empty_response.json.return_value = {"results": [], "pagination": {"items": 0}}
        empty_response.raise_for_status.return_value = None

        fallback_response = Mock()
        fallback_response.json.return_value = {
            "results": [{"title": "Pink Floyd - Dark Side Of The Moon"}],
            "pagination": {"items": 1},
        }
        fallback_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            # Return empty first, then fallback results
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=[empty_response, fallback_response]
            )

            query = RecordQuery(artist="Pink Floyd", album="Dark Side of the Moon")
            results = await service.search_releases(query)

            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_release_details(self):
        """Test fetching release details."""
        service = DiscogsService(user_token="test_token")

        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 123,
            "title": "Pink Floyd - Dark Side Of The Moon",
            "artists": [{"name": "Pink Floyd"}],
            "tracklist": [],
        }
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            details = await service.get_release_details(123)

            assert details["id"] == 123
            assert "Pink Floyd" in details["title"]

    @pytest.mark.asyncio
    async def test_search_and_rank_integration(self):
        """Test the full search and rank pipeline."""
        service = DiscogsService(user_token="test_token")

        # Mock LLM service
        mock_llm = Mock()
        mock_query = RecordQuery(
            artist="Elliott Smith",
            album="Figure 8",
            variant_descriptors=VariantDescriptors(vinyl_color="red"),
        )
        mock_llm.parse_record_description.return_value = mock_query

        # Mock Discogs response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Elliott Smith - Figure 8",
                    "year": "2000",
                    "catno": "TEST123",
                    "formats": [{"name": "Vinyl", "text": "Red Vinyl"}],
                }
            ],
            "pagination": {"items": 1},
        }
        mock_response.raise_for_status.return_value = None

        # Mock LLM ranking
        mock_llm.rank_results.return_value = [
            {
                "release": {"title": "Elliott Smith - Figure 8"},
                "relevance_score": 0.9,
                "match_explanation": "Great match",
            }
        ]

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            with patch(
                "cxz.utils.record_parser.parse_record_description",
                return_value=mock_query,
            ):

                results = await service.search_and_rank(
                    "elliott smith figure 8 red vinyl", mock_llm
                )

                assert len(results) == 1
                assert results[0]["relevance_score"] == 0.9

    def test_validate_credentials_sync(self):
        """Test credential validation (sync version)."""
        service = DiscogsService(user_token="test_token")

        # Mock successful validation
        with patch.object(
            service, "_test_credentials", return_value=asyncio.coroutine(lambda: True)()
        ):
            assert service.validate_credentials() == True

    @pytest.mark.asyncio
    async def test_validate_credentials_async(self):
        """Test credential validation (async version)."""
        service = DiscogsService(user_token="test_token")

        mock_response = Mock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            is_valid = await service._test_credentials()
            assert is_valid == True
