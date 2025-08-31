"""High-level search service that coordinates LLM parsing, Discogs API, and ranking."""

import asyncio
import logging
from typing import List, Dict, Any, Optional

from cxz.api.discogs_service import DiscogsService
from cxz.api.llm_service import LLMService
from cxz.models.record import RecordQuery, RankedResult
from cxz.utils.record_parser import parse_record_description

logger = logging.getLogger(__name__)


class SearchService:
    """Comprehensive search service for vinyl records."""

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        discogs_service: Optional[DiscogsService] = None,
    ):
        """Initialize the search service.

        Args:
            llm_service: Optional LLM service instance
            discogs_service: Optional Discogs service instance
        """
        self.llm_service = llm_service or LLMService()
        self.discogs_service = discogs_service or DiscogsService()

    async def search(
        self, description: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for vinyl records using natural language description.

        Args:
            description: Natural language description (e.g. "Pink Floyd Dark Side red vinyl")
            max_results: Maximum number of results to return

        Returns:
            List of ranked search results with relevance scores

        Raises:
            ValueError: If search fails or description is invalid
        """
        if not description.strip():
            raise ValueError("Search description cannot be empty")

        logger.info(f"Starting search for: '{description}'")

        try:
            # Step 1: Parse natural language into structured query
            logger.info("Parsing description with LLM...")
            query = parse_record_description(description, self.llm_service)
            logger.info(
                f"Parsed query - Artist: {query.artist}, Album: {query.album}, Confidence: {query.confidence:.2f}"
            )

            # Step 2: Search Discogs API using structured query
            logger.info("Searching Discogs API...")
            search_results = await self.discogs_service.search_releases(
                query, max_results * 2
            )
            logger.info(f"Found {len(search_results)} Discogs results")

            if not search_results:
                logger.warning("No results found from Discogs API")
                return []

            # Step 3: Rank results using LLM (especially for variant matching)
            logger.info("Ranking results with LLM...")
            ranked_results = self.llm_service.rank_results(
                query, search_results, description
            )
            final_results = ranked_results[:max_results]

            logger.info(f"Returning {len(final_results)} ranked results")

            # Log top result for debugging
            if final_results:
                top_result = final_results[0]
                logger.info(
                    f"Top result: {top_result['release'].get('title', 'Unknown')} "
                    f"(score: {top_result['relevance_score']:.3f})"
                )

            return final_results

        except Exception as e:
            logger.error(f"Search failed for '{description}': {e}")
            raise ValueError(f"Search failed: {e}")

    async def search_with_details(
        self,
        description: str,
        max_results: int = 10,
        include_full_details: bool = False,
    ) -> List[Dict[str, Any]]:
        """Search with option to include full release details.

        Args:
            description: Natural language description
            max_results: Maximum results to return
            include_full_details: If True, fetches full release details for each result

        Returns:
            List of ranked results, optionally with full details
        """
        results = await self.search(description, max_results)

        if not include_full_details:
            return results

        # Fetch full details for each result
        logger.info("Fetching full details for top results...")
        detailed_results = []

        for result in results:
            try:
                release_id = result["release"].get("id")
                if release_id:
                    full_details = await self.discogs_service.get_release_details(
                        release_id
                    )
                    if full_details:
                        result["full_details"] = full_details

                detailed_results.append(result)

            except Exception as e:
                logger.warning(f"Failed to fetch details for release {release_id}: {e}")
                detailed_results.append(result)  # Include without full details

        return detailed_results

    def get_search_preview(self, description: str) -> Dict[str, Any]:
        """Get a preview of how the search would be structured without actually searching.

        Args:
            description: Natural language description

        Returns:
            Dictionary with parsed query and search strategy
        """
        try:
            query = parse_record_description(description, self.llm_service)

            from cxz.utils.discogs_query import (
                build_discogs_search_params,
                build_fallback_query,
                should_use_variant_ranking,
                get_core_search_confidence,
            )

            search_params = build_discogs_search_params(query)
            fallback_query = build_fallback_query(query)
            will_use_variant_ranking = should_use_variant_ranking(query)
            search_confidence = get_core_search_confidence(query)

            return {
                "parsed_query": query.model_dump(),
                "discogs_search_params": search_params,
                "fallback_query": fallback_query,
                "will_use_variant_ranking": will_use_variant_ranking,
                "search_confidence": search_confidence,
                "has_variant_descriptors": bool(
                    query.variant_descriptors
                    and any(
                        v
                        for v in query.variant_descriptors.model_dump().values()
                        if v is not None and v != [] and v != ""
                    )
                ),
            }

        except Exception as e:
            return {"error": str(e)}

    def validate_services(self) -> Dict[str, bool]:
        """Validate that all services are properly configured.

        Returns:
            Dictionary with service validation status
        """
        validation_results = {}

        # Test LLM service
        try:
            test_query = self.llm_service.parse_record_description("Pink Floyd test")
            validation_results["llm_service"] = isinstance(test_query, RecordQuery)
        except Exception as e:
            logger.error(f"LLM service validation failed: {e}")
            validation_results["llm_service"] = False

        # Test Discogs service
        try:
            validation_results["discogs_service"] = (
                self.discogs_service.validate_credentials()
            )
        except Exception as e:
            logger.error(f"Discogs service validation failed: {e}")
            validation_results["discogs_service"] = False

        return validation_results


# Convenience functions
async def search_records(
    description: str, max_results: int = 10
) -> List[Dict[str, Any]]:
    """Convenience function for searching records.

    Args:
        description: Natural language description
        max_results: Maximum results

    Returns:
        Ranked search results
    """
    service = SearchService()
    return await service.search(description, max_results)


def preview_search(description: str) -> Dict[str, Any]:
    """Preview how a search would be structured.

    Args:
        description: Natural language description

    Returns:
        Search preview information
    """
    service = SearchService()
    return service.get_search_preview(description)
