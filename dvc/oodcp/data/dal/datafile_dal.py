"""Data Access Layer for DataFile persistence operations.

Executes SQL against a SQLite connection to persist and retrieve
DataFile records.
"""

import sqlite3
from typing import Any, Optional


class DataFileDAL:
    """Executes SQL for DataFile CRUD operations.

    Attributes:
        _conn: Shared SQLite connection (managed by DataRepoSQLite).
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, data: dict[str, Any]) -> None:
        """Insert or update a datafile record via UPSERT.

        Args:
            data: Dictionary with keys matching the datafiles table columns.
        """
        self._conn.execute(
            """
            INSERT INTO datafiles (
                uuid, dataset_uuid, name, description, owner,
                status, created_at, updated_at
            ) VALUES (
                :uuid, :dataset_uuid, :name, :description, :owner,
                :status, :created_at, :updated_at
            )
            ON CONFLICT(uuid) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                owner = excluded.owner,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            data,
        )

    def get(self, uuid: str) -> Optional[dict[str, Any]]:
        """Retrieve a datafile by UUID.

        Args:
            uuid: DataFile unique identifier.

        Returns:
            Dictionary of datafile fields, or None if not found.
        """
        cur = self._conn.execute(
            "SELECT * FROM datafiles WHERE uuid = ?", (uuid,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def get_by_name(
        self, dataset_uuid: str, name: str
    ) -> Optional[dict[str, Any]]:
        """Retrieve a datafile by name within a dataset.

        Args:
            dataset_uuid: Parent dataset UUID.
            name: Logical filename.

        Returns:
            Dictionary of datafile fields, or None if not found.
        """
        cur = self._conn.execute(
            "SELECT * FROM datafiles WHERE dataset_uuid = ? AND name = ?",
            (dataset_uuid, name),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def list_for_dataset(
        self, dataset_uuid: str, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """List all datafile records for a dataset.

        Args:
            dataset_uuid: Parent dataset UUID.
            include_deleted: If True, include DELETED datafiles.

        Returns:
            List of datafile dictionaries.
        """
        if include_deleted:
            cur = self._conn.execute(
                "SELECT * FROM datafiles WHERE dataset_uuid = ?",
                (dataset_uuid,),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM datafiles "
                "WHERE dataset_uuid = ? AND status != 'DELETED'",
                (dataset_uuid,),
            )
        return [dict(row) for row in cur.fetchall()]
