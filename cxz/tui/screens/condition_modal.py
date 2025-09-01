"""Condition selection modal for adding records to collection."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static


class ConditionModal(ModalScreen):
    """Modal for selecting condition when adding records to collection."""

    DEFAULT_CSS = """
    ConditionModal {
        align: center middle;
    }

    #condition-dialog {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary 80%;
        padding: 1;
    }

    #condition-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin: 1;
    }

    .condition-row {
        height: 3;
        margin: 1 0;
    }

    .condition-buttons {
        height: 3;
        margin: 1 0;
        align: center middle;
    }
    """

    def __init__(self, record_title: str, record_data: dict[str, Any]) -> None:
        """Initialize condition modal.

        Args:
            record_title: Title of the record to display
            record_data: Full record data to pass back
        """
        super().__init__()
        self.record_title = record_title
        self.record_data = record_data
        self.result: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Vertical(
            Static("Add to Collection", id="condition-title"),
            Static(f"Record: {self.record_title}", classes="record-info"),
            Horizontal(
                Label("Condition:", classes="condition-label"),
                Select(
                    [
                        ("Mint (M)", "Mint (M)"),
                        ("Near Mint (NM)", "Near Mint (NM)"),
                        ("Very Good Plus (VG+)", "Very Good Plus (VG+)"),
                        ("Very Good (VG)", "Very Good (VG)"),
                        ("Good Plus (G+)", "Good Plus (G+)"),
                        ("Good (G)", "Good (G)"),
                        ("Fair (F)", "Fair (F)"),
                        ("Poor (P)", "Poor (P)"),
                    ],
                    value="Very Good Plus (VG+)",
                    id="condition-select",
                ),
                classes="condition-row",
            ),
            Horizontal(
                Label("Sleeve Condition:", classes="condition-label"),
                Select(
                    [
                        ("Mint (M)", "Mint (M)"),
                        ("Near Mint (NM)", "Near Mint (NM)"),
                        ("Very Good Plus (VG+)", "Very Good Plus (VG+)"),
                        ("Very Good (VG)", "Very Good (VG)"),
                        ("Good Plus (G+)", "Good Plus (G+)"),
                        ("Good (G)", "Good (G)"),
                        ("Fair (F)", "Fair (F)"),
                        ("Poor (P)", "Poor (P)"),
                    ],
                    value="Very Good Plus (VG+)",
                    id="sleeve-select",
                ),
                classes="condition-row",
            ),
            Horizontal(
                Label("Notes:", classes="condition-label"),
                Input(placeholder="Optional notes...", id="notes-input"),
                classes="condition-row",
            ),
            Horizontal(
                Button("Add to Collection", id="add-btn", variant="primary"),
                Button("Cancel", id="cancel-btn"),
                classes="condition-buttons",
            ),
            id="condition-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "add-btn":
            # Collect form data
            condition_select = self.query_one("#condition-select", Select)
            sleeve_select = self.query_one("#sleeve-select", Select)
            notes_input = self.query_one("#notes-input", Input)

            self.result = {
                "record_data": self.record_data,
                "condition": condition_select.value,
                "sleeve_condition": sleeve_select.value,
                "notes": notes_input.value or "",
                "action": "add",
            }
            self.dismiss(self.result)

        elif event.button.id == "cancel-btn":
            self.result = {"action": "cancel"}
            self.dismiss(self.result)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select changes."""
        pass  # Could add validation here if needed
