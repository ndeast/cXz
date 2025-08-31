#!/usr/bin/env python3
"""Test the Elliott Smith search specifically."""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from cxz.api.search_service import SearchService


async def main():
    """Test Elliott Smith search."""
    print("🎵 Testing Elliott Smith search specifically\n")

    # Check environment
    if not os.getenv("DISCOGS_USER_TOKEN"):
        print("❌ DISCOGS_USER_TOKEN not set")
        return

    if not os.getenv("GOOGLE_API_KEY"):
        print("❌ GOOGLE_API_KEY not set")
        return

    try:
        service = SearchService()

        # Test the specific Elliott Smith query
        query = "elliott smith figure 8 red white black 25th anniversary repress"
        print(f"🔍 Searching for: '{query}'\n")

        # Get search preview first
        print("📋 Search preview:")
        preview = service.get_search_preview(query)

        if "error" in preview:
            print(f"❌ Preview error: {preview['error']}")
            return

        parsed = preview["parsed_query"]
        print(f"   Artist: {parsed.get('artist')}")
        print(f"   Album: {parsed.get('album')}")
        print(f"   Discogs params: {preview['discogs_search_params']}")
        print(f"   Will use variant ranking: {preview['will_use_variant_ranking']}")

        variant_descriptors = parsed.get("variant_descriptors", {})
        if any(
            v
            for v in variant_descriptors.values()
            if v is not None and v != [] and v != ""
        ):
            print("   Variant descriptors:")
            for key, value in variant_descriptors.items():
                if value is not None and value != [] and value != "":
                    print(f"     • {key}: {value}")

        print("\n🎯 Performing actual search...")

        # Perform search
        results = await service.search(query, max_results=5)

        print(f"Found {len(results)} results\n")

        if not results:
            print("❌ No results found!")
            return

        # Display results
        for i, result in enumerate(results, 1):
            release = result["release"]
            score = result["relevance_score"]
            explanation = result["match_explanation"]

            print(f"{i}. {release.get('title', 'Unknown Title')} (Score: {score:.3f})")
            print(f"   Year: {release.get('year', 'Unknown')}")
            print(f"   Cat#: {release.get('catno', 'Unknown')}")

            formats = release.get("formats", [])
            if formats:
                print("   Formats:")
                for fmt in formats:
                    format_line = f"      • {fmt.get('name', 'Unknown')}"
                    if fmt.get("descriptions"):
                        format_line += f" - {', '.join(fmt['descriptions'])}"
                    if fmt.get("text"):
                        format_line += f" - {fmt['text']}"
                    print(format_line)

            print(f"   Match explanation: {explanation}")
            print()

        print("✅ Search completed successfully!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
