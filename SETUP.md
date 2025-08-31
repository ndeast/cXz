# cXz Setup Guide

## Quick Start

### 1. Install Dependencies

```bash
# Install the project with all dependencies including llm-gemini plugin
uv sync

# The llm-gemini plugin should be automatically installed via pyproject.toml
# If you need to install it separately:
# uv add llm-gemini
```

### 2. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your API credentials
```

Required environment variables in `.env`:

```env
# Discogs API - Get token from: https://www.discogs.com/settings/developers  
DISCOGS_USER_TOKEN=your_discogs_user_token_here

# Google Gemini API - Get key from: https://aistudio.google.com/app/apikey
GOOGLE_API_KEY=your_google_api_key_here

# LLM Model Configuration (uses llm-gemini plugin)
LLM_MODEL=gemini/gemini-2.5-flash
```

### 3. Test the Configuration

```bash
# Test that everything is working
python tests/test_gemini_config.py

# Run the example searches
python examples/search_example.py
```

## API Keys Setup

### Discogs API Token

1. Go to [Discogs Developer Settings](https://www.discogs.com/settings/developers)
2. Click "Generate new token"
3. Copy the token to your `.env` file as `DISCOGS_USER_TOKEN`

### Google Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click "Create API Key"
3. Copy the key to your `.env` file as `GOOGLE_API_KEY`

## Model Configuration

This project uses **Gemini 2.5 Flash** via the `llm-gemini` plugin:

- Model name: `gemini/gemini-2.5-flash`
- Plugin: `llm-gemini>=0.2.0` (automatically installed)
- API Key: Passed directly to prompt calls via `key` parameter
- Rate limits: Configured to respect Discogs and Gemini API limits

## Usage Examples

### Basic Search

```python
from cxz.api.search_service import search_records

# Search for records
results = await search_records("Pink Floyd Dark Side of the Moon limited edition")

for result in results:
    print(f"{result['release']['title']} - Score: {result['relevance_score']:.3f}")
```

### Search with Variants

```python
# The LLM will extract variant descriptors and rank accordingly
results = await search_records("elliott smith figure 8 red white black 25th anniversary repress")
```

### Preview Search Strategy

```python
from cxz.api.search_service import preview_search

preview = preview_search("radiohead ok computer deluxe reissue")
print(f"Will search for: {preview['discogs_search_params']}")
print(f"Variant matching: {preview['will_use_variant_ranking']}")
```

## Architecture

1. **LLM Parsing**: Natural language → Structured query (core fields + variant descriptors)
2. **Discogs Search**: Use core fields for API search to get broad results
3. **LLM Ranking**: Compare variant descriptors against full Discogs data
4. **Results**: Ranked list with relevance scores and explanations

## Troubleshooting

### "No module named 'llm_gemini'"

Make sure the llm-gemini plugin is installed:
```bash
uv add llm-gemini
```

### "Invalid API key" errors

- Check that your API keys are correctly set in `.env`
- Make sure there are no extra spaces or quotes around the keys
- Test individual services with the test script

### Rate limiting

- Discogs: 60 requests/minute (configurable via `DISCOGS_REQUESTS_PER_MINUTE`)
- Gemini: Built-in rate limiting in the llm package

### No search results

- Try simpler queries first (just artist + album)
- Check the search preview to see how your query is being parsed
- Verify your Discogs token has search permissions