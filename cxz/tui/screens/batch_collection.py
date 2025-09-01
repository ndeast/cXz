"""Batch collection management screen."""

from typing import List, Dict, Any, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static, Input, TextArea, Select
from textual.worker import Worker, WorkerState

from cxz.data.database import DatabaseService
from cxz.api.discogs_service import DiscogsService


class BatchCollectionTable(DataTable):
    """Custom DataTable for batch collection records."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True


class EditRecordModal(Screen):
    """Modal screen for editing a batch record."""

    def __init__(self, record: Dict[str, Any]):
        super().__init__()
        self.record = record
        self.db_service = DatabaseService()

    def compose(self) -> ComposeResult:
        """Create the edit modal widgets."""
        conditions = [
            ("Mint (M)", "Mint (M)"),
            ("Near Mint (NM or M-)", "Near Mint (NM or M-)"),
            ("Very Good Plus (VG+)", "Very Good Plus (VG+)"),
            ("Very Good (VG)", "Very Good (VG)"),
            ("Good Plus (G+)", "Good Plus (G+)"),
            ("Good (G)", "Good (G)"),
            ("Fair (F)", "Fair (F)"),
            ("Poor (P)", "Poor (P)"),
        ]

        yield Vertical(
            Static(f"📝 Edit: {self.record['title']}", id="edit-title"),
            Horizontal(
                Vertical(
                    Static("Media Condition:"),
                    Select(
                        conditions,
                        value=self.record["condition"],
                        id="condition-select",
                    ),
                ),
                Vertical(
                    Static("Sleeve Condition:"),
                    Select(
                        conditions,
                        value=self.record["sleeve_condition"],
                        id="sleeve-condition-select",
                    ),
                ),
            ),
            Static("Notes:"),
            TextArea(self.record.get("notes", ""), id="notes-input"),
            Horizontal(
                Button("Save", id="save-btn", variant="primary"),
                Button("Cancel", id="cancel-btn"),
                Button("Remove from Batch", id="remove-btn", variant="error"),
            ),
            id="edit-modal",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in edit modal."""
        if event.button.id == "save-btn":
            self.save_changes()
        elif event.button.id == "cancel-btn":
            self.app.pop_screen()
        elif event.button.id == "remove-btn":
            self.remove_record()

    def save_changes(self) -> None:
        """Save changes to the record."""
        condition = self.query_one("#condition-select", Select).value
        sleeve_condition = self.query_one("#sleeve-condition-select", Select).value
        notes = self.query_one("#notes-input", TextArea).text

        # Run update in worker
        self.run_worker(self._update_worker(condition, sleeve_condition, notes))

    async def _update_worker(
        self, condition: str, sleeve_condition: str, notes: str
    ) -> Dict[str, Any]:
        """Worker to update record."""
        try:
            success = await self.db_service.update_batch_record(
                self.record["id"],
                condition=condition,
                sleeve_condition=sleeve_condition,
                notes=notes,
            )
            return {"success": success}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker completion."""
        if event.worker.name == "_update_worker" and event.state == WorkerState.SUCCESS:
            result = event.worker.result
            if result["success"]:
                self.app.notify("✅ Record updated successfully")
                self.app.pop_screen()
            else:
                self.app.notify(
                    f"❌ Failed to update record: {result.get('error', 'Unknown error')}"
                )

    def remove_record(self) -> None:
        """Remove record from batch collection."""
        self.run_worker(self._remove_worker())

    async def _remove_worker(self) -> Dict[str, Any]:
        """Worker to remove record."""
        try:
            success = await self.db_service.remove_batch_record(self.record["id"])
            return {"success": success}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle remove worker completion."""
        if event.worker.name == "_remove_worker" and event.state == WorkerState.SUCCESS:
            result = event.worker.result
            if result["success"]:
                self.app.notify("✅ Record removed from batch collection")
                self.app.pop_screen()
            else:
                self.app.notify(
                    f"❌ Failed to remove record: {result.get('error', 'Unknown error')}"
                )


class BatchCollectionScreen(Screen):
    """Screen for managing batch collection before publishing to Discogs."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("ctrl+c", "app.quit", "Quit"),
        ("e", "edit_record", "Edit Record"),
        ("enter", "edit_record", "Edit Record"),
        ("d", "remove_record", "Remove Record"),
        ("p", "publish_to_discogs", "Publish to Discogs"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(self):
        super().__init__()
        self.db_service = DatabaseService()
        self.discogs_service = DiscogsService()
        self.current_records = []

    def compose(self) -> ComposeResult:
        """Create child widgets for the batch collection screen."""
        yield Vertical(
            Static("📚 Batch Collection Management", id="batch-title"),
            Horizontal(
                Button("Refresh", id="refresh-btn"),
                Button("Publish All to Discogs", id="publish-btn", variant="primary"),
                Button("Clear Published Records", id="clear-btn"),
                Button("Back", id="back-btn"),
            ),
            ScrollableContainer(
                Static("Loading batch collection...", id="batch-status"),
                BatchCollectionTable(id="batch-table"),
                id="batch-container",
            ),
            id="batch-collection-container",
        )

    def on_mount(self) -> None:
        """Set up the batch table and load records."""
        table = self.query_one("#batch-table", BatchCollectionTable)
        table.add_columns("Title", "Year", "Condition", "Sleeve", "Notes", "Status")
        table.display = False  # Hide initially
        self.load_batch_records()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "refresh-btn":
            self.action_refresh()
        elif event.button.id == "publish-btn":
            self.action_publish_to_discogs()
        elif event.button.id == "clear-btn":
            self.clear_published_records()
        elif event.button.id == "back-btn":
            self.app.pop_screen()

    def load_batch_records(self) -> None:
        """Load batch collection records from database."""
        status_widget = self.query_one("#batch-status", Static)
        status_widget.update("🔄 Loading batch collection records...")

        table = self.query_one("#batch-table", BatchCollectionTable)
        table.display = False

        self.run_worker(self._load_records_worker(), exclusive=True)

    async def _load_records_worker(self) -> List[Dict[str, Any]]:
        """Worker to load records from database."""
        try:
            records = await self.db_service.get_batch_records(
                include_added_to_discogs=True
            )
            stats = await self.db_service.get_batch_stats()
            return {"records": records, "stats": stats}
        except Exception as e:
            return {"error": str(e)}

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        worker_name = getattr(event.worker, "name", "")

        if worker_name == "_load_records_worker" and event.state == WorkerState.SUCCESS:
            result = event.worker.result
            if "error" in result:
                self.query_one("#batch-status", Static).update(
                    f"❌ Error loading records: {result['error']}"
                )
            else:
                self.display_batch_records(result["records"], result["stats"])

        elif worker_name == "_publish_worker" and event.state == WorkerState.SUCCESS:
            result = event.worker.result
            self.handle_publish_result(result)

        elif worker_name == "_clear_worker" and event.state == WorkerState.SUCCESS:
            result = event.worker.result
            if result["success"]:
                self.app.notify(f"✅ Cleared {result['count']} published records")
                self.load_batch_records()  # Refresh the view
            else:
                self.app.notify(
                    f"❌ Failed to clear records: {result.get('error', 'Unknown error')}"
                )

    def display_batch_records(
        self, records: List[Dict[str, Any]], stats: Dict[str, int]
    ) -> None:
        """Display batch records in the table."""
        status_widget = self.query_one("#batch-status", Static)
        table = self.query_one("#batch-table", BatchCollectionTable)

        if not records:
            status_widget.update(
                "📭 No records in batch collection. Use Search to add records."
            )
            return

        # Clear previous records
        table.clear()
        self.current_records = records

        # Populate table with records
        for i, record in enumerate(records):
            title = record["title"] or "Unknown"
            year = str(record["year"]) if record["year"] else ""
            condition = record["condition"] or "Mint (M)"
            sleeve_condition = record["sleeve_condition"] or "Mint (M)"
            notes = (
                record["notes"][:50] + "..."
                if record["notes"] and len(record["notes"]) > 50
                else record["notes"] or ""
            )
            status = "✅ Published" if record["added_to_discogs"] else "⏳ Pending"

            table.add_row(
                title, year, condition, sleeve_condition, notes, status, key=str(i)
            )

        # Update status with stats
        pending = stats["pending"]
        added = stats["added"]
        total = stats["total"]

        status_text = f"📚 Batch Collection: {total} total records ({pending} pending, {added} published)"
        if pending > 0:
            status_text += f"\n▶️ Select a record and press 'E' to edit, 'P' to publish all pending records to Discogs"

        status_widget.update(status_text)
        table.display = True

    def action_refresh(self) -> None:
        """Refresh the batch collection view."""
        self.load_batch_records()

    def action_edit_record(self) -> None:
        """Edit the selected record."""
        table = self.query_one("#batch-table", BatchCollectionTable)

        if not table.cursor_row or not self.current_records:
            self.app.notify("No record selected")
            return

        try:
            # Get selected row index
            row_index = int(table.coordinate_to_cell_key(table.cursor_coordinate).value)
            selected_record = self.current_records[row_index]

            # Show edit modal
            self.app.push_screen(EditRecordModal(selected_record))

        except (ValueError, IndexError) as e:
            self.app.notify(f"Error selecting record: {e}")

    def action_remove_record(self) -> None:
        """Remove the selected record from batch collection."""
        table = self.query_one("#batch-table", BatchCollectionTable)

        if not table.cursor_row or not self.current_records:
            self.app.notify("No record selected")
            return

        try:
            # Get selected row index
            row_index = int(table.coordinate_to_cell_key(table.cursor_coordinate).value)
            selected_record = self.current_records[row_index]

            # Run remove worker
            self.run_worker(self._remove_record_worker(selected_record["id"]))

        except (ValueError, IndexError) as e:
            self.app.notify(f"Error selecting record: {e}")

    async def _remove_record_worker(self, record_id: int) -> Dict[str, Any]:
        """Worker to remove a record."""
        try:
            success = await self.db_service.remove_batch_record(record_id)
            return {"success": success, "record_id": record_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def action_publish_to_discogs(self) -> None:
        """Publish all pending records to Discogs collection."""
        pending_records = [r for r in self.current_records if not r["added_to_discogs"]]

        if not pending_records:
            self.app.notify("No pending records to publish")
            return

        self.query_one("#batch-status", Static).update(
            f"🚀 Publishing {len(pending_records)} records to Discogs..."
        )
        self.run_worker(self._publish_worker(pending_records))

    async def _publish_worker(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Worker to publish records to Discogs."""
        success_count = 0
        failed_records = []
        published_ids = []

        for record in records:
            try:
                self.app.notify(record["condition"])
                success = await self.discogs_service.add_to_collection(
                    record["discogs_id"],
                    condition=record["condition"],
                    sleeve_condition=record["sleeve_condition"],
                    notes=record.get("notes", ""),
                )

                if success:
                    success_count += 1
                    published_ids.append(record["id"])
                else:
                    failed_records.append(record["title"])

            except Exception as e:
                failed_records.append(f"{record['title']} ({e})")

        # Mark successful records as published
        if published_ids:
            await self.db_service.mark_as_added_to_discogs(published_ids)

        return {
            "success_count": success_count,
            "total_count": len(records),
            "failed_records": failed_records,
            "published_ids": published_ids,
        }

    def handle_publish_result(self, result: Dict[str, Any]) -> None:
        """Handle publish worker result."""
        success_count = result["success_count"]
        total_count = result["total_count"]
        failed_count = len(result["failed_records"])

        if success_count == total_count:
            self.app.notify(
                f"🎉 Successfully published all {success_count} records to Discogs!"
            )
        elif success_count > 0:
            self.app.notify(
                f"✅ Published {success_count}/{total_count} records. {failed_count} failed."
            )
        else:
            self.app.notify(
                f"❌ Failed to publish any records. Check your Discogs credentials."
            )

        # Refresh the view
        self.load_batch_records()

    def clear_published_records(self) -> None:
        """Clear all published records from the batch collection."""
        self.run_worker(self._clear_worker())

    async def _clear_worker(self) -> Dict[str, Any]:
        """Worker to clear published records."""
        try:
            count = await self.db_service.clear_added_records()
            return {"success": True, "count": count}
        except Exception as e:
            return {"success": False, "error": str(e)}
