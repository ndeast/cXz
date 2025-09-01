"""Search screen for finding vinyl records."""

import logging
from typing import Any

from rich.text import Text
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
        ("a", "add_selected", "Add Selected"),
        ("r", "reset_search", "Reset Search"),
        ("c", "clear_results", "Clear Results"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.search_service = SearchService()
        self.db_service = DatabaseService()
        self.current_results: list[dict[str, Any]] = []
        self.current_query = ""
        self.ui_state = "search"  # "search", "results", "searching"

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
            if self.ui_state == "search":
                self.perform_search()
        # Enter on results table is handled by on_data_table_row_selected

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
        self.ui_state = "search"

    def perform_search(self) -> None:
        """Perform the record search."""
        search_input = self.query_one("#search-input", Input)
        search_query = search_input.value.strip()

        if not search_query:
            self.app.notify("Please enter a search query")
            return

        self.current_query = search_query
        self.ui_state = "searching"
        
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
        self.run_worker(self._search_worker(search_query), exclusive=True, thread=True)

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
            # Use Text to safely display error messages without markup parsing
            error_msg = results[0]['error']
            safe_text = Text.from_markup("❌ Search error: ") + Text(error_msg)
            status_widget.update(safe_text)
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
            
            # Format info - show comprehensive multi-disc format details
            formats = release.get("formats", [])
            format_text = ""
            if formats:
                format_parts = []
                
                # Separate processing for different format types
                vinyl_info: list[str] = []
                media_info: list[str] = []
                
                for fmt in formats:
                    name = fmt.get("name", "")
                    qty = fmt.get("qty", "1")
                    descriptions = fmt.get("descriptions", [])
                    text = fmt.get("text", "")
                    
                    if name == "All Media":
                        # All Media usually contains variant/edition info
                        media_info.extend(descriptions)
                        if text:
                            media_info.append(text)
                    elif name in ["Vinyl", "CD", "Cassette"]:
                        # Physical format info
                        qty_text = f"{qty}×" if int(qty) > 1 else ""
                        # Only add format name once (prefer quantity version)
                        format_name = f"{qty_text}{name}"
                        if not any(format_name in part or name in part for part in vinyl_info):
                            vinyl_info.append(format_name)
                        vinyl_info.extend(descriptions)
                        # Add variant text (e.g., color info like "Yellow")
                        if text:
                            vinyl_info.append(text)
                    else:
                        # Other formats
                        format_parts.extend(descriptions)
                        if text:
                            format_parts.append(text)
                
                # Combine in priority order: Physical format + variant info
                all_parts = vinyl_info + media_info + format_parts
                
                # Remove duplicates while preserving order
                seen = set()
                unique_parts = []
                for part in all_parts:
                    # Clean up the part
                    part = part.strip()
                    if part and part not in seen:
                        seen.add(part)
                        unique_parts.append(part)
                
                # Join with bullet points, limit to prevent overflow
                format_text = " • ".join(unique_parts[:8])  # Increased limit for more detail

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
        
        # Switch to results mode
        self.ui_state = "results"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in results table (Enter key)."""
        if self.ui_state == "results":
            self.action_add_selected()

    def action_add_selected(self) -> None:
        """Add selected record to batch collection using condition modal."""
        table = self.query_one("#results-table", SearchResultsTable)
        
        # Check if we have results and a valid selection (cursor_row can be 0!)
        if table.cursor_row is None or not self.current_results:
            self.app.notify("No record selected")
            return

        try:
            # Get selected row index - use cursor_row directly as it's 0-indexed
            cursor_row = table.cursor_row
            if cursor_row >= len(self.current_results):
                raise ValueError("No valid row selected")
                
            selected_result = self.current_results[cursor_row]
            record_title = selected_result["release"].get("title", "Unknown Record")
            
            # Show condition modal
            self.show_condition_modal(record_title, selected_result)
            
        except (ValueError, IndexError) as e:
            self.app.notify(f"Error selecting record: {e}")

    def show_condition_modal(self, record_title: str, record_data: dict[str, Any]) -> None:
        """Show modal for selecting condition and adding record."""
        from cxz.tui.screens.condition_modal import ConditionModal
        
        def handle_condition_result(result: dict[str, Any] | None) -> None:
            if result and result.get("action") == "add":
                # Add to batch collection with user-selected condition
                self.run_worker(self._add_to_batch_worker(
                    result["record_data"],
                    self.current_query,
                    result["condition"],
                    result["sleeve_condition"],
                    result["notes"]
                ))
        
        modal = ConditionModal(record_title, record_data)
        self.app.push_screen(modal, handle_condition_result)

    def action_new_search(self) -> None:
        """Start a new search."""
        self.ui_state = "search"
        search_input = self.query_one("#search-input", Input)
        search_input.focus()
        search_input.select_all()
        
        status_widget = self.query_one("#search-status", Static)
        status_widget.update("Enter a search query and press Search to find vinyl records.")

    def action_clear_results(self) -> None:
        """Clear current results and return to search mode."""
        self.clear_search()

    def action_reset_search(self) -> None:
        """Clear results but keep the search query for modification."""
        search_input = self.query_one("#search-input", Input)
        current_query = search_input.value
        
        # Clear results and UI state
        table = self.query_one("#results-table", SearchResultsTable)
        table.clear()
        table.display = False
        
        # Hide progress indicator
        progress = self.query_one("#search-progress", LoadingIndicator)
        progress.display = False
        
        # Reset internal state
        self.current_results = []
        self.ui_state = "search"
        
        # Keep query and focus input for modification
        search_input.value = current_query
        search_input.focus()
        search_input.cursor_position = len(current_query)  # Position cursor at end
        
        # Update status
        status_widget = self.query_one("#search-status", Static)
        status_widget.update("Modify your search query and press Search to find records.")

    async def _add_to_batch_worker(
        self,
        result: dict[str, Any],
        query: str,
        condition: str = "Near Mint (NM)",
        sleeve_condition: str = "Near Mint (NM)",
        notes: str = ""
    ) -> dict[str, Any]:
        """Worker to add record to batch collection."""
        try:
            record_id = await self.db_service.add_search_result_to_batch(
                result,
                query,
                condition=condition,
                sleeve_condition=sleeve_condition,
                notes=notes
            )
            return {"success": True, "record_id": record_id, "title": result["release"].get("title", "Unknown")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def show_batch_collection(self) -> None:
        """Show the batch collection management screen."""
        from cxz.tui.screens.batch_collection import BatchCollectionScreen
        self.app.push_screen(BatchCollectionScreen())
