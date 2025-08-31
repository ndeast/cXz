"""Utilities for building Discogs API queries from parsed record data."""

from typing import Dict, Any, List
from cxz.models.record import RecordQuery


def build_discogs_search_params(query: RecordQuery) -> Dict[str, Any]:
    """Build Discogs API search parameters from a RecordQuery.

    This function extracts only the core searchable fields that work well
    with the Discogs API, ignoring variant descriptors which should be
    handled via LLM comparison of the results.

    Args:
        query: Parsed record query

    Returns:
        Dictionary of search parameters for Discogs API
    """
    params = {}

    # Use general query parameter for better results
    query_parts = []

    if query.artist:
        query_parts.append(query.artist)

    if query.album:
        query_parts.append(query.album)

    if query.track:
        query_parts.append(query.track)

    # Build the main query string
    if query_parts:
        params["q"] = " ".join(query_parts)
    elif query.keywords:
        params["q"] = " ".join(query.keywords[:3])

    # Add specific filters where supported
    if query.year:
        params["year"] = str(query.year)

    if query.genre:
        params["genre"] = query.genre

    if query.format:
        params["format"] = query.format

    if query.label:
        params["label"] = query.label

    if query.catalog_number:
        params["catno"] = query.catalog_number

    if query.country:
        params["country"] = query.country

    # Set search type (release is most appropriate for vinyl records)
    params["type"] = "release"

    return params


def build_fallback_query(query: RecordQuery) -> str:
    """Build a simple text query for fallback search.

    Args:
        query: Parsed record query

    Returns:
        Simple text query string
    """
    parts = []

    if query.artist:
        parts.append(query.artist)

    if query.album:
        parts.append(query.album)

    if query.track:
        parts.append(query.track)

    if query.year:
        parts.append(str(query.year))

    # Add some keywords if main fields are missing
    if not parts and query.keywords:
        parts.extend(query.keywords[:3])

    return " ".join(parts)


def get_variant_search_terms(query: RecordQuery) -> List[str]:
    """Extract variant-related search terms that might help with Discogs search.

    While most variant descriptors should be handled via LLM comparison,
    some terms like "limited" or "deluxe" might appear in Discogs titles.

    Args:
        query: Parsed record query

    Returns:
        List of variant terms that could be included in search
    """
    variant_terms = []

    if not query.variant_descriptors:
        return variant_terms

    # Some variant terms that commonly appear in Discogs titles
    if query.variant_descriptors.reissue_type:
        reissue_type = query.variant_descriptors.reissue_type.lower()
        if any(
            term in reissue_type
            for term in ["anniversary", "deluxe", "expanded", "remaster"]
        ):
            variant_terms.append(query.variant_descriptors.reissue_type)

    if query.variant_descriptors.limited_edition:
        variant_terms.append("limited")

    if query.variant_descriptors.numbered:
        variant_terms.append("numbered")

    # Special features that might be in titles
    for feature in query.variant_descriptors.special_features or []:
        feature_lower = feature.lower()
        if any(term in feature_lower for term in ["gatefold", "deluxe", "box", "set"]):
            variant_terms.append(feature)

    return variant_terms


def should_use_variant_ranking(query: RecordQuery) -> bool:
    """Determine if LLM variant ranking should be used for this query.

    Args:
        query: Parsed record query

    Returns:
        True if variant ranking would be beneficial
    """
    if not query.variant_descriptors:
        return False

    # Check if any meaningful variant descriptors are present
    descriptors = query.variant_descriptors.model_dump()

    for key, value in descriptors.items():
        if value is not None and value != [] and value != "":
            return True

    return False


def get_core_search_confidence(query: RecordQuery) -> float:
    """Calculate confidence score for core searchable fields.

    Args:
        query: Parsed record query

    Returns:
        Confidence score (0-1) based on presence of core fields
    """
    core_fields = ["artist", "album", "track", "year", "genre", "format", "label"]
    present_fields = 0

    for field in core_fields:
        value = getattr(query, field, None)
        if value is not None and value != "":
            present_fields += 1

    # Artist and album are most important
    important_fields = 0
    if query.artist:
        important_fields += 2
    if query.album:
        important_fields += 2
    if query.track:
        important_fields += 1

    # Combine general field presence with important field weighting
    base_score = present_fields / len(core_fields)
    important_score = min(
        important_fields / 4, 1.0
    )  # Max 4 points for important fields

    return (base_score * 0.4) + (important_score * 0.6)
