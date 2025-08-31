"""Tests for record parsing functionality."""

import pytest
from unittest.mock import Mock, patch

from cxz.models.record import RecordQuery
from cxz.utils.record_parser import RecordParser, parse_record_description


class TestRecordParser:
    """Tests for the RecordParser class."""

    def test_init_with_llm_service(self):
        """Test parser initialization with provided LLM service."""
        mock_llm = Mock()
        parser = RecordParser(mock_llm)
        assert parser.llm_service is mock_llm

    def test_init_without_llm_service(self):
        """Test parser initialization without LLM service creates one."""
        with patch("cxz.utils.record_parser.LLMService") as mock_llm_class:
            parser = RecordParser()
            mock_llm_class.assert_called_once()

    def test_parse_successful(self):
        """Test successful parsing of a record description."""
        mock_llm = Mock()
        expected_query = RecordQuery(
            artist="Pink Floyd",
            album="Dark Side of the Moon",
            year=1973,
            confidence=0.8,
        )
        mock_llm.parse_record_description.return_value = expected_query

        parser = RecordParser(mock_llm)
        result = parser.parse("Pink Floyd Dark Side of the Moon 1973")

        assert result.artist == "Pink Floyd"
        assert result.album == "Dark Side of the Moon"
        assert result.year == 1973
        mock_llm.parse_record_description.assert_called_once()

    def test_parse_with_fallback_keywords(self):
        """Test parsing adds fallback keywords when main fields are empty."""
        mock_llm = Mock()
        empty_query = RecordQuery(confidence=0.2)
        mock_llm.parse_record_description.return_value = empty_query

        parser = RecordParser(mock_llm)
        result = parser.parse("obscure psychedelic rock band experimental")

        # Should have added keywords from the description
        assert len(result.keywords) > 0
        assert "obscure" in result.keywords or "psychedelic" in result.keywords

    def test_parse_format_normalization(self):
        """Test format string normalization."""
        mock_llm = Mock()
        query = RecordQuery(format="12 inch", confidence=0.7)
        mock_llm.parse_record_description.return_value = query

        parser = RecordParser(mock_llm)
        result = parser.parse("some 12 inch record")

        assert result.format == '12"'

    def test_parse_invalid_year_cleanup(self):
        """Test cleanup of unrealistic years."""
        mock_llm = Mock()
        query = RecordQuery(year=1850, confidence=0.5)  # Unrealistic year
        mock_llm.parse_record_description.return_value = query

        parser = RecordParser(mock_llm)
        result = parser.parse("old record from 1850")

        assert result.year is None

    def test_parse_propagates_llm_errors(self):
        """Test that LLM errors are propagated."""
        mock_llm = Mock()
        mock_llm.parse_record_description.side_effect = ValueError(
            "Invalid description"
        )

        parser = RecordParser(mock_llm)
        with pytest.raises(ValueError, match="Invalid description"):
            parser.parse("bad input")


def test_convenience_function():
    """Test the convenience function works correctly."""
    with patch("cxz.utils.record_parser.RecordParser") as mock_parser_class:
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        expected_query = RecordQuery(artist="Test", confidence=0.5)
        mock_parser.parse.return_value = expected_query

        result = parse_record_description("test description")

        assert result is expected_query
        mock_parser_class.assert_called_once_with(None)
        mock_parser.parse.assert_called_once_with("test description")
