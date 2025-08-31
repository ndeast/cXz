#!/usr/bin/env python3
"""Debug script to test Discogs API integration step by step."""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from cxz.api.discogs_service import DiscogsService
from cxz.api.llm_service import LLMService
from cxz.utils.record_parser import parse_record_description
from cxz.utils.discogs_query import build_discogs_search_params, build_fallback_query


async def test_discogs_connection():
    """Test basic Discogs API connection."""
    print("🔧 Testing Discogs API connection...")

    if not os.getenv("DISCOGS_USER_TOKEN"):
        print("❌ DISCOGS_USER_TOKEN not set")
        return False

    try:
        service = DiscogsService()

        # Test credentials
        is_valid = await service._test_credentials()
        print(f"   API credentials valid: {'✅' if is_valid else '❌'}")

        if not is_valid:
            print("   Check your DISCOGS_USER_TOKEN")
            return False

        return True

    except Exception as e:
        print(f"❌ Discogs connection failed: {e}")
        return False


async def test_simple_search():
    """Test a simple Discogs search without LLM."""
    print("\n🔍 Testing simple Discogs search...")

    try:
        service = DiscogsService()

        # Test with very basic parameters
        simple_params = {
            "q": "Pink Floyd Dark Side Moon",
            "type": "release",
            "per_page": 5,
        }

        print(f"   Search params: {simple_params}")
        results = await service._search_with_params(simple_params)

        print(f"   Found {len(results)} results")

        if results:
            for i, result in enumerate(results[:3]):
                print(f"   {i+1}. {result.get('title', 'Unknown')}")
                print(f"      Year: {result.get('year', 'Unknown')}")
                print(
                    f"      Formats: {[f.get('name') for f in result.get('formats', [])]}"
                )
        else:
            print("   No results found")

        return len(results) > 0

    except Exception as e:
        print(f"❌ Simple search failed: {e}")
        return False


async def test_structured_search():
    """Test search with structured parameters."""
    print("\n📋 Testing structured search...")

    try:
        # Test LLM parsing first
        if not os.getenv("GOOGLE_API_KEY"):
            print("⚠️  GOOGLE_API_KEY not set, using mock query")
            from cxz.models.record import RecordQuery

            query = RecordQuery(artist="Pink Floyd", album="Dark Side of the Moon")
        else:
            llm_service = LLMService()
            query = parse_record_description(
                "Pink Floyd Dark Side of the Moon", llm_service
            )
            print(f"   LLM parsed - Artist: '{query.artist}', Album: '{query.album}'")

        # Build Discogs search parameters
        params = build_discogs_search_params(query)
        print(f"   Discogs params: {params}")

        service = DiscogsService()
        results = await service._search_with_params(params)

        print(f"   Found {len(results)} results with structured search")

        if not results:
            # Try fallback
            fallback_query = build_fallback_query(query)
            fallback_params = {"q": fallback_query, "type": "release", "per_page": 5}
            print(f"   Trying fallback: {fallback_params}")
            results = await service._search_with_params(fallback_params)
            print(f"   Fallback found {len(results)} results")

        if results:
            for i, result in enumerate(results[:2]):
                print(f"   {i+1}. {result.get('title', 'Unknown')}")

        return len(results) > 0

    except Exception as e:
        print(f"❌ Structured search failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_elliott_smith_search():
    """Test the specific Elliott Smith example."""
    print("\n🎵 Testing Elliott Smith example...")

    try:
        service = DiscogsService()

        # Try the exact Elliott Smith search
        elliott_params = {
            "q": "Elliott Smith Figure 8",
            "type": "release",
            "per_page": 10,
        }

        print(f"   Elliott Smith params: {elliott_params}")
        results = await service._search_with_params(elliott_params)

        print(f"   Found {len(results)} Elliott Smith results")

        if results:
            for i, result in enumerate(results[:3]):
                print(f"\n   {i+1}. {result.get('title', 'Unknown')}")
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

        return len(results) > 0

    except Exception as e:
        print(f"❌ Elliott Smith search failed: {e}")
        return False


async def main():
    """Run all debugging tests."""
    print("🛠️  Debugging Discogs Integration\n")

    # Test 1: Basic connection
    connection_ok = await test_discogs_connection()
    if not connection_ok:
        print("\n❌ Cannot proceed without valid Discogs connection")
        return

    # Test 2: Simple search
    simple_ok = await test_simple_search()

    # Test 3: Structured search
    structured_ok = await test_structured_search()

    # Test 4: Elliott Smith specific
    elliott_ok = await test_elliott_smith_search()

    # Summary
    print(f"\n📊 Test Summary:")
    print(f"   Connection: {'✅' if connection_ok else '❌'}")
    print(f"   Simple search: {'✅' if simple_ok else '❌'}")
    print(f"   Structured search: {'✅' if structured_ok else '❌'}")
    print(f"   Elliott Smith search: {'✅' if elliott_ok else '❌'}")

    if all([connection_ok, simple_ok, structured_ok, elliott_ok]):
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️  Some tests failed - see details above")


if __name__ == "__main__":
    asyncio.run(main())
