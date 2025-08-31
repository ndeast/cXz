"""Search screen for finding vinyl records."""

import logging
from typing import Any

from textual import log
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, LoadingIndicator, Static
from textual.worker import Worker, WorkerState

from cxz.api.search_service import SearchService
from cxz.data.database import DatabaseService


class SearchResultsTable(DataTable):
    """Custom DataTable for search results."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True
        self._search_results: list[dict[str, Any]] = []  # Store results for color mapping
    
    def add_colored_row(self, *cells: Any, key: str | None = None, score: float = 0.0) -> Any:
        """Add a row with color based on match quality score."""
        # Convert score to CSS class (0.0-1.0 range)
        if score >= 0.8:
            css_class = "score-excellent"
        elif score >= 0.6:
            css_class = "score-good"
        elif score >= 0.4:
            css_class = "score-fair"
        else:
            css_class = "score-poor"
        
        row_key = self.add_row(*cells, key=key)
        
        # Apply CSS class to the first cell (score column)
        try:
            self.add_class(css_class)
        except Exception:
            pass  # Fallback if styling fails
        
        return row_key


class SearchScreen(Screen):
    """Screen for searching vinyl records."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back to Main"),
        ("ctrl+c", "app.quit", "Quit"),
        ("a", "add_to_batch", "Add to Batch"),
        ("enter", "add_to_batch", "Add to Batch"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.search_service = SearchService()
        self.db_service = DatabaseService()
        self.current_results: list[dict[str, Any]] = []
        self.current_query = ""

    def compose(self) -> ComposeResult:
        """Create child widgets for the search screen."""
        yield Vertical(
            Static("🎵 Search for Vinyl Records", id="search-title"),
            Horizontal(
                Input(
                    placeholder="e.g., 'Elliott Smith Figure 8 red vinyl limited edition'",
                    id="search-input",
                ),
                Button("Search", id="search-submit", variant="primary"),
                Button("Clear", id="search-clear"),
            ),
            Horizontal(
                Button("View Batch Collection", id="batch-btn", variant="success"),
                Button("Back to Main", id="back-btn"),
            ),
            ScrollableContainer(
                Static("Enter a search query and press Search to find vinyl records.", id="search-status"),
                LoadingIndicator(id="search-progress"),
                SearchResultsTable(id="results-table"),
                id="results-container"
            ),
            id="search-container",
        )

    def on_mount(self) -> None:
        """Set up the results table."""
        table = self.query_one("#results-table", SearchResultsTable)
        table.add_columns("Score", "Title", "Year", "Catalog", "Format")
        table.display = False  # Hide initially
        
        # Hide progress indicator initially
        progress = self.query_one("#search-progress", LoadingIndicator)
        progress.display = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "search-submit":
            self.perform_search()
        elif event.button.id == "search-clear":
            self.clear_search()
        elif event.button.id == "back-btn":
            self.app.pop_screen()
        elif event.button.id == "batch-btn":
            self.show_batch_collection()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key)."""
        if event.input.id == "search-input":
            self.perform_search()

    def clear_search(self) -> None:
        """Clear search input and results."""
        self.query_one("#search-input", Input).value = ""
        self.query_one("#search-status", Static).update("Enter a search query and press Search to find vinyl records.")
        
        table = self.query_one("#results-table", SearchResultsTable)
        table.clear()
        table.display = False
        
        # Hide progress indicator
        progress = self.query_one("#search-progress", LoadingIndicator)
        progress.display = False
        
        self.current_results = []
        self.current_query = ""

    def perform_search(self) -> None:
        """Perform the record search."""
        search_input = self.query_one("#search-input", Input)
        search_query = search_input.value.strip()

        if not search_query:
            self.app.notify("Please enter a search query")
            return

        self.current_query = search_query
        
        # Update status and show progress
        status_widget = self.query_one("#search-status", Static)
        status_widget.update(f"🔍 Searching for: '{search_query}'...")
        
        # Show progress indicator
        progress = self.query_one("#search-progress", LoadingIndicator)
        progress.display = True
        
        # Hide table during search
        table = self.query_one("#results-table", SearchResultsTable)
        table.display = False
        
        # Log search start to console
        log(f"[bold cyan]Starting search for:[/] {search_query}")
        
        # Run search in worker thread to avoid blocking UI
        self.run_worker(self._search_worker(search_query), exclusive=True)

    @staticmethod
    async def _search_worker(search_query: str) -> list[dict[str, Any]]:
        """Worker function to perform search."""
        search_service = SearchService()
        
        # Set up logging to show progress in console
        logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
        
        try:
            log("[bold green]Parsing query with LLM...[/]")
            results = await search_service.search(search_query, max_results=10)
            log(f"[bold green]Search completed![/] Found {len(results)} results")
            return results
        except Exception as e:
            log(f"[bold red]Search failed:[/] {e}")
            return [{"error": str(e)}]

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        # Hide progress indicator when worker completes
        if event.state in (WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED):
            progress = self.query_one("#search-progress", LoadingIndicator)
            progress.display = False
        
        if event.worker.name == "_search_worker":
            if event.state == WorkerState.SUCCESS:
                # Search completed successfully
                results = event.worker.result
                if results is not None:
                    self.display_search_results(results)
            elif event.state == WorkerState.ERROR:
                # Search failed
                status_widget = self.query_one("#search-status", Static)
                status_widget.update(f"❌ Search failed: {event.worker.error}")
                log(f"[bold red]Worker error:[/] {event.worker.error}")
        elif event.worker.name == "_add_to_batch_worker" and event.state == WorkerState.SUCCESS:
            result = event.worker.result
            if result and result["success"]:
                self.app.notify(f"✅ Added '{result['title']}' to batch collection (ID: {result['record_id']})")
            elif result:
                self.app.notify(f"❌ Failed to add to batch: {result['error']}")

    def display_search_results(self, results: list[dict[str, Any]]) -> None:
        """Display search results in the table."""
        status_widget = self.query_one("#search-status", Static)
        table = self.query_one("#results-table", SearchResultsTable)

        # Check for error in results
        if results and "error" in results[0]:
            status_widget.update(f"❌ Search error: {results[0]['error']}")
            return

        if not results:
            status_widget.update("❌ No results found. Try a different search query.")
            return

        # Clear previous results
        table.clear()
        self.current_results = results

        # Populate table with results and color coding
        for i, result in enumerate(results):
            release = result["release"]
            score_value = result['relevance_score']
            score = f"{score_value:.2f}"
            title = release.get("title", "Unknown")
            year = str(release.get("year", ""))
            catno = release.get("catno", "")
            
            # Format info
            formats = release.get("formats", [])
            format_text = ""
            if formats:
                fmt = formats[0]  # Take first format
                format_parts = []
                if fmt.get("name"):
                    format_parts.append(fmt["name"])
                if fmt.get("descriptions"):
                    format_parts.extend(fmt["descriptions"][:2])  # Limit to 2 descriptions
                format_text = ", ".join(format_parts)

            # Add row with color coding based on score
            table.add_colored_row(score, title, year, catno, format_text, key=str(i), score=score_value)
            
            # Log result quality
            quality = "excellent" if score_value >= 0.8 else "good" if score_value >= 0.6 else "fair" if score_value >= 0.4 else "poor"
            log(f"Result {i+1}: {title} - Score: {score_value:.3f} ({quality})")

        # Update status with match quality info
        if results:
            top_score = results[0]['relevance_score']
            if top_score >= 0.8:
                quality_text = "🟢 Excellent matches found!"
            elif top_score >= 0.6:
                quality_text = "🟡 Good matches found."
            elif top_score >= 0.4:
                quality_text = "🟠 Fair matches found."
            else:
                quality_text = "🔴 Poor matches - try refining your search."
        else:
            quality_text = "❌ No matches found."
            
        status_widget.update(f"✅ Found {len(results)} results. {quality_text} Select a record and press 'A' or Enter to add to batch collection.")
        table.display = True

    def action_add_to_batch(self) -> None:
        """Add selected record to batch collection."""
        table = self.query_one("#results-table", SearchResultsTable)
        
        if not table.cursor_row or not self.current_results:
            self.app.notify("No record selected")
            return

        try:
            # Get selected row index - use cursor_row directly as it's 0-indexed
            cursor_row = table.cursor_row
            if cursor_row is None or cursor_row >= len(self.current_results):
                raise ValueError("No valid row selected")
                
            selected_result = self.current_results[cursor_row]
            
            # Add to batch collection
            self.run_worker(self._add_to_batch_worker(selected_result, self.current_query))
            
        except (ValueError, IndexError) as e:
            self.app.notify(f"Error selecting record: {e}")

    async def _add_to_batch_worker(self, result: dict[str, Any], query: str) -> dict[str, Any]:
        """Worker to add record to batch collection."""
        try:
            record_id = await self.db_service.add_search_result_to_batch(
                result,
                query,
                condition="Mint (M)",
                sleeve_condition="Mint (M)",
                notes=""
            )
            return {"success": True, "record_id": record_id, "title": result["release"].get("title", "Unknown")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def show_batch_collection(self) -> None:
        """Show the batch collection management screen."""
        from cxz.tui.screens.batch_collection import BatchCollectionScreen
        self.app.push_screen(BatchCollectionScreen())
