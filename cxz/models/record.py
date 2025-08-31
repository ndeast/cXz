"""Data models for vinyl records and search queries."""

from typing import List, Optional

from pydantic import BaseModel, Field


class VariantDescriptors(BaseModel):
    """Descriptors for vinyl variants that aren't searchable via Discogs API directly."""

    vinyl_color: Optional[str] = Field(
        None, description="Color of vinyl (clear, red, splatter, etc.)"
    )
    limited_edition: Optional[bool] = Field(
        None, description="Whether it's a limited edition"
    )
    numbered: Optional[bool] = Field(None, description="Whether it's numbered")
    reissue_type: Optional[str] = Field(
        None, description="Type of reissue (anniversary, deluxe, etc.)"
    )
    special_features: List[str] = Field(
        default_factory=list, description="Special features (gatefold, booklet, etc.)"
    )
    pressing_plant: Optional[str] = Field(
        None, description="Pressing plant or manufacturer"
    )
    matrix_runout: Optional[str] = Field(
        None, description="Matrix or runout information"
    )
    speed: Optional[str] = Field(None, description="Playing speed (33⅓, 45, 78 RPM)")
    size: Optional[str] = Field(None, description='Record size (7", 10", 12")')
    edition_details: Optional[str] = Field(
        None, description="Edition details (first press, second press, etc.)"
    )


class RecordQuery(BaseModel):
    """Structured query for searching vinyl records."""

    # Core searchable fields (good for Discogs API)
    artist: Optional[str] = Field(None, description="Artist or band name")
    album: Optional[str] = Field(None, description="Album or release title")
    track: Optional[str] = Field(None, description="Specific track name if mentioned")
    year: Optional[int] = Field(None, description="Release year if mentioned")
    genre: Optional[str] = Field(None, description="Musical genre")
    format: Optional[str] = Field(
        None, description='Physical format (LP, 7", 12", etc.)'
    )
    label: Optional[str] = Field(None, description="Record label")
    catalog_number: Optional[str] = Field(None, description="Catalog number")
    country: Optional[str] = Field(None, description="Country of release")
    condition: Optional[str] = Field(None, description="Record condition if mentioned")

    # Variant descriptors for LLM comparison
    variant_descriptors: VariantDescriptors = Field(
        default_factory=VariantDescriptors,
        description="Vinyl variant details for LLM matching",
    )

    # General fields
    keywords: List[str] = Field(
        default_factory=list, description="Additional search keywords"
    )
    confidence: float = Field(0.0, description="Confidence in the parsed query (0-1)")

    # Store original pressing details for backward compatibility
    pressing_details: Optional[str] = Field(
        None, description="Raw pressing details text for fallback"
    )


class DiscogsFormat(BaseModel):
    """Discogs format information."""

    name: str  # e.g. "Vinyl"
    qty: Optional[str] = None  # e.g. "2"
    text: Optional[str] = (
        None  # e.g. "Tri-Color White, Black, Red [Figure 8 Mural], 25th Anniversary Edition"
    )
    descriptions: List[str] = Field(
        default_factory=list
    )  # e.g. ["LP", "45 RPM", "Album", "Reissue"]


class DiscogsCommunity(BaseModel):
    """Discogs community stats."""

    want: Optional[int] = None
    have: Optional[int] = None


class DiscogsRelease(BaseModel):
    """Discogs API release/search result data model."""

    # Core identifiers
    id: Optional[int] = None  # Only in full release, not search results
    master_id: Optional[int] = None
    master_url: Optional[str] = None
    uri: Optional[str] = None
    resource_url: Optional[str] = None

    # Basic info
    title: str
    catno: Optional[str] = None  # Catalog number
    year: Optional[int] = None
    country: Optional[str] = None

    # Media info
    formats: List[DiscogsFormat] = Field(default_factory=list)
    format_quantity: Optional[int] = None

    # Images
    thumb: Optional[str] = None
    cover_image: Optional[str] = None

    # Community data
    community: Optional[DiscogsCommunity] = None

    # Additional fields that might be present in full release data
    artists: List[str] = Field(default_factory=list)
    genres: List[str] = Field(default_factory=list)
    styles: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)


class RankedResult(BaseModel):
    """LLM-ranked search result."""

    release: DiscogsRelease
    relevance_score: float = Field(description="LLM relevance score (0-1)")
    match_explanation: str = Field(
        description="Explanation of why this matches the query"
    )
    original_query: str = Field(description="Original user query")
    structured_query: RecordQuery = Field(description="Parsed structured query")
