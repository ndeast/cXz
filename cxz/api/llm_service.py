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

    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        """Initialize the LLM service.

        Args:
            model_name: Name of the LLM model to use. Defaults to environment variable.
            api_key: API key to use. Defaults to environment variable.
        """
        self.model_name = model_name or os.getenv(
            "LLM_MODEL", "gemini/gemini-2.5-flash"
        )
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
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
            response = model.prompt(prompt, key=self.api_key)
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

Extract information into two categories:

1. CORE SEARCHABLE FIELDS (use these for Discogs API search):
- Artist/band name
- Album/release title  
- Track name (if specific track mentioned)
- Release year
- Genre
- Format (LP, 7", 12", etc.)
- Record label
- Catalog number
- Country of release
- Condition
- Additional search keywords

2. VARIANT DESCRIPTORS (use these for LLM matching after API results):
- Vinyl color (clear, red, blue, splatter, marble, etc.)
- Limited edition (true/false)
- Numbered edition (true/false)
- Reissue type (anniversary, deluxe, expanded, etc.)
- Special features (gatefold, booklet, poster, colored sleeve, etc.)
- Pressing plant/manufacturer
- Matrix/runout information
- Playing speed (33⅓, 45, 78 RPM)
- Record size (7", 10", 12")
- Edition details (first pressing, second pressing, etc.)

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
    "condition": null,
    "pressing_details": null,
    "variant_descriptors": {{
        "vinyl_color": null,
        "limited_edition": null,
        "numbered": null,
        "reissue_type": null,
        "special_features": [],
        "pressing_plant": null,
        "matrix_runout": null,
        "speed": null,
        "size": null,
        "edition_details": null
    }},
    "keywords": [],
    "confidence": 0.0
}}

Rules:
- Use null for missing information, not empty strings
- For boolean fields (limited_edition, numbered), use true/false or null
- For arrays (special_features, keywords), use [] if empty
- Be conservative - only extract information you're confident about
- If a field is unclear or ambiguous, use null
- Extract variant descriptors carefully as they're crucial for matching specific pressings
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

        # First add basic relevance scores and ensure IDs are preserved
        for result in results:
            # Ensure Discogs ID is preserved from search results
            if 'id' not in result and 'resource_url' in result:
                # Extract ID from resource_url (e.g., /releases/123456)
                try:
                    result['id'] = int(result['resource_url'].split('/')[-1])
                except (ValueError, IndexError):
                    result['id'] = None

        # Use batch LLM ranking if we have variant descriptors
        if self._has_variant_descriptors(query.variant_descriptors):
            try:
                return self._batch_rank_variants(query, results, original_description)
            except Exception as e:
                # Fall back to basic scoring if LLM fails
                return self._fallback_basic_ranking(query, results, original_description, f"Batch LLM ranking failed: {e}")
        else:
            # No variant descriptors - use basic scoring only
            return self._fallback_basic_ranking(query, results, original_description, "No variant descriptors specified")

    def _calculate_relevance_score(self, query: RecordQuery, result: dict) -> float:
        """Calculate a simple relevance score for a search result.

        Args:
            query: Structured query
            result: Discogs search result (actual Discogs API format)

        Returns:
            Relevance score between 0 and 1
        """
        score = 0.0
        total_weight = 0.0

        # Artist match (high weight) - extract from title since Discogs search results
        # have format "Artist - Album" in the title field
        if query.artist and "title" in result:
            title_lower = result["title"].lower()
            artist_lower = query.artist.lower()
            if artist_lower in title_lower:
                score += 0.4
            total_weight += 0.4

        # Album match (high weight) - also from title field
        if query.album and "title" in result:
            title_lower = result["title"].lower()
            album_lower = query.album.lower()
            if album_lower in title_lower:
                score += 0.3
            total_weight += 0.3

        # Year match (medium weight)
        if query.year and "year" in result and result["year"]:
            try:
                result_year = int(result["year"])
                if abs(result_year - query.year) <= 2:  # Allow 2-year tolerance
                    score += 0.2
            except (ValueError, TypeError):
                pass  # Invalid year, skip
            total_weight += 0.2

        # Format match (low weight) - check formats array
        if query.format and "formats" in result:
            formats = result.get("formats", [])
            query_format_lower = query.format.lower()

            for fmt in formats:
                # Check format name (Vinyl, CD, etc.)
                if (
                    fmt.get("name", "").lower() == "vinyl"
                    and "vinyl" in query_format_lower
                ):
                    score += 0.05

                # Check format descriptions (LP, 7", 12", etc.)
                descriptions = fmt.get("descriptions", [])
                for desc in descriptions:
                    if query_format_lower in desc.lower():
                        score += 0.05
                        break
            total_weight += 0.1

        # Catalog number match (medium-high weight if present)
        if query.catalog_number and "catno" in result:
            if query.catalog_number.lower() == result.get("catno", "").lower():
                score += 0.25
            total_weight += 0.1  # Low weight since rarely specified

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

    def _has_variant_descriptors(self, variant_descriptors) -> bool:
        """Check if the query has meaningful variant descriptors."""
        if not variant_descriptors:
            return False

        # Check if any field has a meaningful value
        descriptor_dict = (
            variant_descriptors.model_dump()
            if hasattr(variant_descriptors, "model_dump")
            else variant_descriptors.__dict__
        )

        for key, value in descriptor_dict.items():
            if value is not None and value != [] and value != "":
                return True
        return False

    def _llm_rank_variant(
        self, query: RecordQuery, result: dict, original_description: str
    ) -> tuple[float, str]:
        """Use LLM to rank a result based on variant descriptors.

        Args:
            query: Structured query with variant descriptors
            result: Discogs search result
            original_description: Original user query

        Returns:
            Tuple of (score, explanation) where score is 0-1
        """
        prompt = self._build_variant_ranking_prompt(query, result, original_description)

        try:
            model = self._get_model()
            response = model.prompt(prompt, key=self.api_key)
            result_text = response.text().strip()

            # Try to extract JSON from the response
            json_start = result_text.find("{")
            json_end = result_text.rfind("}") + 1

            if json_start == -1 or json_end <= json_start:
                return 0.0, "No valid ranking response from LLM"

            json_str = result_text[json_start:json_end]
            ranking_data = json.loads(json_str)

            score = float(ranking_data.get("relevance_score", 0.0))
            explanation = ranking_data.get("explanation", "No explanation provided")

            # Clamp score to 0-1 range
            score = max(0.0, min(1.0, score))

            return score, explanation

        except Exception as e:
            return 0.0, f"LLM variant ranking error: {e}"

    def _build_variant_ranking_prompt(
        self, query: RecordQuery, result: dict, original_description: str
    ) -> str:
        """Build prompt for LLM variant ranking."""

        # Extract variant descriptors
        variant_info = []
        if hasattr(query.variant_descriptors, "model_dump"):
            descriptors = query.variant_descriptors.model_dump()
        else:
            descriptors = query.variant_descriptors.__dict__

        for key, value in descriptors.items():
            if value is not None and value != [] and value != "":
                variant_info.append(f"- {key}: {value}")

        variant_text = (
            "\n".join(variant_info)
            if variant_info
            else "No specific variant requirements"
        )

        # Extract detailed format information from Discogs result
        format_details = []
        formats = result.get("formats", [])

        for fmt in formats:
            format_info = f"Format: {fmt.get('name', 'Unknown')}"
            if fmt.get("qty"):
                format_info += f" (Qty: {fmt['qty']})"
            if fmt.get("descriptions"):
                format_info += f" - Descriptions: {', '.join(fmt['descriptions'])}"
            if fmt.get("text"):  # This is where the key variant info lives!
                format_info += f" - Details: {fmt['text']}"
            format_details.append(format_info)

        format_text = (
            "\n".join(format_details) if format_details else "No format information"
        )

        # Basic result info
        result_title = result.get("title", "Unknown Title")
        result_year = result.get("year", "Unknown Year")
        result_catno = result.get("catno", "Unknown")

        return f"""You are a vinyl record expert. Compare a user's variant requirements against a Discogs search result to determine how well they match.

USER'S ORIGINAL QUERY: "{original_description}"

USER'S VARIANT REQUIREMENTS:
{variant_text}

DISCOGS SEARCH RESULT TO EVALUATE:
Title: {result_title}
Year: {result_year}
Catalog Number: {result_catno}

DETAILED FORMAT INFORMATION:
{format_text}

Your task: Analyze how well this Discogs result matches the user's variant requirements (vinyl color, limited edition, pressing details, etc.). The core album/artist matching is handled separately.

Pay special attention to:
- Format "Details" or "text" fields which often contain vinyl color, edition info
- Descriptions like "Limited Edition", "Deluxe Edition", "Reissue", "Anniversary"  
- Vinyl colors mentioned in format details (e.g. "Tri-Color White, Black, Red")
- Special edition information (25th Anniversary, numbered, etc.)
- Physical characteristics (gatefold, booklet, poster, etc.)

Return your analysis as JSON:
{{
    "relevance_score": 0.85,
    "explanation": "Strong match - format details mention 'Tri-Color White, Black, Red' matching red/white/black request, '25th Anniversary Edition' matches anniversary requirement",
    "matching_aspects": ["vinyl_color", "reissue_type"],
    "missing_aspects": []
}}

Rules:
- Score from 0.0 (no match) to 1.0 (perfect match)
- Focus ONLY on variant descriptors, not basic artist/album matching
- Be specific about what matches and what doesn't
- Look carefully at format text/details fields for variant information
- If no variant requirements were specified, return score 0.5
- If result has no variant info to compare against, return score 0.3

JSON Response:"""

    def _calculate_basic_relevance_score(
        self, query: RecordQuery, result: dict
    ) -> float:
        """Calculate basic relevance score without variant descriptors."""
        return self._calculate_relevance_score(query, result)

    def _generate_combined_explanation(
        self,
        query: RecordQuery,
        result: dict,
        basic_score: float,
        variant_score: float,
        variant_explanation: str,
    ) -> str:
        """Generate combined explanation for match quality."""
        basic_explanation = self._generate_match_explanation(query, result, basic_score)

        if variant_score > 0 and variant_explanation:
            return f"{basic_explanation} | Variant match: {variant_explanation}"
        else:
            return basic_explanation

    def _batch_rank_variants(
        self, query: RecordQuery, results: list, original_description: str
    ) -> list:
        """Batch rank all results using a single LLM call.

        Args:
            query: Structured query with variant descriptors
            results: List of Discogs search results
            original_description: Original user query

        Returns:
            List of ranked results with relevance scores
        """
        # Limit to top 20 results to avoid token limits
        limited_results = results[:20]
        
        prompt = self._build_batch_ranking_prompt(query, limited_results, original_description)

        try:
            model = self._get_model()
            response = model.prompt(prompt, key=self.api_key)
            result_text = response.text().strip()

            # Try to extract JSON from the response
            json_start = result_text.find("{")
            json_end = result_text.rfind("}") + 1

            if json_start == -1 or json_end <= json_start:
                raise ValueError("No valid JSON found in batch ranking response")

            json_str = result_text[json_start:json_end]
            ranking_data = json.loads(json_str)

            # Process the batch rankings
            ranked_results = []
            rankings = ranking_data.get("rankings", [])

            # Create a mapping of discogs_id to ranking for quick lookup
            ranking_map = {}
            for ranking in rankings:
                discogs_id = ranking.get("discogs_id")
                if discogs_id:
                    ranking_map[discogs_id] = ranking

            # Build final results
            for result in limited_results:
                discogs_id = result.get('id')
                basic_score = self._calculate_basic_relevance_score(query, result)
                
                if discogs_id and discogs_id in ranking_map:
                    ranking = ranking_map[discogs_id]
                    variant_score = float(ranking.get("relevance_score", 0.0))
                    variant_explanation = ranking.get("explanation", "No explanation")
                else:
                    # No LLM ranking found - use default
                    variant_score = 0.5
                    variant_explanation = "Not ranked by LLM"

                # Combine basic and variant scores (weighted average)
                final_score = (basic_score * 0.6) + (variant_score * 0.4)

                explanation = self._generate_combined_explanation(
                    query, result, basic_score, variant_score, variant_explanation
                )

                ranked_results.append({
                    "release": result,
                    "relevance_score": final_score,
                    "match_explanation": explanation,
                    "original_query": original_description,
                    "structured_query": query,
                })

            # Sort by relevance score (highest first)
            ranked_results.sort(key=lambda x: x["relevance_score"], reverse=True)
            return ranked_results[:10]  # Return top 10 results

        except Exception as e:
            # Fall back to basic ranking if batch ranking fails
            return self._fallback_basic_ranking(
                query, limited_results, original_description, f"Batch ranking error: {e}"
            )

    def _build_batch_ranking_prompt(
        self, query: RecordQuery, results: list, original_description: str
    ) -> str:
        """Build prompt for batch ranking all results at once."""

        # Extract variant descriptors
        variant_info = []
        if hasattr(query.variant_descriptors, "model_dump"):
            descriptors = query.variant_descriptors.model_dump()
        else:
            descriptors = query.variant_descriptors.__dict__

        for key, value in descriptors.items():
            if value is not None and value != [] and value != "":
                variant_info.append(f"- {key}: {value}")

        variant_text = (
            "\n".join(variant_info)
            if variant_info
            else "No specific variant requirements"
        )

        # Build results list for evaluation
        results_text = []
        for i, result in enumerate(results, 1):
            discogs_id = result.get('id', 'unknown')
            
            # Extract detailed format information
            format_details = []
            formats = result.get("formats", [])

            for fmt in formats:
                format_info = f"Format: {fmt.get('name', 'Unknown')}"
                if fmt.get("qty"):
                    format_info += f" (Qty: {fmt['qty']})"
                if fmt.get("descriptions"):
                    format_info += f" - Descriptions: {', '.join(fmt['descriptions'])}"
                if fmt.get("text"):
                    format_info += f" - Details: {fmt['text']}"
                format_details.append(format_info)

            format_text = "\n    ".join(format_details) if format_details else "No format information"
            
            result_text = f"""
{i}. DISCOGS_ID: {discogs_id}
   Title: {result.get('title', 'Unknown Title')}
   Year: {result.get('year', 'Unknown Year')}
   Catalog Number: {result.get('catno', 'Unknown')}
   Format Details:
    {format_text}"""
            
            results_text.append(result_text)

        all_results_text = "\n".join(results_text)

        return f"""You are a vinyl record expert. Compare a user's variant requirements against multiple Discogs search results to rank them by relevance. This is a BATCH ranking - evaluate ALL results at once and return scores for each.

USER'S ORIGINAL QUERY: "{original_description}"

USER'S VARIANT REQUIREMENTS:
{variant_text}

DISCOGS SEARCH RESULTS TO EVALUATE:
{all_results_text}

Your task: Analyze how well EACH result matches the user's variant requirements (vinyl color, limited edition, pressing details, etc.). The core album/artist matching is handled separately - focus ONLY on variant descriptors.

Pay special attention to:
- Format "Details" or "text" fields which often contain vinyl color, edition info
- Descriptions like "Limited Edition", "Deluxe Edition", "Reissue", "Anniversary"  
- Vinyl colors mentioned in format details (e.g. "Tri-Color White, Black, Red")
- Special edition information (25th Anniversary, numbered, etc.)
- Physical characteristics (gatefold, booklet, poster, etc.)

Return your analysis as JSON with scores for ALL results:
{{
    "rankings": [
        {{
            "discogs_id": 123456,
            "relevance_score": 0.85,
            "explanation": "Strong match - format details mention 'Tri-Color White, Black, Red' matching red/white/black request, '25th Anniversary Edition' matches anniversary requirement",
            "matching_aspects": ["vinyl_color", "reissue_type"],
            "missing_aspects": []
        }},
        {{
            "discogs_id": 789012,
            "relevance_score": 0.3,
            "explanation": "Weak match - standard black vinyl, no special edition features mentioned",
            "matching_aspects": [],
            "missing_aspects": ["vinyl_color", "reissue_type"]
        }}
    ]
}}

Rules:
- Score from 0.0 (no match) to 1.0 (perfect match) for EACH result
- Focus ONLY on variant descriptors, not basic artist/album matching
- Be specific about what matches and what doesn't for each result
- Look carefully at format text/details fields for variant information
- If no variant requirements were specified, return score 0.5 for all
- If a result has no variant info to compare against, return score 0.3
- Include ALL results in your rankings array, even if some score 0.0
- Make sure discogs_id matches exactly what was provided

JSON Response:"""

    def _fallback_basic_ranking(
        self, query: RecordQuery, results: list, original_description: str, reason: str
    ) -> list:
        """Fallback to basic relevance ranking when LLM ranking fails."""
        ranked_results = []

        for result in results:
            basic_score = self._calculate_basic_relevance_score(query, result)
            explanation = self._generate_match_explanation(query, result, basic_score)
            
            # Add fallback reason to explanation
            full_explanation = f"{explanation} | {reason}"

            ranked_results.append({
                "release": result,
                "relevance_score": basic_score,
                "match_explanation": full_explanation,
                "original_query": original_description,
                "structured_query": query,
            })

        # Sort by relevance score (highest first)
        ranked_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return ranked_results[:10]  # Return top 10 results
