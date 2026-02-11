"""Data Access Layer for DataVersion persistence operations.

Executes SQL against a SQLite connection to persist and retrieve
DataVersion records. Includes lineage traversal via recursive CTE.
"""

import sqlite3
from typing import Any, Optional


class DataVersionDAL:
    """Executes SQL for DataVersion CRUD operations.

    Attributes:
        _conn: Shared SQLite connection (managed by DataRepoSQLite).
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, data: dict[str, Any]) -> None:
        """Insert or update a dataversion record via UPSERT.

        Args:
            data: Dictionary with keys matching the dataversions table columns.
        """
        self._conn.execute(
            """
            INSERT INTO dataversions (
                uuid, datafile_uuid, version_number, dvc_hash,
                hash_algorithm, storage_uri, storage_type, status,
                source_version_uuid, transformer, metadata,
                created_at, updated_at
            ) VALUES (
                :uuid, :datafile_uuid, :version_number, :dvc_hash,
                :hash_algorithm, :storage_uri, :storage_type, :status,
                :source_version_uuid, :transformer, :metadata,
                :created_at, :updated_at
            )
            ON CONFLICT(uuid) DO UPDATE SET
                dvc_hash = excluded.dvc_hash,
                hash_algorithm = excluded.hash_algorithm,
                storage_uri = excluded.storage_uri,
                status = excluded.status,
                transformer = excluded.transformer,
                metadata = excluded.metadata,
                updated_at = excluded.updated_at
            """,
            data,
        )

    def get(self, uuid: str) -> Optional[dict[str, Any]]:
        """Retrieve a dataversion by UUID.

        Args:
            uuid: DataVersion unique identifier.

        Returns:
            Dictionary of version fields, or None if not found.
        """
        cur = self._conn.execute(
            "SELECT * FROM dataversions WHERE uuid = ?", (uuid,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def get_latest(
        self, datafile_uuid: str
    ) -> Optional[dict[str, Any]]:
        """Retrieve the highest-numbered COMMITTED version for a datafile.

        Args:
            datafile_uuid: Parent datafile UUID.

        Returns:
            Dictionary of version fields, or None if no committed version.
        """
        cur = self._conn.execute(
            "SELECT * FROM dataversions "
            "WHERE datafile_uuid = ? AND status = 'COMMITTED' "
            "ORDER BY version_number DESC LIMIT 1",
            (datafile_uuid,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def list_for_datafile(
        self, datafile_uuid: str, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """List all dataversion records for a datafile, ordered by version_number.

        Args:
            datafile_uuid: Parent datafile UUID.
            include_deleted: If True, include DELETED versions.

        Returns:
            List of version dictionaries ordered by version_number.
        """
        if include_deleted:
            cur = self._conn.execute(
                "SELECT * FROM dataversions "
                "WHERE datafile_uuid = ? ORDER BY version_number",
                (datafile_uuid,),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM dataversions "
                "WHERE datafile_uuid = ? AND status != 'DELETED' "
                "ORDER BY version_number",
                (datafile_uuid,),
            )
        return [dict(row) for row in cur.fetchall()]

    def get_next_version_number(self, datafile_uuid: str) -> int:
        """Get the next available version number (max + 1, or 1).

        Args:
            datafile_uuid: Parent datafile UUID.

        Returns:
            Next sequential version number (starts at 1).
        """
        cur = self._conn.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 "
            "FROM dataversions WHERE datafile_uuid = ?",
            (datafile_uuid,),
        )
        return cur.fetchone()[0]

    def get_lineage_chain(
        self, version_uuid: str, max_depth: int = 100
    ) -> list[dict[str, Any]]:
        """Traverse source_version_uuid pointers via recursive CTE.

        Args:
            version_uuid: Starting version UUID.
            max_depth: Maximum traversal depth.

        Returns:
            Ordered list of version dicts from newest to oldest ancestor.
        """
        cur = self._conn.execute(
            """
            WITH RECURSIVE lineage(
                uuid, datafile_uuid, version_number, dvc_hash,
                hash_algorithm, storage_uri, storage_type, status,
                source_version_uuid, transformer, metadata,
                created_at, updated_at, depth
            ) AS (
                SELECT *, 1 AS depth
                FROM dataversions
                WHERE uuid = ?
                UNION ALL
                SELECT dv.*, l.depth + 1
                FROM dataversions dv
                JOIN lineage l ON dv.uuid = l.source_version_uuid
                WHERE l.depth < ?
            )
            SELECT uuid, datafile_uuid, version_number, dvc_hash,
                   hash_algorithm, storage_uri, storage_type, status,
                   source_version_uuid, transformer, metadata,
                   created_at, updated_at
            FROM lineage
            ORDER BY depth
            """,
            (version_uuid, max_depth),
        )
        return [dict(row) for row in cur.fetchall()]
