"""Search screen for finding vinyl records."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static


class SearchScreen(Screen):
    """Screen for searching vinyl records."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back to Main"),
        ("ctrl+c", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the search screen."""
        yield Vertical(
            Static("🎵 Search for Vinyl Records", id="search-title"),
            Label("Describe the record you're looking for:"),
            Input(
                placeholder="e.g., 'Pink Floyd Dark Side of the Moon original pressing'",
                id="search-input",
            ),
            Horizontal(
                Button("Search", id="search-submit", variant="primary"),
                Button("Clear", id="search-clear"),
                Button("Back", id="back-btn"),
            ),
            Static("Search results will appear here...", id="search-results"),
            id="search-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "search-submit":
            self.perform_search()
        elif event.button.id == "search-clear":
            self.query_one("#search-input", Input).value = ""
            self.query_one("#search-results", Static).update(
                "Search results will appear here..."
            )
        elif event.button.id == "back-btn":
            self.app.pop_screen()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key)."""
        if event.input.id == "search-input":
            self.perform_search()

    def perform_search(self) -> None:
        """Perform the record search."""
        search_input = self.query_one("#search-input", Input)
        search_query = search_input.value.strip()

        if not search_query:
            self.app.notify("Please enter a search query")
            return

        results_widget = self.query_one("#search-results", Static)
        results_widget.update(
            f"Searching for: '{search_query}'\n\n(Search functionality will be implemented with Discogs API and LLM integration)"
        )

        self.app.notify("Search feature coming soon!")
