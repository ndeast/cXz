"""SQLite database service for batch record management."""

import sqlite3
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import json


class DatabaseService:
    """Service for managing local SQLite database for batch operations."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the database service.
        
        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            # Store in user's home directory
            home_dir = Path.home()
            db_dir = home_dir / ".cxz"
            db_dir.mkdir(exist_ok=True)
            self.db_path = str(db_dir / "cxz.db")
        else:
            self.db_path = db_path

        self.init_database()

    def init_database(self) -> None:
        """Initialize the database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS batch_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discogs_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT,
                    album TEXT,
                    year INTEGER,
                    catno TEXT,
                    format_info TEXT,  -- JSON string of format details
                    condition TEXT DEFAULT 'Mint (M)',
                    sleeve_condition TEXT DEFAULT 'Mint (M)',
                    notes TEXT,
                    relevance_score REAL,
                    match_explanation TEXT,
                    original_query TEXT,
                    added_to_discogs BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_batch_records_discogs_id 
                ON batch_records(discogs_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_batch_records_added_to_discogs 
                ON batch_records(added_to_discogs)
            """)
            
            conn.commit()

    async def add_search_result_to_batch(
        self, 
        search_result: Dict[str, Any], 
        original_query: str,
        condition: str = "Mint (M)",
        sleeve_condition: str = "Mint (M)",
        notes: str = ""
    ) -> int:
        """Add a search result to the batch collection list.
        
        Args:
            search_result: Search result from the search service
            original_query: Original search query
            condition: Media condition
            sleeve_condition: Sleeve condition
            notes: User notes
            
        Returns:
            The ID of the inserted record
        """
        release = search_result["release"]
        
        # Extract format information as JSON
        format_info = json.dumps(release.get("formats", []))
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO batch_records (
                    discogs_id, title, artist, album, year, catno,
                    format_info, condition, sleeve_condition, notes,
                    relevance_score, match_explanation, original_query
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                release.get("id"),
                release.get("title", ""),
                self._extract_artist(release.get("title", "")),
                self._extract_album(release.get("title", "")),
                release.get("year"),
                release.get("catno", ""),
                format_info,
                condition,
                sleeve_condition,
                notes,
                search_result.get("relevance_score", 0.0),
                search_result.get("match_explanation", ""),
                original_query
            ))
            
            conn.commit()
            return cursor.lastrowid

    def _extract_artist(self, title: str) -> str:
        """Extract artist from Discogs title format 'Artist - Album'."""
        if " - " in title:
            return title.split(" - ")[0].strip()
        return ""

    def _extract_album(self, title: str) -> str:
        """Extract album from Discogs title format 'Artist - Album'."""
        if " - " in title:
            parts = title.split(" - ", 1)
            if len(parts) > 1:
                return parts[1].strip()
        return title.strip()

    async def get_batch_records(
        self, 
        include_added_to_discogs: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all records in the batch collection list.
        
        Args:
            include_added_to_discogs: If True, includes records already added to Discogs
            
        Returns:
            List of batch records
        """
        query = """
            SELECT * FROM batch_records
        """
        params = []
        
        if not include_added_to_discogs:
            query += " WHERE added_to_discogs = FALSE"
            
        query += " ORDER BY created_at DESC"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            
            records = []
            for row in cursor.fetchall():
                record = dict(row)
                # Parse format_info JSON
                try:
                    record["format_info"] = json.loads(record["format_info"])
                except (json.JSONDecodeError, TypeError):
                    record["format_info"] = []
                records.append(record)
            
            return records

    async def update_batch_record(
        self,
        record_id: int,
        condition: Optional[str] = None,
        sleeve_condition: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        """Update a batch record.
        
        Args:
            record_id: Database record ID
            condition: New media condition
            sleeve_condition: New sleeve condition
            notes: New notes
            
        Returns:
            True if record was updated
        """
        updates = []
        params = []
        
        if condition is not None:
            updates.append("condition = ?")
            params.append(condition)
            
        if sleeve_condition is not None:
            updates.append("sleeve_condition = ?")
            params.append(sleeve_condition)
            
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
            
        if not updates:
            return False
            
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(record_id)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f"""
                UPDATE batch_records 
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            
            conn.commit()
            return cursor.rowcount > 0

    async def remove_batch_record(self, record_id: int) -> bool:
        """Remove a record from the batch collection list.
        
        Args:
            record_id: Database record ID
            
        Returns:
            True if record was removed
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM batch_records WHERE id = ?", (record_id,))
            conn.commit()
            return cursor.rowcount > 0

    async def mark_as_added_to_discogs(self, record_ids: List[int]) -> int:
        """Mark records as added to Discogs collection.
        
        Args:
            record_ids: List of database record IDs
            
        Returns:
            Number of records updated
        """
        if not record_ids:
            return 0
            
        placeholders = ",".join(["?"] * len(record_ids))
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f"""
                UPDATE batch_records 
                SET added_to_discogs = TRUE, updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
            """, record_ids)
            
            conn.commit()
            return cursor.rowcount

    async def get_record_by_discogs_id(self, discogs_id: int) -> Optional[Dict[str, Any]]:
        """Get a batch record by Discogs ID.
        
        Args:
            discogs_id: Discogs release ID
            
        Returns:
            Record dict or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM batch_records WHERE discogs_id = ?", 
                (discogs_id,)
            )
            
            row = cursor.fetchone()
            if row:
                record = dict(row)
                try:
                    record["format_info"] = json.loads(record["format_info"])
                except (json.JSONDecodeError, TypeError):
                    record["format_info"] = []
                return record
            return None

    async def clear_added_records(self) -> int:
        """Remove all records that have been added to Discogs.
        
        Returns:
            Number of records removed
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM batch_records WHERE added_to_discogs = TRUE")
            conn.commit()
            return cursor.rowcount

    async def get_batch_stats(self) -> Dict[str, int]:
        """Get statistics about batch records.
        
        Returns:
            Dictionary with batch statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN added_to_discogs = FALSE THEN 1 END) as pending,
                    COUNT(CASE WHEN added_to_discogs = TRUE THEN 1 END) as added
                FROM batch_records
            """)
            
            row = cursor.fetchone()
            return {
                "total": row[0],
                "pending": row[1], 
                "added": row[2]
            }