# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

cXz is a Python TUI (Text User Interface) application for cataloging vinyl records. It combines Discogs API integration with AI-powered search ranking using Google Gemini LLM to intelligently parse natural language queries and rank search results.

## Development Commands

### Environment Setup
```bash
# Install all dependencies (including dev dependencies)
uv sync

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your API credentials (DISCOGS_USER_TOKEN, GOOGLE_API_KEY)
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_record_parser.py

# Run with verbose output
pytest -v

# Run integration tests (requires API keys)
python tests/test_gemini_config.py
python tests/test_discogs_integration.py
```

### Code Quality
```bash
# Run linting (Ruff)
ruff check .

# Fix linting issues automatically
ruff check . --fix

# Run type checking (mypy)
mypy .

# Format code
black .
```

### Running the Application
```bash
# Run the TUI application
cxz

# Or run directly
python -m cxz.main

# Run example searches (programmatic)
python examples/search_example.py
```

### TUI Navigation
- **Main Screen**: Shows batch collection statistics and navigation options
- **Search Screen** (`S` key): Search for records, add to batch collection
- **Batch Collection** (`C` key): Manage batch collection, edit conditions, publish to Discogs
- **Navigation**: Use arrow keys to select, `Enter` to select, `Escape` to go back

## Architecture

### Core Components

1. **TUI Layer** (`cxz/tui/`): Textual-based terminal user interface
   - `app.py`: Main application with navigation and batch stats
   - `screens/search.py`: Search interface with table results and batch integration
   - `screens/batch_collection.py`: Batch collection management with edit/publish functionality

2. **API Services** (`cxz/api/`): External service integrations
   - `search_service.py`: High-level search orchestration (LLM + Discogs + ranking)
   - `llm_service.py`: Google Gemini LLM integration via llm-gemini plugin
   - `discogs_service.py`: Discogs API client with rate limiting

3. **Data Layer** (`cxz/data/`): Database and persistence
   - `database.py`: SQLite database service for batch record management

4. **Models** (`cxz/models/`): Pydantic data models
   - `record.py`: RecordQuery, VariantDescriptors, RankedResult models

5. **Utilities** (`cxz/utils/`): Core parsing and query building
   - `record_parser.py`: Natural language → structured query parsing
   - `discogs_query.py`: Discogs API query construction

### Search Flow Architecture

1. **LLM Parsing**: Natural language description → `RecordQuery` (core fields + variant descriptors)
2. **Discogs Search**: Use core fields (artist, album) for broad API search (preserves Discogs IDs)
3. **Batch LLM Ranking**: Single LLM call to rank ALL results against variant descriptors
4. **Results**: Ranked list with relevance scores, explanations, and preserved Discogs IDs for collection management

### Key Dependencies

- **Textual** (`>=0.83.0`): TUI framework
- **httpx** (`>=0.27.0`): Async HTTP client for APIs
- **Pydantic** (`>=2.9.0`): Data validation and parsing
- **llm** (`>=0.27.1`) + **llm-gemini** (`>=0.2.0`): LLM integration
- **python-dotenv**: Environment variable management

## Configuration

### Required Environment Variables
```env
DISCOGS_USER_TOKEN=your_discogs_user_token_here
GOOGLE_API_KEY=your_google_api_key_here
LLM_MODEL=gemini/gemini-2.5-flash
DISCOGS_REQUESTS_PER_MINUTE=60
```

### LLM Configuration
- Uses Gemini 2.5 Flash via the `llm-gemini` plugin
- API key passed directly to prompt calls via `key` parameter
- Rate limiting handled by the llm package

## Code Style

- Python 3.13+ required
- Ruff for linting with line length 88
- mypy for type checking with strict settings
- All functions must have type hints
- Use Pydantic models for data structures
- Async/await for I/O operations

## Testing Strategy

- **Unit tests**: Test individual parsing and ranking functions
- **Integration tests**: Test with real APIs (require API keys)
- **Example tests**: Validate specific use cases (Elliott Smith, etc.)
- Tests use pytest with asyncio mode enabled

## Common Patterns

### Error Handling
- Raise `ValueError` for user input errors
- Log detailed errors with logger.error()
- Graceful degradation when services fail

### Service Initialization
```python
# Services can be injected for testing
service = SearchService(llm_service=mock_llm, discogs_service=mock_discogs)

# Or use defaults
service = SearchService()  # Uses real services
```

### Query Parsing
```python
# Parse natural language into structured query
query = parse_record_description("Pink Floyd Dark Side red vinyl", llm_service)

# Check confidence before proceeding
if query.confidence < 0.7:
    # Handle low confidence
```

### Collection Management
```python
# Search and add to collection
results = await search_service.search("Elliott Smith Figure 8 red vinyl")
top_result = results[0]
discogs_id = top_result["release"]["id"]

# Add to collection with condition
discogs_service = DiscogsService()
success = await discogs_service.add_to_collection(
    discogs_id, 
    condition="Near Mint (NM)", 
    sleeve_condition="Very Good Plus (VG+)"
)
```

## Performance Optimizations

### Batch LLM Ranking
- **2 LLM calls total**: 1 for parsing + 1 for batch ranking (vs. N+1 individual calls)
- Processes up to 20 results in single ranking call
- Preserves Discogs IDs for collection management
- Falls back to basic relevance scoring if LLM fails

### Database Integration
- **SQLite database** stored in `~/.cxz/cxz.db` for batch record management
- Records include: Discogs ID, conditions, notes, relevance scores, publication status
- Supports batch operations: add, edit, remove, publish to Discogs
- Tracks which records have been published to avoid duplicates

## TUI Workflow

### Enhanced Search Experience (2024 Updates)

#### Visual Feedback & Progress
- **Animated Progress Indicator**: Shows spinning progress wheel during search
- **Real-time Console Logging**: Displays search phases for debugging
- **Color-Coded Match Quality**: Results colored by confidence score
  - 🟢 **Green (80%+)**: Excellent matches  
  - 🟡 **Yellow (60-79%)**: Good matches
  - 🟠 **Orange (40-59%)**: Fair matches
  - 🔴 **Red (<40%)**: Poor matches, refine search

#### Smart Enter Key Behavior
- **Search Mode**: Enter in input field = perform search
- **Results Mode**: Enter on selected row = add to collection
- **Condition Modal**: Prompts for record/sleeve condition and notes

#### Enhanced Format Display
- **Multi-disc Support**: Shows quantity (e.g., "2×Vinyl")
- **Comprehensive Details**: All format descriptors (LP, Album, 45 RPM, Reissue)
- **Variant Information**: Color variants, limited editions, anniversary details
- **Priority Parsing**: Physical format + variant info + edition details

### Key Bindings
- **A**: Add selected record to batch (with condition prompt)
- **R**: Start new search (Search Again)
- **C**: Clear results and return to search mode
- **Enter**: Context-sensitive (search or select)
- **Escape**: Back to main screen

### Search and Add to Batch (Updated)
1. Launch TUI with `cxz`
2. Press 'S' to search for records
3. Enter natural language query (e.g., "Elliott Smith Figure 8 red vinyl")
4. **Progress indicator shows** search phases
5. **Results display** with color-coded match quality
6. Select record and press 'A' or Enter
7. **Condition modal opens** - select record condition, sleeve condition, add notes
8. **Record saved** to local SQLite database with user preferences

### Manage Batch Collection
1. Press 'C' to view batch collection
2. Select records and press 'E' to edit condition, sleeve condition, or notes
3. Press 'D' to remove records from batch
4. Press 'P' to publish all pending records to Discogs collection
5. Press 'R' to refresh the view

## Recent TUI Improvements (2024)

### Critical Bug Fixes
- **Markup Crash Fix**: Safe error message handling prevents crashes on special characters
- **Row Selection Fix**: Fixed "No Record Selected" bug when selecting first row (index 0)
- **Thread Safety**: Improved async worker handling for better UI responsiveness

### User Experience Enhancements
- **Multi-disc Format Parsing**: Extracts variant info from all format entries including "All Media"
- **State Management**: Clear UI states (search/results/searching) with appropriate actions
- **Condition Selection**: Full workflow for adding records with proper grading
- **Enhanced Status Messages**: Match quality feedback and actionable guidance

### Technical Improvements
- **Progress Animation**: LoadingIndicator with proper threading for smooth animation
- **Error Resilience**: Safe text rendering with Rich.Text for markup-sensitive content
- **Type Safety**: Full mypy compliance with proper type annotations
- **Code Quality**: Ruff linting compliance with clean, maintainable code

### File Structure Updates
1. **TUI Layer** (`cxz/tui/`): 
   - `screens/search.py`: Enhanced search interface with state management
   - `screens/condition_modal.py`: **NEW** - Modal for condition/notes selection
   - `screens/batch_collection.py`: Batch collection management
   - `app.tcss`: **UPDATED** - CSS styles for color-coded results

### Development Workflow Updates
```bash
# Use uv for all development commands
uv sync --extra dev  # Install dev dependencies
uv run pytest        # Run tests
uv run ruff check .  # Run linting  
uv run mypy .        # Run type checking
uv run cxz           # Run application
```

## Latest Critical Fixes (September 2025)

### Discogs Collection Publishing Fix
**Issue**: Publishing records to Discogs collection was not properly setting conditions or notes.

**Root Cause**: Discogs API requires a two-step process:
1. Add item to collection (returns `instance_id`)
2. Use Edit Fields Instance API with `instance_id` to set conditions

**Solution Implemented**:
- **Field IDs**: Media Condition = 1, Sleeve Condition = 2, Notes = 3 (likely)
- **API Endpoints**: 
  - Add: `POST /users/{username}/collection/folders/1/releases/{release_id}`
  - Set conditions: `POST /users/{username}/collection/folders/1/releases/{release_id}/instances/{instance_id}/fields/{field_id}`
- **Payload**: `{"value": "Near Mint (NM or M-)"}`

**Files Modified**:
- `cxz/api/discogs_service.py`: Complete rewrite of `add_to_collection()` method
- `cxz/tui/screens/batch_collection.py`: Added notes parameter to publishing workflow

### Enhanced Format Parsing for Variant Colors
**Issue**: Yellow vinyl variant not showing in format column despite being in `formats[0].text` field.

**Solution**: Enhanced format parsing to extract `text` field from all format entries, particularly for vinyl variants.
```python
# Now extracts color info from format.text field
if text:
    vinyl_info.append(text)  # "Yellow", "Red", "Clear", etc.
```

### Reset Search Functionality
**Issue**: No way to modify search query after getting results.

**Solution**: Added `R` key binding for "Reset Search" that:
- Clears results but keeps the search query
- Focuses input with cursor at end for easy modification
- Provides helpful status message

**Key Bindings Updated**:
- `R` → Reset Search (was "Search Again" which cleared everything)
- `C` → Clear Results (complete reset)

### Improved Natural Language Parsing
**Issue**: Queries like "dark thoughts highway to the end yellow vinyl" failed but "dark thoughts - highway to the end - yellow vinyl" worked.

**Solution**: Enhanced LLM parsing prompt with:
- **Parsing Strategy**: Explicit guidance for handling ambiguous descriptions
- **Examples**: Specific examples of successful parsing patterns
- **Artist Recognition**: Better handling of known artist names without delimiters
- **Context Clues**: Instructions to use music knowledge for artist/album separation

### Search Quality Improvements
- **Format Display**: Now shows comprehensive multi-disc information with color variants
- **Color Coding**: Results colored by confidence score (🟢 80%+ 🟡 60-79% 🟠 40-59% 🔴 <40%)
- **Progress Feedback**: Animated progress indicators during search operations
- **Error Handling**: Safe markup rendering prevents crashes on special characters

### API Integration Enhancements
- **Two-Phase Collection Adding**: Proper Discogs API workflow for setting conditions
- **Rate Limiting**: Proper delays between API calls for condition setting
- **Error Recovery**: Graceful handling of already-in-collection scenarios
- **Instance Management**: Automatic retrieval of collection instance IDs

### Development Notes
- **Always use `uv`** for package management and running commands
- **LLM Model**: Uses Gemini 2.5 Flash for parsing and ranking
- **Database**: SQLite for local batch collection management
- **Threading**: Proper async workers for non-blocking UI operations
- **Type Safety**: Full mypy compliance with proper annotations

### Known Issues & Workarounds
1. **Notes Field ID**: Assuming field_id=3 for notes, may need adjustment based on user's custom fields
2. **Rate Limiting**: Discogs API has 60 requests/minute limit - proper delays implemented
3. **LLM Parsing**: Some edge cases may still require explicit delimiters for complex queries