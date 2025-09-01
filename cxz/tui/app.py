"""Main TUI application using Textual."""

from typing import Dict

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Static
from textual.worker import Worker, WorkerState

from cxz.tui.screens.search import SearchScreen
from cxz.tui.screens.batch_collection import BatchCollectionScreen
from cxz.data.database import DatabaseService


class CxzApp(App):
    """Main cXz TUI application."""

    TITLE = "cXz - Vinyl Record Catalog"
    SUB_TITLE = "Search and catalog your vinyl collection"
    CSS_PATH = "app.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("s", "show_search", "Search Records"),
        ("c", "show_batch_collection", "Batch Collection"),
    ]

    def __init__(self):
        super().__init__()
        self.db_service = DatabaseService()

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Vertical(
            Static(
                "Welcome to cXz!\n\n"
                "This tool helps you catalog vinyl records using the Discogs API\n"
                "with AI-powered search ranking and batch collection management.\n\n"
                "• Press 'S' to search for records\n"
                "• Press 'C' to manage your batch collection",
                id="welcome",
            ),
            Horizontal(
                Button("Search Records", id="search-btn", variant="primary"),
                Button("Batch Collection", id="collection-btn", variant="success"),
                Button("Settings", id="settings-btn"),
                id="menu-buttons",
            ),
            Static("Batch collection stats will appear here...", id="stats-display"),
            id="main-content",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Load initial stats when app starts."""
        self.load_batch_stats()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "search-btn":
            self.action_show_search()
        elif event.button.id == "collection-btn":
            self.action_show_batch_collection()
        elif event.button.id == "settings-btn":
            self.notify("Settings not implemented yet")

    def action_show_search(self) -> None:
        """Show the search screen."""
        self.push_screen(SearchScreen())

    def action_show_batch_collection(self) -> None:
        """Show the batch collection screen."""
        self.push_screen(BatchCollectionScreen())

    def load_batch_stats(self) -> None:
        """Load and display batch collection statistics."""
        self.run_worker(self._load_stats_worker())

    async def _load_stats_worker(self) -> Dict[str, int]:
        """Worker to load batch statistics."""
        try:
            stats = await self.db_service.get_batch_stats()
            return stats
        except Exception as e:
            return {"error": str(e)}

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker completion."""
        if (
            event.worker.name == "_load_stats_worker"
            and event.state == WorkerState.SUCCESS
        ):
            result = event.worker.result
            if "error" in result:
                stats_text = f"⚠️  Error loading batch stats: {result['error']}"
            else:
                total = result["total"]
                pending = result["pending"]
                added = result["added"]

                if total == 0:
                    stats_text = (
                        "📭 No records in batch collection. Use Search to add some!"
                    )
                else:
                    stats_text = f"📚 Batch Collection: {total} records ({pending} pending, {added} published to Discogs)"

            self.query_one("#stats-display", Static).update(stats_text)
