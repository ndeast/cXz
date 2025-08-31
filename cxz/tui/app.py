"""Main TUI application using Textual."""

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Static

from cxz.tui.screens.search import SearchScreen


class CxzApp(App):
    """Main cXz TUI application."""

    TITLE = "cXz - Vinyl Record Catalog"
    SUB_TITLE = "Search and catalog your vinyl collection"
    CSS_PATH = "app.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("s", "show_search", "Search Records"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Vertical(
            Static(
                "Welcome to cXz!\n\n"
                "This tool helps you catalog vinyl records using the Discogs API\n"
                "with AI-powered search ranking.\n\n"
                "Press 'S' to start searching for records.",
                id="welcome",
            ),
            Horizontal(
                Button("Search Records", id="search-btn", variant="primary"),
                Button("View Collection", id="collection-btn"),
                Button("Settings", id="settings-btn"),
                id="menu-buttons",
            ),
            id="main-content",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "search-btn":
            self.action_show_search()
        elif event.button.id == "collection-btn":
            self.notify("Collection view not implemented yet")
        elif event.button.id == "settings-btn":
            self.notify("Settings not implemented yet")

    def action_show_search(self) -> None:
        """Show the search screen."""
        self.push_screen(SearchScreen())
