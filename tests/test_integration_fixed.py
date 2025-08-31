#!/usr/bin/env python3
"""Final integration test for the fixed Discogs implementation."""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
load_dotenv(project_root / ".env")


async def test_fixed_implementation():
    """Test the fixed implementation."""
    print("🔧 Testing Fixed Discogs Integration\n")

    # Check environment variables
    if not os.getenv("DISCOGS_USER_TOKEN"):
        print("❌ Please set DISCOGS_USER_TOKEN in your .env file")
        print("   Get token from: https://www.discogs.com/settings/developers")
        return

    if not os.getenv("GOOGLE_API_KEY"):
        print("❌ Please set GOOGLE_API_KEY in your .env file")
        print("   Get key from: https://aistudio.google.com/app/apikey")
        return

    try:
        from cxz.api.discogs_service import DiscogsService
        from cxz.api.llm_service import LLMService
        from cxz.utils.record_parser import parse_record_description
        from cxz.utils.discogs_query import build_discogs_search_params

        print("✅ All imports successful")

        # Test 1: LLM Service
        print("\n🤖 Testing LLM Service...")
        llm_service = LLMService()
        print(f"   Model: {llm_service.model_name}")
        print(f"   API Key loaded: {'Yes' if llm_service.api_key else 'No'}")

        # Test 2: Parse a query
        print("\n📝 Testing Query Parsing...")
        test_description = (
            "elliott smith figure 8 red white black 25th anniversary repress"
        )
        parsed_query = parse_record_description(test_description, llm_service)

        print(f"   Original: '{test_description}'")
        print(f"   Artist: {parsed_query.artist}")
        print(f"   Album: {parsed_query.album}")
        print(f"   Confidence: {parsed_query.confidence:.2f}")

        if parsed_query.variant_descriptors:
            variants = parsed_query.variant_descriptors.model_dump()
            variant_found = False
            for key, value in variants.items():
                if value is not None and value != [] and value != "":
                    if not variant_found:
                        print("   Variants found:")
                        variant_found = True
                    print(f"     • {key}: {value}")

        # Test 3: Build search parameters
        print("\n🔍 Testing Search Parameters...")
        search_params = build_discogs_search_params(parsed_query)
        print(f"   Discogs params: {search_params}")

        # Test 4: Test Discogs connection
        print("\n🎵 Testing Discogs Connection...")
        discogs_service = DiscogsService()

        # Test credential validation
        creds_valid = await discogs_service._test_credentials()
        print(f"   Credentials valid: {'✅' if creds_valid else '❌'}")

        if not creds_valid:
            print("   Check your DISCOGS_USER_TOKEN")
            return

        # Test 5: Actual search
        print("\n🔎 Testing Actual Search...")
        results = await discogs_service.search_releases(parsed_query, max_results=5)

        print(f"   Found {len(results)} results")

        if results:
            print("\n📀 Top Results:")
            for i, result in enumerate(results[:3], 1):
                print(f"\n   {i}. {result.get('title', 'Unknown')}")
                print(f"      Year: {result.get('year', 'Unknown')}")
                print(f"      Cat#: {result.get('catno', 'Unknown')}")

                formats = result.get("formats", [])
                if formats:
                    print("      Formats:")
                    for fmt in formats:
                        format_line = f"         • {fmt.get('name', 'Unknown')}"
                        if fmt.get("descriptions"):
                            format_line += f" - {', '.join(fmt['descriptions'])}"
                        if fmt.get("text"):
                            format_line += f" - {fmt['text']}"
                        print(format_line)
        else:
            print("   ⚠️  No results found")

        # Test 6: Full search service
        print("\n🎯 Testing Full Search Service...")
        from cxz.api.search_service import SearchService

        search_service = SearchService()
        final_results = await search_service.search(test_description, max_results=3)

        print(f"   Final ranked results: {len(final_results)}")

        if final_results:
            print("\n🏆 Ranked Results:")
            for i, result in enumerate(final_results, 1):
                release = result["release"]
                score = result["relevance_score"]
                explanation = result["match_explanation"]

                print(
                    f"\n   {i}. {release.get('title', 'Unknown')} (Score: {score:.3f})"
                )
                print(f"      Match: {explanation}")

        print("\n✅ All tests completed successfully!")

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_fixed_implementation())
