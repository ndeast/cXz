"""Test script to validate Gemini 2.5 Flash configuration."""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from cxz.api.llm_service import LLMService


def test_gemini_model_name():
    """Test that the LLM service uses the correct Gemini model."""
    # Ensure we have API key for tests
    if not os.getenv("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = "test-key-for-config-test"

    # Test with environment variable
    os.environ["LLM_MODEL"] = "gemini/gemini-2.5-flash"
    service = LLMService()
    assert service.model_name == "gemini/gemini-2.5-flash"

    # Test with explicit model name
    service_explicit = LLMService(model_name="gemini/gemini-2.5-flash")
    assert service_explicit.model_name == "gemini/gemini-2.5-flash"

    # Test default fallback
    if "LLM_MODEL" in os.environ:
        del os.environ["LLM_MODEL"]
    service_default = LLMService()
    assert service_default.model_name == "gemini/gemini-2.5-flash"

    print("✅ Model name configuration test passed")


def test_api_key_requirement():
    """Test that the LLM service requires a Google API key."""
    # Temporarily remove API key
    original_key = os.environ.get("GOOGLE_API_KEY")
    if "GOOGLE_API_KEY" in os.environ:
        del os.environ["GOOGLE_API_KEY"]

    try:
        # Should raise ValueError without API key
        try:
            service = LLMService()
            assert False, "Should have raised ValueError for missing API key"
        except ValueError as e:
            assert "GOOGLE_API_KEY" in str(e)
            print("✅ API key requirement test passed")

    finally:
        # Restore original key
        if original_key:
            os.environ["GOOGLE_API_KEY"] = original_key


def test_gemini_integration():
    """Test basic integration with Gemini model."""
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  GOOGLE_API_KEY not set, skipping integration test")
        return

    try:
        # Test that LLM service requires API key
        service = LLMService(model_name="gemini/gemini-2.5-flash")
        assert service.api_key is not None, "API key should be loaded"

        # Test simple record parsing
        result = service.parse_record_description("Pink Floyd Dark Side of the Moon")

        assert (
            result.artist is not None or result.album is not None
        ), "Should parse at least artist or album"
        print(
            f"✅ Successfully parsed: Artist='{result.artist}', Album='{result.album}'"
        )
        print(f"   Confidence: {result.confidence:.2f}")

    except Exception as e:
        print(f"❌ Gemini integration test failed: {e}")
        raise


def test_variant_parsing():
    """Test parsing with variant descriptors."""
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  GOOGLE_API_KEY not set, skipping variant parsing test")
        return

    try:
        service = LLMService(model_name="gemini/gemini-2.5-flash")

        # Test variant descriptor parsing
        result = service.parse_record_description(
            "elliott smith figure 8 red white black vinyl 25th anniversary repress limited edition"
        )

        print(f"✅ Variant parsing test:")
        print(f"   Artist: {result.artist}")
        print(f"   Album: {result.album}")
        print(f"   Confidence: {result.confidence:.2f}")

        # Check variant descriptors
        variants = result.variant_descriptors
        print(f"   Vinyl Color: {variants.vinyl_color}")
        print(f"   Reissue Type: {variants.reissue_type}")
        print(f"   Limited Edition: {variants.limited_edition}")

        # Should have extracted some variant info
        has_variants = any(
            [variants.vinyl_color, variants.reissue_type, variants.limited_edition]
        )
        assert has_variants, "Should extract some variant descriptors"

    except Exception as e:
        print(f"❌ Variant parsing test failed: {e}")
        raise


if __name__ == "__main__":
    print("🧪 Testing Gemini 2.5 Flash Configuration\n")

    test_gemini_model_name()
    print()

    test_api_key_requirement()
    print()

    test_gemini_integration()
    print()

    test_variant_parsing()
    print()

    print("🎉 All tests passed!")
