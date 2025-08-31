"""Test with the real Elliott Smith Discogs example data."""

import pytest
from unittest.mock import Mock

from cxz.api.llm_service import LLMService
from cxz.models.record import RecordQuery, VariantDescriptors
from cxz.utils.record_parser import RecordParser


# Real Discogs API response example
ELLIOTT_SMITH_DISCOGS_RESULT = {
    "master_id": 6163,
    "master_url": "https://api.discogs.com/masters/6163",
    "uri": "/release/34192345-Elliott-Smith-Figure-8",
    "catno": "602475813293",
    "title": "Elliott Smith - Figure 8",
    "thumb": "https://i.discogs.com/yXuRo1nU0sDjqGxNyaomnJsnniBVYDwEAPndJiU1qnM/rs:fit/g:sm/q:40/h:150/w:150/czM6Ly9kaXNjb2dz/LWRhdGFiYXNl/LWltYWdlcy9SLTM0/MTkyMzQ1LTE3NDky/MTgzNDEtMzkzOC5q/cGVn.jpeg",
    "cover_image": "https://i.discogs.com/44vvpAh512yEEdzqZPb5YrDigwknCfqUBfPwKrepDNs/rs:fit/g:sm/q:90/h:592/w:600/czM6Ly9kaXNjb2dz/LWRhdGFiYXNl/LWltYWdlcy9SLTM0/MTkyMzQ1LTE3NDky/MTgzNDEtMzkzOC5q/cGVn.jpeg",
    "resource_url": "https://api.discogs.com/releases/34192345",
    "community": {"want": 224, "have": 984},
    "format_quantity": 3,
    "formats": [
        {
            "name": "Vinyl",
            "qty": "2",
            "descriptions": ["LP", "45 RPM", "Album", "Reissue"],
        },
        {"name": "Vinyl", "qty": "1", "descriptions": ["LP", "45 RPM"]},
        {
            "name": "All Media",
            "qty": "1",
            "text": "Tri-Color White, Black, Red [Figure 8 Mural], 25th Anniversary Edition",
            "descriptions": ["Deluxe Edition", "Limited Edition"],
        },
    ],
}


class TestElliottSmithExample:
    """Test the LLM integration with real Discogs data."""

    def test_parse_elliott_smith_query(self):
        """Test parsing of Elliott Smith query with variants."""
        # Mock the LLM service to return expected parsing
        mock_llm = Mock()
        expected_query = RecordQuery(
            artist="Elliott Smith",
            album="Figure 8",
            variant_descriptors=VariantDescriptors(
                vinyl_color="red white black",
                reissue_type="25th anniversary",
                edition_details="repress",
            ),
            confidence=0.8,
        )
        mock_llm.parse_record_description.return_value = expected_query

        parser = RecordParser(mock_llm)
        result = parser.parse(
            "elliott smith figure 8 red white black 25th anniversary repress"
        )

        assert result.artist == "Elliott Smith"
        assert result.album == "Figure 8"
        assert result.variant_descriptors.vinyl_color == "red white black"
        assert result.variant_descriptors.reissue_type == "25th anniversary"
        assert result.variant_descriptors.edition_details == "repress"

    def test_basic_relevance_score_elliott_smith(self):
        """Test basic relevance scoring with Elliott Smith data."""
        llm_service = LLMService()

        query = RecordQuery(artist="Elliott Smith", album="Figure 8")

        score = llm_service._calculate_relevance_score(
            query, ELLIOTT_SMITH_DISCOGS_RESULT
        )

        # Should score high for artist + album match
        assert score > 0.7  # Both artist and album should match in title

    def test_variant_descriptor_detection(self):
        """Test that variant descriptors are properly detected."""
        llm_service = LLMService()

        query = RecordQuery(
            artist="Elliott Smith",
            album="Figure 8",
            variant_descriptors=VariantDescriptors(
                vinyl_color="red white black", reissue_type="25th anniversary"
            ),
        )

        assert llm_service._has_variant_descriptors(query.variant_descriptors) == True

        # Test empty variant descriptors
        empty_query = RecordQuery(artist="Elliott Smith", album="Figure 8")
        assert (
            llm_service._has_variant_descriptors(empty_query.variant_descriptors)
            == False
        )

    def test_build_variant_ranking_prompt(self):
        """Test that the variant ranking prompt extracts format information correctly."""
        llm_service = LLMService()

        query = RecordQuery(
            artist="Elliott Smith",
            album="Figure 8",
            variant_descriptors=VariantDescriptors(
                vinyl_color="red white black", reissue_type="25th anniversary"
            ),
        )

        prompt = llm_service._build_variant_ranking_prompt(
            query,
            ELLIOTT_SMITH_DISCOGS_RESULT,
            "elliott smith figure 8 red white black 25th anniversary repress",
        )

        # Check that the prompt includes the key variant information from Discogs
        assert "Tri-Color White, Black, Red" in prompt
        assert "25th Anniversary Edition" in prompt
        assert "Limited Edition" in prompt
        assert "Deluxe Edition" in prompt
        assert "Reissue" in prompt

        # Check that user requirements are included
        assert "vinyl_color: red white black" in prompt
        assert "reissue_type: 25th anniversary" in prompt

    def test_format_extraction_from_discogs_result(self):
        """Test that we properly extract all format information."""
        formats = ELLIOTT_SMITH_DISCOGS_RESULT["formats"]

        # Should have 3 format entries
        assert len(formats) == 3

        # Key variant info should be in the "All Media" format with text field
        all_media_format = formats[2]
        assert all_media_format["name"] == "All Media"
        assert "Tri-Color White, Black, Red" in all_media_format["text"]
        assert "25th Anniversary Edition" in all_media_format["text"]
        assert "Limited Edition" in all_media_format["descriptions"]
        assert "Deluxe Edition" in all_media_format["descriptions"]

    def test_mock_llm_variant_ranking(self):
        """Test LLM variant ranking with mocked response."""
        llm_service = LLMService()

        # Mock the model response
        mock_response = Mock()
        mock_response.text.return_value = """
        {
            "relevance_score": 0.95,
            "explanation": "Excellent match - Tri-Color White, Black, Red matches red/white/black request, 25th Anniversary Edition matches anniversary requirement, Reissue matches repress request",
            "matching_aspects": ["vinyl_color", "reissue_type", "edition_details"],
            "missing_aspects": []
        }
        """

        mock_model = Mock()
        mock_model.prompt.return_value = mock_response
        llm_service._model = mock_model

        query = RecordQuery(
            artist="Elliott Smith",
            album="Figure 8",
            variant_descriptors=VariantDescriptors(
                vinyl_color="red white black",
                reissue_type="25th anniversary",
                edition_details="repress",
            ),
        )

        score, explanation = llm_service._llm_rank_variant(
            query,
            ELLIOTT_SMITH_DISCOGS_RESULT,
            "elliott smith figure 8 red white black 25th anniversary repress",
        )

        assert score == 0.95
        assert "Excellent match" in explanation
        assert "Tri-Color White, Black, Red" in explanation
