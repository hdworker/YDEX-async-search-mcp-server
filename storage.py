"""
Yandex Search API MCP Server - Operation Storage

SQLite-based storage for async search operation IDs.
Tracks pending, completed, and failed operations.

Copyright © 2025 Yandex LLC. Licensed under Apache License 2.0.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any


class OperationStorage:
    """
    SQLite storage for Yandex Search API async operations.
    
    Tracks operation IDs, queries, status, and results.
    Automatically creates the database and table on first use.
    """

    def __init__(self, db_path: str = "operations.db"):
        """
        Initialize the storage with a SQLite database.
        
        Args:
            db_path: Path to the SQLite database file.
                     Defaults to 'operations.db' in the current directory.
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Create the operations table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    result TEXT,
                    folder_id TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON operations(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at ON operations(created_at)
            """)

    def save(self, operation_id: str, query: str, folder_id: str) -> None:
        """
        Save a new operation after async request.
        
        Args:
            operation_id: The Yandex operation ID.
            query: The search query text.
            folder_id: The Yandex Cloud folder ID.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO operations (id, query, status, created_at, folder_id)
                VALUES (?, ?, 'PENDING', ?, ?)
                """,
                (operation_id, query, datetime.utcnow().isoformat(), folder_id)
            )

    def get(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an operation by ID.
        
        Args:
            operation_id: The Yandex operation ID.
            
        Returns:
            Dict with operation data or None if not found.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM operations WHERE id = ?",
                (operation_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def update_result(self, operation_id: str, status: str, result: Optional[str] = None) -> None:
        """
        Update operation status and result.
        
        Args:
            operation_id: The Yandex operation ID.
            status: New status (COMPLETED, FAILED, or PENDING).
            result: The search result (rawData) if completed.
        """
        with sqlite3.connect(self.db_path) as conn:
            completed_at = datetime.utcnow().isoformat() if status in ('COMPLETED', 'FAILED') else None
            conn.execute(
                """
                UPDATE operations 
                SET status = ?, result = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, result, completed_at, operation_id)
            )

    def get_pending(self) -> List[Dict[str, Any]]:
        """
        Get all pending operations.
        
        Returns:
            List of dicts with pending operation data.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM operations WHERE status = 'PENDING' ORDER BY created_at ASC"
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all operations with limit.
        
        Args:
            limit: Maximum number of operations to return.
            
        Returns:
            List of dicts with operation data.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM operations ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def cleanup(self, days: int = 7) -> int:
        """
        Delete operations older than specified days.
        
        Args:
            days: Number of days to keep operations.
            
        Returns:
            Number of deleted operations.
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM operations WHERE created_at < ?",
                (cutoff,)
            )
            return cursor.rowcount

    def count_by_status(self) -> Dict[str, int]:
        """
        Get count of operations by status.
        
        Returns:
            Dict with status counts.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT status, COUNT(*) as count FROM operations GROUP BY status"
            )
            return {row[0]: row[1] for row in cursor.fetchall()}


def get_storage(db_path: str = "operations.db") -> OperationStorage:
    """
    Get or create storage instance.
    
    Args:
        db_path: Path to the SQLite database file.
        
    Returns:
        OperationStorage instance.
    """
    return OperationStorage(db_path)
