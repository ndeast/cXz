"""Data models for vinyl records and search queries."""

from typing import List, Optional

from pydantic import BaseModel, Field


class RecordQuery(BaseModel):
    """Structured query for searching vinyl records."""

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
    pressing_details: Optional[str] = Field(
        None, description="Pressing details (first pressing, reissue, etc.)"
    )
    condition: Optional[str] = Field(None, description="Record condition if mentioned")
    keywords: List[str] = Field(
        default_factory=list, description="Additional search keywords"
    )
    confidence: float = Field(0.0, description="Confidence in the parsed query (0-1)")


class DiscogsRelease(BaseModel):
    """Discogs API release data model."""

    id: int
    title: str
    artists: List[str]
    year: Optional[int] = None
    genres: List[str] = Field(default_factory=list)
    styles: List[str] = Field(default_factory=list)
    formats: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    country: Optional[str] = None
    thumb: Optional[str] = None
    uri: Optional[str] = None
    resource_url: Optional[str] = None
    master_id: Optional[int] = None
    master_url: Optional[str] = None


class RankedResult(BaseModel):
    """LLM-ranked search result."""

    release: DiscogsRelease
    relevance_score: float = Field(description="LLM relevance score (0-1)")
    match_explanation: str = Field(
        description="Explanation of why this matches the query"
    )
    original_query: str = Field(description="Original user query")
    structured_query: RecordQuery = Field(description="Parsed structured query")
