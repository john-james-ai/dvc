"""Data Access Layer for DataSet persistence operations.

Executes SQL against a SQLite connection to persist and retrieve
DataSet records. All methods operate on plain dictionaries to
keep the DAL decoupled from domain entity classes.
"""

import sqlite3
from typing import Any, Optional


class DataSetDAL:
    """Executes SQL for DataSet CRUD operations.

    Attributes:
        _conn: Shared SQLite connection (managed by DataRepoSQLite).
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, data: dict[str, Any]) -> None:
        """Insert or update a dataset record via UPSERT.

        Args:
            data: Dictionary with keys matching the datasets table columns.
        """
        self._conn.execute(
            """
            INSERT INTO datasets (
                uuid, name, description, project, owner,
                status, created_at, updated_at, shared_metadata
            ) VALUES (
                :uuid, :name, :description, :project, :owner,
                :status, :created_at, :updated_at, :shared_metadata
            )
            ON CONFLICT(uuid) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                project = excluded.project,
                owner = excluded.owner,
                status = excluded.status,
                updated_at = excluded.updated_at,
                shared_metadata = excluded.shared_metadata
            """,
            data,
        )

    def get(self, uuid: str) -> Optional[dict[str, Any]]:
        """Retrieve a dataset by UUID.

        Args:
            uuid: Dataset unique identifier.

        Returns:
            Dictionary of dataset fields, or None if not found.
        """
        cur = self._conn.execute(
            "SELECT * FROM datasets WHERE uuid = ?", (uuid,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def get_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Retrieve a dataset by unique name.

        Args:
            name: Dataset human-readable name.

        Returns:
            Dictionary of dataset fields, or None if not found.
        """
        cur = self._conn.execute(
            "SELECT * FROM datasets WHERE name = ?", (name,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def list_all(
        self, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """List all dataset records.

        Args:
            include_deleted: If True, include DELETED datasets.

        Returns:
            List of dataset dictionaries.
        """
        if include_deleted:
            cur = self._conn.execute("SELECT * FROM datasets")
        else:
            cur = self._conn.execute(
                "SELECT * FROM datasets WHERE status != 'DELETED'"
            )
        return [dict(row) for row in cur.fetchall()]
