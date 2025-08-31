"""Utility functions for parsing record descriptions."""

import logging
from typing import Optional

from cxz.api.llm_service import LLMService
from cxz.models.record import RecordQuery

logger = logging.getLogger(__name__)


class RecordParser:
    """High-level interface for parsing record descriptions."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        """Initialize the record parser.

        Args:
            llm_service: Optional LLM service instance. Creates one if not provided.
        """
        self.llm_service = llm_service or LLMService()

    def parse(self, description: str) -> RecordQuery:
        """Parse a record description into a structured query.

        Args:
            description: Natural language description of the record

        Returns:
            RecordQuery: Parsed and validated query

        Raises:
            ValueError: If the description is invalid or cannot be parsed
            RuntimeError: If there's an issue with the LLM service
        """
        try:
            logger.info(f"Parsing record description: {description[:100]}...")

            # Use LLM service to parse the description
            query = self.llm_service.parse_record_description(description)

            # Post-process and validate the query
            query = self._post_process_query(query, description)

            logger.info(
                f"Successfully parsed query with confidence {query.confidence:.2f}"
            )
            return query

        except Exception as e:
            logger.error(f"Failed to parse record description: {e}")
            raise

    def _post_process_query(
        self, query: RecordQuery, original_description: str
    ) -> RecordQuery:
        """Post-process and enhance the parsed query.

        Args:
            query: Initial parsed query
            original_description: Original description text

        Returns:
            Enhanced RecordQuery
        """
        # Add fallback keywords from original description if main fields are empty
        if not any([query.artist, query.album, query.track]):
            # Extract potential keywords from the original description
            words = original_description.lower().split()
            # Filter out common stop words
            stop_words = {
                "the",
                "a",
                "an",
                "and",
                "or",
                "but",
                "in",
                "on",
                "at",
                "to",
                "for",
                "of",
                "with",
                "by",
                "is",
                "are",
                "was",
                "were",
                "been",
                "be",
                "have",
                "has",
                "had",
                "do",
                "does",
                "did",
                "will",
                "would",
                "could",
                "should",
                "vinyl",
                "record",
                "album",
                "song",
                "music",
                "looking",
                "search",
                "find",
            }

            keywords = [
                word.strip('.,!?";:()[]{}')
                for word in words
                if len(word) > 2 and word.lower() not in stop_words
            ]

            # Limit to most relevant keywords
            if keywords and not query.keywords:
                query.keywords = keywords[:5]

        # Normalize format strings
        if query.format:
            format_mappings = {
                "lp": "LP",
                '12"': '12"',
                "12 inch": '12"',
                "twelve inch": '12"',
                '7"': '7"',
                "7 inch": '7"',
                "seven inch": '7"',
                "45": '7"',
                "single": '7"',
                "cd": "CD",
                "cassette": "Cassette",
                "tape": "Cassette",
            }

            format_lower = query.format.lower()
            for key, value in format_mappings.items():
                if key in format_lower:
                    query.format = value
                    break

        # Clean up year if it's unrealistic
        if query.year and (query.year < 1900 or query.year > 2030):
            query.year = None

        return query


def parse_record_description(
    description: str, llm_service: Optional[LLMService] = None
) -> RecordQuery:
    """Convenience function to parse a record description.

    Args:
        description: Natural language description
        llm_service: Optional LLM service instance

    Returns:
        Parsed RecordQuery
    """
    parser = RecordParser(llm_service)
    return parser.parse(description)
