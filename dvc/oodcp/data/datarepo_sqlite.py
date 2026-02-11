"""Concrete DataRepo implementation backed by SQLite.

Implements the DataRepo ABC from the Domain Layer by delegating
all I/O to DAL objects that execute SQL on a SQLite database.
Handles entity-to-dict and dict-to-entity conversions, including
JSON serialization for metadata fields and enum mapping for
DataVersion subclass selection.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from dvc.oodcp.data.dal.datafile_dal import DataFileDAL
from dvc.oodcp.data.dal.dataset_dal import DataSetDAL
from dvc.oodcp.data.dal.dataversion_dal import DataVersionDAL
from dvc.oodcp.data.schema import SCHEMA_DDL
from dvc.oodcp.domain.entities.datafile import DataFile
from dvc.oodcp.domain.entities.datarepo import DataRepo
from dvc.oodcp.domain.entities.dataset import DataSet
from dvc.oodcp.domain.entities.dataversion import (
    AzureDataVersion,
    DataVersion,
    GCSDataVersion,
    LocalDataVersion,
    S3DataVersion,
)
from dvc.oodcp.domain.enums import EntityStatus, StorageType, VersionStatus

_VERSION_CLS_MAP = {
    StorageType.S3: S3DataVersion,
    StorageType.GCS: GCSDataVersion,
    StorageType.AZURE: AzureDataVersion,
    StorageType.LOCAL: LocalDataVersion,
}


class DataRepoSQLite(DataRepo):
    """Concrete DataRepo backed by SQLite via DAL objects.

    Manages a single SQLite connection with WAL mode for concurrent
    reads. Creates tables on first access. Delegates all SQL execution
    to DAL classes (DataSetDAL, DataFileDAL, DataVersionDAL).

    Attributes:
        _db_path: Path to SQLite database file (or ':memory:').
        _conn: Lazy-initialized SQLite connection.
        _dataset_dal: DAL for dataset operations.
        _datafile_dal: DAL for datafile operations.
        _dataversion_dal: DAL for dataversion operations.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        """Initialize with database path.

        Args:
            db_path: Path to SQLite database file.
                     Use ':memory:' for in-memory testing.
        """
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._dataset_dal: Optional[DataSetDAL] = None
        self._datafile_dal: Optional[DataFileDAL] = None
        self._dataversion_dal: Optional[DataVersionDAL] = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Lazy-initialize and return the database connection.

        Returns:
            Active SQLite connection with WAL mode and foreign keys.
        """
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._ensure_schema()
            self._dataset_dal = DataSetDAL(self._conn)
            self._datafile_dal = DataFileDAL(self._conn)
            self._dataversion_dal = DataVersionDAL(self._conn)
        return self._conn

    @property
    def dataset_dal(self) -> DataSetDAL:
        """Access the DataSet DAL (triggers connection if needed)."""
        self.conn  # ensure initialized
        return self._dataset_dal

    @property
    def datafile_dal(self) -> DataFileDAL:
        """Access the DataFile DAL (triggers connection if needed)."""
        self.conn  # ensure initialized
        return self._datafile_dal

    @property
    def dataversion_dal(self) -> DataVersionDAL:
        """Access the DataVersion DAL (triggers connection if needed)."""
        self.conn  # ensure initialized
        return self._dataversion_dal

    def _ensure_schema(self) -> None:
        """Create tables and indexes if they don't exist."""
        self._conn.executescript(SCHEMA_DDL)

    # ── DataSet operations ────────────────────────────────────

    def add_dataset(self, dataset: DataSet) -> None:
        data = self._dataset_to_dict(dataset)
        self.dataset_dal.save(data)
        self.conn.commit()

    def get_dataset(self, uuid: str) -> Optional[DataSet]:
        data = self.dataset_dal.get(uuid)
        if data is None:
            return None
        return self._dataset_from_dict(data)

    def get_dataset_by_name(self, name: str) -> Optional[DataSet]:
        data = self.dataset_dal.get_by_name(name)
        if data is None:
            return None
        return self._dataset_from_dict(data)

    def list_datasets(self, include_deleted: bool = False) -> list[DataSet]:
        rows = self.dataset_dal.list_all(include_deleted)
        return [self._dataset_from_dict(row) for row in rows]

    def update_dataset(self, dataset: DataSet) -> None:
        data = self._dataset_to_dict(dataset)
        self.dataset_dal.save(data)
        self.conn.commit()

    # ── DataFile operations ───────────────────────────────────

    def add_datafile(self, datafile: DataFile) -> None:
        data = self._datafile_to_dict(datafile)
        self.datafile_dal.save(data)
        self.conn.commit()

    def get_datafile(self, uuid: str) -> Optional[DataFile]:
        data = self.datafile_dal.get(uuid)
        if data is None:
            return None
        return self._datafile_from_dict(data)

    def get_datafile_by_name(
        self, dataset_uuid: str, name: str
    ) -> Optional[DataFile]:
        data = self.datafile_dal.get_by_name(dataset_uuid, name)
        if data is None:
            return None
        return self._datafile_from_dict(data)

    def list_datafiles(
        self, dataset_uuid: str, include_deleted: bool = False
    ) -> list[DataFile]:
        rows = self.datafile_dal.list_for_dataset(dataset_uuid, include_deleted)
        return [self._datafile_from_dict(row) for row in rows]

    def update_datafile(self, datafile: DataFile) -> None:
        data = self._datafile_to_dict(datafile)
        self.datafile_dal.save(data)
        self.conn.commit()

    # ── DataVersion operations ────────────────────────────────

    def add_dataversion(self, version: DataVersion) -> None:
        data = self._dataversion_to_dict(version)
        self.dataversion_dal.save(data)
        self.conn.commit()

    def get_dataversion(self, uuid: str) -> Optional[DataVersion]:
        data = self.dataversion_dal.get(uuid)
        if data is None:
            return None
        return self._dataversion_from_dict(data)

    def get_latest_dataversion(
        self, datafile_uuid: str
    ) -> Optional[DataVersion]:
        data = self.dataversion_dal.get_latest(datafile_uuid)
        if data is None:
            return None
        return self._dataversion_from_dict(data)

    def list_dataversions(
        self, datafile_uuid: str, include_deleted: bool = False
    ) -> list[DataVersion]:
        rows = self.dataversion_dal.list_for_datafile(
            datafile_uuid, include_deleted
        )
        return [self._dataversion_from_dict(row) for row in rows]

    def update_dataversion(self, version: DataVersion) -> None:
        data = self._dataversion_to_dict(version)
        self.dataversion_dal.save(data)
        self.conn.commit()

    def get_next_version_number(self, datafile_uuid: str) -> int:
        return self.dataversion_dal.get_next_version_number(datafile_uuid)

    # ── Lineage ───────────────────────────────────────────────

    def query_lineage(
        self, version_uuid: str, depth: int = 100
    ) -> list[DataVersion]:
        rows = self.dataversion_dal.get_lineage_chain(version_uuid, depth)
        return [self._dataversion_from_dict(row) for row in rows]

    # ── Lifecycle ─────────────────────────────────────────────

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            self._dataset_dal = None
            self._datafile_dal = None
            self._dataversion_dal = None

    # ── Serialization helpers ─────────────────────────────────

    def _dataset_to_dict(self, dataset: DataSet) -> dict:
        """Convert DataSet entity to persistence dictionary."""
        return {
            "uuid": dataset.uuid,
            "name": dataset.name,
            "description": dataset.description,
            "project": dataset.project,
            "owner": dataset.owner,
            "status": dataset.status.value,
            "created_at": dataset.created_at.isoformat(),
            "updated_at": dataset.updated_at.isoformat(),
            "shared_metadata": json.dumps(dataset.shared_metadata),
        }

    def _dataset_from_dict(self, data: dict) -> DataSet:
        """Reconstruct DataSet entity from persistence dictionary."""
        return DataSet(
            uuid=data["uuid"],
            name=data["name"],
            description=data["description"],
            project=data["project"],
            owner=data["owner"],
            status=EntityStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            shared_metadata=json.loads(data["shared_metadata"]),
            _repo=self,
        )

    def _datafile_to_dict(self, datafile: DataFile) -> dict:
        """Convert DataFile entity to persistence dictionary."""
        return {
            "uuid": datafile.uuid,
            "dataset_uuid": datafile.dataset_uuid,
            "name": datafile.name,
            "description": datafile.description,
            "owner": datafile.owner,
            "status": datafile.status.value,
            "created_at": datafile.created_at.isoformat(),
            "updated_at": datafile.updated_at.isoformat(),
        }

    def _datafile_from_dict(self, data: dict) -> DataFile:
        """Reconstruct DataFile entity from persistence dictionary."""
        return DataFile(
            uuid=data["uuid"],
            dataset_uuid=data["dataset_uuid"],
            name=data["name"],
            description=data["description"],
            owner=data["owner"],
            status=EntityStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            _repo=self,
        )

    def _dataversion_to_dict(self, version: DataVersion) -> dict:
        """Convert DataVersion entity to persistence dictionary."""
        return {
            "uuid": version.uuid,
            "datafile_uuid": version.datafile_uuid,
            "version_number": version.version_number,
            "dvc_hash": version.dvc_hash,
            "hash_algorithm": version.hash_algorithm,
            "storage_uri": version.storage_uri,
            "storage_type": version.storage_type.value,
            "status": version.status.value,
            "source_version_uuid": version.source_version_uuid,
            "transformer": version.transformer,
            "metadata": json.dumps(version.metadata),
            "created_at": version.created_at.isoformat(),
            "updated_at": version.updated_at.isoformat(),
        }

    def _dataversion_from_dict(self, data: dict) -> DataVersion:
        """Reconstruct correct DataVersion subclass from dictionary."""
        storage_type = StorageType(data["storage_type"])
        cls = _VERSION_CLS_MAP.get(storage_type, LocalDataVersion)

        metadata_raw = data["metadata"]
        if isinstance(metadata_raw, str):
            metadata = json.loads(metadata_raw)
        else:
            metadata = metadata_raw or {}

        return cls(
            uuid=data["uuid"],
            datafile_uuid=data["datafile_uuid"],
            version_number=data["version_number"],
            dvc_hash=data["dvc_hash"],
            hash_algorithm=data["hash_algorithm"],
            storage_uri=data["storage_uri"],
            status=VersionStatus(data["status"]),
            source_version_uuid=data["source_version_uuid"],
            transformer=data["transformer"],
            metadata=metadata,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
