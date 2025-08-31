#!/usr/bin/env python3
"""Example script showing how to use the cXz search functionality."""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from cxz.api.search_service import SearchService, preview_search


async def main():
    """Run search examples."""
    print("🎵 cXz Vinyl Search Examples\n")

    # Check if we have required environment variables
    if not os.getenv("DISCOGS_USER_TOKEN"):
        print("❌ Please set DISCOGS_USER_TOKEN in your .env file")
        print(
            "   You can get a token from: https://www.discogs.com/settings/developers"
        )
        return

    if not os.getenv("GOOGLE_API_KEY"):
        print("❌ Please set GOOGLE_API_KEY in your .env file")
        print("   You can get an API key from: https://aistudio.google.com/app/apikey")
        return

    # Check if we have the right model configured
    model_name = os.getenv("LLM_MODEL", "gemini/gemini-2.5-flash")
    if not model_name.startswith("gemini/"):
        print("❌ Please set LLM_MODEL=gemini/gemini-2.5-flash in your .env file")
        print("   This requires the llm-gemini plugin: uv add llm-gemini")
        return

    # Initialize search service
    try:
        search_service = SearchService()

        # Validate services
        print("🔧 Validating services...")
        validation = search_service.validate_services()
        for service, is_valid in validation.items():
            status = "✅" if is_valid else "❌"
            print(f"   {status} {service}")

        if not all(validation.values()):
            print(
                "❌ Some services failed validation. Please check your configuration."
            )
            return

        print("\n" + "=" * 50)

    except Exception as e:
        print(f"❌ Failed to initialize search service: {e}")
        return

    # Example searches
    example_queries = [
        "Pink Floyd Dark Side of the Moon original pressing",
        "elliott smith figure 8 red white black 25th anniversary repress",
        "Radiohead OK Computer limited edition vinyl",
        "Miles Davis Kind of Blue blue note pressing",
        "The Beatles White Album numbered copy",
    ]

    for i, query in enumerate(example_queries, 1):
        print(f"\n🔍 Example {i}: '{query}'")
        print("-" * 50)

        try:
            # Show search preview first
            print("📋 Search Preview:")
            preview = preview_search(query)

            if "error" in preview:
                print(f"   ❌ Preview failed: {preview['error']}")
                continue

            parsed = preview["parsed_query"]
            print(f"   Artist: {parsed.get('artist', 'Not specified')}")
            print(f"   Album: {parsed.get('album', 'Not specified')}")
            print(f"   Confidence: {parsed.get('confidence', 0):.2f}")

            variant_descriptors = parsed.get("variant_descriptors", {})
            if any(
                v
                for v in variant_descriptors.values()
                if v is not None and v != [] and v != ""
            ):
                print("   Variant descriptors found:")
                for key, value in variant_descriptors.items():
                    if value is not None and value != [] and value != "":
                        print(f"     • {key}: {value}")

            print(
                f"   Will use LLM ranking: {'Yes' if preview['will_use_variant_ranking'] else 'No'}"
            )

            # Perform actual search
            print("\n🎯 Search Results:")
            results = await search_service.search(query, max_results=3)

            if not results:
                print("   No results found")
                continue

            for j, result in enumerate(results, 1):
                release = result["release"]
                score = result["relevance_score"]
                explanation = result["match_explanation"]

                print(
                    f"\n   {j}. {release.get('title', 'Unknown Title')} ({score:.3f})"
                )
                print(f"      📅 Year: {release.get('year', 'Unknown')}")
                print(f"      🏷️  Cat#: {release.get('catno', 'Unknown')}")

                # Show format info
                formats = release.get("formats", [])
                if formats:
                    print("      💿 Formats:")
                    for fmt in formats:
                        format_line = f"         • {fmt.get('name', 'Unknown')}"
                        if fmt.get("descriptions"):
                            format_line += f" - {', '.join(fmt['descriptions'])}"
                        if fmt.get("text"):
                            format_line += f" - {fmt['text']}"
                        print(format_line)

                print(f"      🤔 Match: {explanation}")

        except Exception as e:
            print(f"   ❌ Search failed: {e}")

        print("\n" + "=" * 50)

    print("\n✅ All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
