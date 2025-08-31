"""LLM service for parsing record descriptions using simonw/llm with Google Gemini."""

import json
import os
from typing import Optional

import llm
from dotenv import load_dotenv
from pydantic import ValidationError

from cxz.models.record import RecordQuery

load_dotenv()


class LLMService:
    """Service for interacting with LLM to parse record descriptions."""

    def __init__(self, model_name: Optional[str] = None):
        """Initialize the LLM service.

        Args:
            model_name: Name of the LLM model to use. Defaults to environment variable.
        """
        self.model_name = model_name or os.getenv("LLM_MODEL", "gemini-1.5-flash")
        self._model = None

    def _get_model(self):
        """Get or create the LLM model instance."""
        if self._model is None:
            try:
                self._model = llm.get_model(self.model_name)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to initialize LLM model '{self.model_name}': {e}"
                )
        return self._model

    def parse_record_description(self, description: str) -> RecordQuery:
        """Parse a natural language record description into a structured query.

        Args:
            description: Natural language description of the record

        Returns:
            RecordQuery: Structured query object

        Raises:
            ValueError: If the description cannot be parsed
            RuntimeError: If there's an issue with the LLM service
        """
        if not description.strip():
            raise ValueError("Record description cannot be empty")

        prompt = self._build_parsing_prompt(description)

        try:
            model = self._get_model()
            response = model.prompt(prompt)
            result_text = response.text().strip()

            # Try to extract JSON from the response
            json_start = result_text.find("{")
            json_end = result_text.rfind("}") + 1

            if json_start == -1 or json_end <= json_start:
                raise ValueError("No valid JSON found in LLM response")

            json_str = result_text[json_start:json_end]
            parsed_data = json.loads(json_str)

            # Create RecordQuery from parsed data
            record_query = RecordQuery(**parsed_data)

            # Set confidence based on how well-formed the response is
            non_empty_fields = sum(
                1
                for field, value in record_query.model_dump().items()
                if value is not None and value != [] and value != ""
            )
            record_query.confidence = min(
                non_empty_fields / 5.0, 1.0
            )  # Normalize to 0-1

            return record_query

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}")
        except ValidationError as e:
            raise ValueError(f"Failed to validate parsed record query: {e}")
        except Exception as e:
            raise RuntimeError(f"LLM service error: {e}")

    def _build_parsing_prompt(self, description: str) -> str:
        """Build the prompt for parsing a record description.

        Args:
            description: Natural language description

        Returns:
            Formatted prompt string
        """
        return f"""You are a vinyl record expert. Parse the following natural language description of a vinyl record into structured data.

Extract information about:
- Artist/band name
- Album/release title
- Track name (if specific track mentioned)
- Release year
- Genre
- Format (LP, 7", 12", etc.)
- Record label
- Catalog number
- Country of release
- Pressing details (first pressing, reissue, etc.)
- Condition
- Additional keywords for search

User description: "{description}"

Return your response as valid JSON matching this exact structure:
{{
    "artist": null,
    "album": null,
    "track": null,
    "year": null,
    "genre": null,
    "format": null,
    "label": null,
    "catalog_number": null,
    "country": null,
    "pressing_details": null,
    "condition": null,
    "keywords": [],
    "confidence": 0.0
}}

Rules:
- Use null for missing information, not empty strings
- For keywords, extract any additional relevant search terms
- Be conservative - only extract information you're confident about
- If a field is unclear or ambiguous, use null
- Return ONLY the JSON, no additional text

JSON Response:"""

    def rank_results(
        self, query: RecordQuery, results: list, original_description: str
    ) -> list:
        """Rank Discogs search results based on relevance to the original query.

        Args:
            query: Structured query
            results: List of Discogs search results
            original_description: Original user description

        Returns:
            List of ranked results with relevance scores
        """
        if not results:
            return []

        # For now, implement a simple ranking algorithm
        # TODO: Use LLM for more sophisticated ranking
        ranked = []

        for result in results[:10]:  # Limit to top 10 for LLM ranking
            score = self._calculate_relevance_score(query, result)
            ranked.append(
                {
                    "release": result,
                    "relevance_score": score,
                    "match_explanation": self._generate_match_explanation(
                        query, result, score
                    ),
                    "original_query": original_description,
                    "structured_query": query,
                }
            )

        # Sort by relevance score (highest first)
        ranked.sort(key=lambda x: x["relevance_score"], reverse=True)
        return ranked

    def _calculate_relevance_score(self, query: RecordQuery, result: dict) -> float:
        """Calculate a simple relevance score for a search result.

        Args:
            query: Structured query
            result: Discogs search result

        Returns:
            Relevance score between 0 and 1
        """
        score = 0.0
        total_weight = 0.0

        # Artist match (high weight)
        if query.artist and "title" in result:
            title_lower = result["title"].lower()
            artist_lower = query.artist.lower()
            if artist_lower in title_lower:
                score += 0.4
            total_weight += 0.4

        # Album match (high weight)
        if query.album and "title" in result:
            title_lower = result["title"].lower()
            album_lower = query.album.lower()
            if album_lower in title_lower:
                score += 0.3
            total_weight += 0.3

        # Year match (medium weight)
        if query.year and "year" in result and result["year"]:
            if abs(int(result["year"]) - query.year) <= 2:  # Allow 2-year tolerance
                score += 0.2
            total_weight += 0.2

        # Format match (low weight)
        if query.format and "format" in result:
            formats = result.get("format", [])
            if isinstance(formats, list):
                format_str = " ".join(formats).lower()
                if query.format.lower() in format_str:
                    score += 0.1
            total_weight += 0.1

        # Normalize score
        return score / total_weight if total_weight > 0 else 0.0

    def _generate_match_explanation(
        self, query: RecordQuery, result: dict, score: float
    ) -> str:
        """Generate an explanation for why a result matches the query.

        Args:
            query: Structured query
            result: Search result
            score: Calculated relevance score

        Returns:
            Human-readable explanation
        """
        explanations = []

        if score >= 0.8:
            explanations.append("Strong match")
        elif score >= 0.5:
            explanations.append("Good match")
        elif score >= 0.3:
            explanations.append("Possible match")
        else:
            explanations.append("Weak match")

        # Add specific matching criteria
        if query.artist and "title" in result:
            title_lower = result["title"].lower()
            if query.artist.lower() in title_lower:
                explanations.append(f"artist '{query.artist}' found")

        if query.album and "title" in result:
            title_lower = result["title"].lower()
            if query.album.lower() in title_lower:
                explanations.append(f"album '{query.album}' found")

        return "; ".join(explanations)
