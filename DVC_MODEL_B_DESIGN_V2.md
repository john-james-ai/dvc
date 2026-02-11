# OOD-CP Design Document V2

## 1. Context

Current DVC treats datasets as location-specific paths, forcing data scientists to work through a "file-system lens." Semantically identical information is scattered across Git branches, hashes, and directory paths. There is no native way to manage the Logical Entity separately from its Physical Snapshots.

The OOD-CP adds an object-oriented control plane on top of DVC around four core entities: **DataSet**, **DataFile**, **DataVersion**, and **DataRepo**, plus **DataFactory** classes for creation. It invokes DVC commands for versioning, persistence, pipelines, and experiments rather than replacing them. All backend clients are injected (not instantiated directly), enabling pure mock-based validation.

---

## 2. Architecture Overview

### 2.1 DDD Layer Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  APP LAYER  (dvc/oodcp/app/)                                │
│  Entity Creation & Use Case Orchestration                   │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────┐ │
│  │ DataSet      │ │ DataFile     │ │ DataVersion         │ │
│  │ Factory      │ │ Factory      │ │ Factory             │ │
│  └──────────────┘ └──────────────┘ └─────────────────────┘ │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ OodcpManager (Facade)                                │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  DOMAIN LAYER  (dvc/oodcp/domain/)                          │
│  Entity Definitions, Value Objects, Domain Services         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ DataSet  │ │ DataFile │ │ DataVer  │ │ DataRepo │      │
│  │ (Entity) │ │ (Entity) │ │ (ABC)    │ │ (Aggreg) │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐    │
│  │ Value Objects│ │ Enums        │ │ Domain Services  │    │
│  │ StorageURI   │ │ EntityStatus │ │ LineageService   │    │
│  │ DVCHash      │ │ VersionStat  │ │ IntegrityService │    │
│  └──────────────┘ └──────────────┘ └──────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  REPO LAYER  (dvc/oodcp/repo/)                              │
│  Repository Interfaces & Implementations                    │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │ DataSet      │ │ DataFile     │ │ DataVersion        │  │
│  │ Repository   │ │ Repository   │ │ Repository         │  │
│  └──────────────┘ └──────────────┘ └────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ UnitOfWork (Transaction Boundary)                    │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  DATA LAYER  (dvc/oodcp/data/)                              │
│  Concrete Adapters for DVC, Git, LakeFS                     │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │ DVCStorage   │ │ SQLite       │ │ LakeFS             │  │
│  │ Adapter      │ │ Adapter      │ │ Adapter (stub)     │  │
│  └──────────────┘ └──────────────┘ └────────────────────┘  │
│  Wraps: DataCloud, CacheManager, SCM, sqlite3, lakefs-sdk  │
├─────────────────────────────────────────────────────────────┤
│  INFRASTRUCTURE LAYER  (dvc/oodcp/infrastructure/)          │
│  Gateway Protocols (Abstract Interfaces)                    │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │ Storage      │ │ Metadata     │ │ SCM                │  │
│  │ Gateway      │ │ Gateway      │ │ Gateway            │  │
│  └──────────────┘ └──────────────┘ └────────────────────┘  │
│  (Protocol definitions only — no implementations)           │
└─────────────────────────────────────────────────────────────┘
          │                    │                  │
          ▼                    ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│  DVC CORE  (existing, unmodified)                           │
│  Repo, DataCloud, CacheManager, SCM, Experiments            │
│  dvc_data: HashFileDB, HashInfo, Meta, Transfer             │
│  fsspec: S3, GCS, Azure, Local filesystems                  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Dependency Direction

All dependencies point **downward**. Upper layers depend on lower layers, never the reverse:
- App Layer depends on Domain Layer and Repo Layer
- Domain Layer has **zero** external dependencies (pure Python)
- Repo Layer depends on Infrastructure Layer (gateway protocols)
- Data Layer implements Infrastructure Layer protocols
- Infrastructure Layer defines protocols only (no implementations)

### 2.3 Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Entity style | Mutable `@dataclass` | Entities undergo status transitions (DRAFT→COMMITTED→DELETED) |
| Gateway contracts | PEP 544 `Protocol` | Enables DI and mock-based testing without ABC inheritance |
| Metadata persistence | SQLite at `.dvc/tmp/oodcp/metadata.db` | Follows DVC's `DataIndex` pattern; no external dependencies |
| Domain purity | Domain layer has no imports from DVC | Enables isolated unit testing with mocks |
| Factory pattern | Separate factory per entity type | Separation of creation from use per user spec |

---

## 3. Package Structure

```
dvc/oodcp/
├── __init__.py
├── infrastructure/                    # INFRASTRUCTURE LAYER
│   ├── __init__.py
│   └── gateways/
│       ├── __init__.py
│       ├── storage_gateway.py         # StorageGateway Protocol
│       ├── metadata_gateway.py        # MetadataGateway Protocol
│       └── scm_gateway.py            # SCMGateway Protocol
├── data/                              # DATA LAYER
│   ├── __init__.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── dvc_storage_adapter.py     # DVCStorageAdapter
│   │   ├── sqlite_adapter.py         # SQLiteMetadataAdapter
│   │   └── lakefs_adapter.py         # LakeFSStorageAdapter (stub)
│   └── schema.py                      # SQLite DDL
├── repo/                              # REPO LAYER
│   ├── __init__.py
│   ├── dataset_repository.py          # DataSetRepository
│   ├── datafile_repository.py         # DataFileRepository
│   ├── dataversion_repository.py      # DataVersionRepository
│   └── unit_of_work.py               # UnitOfWork
├── domain/                            # DOMAIN LAYER
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── dataset.py                 # DataSet entity
│   │   ├── datafile.py                # DataFile entity
│   │   ├── dataversion.py            # DataVersion ABC + concrete subclasses
│   │   └── datarepo.py               # DataRepo aggregate root
│   ├── value_objects.py               # StorageURI, DVCHash, VersionNumber
│   ├── enums.py                       # EntityStatus, VersionStatus, StorageType
│   ├── exceptions.py                  # Domain-specific exceptions
│   └── services/
│       ├── __init__.py
│       ├── lineage_service.py         # LineageService
│       └── integrity_service.py       # IntegrityService
├── app/                               # APP LAYER
│   ├── __init__.py
│   ├── factory/
│   │   ├── __init__.py
│   │   ├── dataset_factory.py         # DataSetFactory
│   │   ├── datafile_factory.py        # DataFileFactory
│   │   └── dataversion_factory.py    # DataVersionFactory
│   └── manager.py                     # OodcpManager facade
└── integration/                       # DVC Integration (crosses layers)
    ├── __init__.py
    ├── pipeline.py                    # OodcpDependency
    └── experiments.py                 # ExperimentVersionMapper
```

---

## 4. Detailed Class Definitions

### 4.1 INFRASTRUCTURE LAYER — Gateway Protocols

#### 4.1.1 StorageGateway (`dvc/oodcp/infrastructure/gateways/storage_gateway.py`)

```python
from typing import Optional, Protocol, runtime_checkable

@runtime_checkable
class StorageGateway(Protocol):
    """Abstract gateway for data storage operations.

    Defines the contract for pushing, pulling, verifying, and transferring
    data between storage backends. Implementations wrap specific storage
    systems (DVC remotes, LakeFS, local filesystem).

    All methods accept hash-based identifiers and storage URIs, keeping
    the domain layer decoupled from any specific storage technology.
    """

    def push(
        self,
        source_path: str,
        storage_uri: str,
        remote_name: Optional[str] = None,
        jobs: Optional[int] = None,
    ) -> tuple[str, str]:
        """Push local data to remote storage.

        Args:
            source_path: Absolute path to local file or directory.
            storage_uri: Target URI (e.g., "s3://bucket/path").
            remote_name: Named remote from DVC config. If None, uses default.
            jobs: Number of parallel transfer jobs. If None, uses default.

        Returns:
            Tuple of (dvc_hash: str, hash_algorithm: str) for the pushed data.

        Raises:
            StorageError: If the push operation fails.
        """
        ...

    def pull(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        dest_path: str,
        remote_name: Optional[str] = None,
        jobs: Optional[int] = None,
    ) -> str:
        """Pull data from remote storage to local path.

        Args:
            dvc_hash: Content-addressed hash of the data.
            hash_algorithm: Algorithm used for hashing (e.g., "md5").
            dest_path: Local destination path.
            remote_name: Named remote from DVC config. If None, uses default.
            jobs: Number of parallel transfer jobs. If None, uses default.

        Returns:
            Absolute path to the retrieved data.

        Raises:
            StorageError: If the pull operation fails.
            DataNotFoundError: If the hash does not exist on the remote.
        """
        ...

    def verify(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        remote_name: Optional[str] = None,
    ) -> bool:
        """Verify that data exists and is intact on remote storage.

        Args:
            dvc_hash: Content-addressed hash of the data.
            hash_algorithm: Algorithm used for hashing.
            remote_name: Named remote from DVC config.

        Returns:
            True if data exists and hash matches, False otherwise.
        """
        ...

    def transfer(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        source_remote: str,
        dest_remote: str,
        jobs: Optional[int] = None,
    ) -> bool:
        """Transfer data between two remote storage locations.

        Args:
            dvc_hash: Content-addressed hash of the data.
            hash_algorithm: Algorithm used for hashing.
            source_remote: Name of source remote.
            dest_remote: Name of destination remote.
            jobs: Number of parallel transfer jobs.

        Returns:
            True if transfer succeeded, False otherwise.

        Raises:
            StorageError: If the transfer operation fails.
        """
        ...
```

#### 4.1.2 MetadataGateway (`dvc/oodcp/infrastructure/gateways/metadata_gateway.py`)

```python
from typing import Any, Optional, Protocol, runtime_checkable

@runtime_checkable
class MetadataGateway(Protocol):
    """Abstract gateway for OOD-CP metadata persistence.

    Defines the contract for storing and retrieving DataSet, DataFile,
    and DataVersion metadata. Implementations may use SQLite, PostgreSQL,
    or any other persistence mechanism.

    All methods operate on plain dictionaries to keep the gateway
    decoupled from domain entity classes.
    """

    def save_dataset(self, data: dict[str, Any]) -> None:
        """Persist a DataSet record (insert or update).

        Args:
            data: Dictionary with keys: uuid, name, description, project,
                  owner, status, created_at, updated_at, shared_metadata.

        Raises:
            MetadataError: If persistence fails.
            DuplicateNameError: If a dataset with the same name already exists.
        """
        ...

    def get_dataset(self, uuid: str) -> Optional[dict[str, Any]]:
        """Retrieve a DataSet record by UUID.

        Args:
            uuid: The dataset's unique identifier.

        Returns:
            Dictionary of dataset fields, or None if not found.
        """
        ...

    def get_dataset_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Retrieve a DataSet record by name.

        Args:
            name: The dataset's human-readable name.

        Returns:
            Dictionary of dataset fields, or None if not found.
        """
        ...

    def list_datasets(
        self, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """List all DataSet records.

        Args:
            include_deleted: If True, include DELETED datasets.

        Returns:
            List of dataset dictionaries.
        """
        ...

    def save_datafile(self, data: dict[str, Any]) -> None:
        """Persist a DataFile record (insert or update).

        Args:
            data: Dictionary with keys: uuid, dataset_uuid, name,
                  description, owner, status, created_at, updated_at.

        Raises:
            MetadataError: If persistence fails.
            DuplicateNameError: If a file with the same name exists
                                in the same dataset.
        """
        ...

    def get_datafile(self, uuid: str) -> Optional[dict[str, Any]]:
        """Retrieve a DataFile record by UUID.

        Args:
            uuid: The datafile's unique identifier.

        Returns:
            Dictionary of datafile fields, or None if not found.
        """
        ...

    def get_datafile_by_name(
        self, dataset_uuid: str, name: str
    ) -> Optional[dict[str, Any]]:
        """Retrieve a DataFile by name within a dataset.

        Args:
            dataset_uuid: Parent dataset UUID.
            name: The datafile's logical name.

        Returns:
            Dictionary of datafile fields, or None if not found.
        """
        ...

    def list_datafiles(
        self, dataset_uuid: str, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """List all DataFile records for a dataset.

        Args:
            dataset_uuid: Parent dataset UUID.
            include_deleted: If True, include DELETED datafiles.

        Returns:
            List of datafile dictionaries.
        """
        ...

    def save_dataversion(self, data: dict[str, Any]) -> None:
        """Persist a DataVersion record (insert or update).

        Args:
            data: Dictionary with keys: uuid, datafile_uuid, version_number,
                  dvc_hash, hash_algorithm, storage_uri, storage_type,
                  status, source_version_uuid, transformer, metadata,
                  created_at, updated_at.

        Raises:
            MetadataError: If persistence fails.
        """
        ...

    def get_dataversion(self, uuid: str) -> Optional[dict[str, Any]]:
        """Retrieve a DataVersion record by UUID.

        Args:
            uuid: The version's unique identifier.

        Returns:
            Dictionary of version fields, or None if not found.
        """
        ...

    def get_latest_dataversion(
        self, datafile_uuid: str
    ) -> Optional[dict[str, Any]]:
        """Retrieve the highest-numbered COMMITTED version for a datafile.

        Args:
            datafile_uuid: Parent datafile UUID.

        Returns:
            Dictionary of version fields, or None if no committed version.
        """
        ...

    def list_dataversions(
        self, datafile_uuid: str, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """List all DataVersion records for a datafile.

        Args:
            datafile_uuid: Parent datafile UUID.
            include_deleted: If True, include DELETED versions.

        Returns:
            List of version dictionaries ordered by version_number.
        """
        ...

    def get_next_version_number(self, datafile_uuid: str) -> int:
        """Get the next available version number for a datafile.

        Args:
            datafile_uuid: Parent datafile UUID.

        Returns:
            Next sequential version number (starts at 1).
        """
        ...

    def get_lineage_chain(
        self, version_uuid: str, max_depth: int = 100
    ) -> list[dict[str, Any]]:
        """Traverse source_version_uuid pointers to build lineage.

        Args:
            version_uuid: Starting version UUID.
            max_depth: Maximum traversal depth.

        Returns:
            Ordered list of version dicts from newest to oldest ancestor.
        """
        ...

    def close(self) -> None:
        """Release any held resources (connections, file handles)."""
        ...
```

#### 4.1.3 SCMGateway (`dvc/oodcp/infrastructure/gateways/scm_gateway.py`)

```python
from typing import Optional, Protocol, runtime_checkable

@runtime_checkable
class SCMGateway(Protocol):
    """Abstract gateway for source control operations.

    Used by OOD-CP to track metadata files and resolve Git revisions
    without directly depending on scmrepo or Git.
    """

    def track_file(self, path: str) -> None:
        """Stage a file for the next commit.

        Args:
            path: Path to file to track.
        """
        ...

    def get_rev(self) -> str:
        """Get current HEAD revision SHA.

        Returns:
            Hex string of current commit SHA.
        """
        ...

    def resolve_rev(self, rev: str) -> str:
        """Resolve a revision reference to a commit SHA.

        Args:
            rev: Branch name, tag, or partial SHA.

        Returns:
            Full hex SHA of the resolved commit.
        """
        ...
```

---

### 4.2 DATA LAYER — Concrete Adapters

#### 4.2.1 DVCStorageAdapter (`dvc/oodcp/data/adapters/dvc_storage_adapter.py`)

```python
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from dvc.repo import Repo

class DVCStorageAdapter:
    """Concrete StorageGateway implementation wrapping DVC DataCloud.

    Delegates push/pull/verify/transfer operations to DVC's DataCloud
    and CacheManager. Bridges OOD-CP's hash/URI model with DVC's
    HashInfo-based object storage.

    This is the only class that imports from dvc.data_cloud and
    dvc.cachemgr, keeping all DVC-specific knowledge in the Data Layer.

    Attributes:
        _repo: Reference to the DVC Repo instance.
    """

    def __init__(self, repo: "Repo") -> None:
        """Initialize with a DVC Repo instance.

        Args:
            repo: Initialized DVC Repo providing cloud and cache access.
        """
        self._repo = repo

    def push(
        self,
        source_path: str,
        storage_uri: str,
        remote_name: Optional[str] = None,
        jobs: Optional[int] = None,
    ) -> tuple[str, str]:
        """Push local data to remote via DVC.

        Builds a content hash using dvc_data.hashfile.build, stages
        to local cache, then pushes to remote via DataCloud.push().

        Args:
            source_path: Absolute path to local file or directory.
            storage_uri: Target URI (used to resolve remote name).
            remote_name: DVC remote name override.
            jobs: Parallel transfer jobs.

        Returns:
            Tuple of (dvc_hash, hash_algorithm).
        """
        ...

    def pull(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        dest_path: str,
        remote_name: Optional[str] = None,
        jobs: Optional[int] = None,
    ) -> str:
        """Pull data from remote via DVC.

        Converts (dvc_hash, hash_algorithm) to HashInfo, calls
        DataCloud.pull(), then checks out to dest_path.

        Args:
            dvc_hash: Content hash value.
            hash_algorithm: Hash algorithm name (e.g., "md5").
            dest_path: Local destination path.
            remote_name: DVC remote name override.
            jobs: Parallel transfer jobs.

        Returns:
            Absolute path to retrieved data.
        """
        ...

    def verify(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        remote_name: Optional[str] = None,
    ) -> bool:
        """Verify data integrity on remote via DVC.

        Converts to HashInfo and calls DataCloud.status() to check
        whether the object exists on the remote.

        Args:
            dvc_hash: Content hash value.
            hash_algorithm: Hash algorithm name.
            remote_name: DVC remote name override.

        Returns:
            True if data exists and is intact.
        """
        ...

    def transfer(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        source_remote: str,
        dest_remote: str,
        jobs: Optional[int] = None,
    ) -> bool:
        """Transfer data between remotes via DVC.

        Gets ODB instances for both remotes and calls
        DataCloud.transfer().

        Args:
            dvc_hash: Content hash value.
            hash_algorithm: Hash algorithm name.
            source_remote: Source remote name.
            dest_remote: Destination remote name.
            jobs: Parallel transfer jobs.

        Returns:
            True if transfer succeeded.
        """
        ...
```

#### 4.2.2 SQLiteMetadataAdapter (`dvc/oodcp/data/adapters/sqlite_adapter.py`)

```python
import sqlite3
from typing import Any, Optional

class SQLiteMetadataAdapter:
    """Concrete MetadataGateway implementation using SQLite.

    Stores OOD-CP metadata in a SQLite database at
    .dvc/tmp/oodcp/metadata.db. Uses WAL mode for concurrent reads.
    JSON TEXT columns for shared_metadata and metadata dicts.

    Attributes:
        _db_path: Path to the SQLite database file.
        _conn: Active SQLite connection (lazy-initialized).
    """

    def __init__(self, db_path: str) -> None:
        """Initialize with database path.

        Args:
            db_path: Path to SQLite database file.
                     Use \":memory:\" for in-memory testing.
        """
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Lazy-initialize and return the database connection.

        Returns:
            Active SQLite connection with WAL mode and foreign keys.
        """
        ...

    def _ensure_schema(self) -> None:
        """Create tables and indexes if they don't exist.

        Creates: datasets, datafiles, dataversions tables.
        Creates indexes on foreign keys and unique constraints.
        """
        ...

    def save_dataset(self, data: dict[str, Any]) -> None:
        """Insert or update a dataset record via UPSERT."""
        ...

    def get_dataset(self, uuid: str) -> Optional[dict[str, Any]]:
        """Retrieve dataset by UUID."""
        ...

    def get_dataset_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Retrieve dataset by unique name."""
        ...

    def list_datasets(
        self, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """List datasets, optionally including DELETED."""
        ...

    def save_datafile(self, data: dict[str, Any]) -> None:
        """Insert or update a datafile record via UPSERT."""
        ...

    def get_datafile(self, uuid: str) -> Optional[dict[str, Any]]:
        """Retrieve datafile by UUID."""
        ...

    def get_datafile_by_name(
        self, dataset_uuid: str, name: str
    ) -> Optional[dict[str, Any]]:
        """Retrieve datafile by name within a dataset."""
        ...

    def list_datafiles(
        self, dataset_uuid: str, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """List datafiles for a dataset."""
        ...

    def save_dataversion(self, data: dict[str, Any]) -> None:
        """Insert or update a dataversion record via UPSERT."""
        ...

    def get_dataversion(self, uuid: str) -> Optional[dict[str, Any]]:
        """Retrieve dataversion by UUID."""
        ...

    def get_latest_dataversion(
        self, datafile_uuid: str
    ) -> Optional[dict[str, Any]]:
        """Get highest-numbered COMMITTED version for a datafile."""
        ...

    def list_dataversions(
        self, datafile_uuid: str, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """List dataversions for a datafile, ordered by version_number."""
        ...

    def get_next_version_number(self, datafile_uuid: str) -> int:
        """Get next sequential version number (max + 1, or 1)."""
        ...

    def get_lineage_chain(
        self, version_uuid: str, max_depth: int = 100
    ) -> list[dict[str, Any]]:
        """Recursive CTE traversal of source_version_uuid pointers."""
        ...

    def close(self) -> None:
        """Close the database connection."""
        ...
```

#### 4.2.3 SQLite Schema (`dvc/oodcp/data/schema.py`)

```python
SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS datasets (
    uuid          TEXT PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    description   TEXT NOT NULL DEFAULT '',
    project       TEXT NOT NULL DEFAULT '',
    owner         TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    shared_metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS datafiles (
    uuid          TEXT PRIMARY KEY,
    dataset_uuid  TEXT NOT NULL REFERENCES datasets(uuid),
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    owner         TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE(dataset_uuid, name)
);

CREATE TABLE IF NOT EXISTS dataversions (
    uuid                TEXT PRIMARY KEY,
    datafile_uuid       TEXT NOT NULL REFERENCES datafiles(uuid),
    version_number      INTEGER NOT NULL,
    dvc_hash            TEXT NOT NULL DEFAULT '',
    hash_algorithm      TEXT NOT NULL DEFAULT 'md5',
    storage_uri         TEXT NOT NULL DEFAULT '',
    storage_type        TEXT NOT NULL DEFAULT 'LOCAL',
    status              TEXT NOT NULL DEFAULT 'DRAFT',
    source_version_uuid TEXT REFERENCES dataversions(uuid),
    transformer         TEXT NOT NULL DEFAULT '',
    metadata            TEXT NOT NULL DEFAULT '{}',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    UNIQUE(datafile_uuid, version_number)
);

CREATE INDEX IF NOT EXISTS idx_datafiles_dataset
    ON datafiles(dataset_uuid);
CREATE INDEX IF NOT EXISTS idx_dataversions_datafile
    ON dataversions(datafile_uuid);
CREATE INDEX IF NOT EXISTS idx_dataversions_source
    ON dataversions(source_version_uuid);
"""
```

#### 4.2.4 LakeFSStorageAdapter (`dvc/oodcp/data/adapters/lakefs_adapter.py`)

```python
from typing import Optional

class LakeFSStorageAdapter:
    """Concrete StorageGateway implementation for LakeFS.

    Stub implementation for Phase 3+. LakeFS provides an S3-compatible
    API, so this adapter will wrap the lakefs-sdk client to push/pull
    data via LakeFS branches and commits.

    Attributes:
        _endpoint: LakeFS server endpoint URL.
        _access_key_id: LakeFS access key.
        _secret_access_key: LakeFS secret key.
        _repository: LakeFS repository name.
    """

    def __init__(
        self,
        endpoint: str,
        access_key_id: str,
        secret_access_key: str,
        repository: str,
    ) -> None:
        """Initialize with LakeFS connection parameters.

        Args:
            endpoint: LakeFS server URL (e.g., "https://lakefs.example.com").
            access_key_id: LakeFS access key ID.
            secret_access_key: LakeFS secret access key.
            repository: LakeFS repository name.
        """
        ...

    def push(
        self,
        source_path: str,
        storage_uri: str,
        remote_name: Optional[str] = None,
        jobs: Optional[int] = None,
    ) -> tuple[str, str]:
        """Push data to LakeFS repository."""
        raise NotImplementedError("LakeFS adapter not yet implemented")

    def pull(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        dest_path: str,
        remote_name: Optional[str] = None,
        jobs: Optional[int] = None,
    ) -> str:
        """Pull data from LakeFS repository."""
        raise NotImplementedError("LakeFS adapter not yet implemented")

    def verify(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        remote_name: Optional[str] = None,
    ) -> bool:
        """Verify data on LakeFS repository."""
        raise NotImplementedError("LakeFS adapter not yet implemented")

    def transfer(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        source_remote: str,
        dest_remote: str,
        jobs: Optional[int] = None,
    ) -> bool:
        """Transfer data between LakeFS branches."""
        raise NotImplementedError("LakeFS adapter not yet implemented")
```

---

### 4.3 REPO LAYER — Repositories

#### 4.3.1 DataSetRepository (`dvc/oodcp/repo/dataset_repository.py`)

```python
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.dataset import DataSet
    from dvc.oodcp.infrastructure.gateways.metadata_gateway import (
        MetadataGateway,
    )

class DataSetRepository:
    """Repository for persisting and retrieving DataSet entities.

    Translates between DataSet domain objects and the flat dictionary
    format expected by MetadataGateway. Handles serialization of
    shared_metadata (dict → JSON string) and timestamp formatting.

    Attributes:
        _gateway: Injected MetadataGateway for persistence operations.
    """

    def __init__(self, gateway: "MetadataGateway") -> None:
        """Initialize with a MetadataGateway.

        Args:
            gateway: Concrete gateway implementation (e.g., SQLiteMetadataAdapter).
        """
        self._gateway = gateway

    def save(self, dataset: "DataSet") -> None:
        """Persist a DataSet entity.

        Converts the DataSet to a dictionary and delegates to the gateway.

        Args:
            dataset: DataSet entity to persist.
        """
        ...

    def get(self, uuid: str) -> Optional["DataSet"]:
        """Retrieve a DataSet by UUID.

        Args:
            uuid: DataSet unique identifier.

        Returns:
            Reconstructed DataSet entity, or None if not found.
        """
        ...

    def get_by_name(self, name: str) -> Optional["DataSet"]:
        """Retrieve a DataSet by name.

        Args:
            name: DataSet human-readable name.

        Returns:
            Reconstructed DataSet entity, or None if not found.
        """
        ...

    def list_all(
        self, include_deleted: bool = False
    ) -> list["DataSet"]:
        """List all DataSet entities.

        Args:
            include_deleted: If True, include DELETED datasets.

        Returns:
            List of DataSet entities.
        """
        ...

    def _to_dict(self, dataset: "DataSet") -> dict:
        """Convert DataSet entity to persistence dictionary."""
        ...

    def _from_dict(self, data: dict) -> "DataSet":
        """Reconstruct DataSet entity from persistence dictionary."""
        ...
```

#### 4.3.2 DataFileRepository (`dvc/oodcp/repo/datafile_repository.py`)

```python
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.datafile import DataFile
    from dvc.oodcp.infrastructure.gateways.metadata_gateway import (
        MetadataGateway,
    )

class DataFileRepository:
    """Repository for persisting and retrieving DataFile entities.

    Attributes:
        _gateway: Injected MetadataGateway for persistence operations.
    """

    def __init__(self, gateway: "MetadataGateway") -> None:
        """Initialize with a MetadataGateway.

        Args:
            gateway: Concrete gateway implementation.
        """
        self._gateway = gateway

    def save(self, datafile: "DataFile") -> None:
        """Persist a DataFile entity.

        Args:
            datafile: DataFile entity to persist.
        """
        ...

    def get(self, uuid: str) -> Optional["DataFile"]:
        """Retrieve a DataFile by UUID.

        Args:
            uuid: DataFile unique identifier.

        Returns:
            Reconstructed DataFile entity, or None if not found.
        """
        ...

    def get_by_name(
        self, dataset_uuid: str, name: str
    ) -> Optional["DataFile"]:
        """Retrieve a DataFile by name within a dataset.

        Args:
            dataset_uuid: Parent dataset UUID.
            name: Logical filename.

        Returns:
            Reconstructed DataFile entity, or None if not found.
        """
        ...

    def list_for_dataset(
        self, dataset_uuid: str, include_deleted: bool = False
    ) -> list["DataFile"]:
        """List all DataFiles belonging to a dataset.

        Args:
            dataset_uuid: Parent dataset UUID.
            include_deleted: If True, include DELETED files.

        Returns:
            List of DataFile entities.
        """
        ...

    def _to_dict(self, datafile: "DataFile") -> dict:
        """Convert DataFile entity to persistence dictionary."""
        ...

    def _from_dict(self, data: dict) -> "DataFile":
        """Reconstruct DataFile entity from persistence dictionary."""
        ...
```

#### 4.3.3 DataVersionRepository (`dvc/oodcp/repo/dataversion_repository.py`)

```python
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.dataversion import DataVersion
    from dvc.oodcp.infrastructure.gateways.metadata_gateway import (
        MetadataGateway,
    )

class DataVersionRepository:
    """Repository for persisting and retrieving DataVersion entities.

    Handles serialization of the metadata dict (JSON) and maps
    storage_type to the correct DataVersion subclass on retrieval.

    Attributes:
        _gateway: Injected MetadataGateway for persistence operations.
    """

    def __init__(self, gateway: "MetadataGateway") -> None:
        """Initialize with a MetadataGateway.

        Args:
            gateway: Concrete gateway implementation.
        """
        self._gateway = gateway

    def save(self, version: "DataVersion") -> None:
        """Persist a DataVersion entity.

        Args:
            version: DataVersion entity to persist.
        """
        ...

    def get(self, uuid: str) -> Optional["DataVersion"]:
        """Retrieve a DataVersion by UUID.

        Maps storage_type field to the correct concrete subclass.

        Args:
            uuid: DataVersion unique identifier.

        Returns:
            Reconstructed DataVersion subclass instance, or None.
        """
        ...

    def get_latest(
        self, datafile_uuid: str
    ) -> Optional["DataVersion"]:
        """Retrieve the latest COMMITTED version for a datafile.

        Args:
            datafile_uuid: Parent datafile UUID.

        Returns:
            DataVersion with highest version_number in COMMITTED status.
        """
        ...

    def list_for_datafile(
        self, datafile_uuid: str, include_deleted: bool = False
    ) -> list["DataVersion"]:
        """List all versions for a datafile.

        Args:
            datafile_uuid: Parent datafile UUID.
            include_deleted: If True, include DELETED versions.

        Returns:
            List of DataVersion entities ordered by version_number.
        """
        ...

    def get_next_version_number(self, datafile_uuid: str) -> int:
        """Get the next available version number.

        Args:
            datafile_uuid: Parent datafile UUID.

        Returns:
            Next sequential version number (starts at 1).
        """
        ...

    def get_lineage(
        self, version_uuid: str, max_depth: int = 100
    ) -> list["DataVersion"]:
        """Build lineage chain by traversing source_version_uuid.

        Args:
            version_uuid: Starting version UUID.
            max_depth: Maximum traversal depth.

        Returns:
            Ordered list from newest to oldest ancestor.
        """
        ...

    def _to_dict(self, version: "DataVersion") -> dict:
        """Convert DataVersion entity to persistence dictionary."""
        ...

    def _from_dict(self, data: dict) -> "DataVersion":
        """Reconstruct correct DataVersion subclass from dictionary."""
        ...
```

#### 4.3.4 UnitOfWork (`dvc/oodcp/repo/unit_of_work.py`)

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dvc.oodcp.infrastructure.gateways.metadata_gateway import (
        MetadataGateway,
    )
    from dvc.oodcp.repo.datafile_repository import DataFileRepository
    from dvc.oodcp.repo.dataset_repository import DataSetRepository
    from dvc.oodcp.repo.dataversion_repository import DataVersionRepository

class UnitOfWork:
    """Transaction boundary for coordinated persistence.

    Groups multiple repository operations into a single atomic
    transaction. Uses SQLite's native transaction support.

    Usage:
        with UnitOfWork(gateway) as uow:
            uow.datasets.save(dataset)
            uow.datafiles.save(datafile)
            uow.dataversions.save(version)
        # Auto-commits on exit, rolls back on exception.

    Attributes:
        datasets: DataSetRepository bound to this transaction.
        datafiles: DataFileRepository bound to this transaction.
        dataversions: DataVersionRepository bound to this transaction.
    """

    def __init__(self, gateway: "MetadataGateway") -> None:
        """Initialize repositories with the shared gateway.

        Args:
            gateway: MetadataGateway providing transactional persistence.
        """
        self._gateway = gateway
        self.datasets: DataSetRepository = DataSetRepository(gateway)
        self.datafiles: DataFileRepository = DataFileRepository(gateway)
        self.dataversions: DataVersionRepository = DataVersionRepository(
            gateway
        )

    def __enter__(self) -> "UnitOfWork":
        """Begin a transaction.

        Returns:
            Self for use in with-statement.
        """
        ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Commit on success, rollback on exception.

        Args:
            exc_type: Exception type if raised, None otherwise.
            exc_val: Exception value if raised, None otherwise.
            exc_tb: Traceback if raised, None otherwise.
        """
        ...

    def commit(self) -> None:
        """Explicitly commit the current transaction."""
        ...

    def rollback(self) -> None:
        """Explicitly rollback the current transaction."""
        ...
```

---

### 4.4 DOMAIN LAYER — Entities, Value Objects, Enums, Services

#### 4.4.1 Enums (`dvc/oodcp/domain/enums.py`)

```python
from enum import Enum

class EntityStatus(str, Enum):
    """Lifecycle status for DataSet and DataFile entities."""
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"

class VersionStatus(str, Enum):
    """Lifecycle status for DataVersion entities."""
    DRAFT = "DRAFT"
    COMMITTED = "COMMITTED"
    DELETED = "DELETED"

class StorageType(str, Enum):
    """Supported storage backend types for DataVersion."""
    S3 = "S3"
    GCS = "GCS"
    AZURE = "AZURE"
    LOCAL = "LOCAL"
```

#### 4.4.2 Value Objects (`dvc/oodcp/domain/value_objects.py`)

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class DVCHash:
    """Immutable content-addressed hash produced by DVC.

    Attributes:
        value: The hex string hash value (e.g., "d41d8cd9...").
        algorithm: Hash algorithm name (e.g., "md5", "md5-dos2unix").
    """
    value: str
    algorithm: str = "md5"

    def __bool__(self) -> bool:
        """Return True if hash value is non-empty."""
        return bool(self.value)

@dataclass(frozen=True)
class StorageURI:
    """Immutable physical address of versioned data.

    Attributes:
        uri: Full URI string (e.g., "s3://bucket/path", "/local/path").
    """
    uri: str

    @property
    def scheme(self) -> str:
        """Extract scheme from URI (e.g., 's3', 'gs', 'file').

        Returns:
            URI scheme string, or empty string for local paths.
        """
        ...

    def __str__(self) -> str:
        return self.uri

@dataclass(frozen=True)
class VersionNumber:
    """Immutable sequential version identifier.

    Attributes:
        value: Positive integer version number (>= 1).
    """
    value: int

    def __post_init__(self) -> None:
        """Validate that version number is >= 1."""
        if self.value < 1:
            raise ValueError(
                f"Version number must be >= 1, got {self.value}"
            )

    def __int__(self) -> int:
        return self.value
```

#### 4.4.3 Exceptions (`dvc/oodcp/domain/exceptions.py`)

```python
class OodcpError(Exception):
    """Base exception for all OOD-CP errors."""

class EntityNotFoundError(OodcpError):
    """Raised when a requested entity does not exist.

    Attributes:
        entity_type: Type name (e.g., "DataSet", "DataFile").
        identifier: UUID or name used in the lookup.
    """
    def __init__(self, entity_type: str, identifier: str) -> None:
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} not found: {identifier}")

class DuplicateNameError(OodcpError):
    """Raised when an entity name conflicts with an existing one.

    Attributes:
        entity_type: Type name.
        name: The conflicting name.
    """
    def __init__(self, entity_type: str, name: str) -> None:
        self.entity_type = entity_type
        self.name = name
        super().__init__(f"{entity_type} already exists: {name}")

class InvalidStatusTransitionError(OodcpError):
    """Raised when an entity status change violates lifecycle rules.

    Attributes:
        current: Current status value.
        target: Attempted target status.
    """
    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition from {current} to {target}")

class StorageError(OodcpError):
    """Raised when a storage operation fails."""

class DataNotFoundError(StorageError):
    """Raised when requested data does not exist on remote."""

class IntegrityError(OodcpError):
    """Raised when data hash verification fails."""

class DeleteConstraintError(OodcpError):
    """Raised when deletion is blocked by active children."""
```

#### 4.4.4 DataSet Entity (`dvc/oodcp/domain/entities/dataset.py`)

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from dvc.oodcp.domain.enums import EntityStatus

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.datafile import DataFile
    from dvc.oodcp.repo.datafile_repository import DataFileRepository
    from dvc.oodcp.repo.dataset_repository import DataSetRepository

@dataclass
class DataSet:
    """A logical grouping of related data entities.

    Provides the domain context and shared metadata for a collection
    of DataFiles (e.g., CIFAR-10). Does not carry a version itself;
    acts as a namespace and registry for DataFile objects.

    Attributes:
        uuid: Unique identifier (UUID v4 string).
        name: Human-readable name (e.g., "Object-Detection-Alpha").
        description: Summary of the dataset's purpose or contents.
        project: Identity of the project team responsible.
        owner: Identity of the user responsible for the collection.
        status: Lifecycle status (ACTIVE or DELETED).
        created_at: When this dataset was first created.
        updated_at: When this dataset was last modified.
        shared_metadata: Key-value pairs applying to all files
                         (e.g., License, Data Source).
        _dataset_repo: Injected repository for self-persistence.
        _datafile_repo: Injected repository for child DataFile ops.
    """

    uuid: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    project: str = ""
    owner: str = ""
    status: EntityStatus = EntityStatus.ACTIVE
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    shared_metadata: dict = field(default_factory=dict)

    # Injected repositories (not persisted)
    _dataset_repo: Optional["DataSetRepository"] = field(
        default=None, repr=False, compare=False
    )
    _datafile_repo: Optional["DataFileRepository"] = field(
        default=None, repr=False, compare=False
    )

    def addfile(
        self,
        name: str,
        description: str = "",
        owner: str = "",
    ) -> "DataFile":
        """Register a new DataFile within this dataset.

        Creates a DataFile linked to this DataSet's UUID and persists
        it via the injected repository.

        Args:
            name: Logical filename (must be unique within this dataset).
            description: Optional summary of the file's purpose.
            owner: Optional owner identity.

        Returns:
            Newly created DataFile entity.

        Raises:
            DuplicateNameError: If name already exists in this dataset.
        """
        ...

    def getfile(
        self, name: Optional[str] = None, uuid: Optional[str] = None
    ) -> "DataFile":
        """Retrieve a DataFile by name or UUID.

        Args:
            name: Logical filename to look up.
            uuid: DataFile UUID to look up.

        Returns:
            The matching DataFile entity.

        Raises:
            EntityNotFoundError: If no matching DataFile exists.
            ValueError: If neither name nor uuid is provided.
        """
        ...

    def listfiles(self, include_deleted: bool = False) -> list["DataFile"]:
        """Return all DataFiles in this dataset.

        Args:
            include_deleted: If True, include DELETED files.

        Returns:
            List of DataFile entities.
        """
        ...

    def delfile(self, name: str) -> None:
        """Soft-delete a DataFile by name.

        Sets the DataFile's status to DELETED. Does not remove data.

        Args:
            name: Logical filename to delete.

        Raises:
            EntityNotFoundError: If no file with this name exists.
        """
        ...

    def delallfiles(self) -> None:
        """Soft-delete all DataFiles in this dataset."""
        ...

    def candelete(self) -> bool:
        """Check whether this DataSet can be deleted.

        Returns:
            True if all child DataFiles are already DELETED or
            if there are no child DataFiles.
        """
        ...
```

#### 4.4.5 DataFile Entity (`dvc/oodcp/domain/entities/datafile.py`)

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from dvc.oodcp.domain.enums import EntityStatus, VersionStatus

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.dataversion import DataVersion
    from dvc.oodcp.repo.datafile_repository import DataFileRepository
    from dvc.oodcp.repo.dataversion_repository import DataVersionRepository

@dataclass
class DataFile:
    """Logical abstraction of physical data with one or more versions.

    Represents a specific named data entity within a DataSet
    (e.g., CIFAR-10DEVTRAIN). Each DataFile may have multiple
    DataVersion snapshots.

    Attributes:
        uuid: Unique identifier (UUID v4 string).
        dataset_uuid: Foreign key to parent DataSet.
        name: Logical filename (unique within parent DataSet).
        description: Summary of the file's purpose or contents.
        owner: Identity of the user responsible.
        status: Lifecycle status (ACTIVE or DELETED).
        created_at: When this file identity was first established.
        updated_at: When this file was last modified.
        _datafile_repo: Injected repository for self-persistence.
        _dataversion_repo: Injected repository for child version ops.
    """

    uuid: str = field(default_factory=lambda: str(uuid4()))
    dataset_uuid: str = ""
    name: str = ""
    description: str = ""
    owner: str = ""
    status: EntityStatus = EntityStatus.ACTIVE
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Injected repositories (not persisted)
    _datafile_repo: Optional["DataFileRepository"] = field(
        default=None, repr=False, compare=False
    )
    _dataversion_repo: Optional["DataVersionRepository"] = field(
        default=None, repr=False, compare=False
    )

    def getversion(
        self,
        version_number: Optional[int] = None,
        uuid: Optional[str] = None,
    ) -> "DataVersion":
        """Retrieve a specific DataVersion by number or UUID.

        Args:
            version_number: Sequential version number.
            uuid: DataVersion UUID.

        Returns:
            The matching DataVersion entity.

        Raises:
            EntityNotFoundError: If no matching version exists.
            ValueError: If neither version_number nor uuid is provided.
        """
        ...

    def getlatestversion(self) -> "DataVersion":
        """Return the highest-numbered COMMITTED DataVersion.

        Returns:
            DataVersion with the highest version_number in COMMITTED status.

        Raises:
            EntityNotFoundError: If no COMMITTED version exists.
        """
        ...

    def addversion(
        self,
        source_path: str,
        storage_gateway: "...",
        storage_uri: str = "",
        source_version_uuid: Optional[str] = None,
        transformer: str = "",
        metadata: Optional[dict] = None,
    ) -> "DataVersion":
        """Create and persist a new DataVersion.

        Auto-increments version_number. Hashes data via storage_gateway
        and sets status to COMMITTED.

        Args:
            source_path: Local path to the data to version.
            storage_gateway: Injected StorageGateway for push.
            storage_uri: Target storage URI.
            source_version_uuid: Optional lineage pointer.
            transformer: Description of transformation process.
            metadata: File-specific metrics (row count, size, etc.).

        Returns:
            Newly created and committed DataVersion.
        """
        ...

    def listversions(
        self, include_deleted: bool = False
    ) -> list["DataVersion"]:
        """Return all DataVersions for this file.

        Args:
            include_deleted: If True, include DELETED versions.

        Returns:
            List of DataVersion entities ordered by version_number.
        """
        ...

    def delversion(self, version_number: int) -> None:
        """Soft-delete a DataVersion by version number.

        Sets the version's status to DELETED.

        Args:
            version_number: Version to delete.

        Raises:
            EntityNotFoundError: If no version with this number exists.
        """
        ...

    def delallversions(self) -> None:
        """Soft-delete all DataVersions for this file."""
        ...

    def candelete(self) -> bool:
        """Check whether this DataFile can be deleted.

        Returns:
            True if all child DataVersions are DELETED or none exist.
        """
        ...
```

#### 4.4.6 DataVersion Entity (`dvc/oodcp/domain/entities/dataversion.py`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from dvc.oodcp.domain.enums import StorageType, VersionStatus
from dvc.oodcp.domain.value_objects import DVCHash, StorageURI

if TYPE_CHECKING:
    from dvc.oodcp.infrastructure.gateways.storage_gateway import (
        StorageGateway,
    )

@dataclass
class DataVersion(ABC):
    """Abstract base for versioned data snapshots.

    Represents an immutable snapshot of data at a specific point in
    time. Concrete subclasses (S3DataVersion, GCSDataVersion, etc.)
    handle storage-type-specific details.

    Attributes:
        uuid: Unique identifier (UUID v4 string).
        datafile_uuid: Foreign key to parent DataFile.
        version_number: Sequential integer (>= 1).
        dvc_hash: Content-addressed hash value.
        hash_algorithm: Hash algorithm name (e.g., "md5").
        storage_uri: Physical address of the data.
        status: Lifecycle status (DRAFT, COMMITTED, DELETED).
        source_version_uuid: Lineage pointer to source version.
        transformer: Process that created this version.
        metadata: File-specific metrics (row count, size, etc.).
        created_at: When this version was created.
        updated_at: When this version was last modified.
        _storage_gateway: Injected gateway for data operations.
    """

    uuid: str = field(default_factory=lambda: str(uuid4()))
    datafile_uuid: str = ""
    version_number: int = 0
    dvc_hash: str = ""
    hash_algorithm: str = "md5"
    storage_uri: str = ""
    status: VersionStatus = VersionStatus.DRAFT
    source_version_uuid: Optional[str] = None
    transformer: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Injected gateway (not persisted)
    _storage_gateway: Optional["StorageGateway"] = field(
        default=None, repr=False, compare=False
    )

    @property
    @abstractmethod
    def storage_type(self) -> StorageType:
        """Return the storage backend type for this version.

        Returns:
            StorageType enum value.
        """
        ...

    @property
    def hash_info(self) -> DVCHash:
        """Convert to DVCHash value object.

        Returns:
            DVCHash with this version's hash value and algorithm.
        """
        return DVCHash(value=self.dvc_hash, algorithm=self.hash_algorithm)

    def getdata(self, dest_path: str) -> str:
        """Lazy-load: pull data from storage to local path.

        Args:
            dest_path: Local destination path.

        Returns:
            Absolute path to the retrieved data.

        Raises:
            StorageError: If pull operation fails.
            DataNotFoundError: If data doesn't exist on remote.
        """
        ...

    def savedata(self, source_path: str) -> None:
        """Push local data to remote storage and commit.

        Hashes the data, pushes to remote, updates dvc_hash and
        storage_uri, and sets status to COMMITTED.

        Args:
            source_path: Absolute path to local data.

        Raises:
            StorageError: If push operation fails.
            InvalidStatusTransitionError: If already COMMITTED.
        """
        ...

    def verify(self) -> bool:
        """Check data integrity against stored hash.

        Returns:
            True if remote data matches dvc_hash.

        Raises:
            StorageError: If verification operation fails.
        """
        ...


@dataclass
class S3DataVersion(DataVersion):
    """DataVersion stored on Amazon S3.

    Inherits all attributes and methods from DataVersion.
    """

    @property
    def storage_type(self) -> StorageType:
        """Return StorageType.S3."""
        return StorageType.S3


@dataclass
class GCSDataVersion(DataVersion):
    """DataVersion stored on Google Cloud Storage."""

    @property
    def storage_type(self) -> StorageType:
        """Return StorageType.GCS."""
        return StorageType.GCS


@dataclass
class AzureDataVersion(DataVersion):
    """DataVersion stored on Azure Blob Storage."""

    @property
    def storage_type(self) -> StorageType:
        """Return StorageType.AZURE."""
        return StorageType.AZURE


@dataclass
class LocalDataVersion(DataVersion):
    """DataVersion stored on local filesystem."""

    @property
    def storage_type(self) -> StorageType:
        """Return StorageType.LOCAL."""
        return StorageType.LOCAL
```

#### 4.4.7 DataRepo Entity (`dvc/oodcp/domain/entities/datarepo.py`)

```python
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.dataset import DataSet
    from dvc.oodcp.domain.entities.dataversion import DataVersion
    from dvc.oodcp.repo.datafile_repository import DataFileRepository
    from dvc.oodcp.repo.dataset_repository import DataSetRepository
    from dvc.oodcp.repo.dataversion_repository import DataVersionRepository

@dataclass
class DataRepo:
    """Aggregate root for DataSet persistence and retrieval.

    Serves as the gateway between the control plane's business logic
    and the underlying metadata database. Coordinates DataSet,
    DataFile, and DataVersion persistence.

    Attributes:
        registry_uri: Connection string for the metadata database.
        storage_configurations: Global settings for credentials.
        _dataset_repo: Injected DataSetRepository.
        _datafile_repo: Injected DataFileRepository.
        _dataversion_repo: Injected DataVersionRepository.
    """

    registry_uri: str = ""
    storage_configurations: dict = field(default_factory=dict)

    # Injected repositories (not persisted)
    _dataset_repo: Optional["DataSetRepository"] = field(
        default=None, repr=False, compare=False
    )
    _datafile_repo: Optional["DataFileRepository"] = field(
        default=None, repr=False, compare=False
    )
    _dataversion_repo: Optional["DataVersionRepository"] = field(
        default=None, repr=False, compare=False
    )

    def getdataset(
        self,
        uuid: Optional[str] = None,
        name: Optional[str] = None,
    ) -> "DataSet":
        """Retrieve a DataSet by UUID or name.

        Reconstructs the DataSet with injected repositories so its
        methods (addfile, getfile, etc.) are functional.

        Args:
            uuid: DataSet UUID.
            name: DataSet human-readable name.

        Returns:
            Fully wired DataSet entity.

        Raises:
            EntityNotFoundError: If no matching DataSet exists.
            ValueError: If neither uuid nor name is provided.
        """
        ...

    def savedataset(self, dataset: "DataSet") -> None:
        """Persist a DataSet and all its children atomically.

        Saves the DataSet, all its DataFiles, and all their
        DataVersions in a single transaction.

        Args:
            dataset: DataSet entity to persist.
        """
        ...

    def list_datasets(
        self, include_deleted: bool = False
    ) -> list["DataSet"]:
        """List all DataSets.

        Args:
            include_deleted: If True, include DELETED datasets.

        Returns:
            List of DataSet entities.
        """
        ...

    def querylineage(
        self, version_uuid: str, depth: int = 100
    ) -> list["DataVersion"]:
        """Traverse source_version_uuid pointers for provenance.

        Generates a full provenance chain from the given version
        back through its ancestors.

        Args:
            version_uuid: Starting DataVersion UUID.
            depth: Maximum traversal depth.

        Returns:
            List of DataVersion entities from newest to oldest.

        Raises:
            EntityNotFoundError: If starting version doesn't exist.
        """
        ...
```

#### 4.4.8 Domain Services

**LineageService** (`dvc/oodcp/domain/services/lineage_service.py`):

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.dataversion import DataVersion
    from dvc.oodcp.repo.dataversion_repository import DataVersionRepository

class LineageService:
    """Domain service for data lineage and provenance queries.

    Traverses source_version_uuid chains to build lineage graphs
    and provenance reports.

    Attributes:
        _version_repo: Injected DataVersionRepository.
    """

    def __init__(self, version_repo: "DataVersionRepository") -> None:
        """Initialize with a DataVersionRepository.

        Args:
            version_repo: Repository for version retrieval.
        """
        self._version_repo = version_repo

    def get_lineage(
        self, version_uuid: str, max_depth: int = 100
    ) -> list["DataVersion"]:
        """Build lineage chain for a version.

        Args:
            version_uuid: Starting version UUID.
            max_depth: Maximum chain depth.

        Returns:
            Ordered list from given version to oldest ancestor.
        """
        ...

    def get_descendants(
        self, version_uuid: str
    ) -> list["DataVersion"]:
        """Find all versions derived from the given version.

        Args:
            version_uuid: Ancestor version UUID.

        Returns:
            List of DataVersion entities that cite this version as source.
        """
        ...
```

**IntegrityService** (`dvc/oodcp/domain/services/integrity_service.py`):

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.dataversion import DataVersion
    from dvc.oodcp.infrastructure.gateways.storage_gateway import (
        StorageGateway,
    )

class IntegrityService:
    """Domain service for verifying data integrity.

    Provides batch verification of DataVersion hashes against
    remote storage.

    Attributes:
        _storage_gateway: Injected StorageGateway for verification.
    """

    def __init__(self, storage_gateway: "StorageGateway") -> None:
        """Initialize with a StorageGateway.

        Args:
            storage_gateway: Gateway for remote verification calls.
        """
        self._storage_gateway = storage_gateway

    def verify_version(self, version: "DataVersion") -> bool:
        """Verify a single DataVersion's integrity.

        Args:
            version: DataVersion to verify.

        Returns:
            True if hash matches remote data.
        """
        ...

    def verify_batch(
        self, versions: list["DataVersion"]
    ) -> dict[str, bool]:
        """Verify multiple DataVersions.

        Args:
            versions: List of DataVersions to verify.

        Returns:
            Dict mapping version UUID to verification result.
        """
        ...
```

---

### 4.5 APP LAYER — Factories and Manager

#### 4.5.1 DataSetFactory (`dvc/oodcp/app/factory/dataset_factory.py`)

```python
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.dataset import DataSet
    from dvc.oodcp.repo.datafile_repository import DataFileRepository
    from dvc.oodcp.repo.dataset_repository import DataSetRepository

class DataSetFactory:
    """Factory for creating DataSet entities with injected dependencies.

    Ensures every DataSet is created with proper repository wiring
    so its methods (addfile, getfile, etc.) are functional.

    Attributes:
        _dataset_repo: Repository for DataSet persistence.
        _datafile_repo: Repository for DataFile persistence.
    """

    def __init__(
        self,
        dataset_repo: "DataSetRepository",
        datafile_repo: "DataFileRepository",
    ) -> None:
        """Initialize with injected repositories.

        Args:
            dataset_repo: For DataSet persistence.
            datafile_repo: For child DataFile operations.
        """
        self._dataset_repo = dataset_repo
        self._datafile_repo = datafile_repo

    def create(
        self,
        name: str,
        description: str = "",
        project: str = "",
        owner: str = "",
        shared_metadata: Optional[dict] = None,
    ) -> "DataSet":
        """Create a new DataSet with injected repositories.

        Args:
            name: Human-readable dataset name.
            description: Optional dataset description.
            project: Optional project identity.
            owner: Optional owner identity.
            shared_metadata: Optional key-value pairs.

        Returns:
            New DataSet entity wired with repositories.
        """
        ...
```

#### 4.5.2 DataFileFactory (`dvc/oodcp/app/factory/datafile_factory.py`)

```python
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.datafile import DataFile
    from dvc.oodcp.repo.datafile_repository import DataFileRepository
    from dvc.oodcp.repo.dataversion_repository import DataVersionRepository

class DataFileFactory:
    """Factory for creating DataFile entities with injected dependencies.

    Attributes:
        _datafile_repo: Repository for DataFile persistence.
        _dataversion_repo: Repository for child DataVersion operations.
    """

    def __init__(
        self,
        datafile_repo: "DataFileRepository",
        dataversion_repo: "DataVersionRepository",
    ) -> None:
        """Initialize with injected repositories.

        Args:
            datafile_repo: For DataFile persistence.
            dataversion_repo: For child DataVersion operations.
        """
        self._datafile_repo = datafile_repo
        self._dataversion_repo = dataversion_repo

    def create(
        self,
        dataset_uuid: str,
        name: str,
        description: str = "",
        owner: str = "",
    ) -> "DataFile":
        """Create a new DataFile with injected repositories.

        Args:
            dataset_uuid: Parent DataSet UUID.
            name: Logical filename.
            description: Optional file description.
            owner: Optional owner identity.

        Returns:
            New DataFile entity wired with repositories.
        """
        ...
```

#### 4.5.3 DataVersionFactory (`dvc/oodcp/app/factory/dataversion_factory.py`)

```python
from typing import TYPE_CHECKING, Optional

from dvc.oodcp.domain.enums import StorageType

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.dataversion import DataVersion
    from dvc.oodcp.infrastructure.gateways.storage_gateway import (
        StorageGateway,
    )

class DataVersionFactory:
    """Factory for creating DataVersion subclass instances.

    Uses a registry pattern mapping StorageType to concrete class.
    Supports two creation modes:
    1. With source_path: hashes data immediately via StorageGateway.
    2. With dvc_hash: uses a pre-known hash (no immediate I/O).

    Attributes:
        _storage_gateway: Injected gateway for push operations.
        _registry: Maps StorageType to concrete DataVersion class.
    """

    _registry: dict[StorageType, type["DataVersion"]] = {}

    def __init__(self, storage_gateway: "StorageGateway") -> None:
        """Initialize with a StorageGateway.

        Args:
            storage_gateway: For push operations during creation.
        """
        self._storage_gateway = storage_gateway

    @classmethod
    def register(
        cls,
        storage_type: StorageType,
        version_cls: type["DataVersion"],
    ) -> None:
        """Register a DataVersion subclass for a storage type.

        Args:
            storage_type: The storage type this class handles.
            version_cls: Concrete DataVersion subclass.
        """
        cls._registry[storage_type] = version_cls

    def create(
        self,
        datafile_uuid: str,
        version_number: int,
        storage_type: StorageType,
        storage_uri: str = "",
        source_path: Optional[str] = None,
        dvc_hash: Optional[str] = None,
        hash_algorithm: str = "md5",
        source_version_uuid: Optional[str] = None,
        transformer: str = "",
        metadata: Optional[dict] = None,
    ) -> "DataVersion":
        """Create a DataVersion of the appropriate subclass.

        If source_path is provided, data is hashed and pushed
        immediately. If dvc_hash is provided, the version is
        created with a pre-known hash.

        Args:
            datafile_uuid: Parent DataFile UUID.
            version_number: Sequential version number.
            storage_type: Target storage backend.
            storage_uri: Physical storage address.
            source_path: Local data path (triggers immediate push).
            dvc_hash: Pre-known hash (skips push).
            hash_algorithm: Hash algorithm name.
            source_version_uuid: Optional lineage pointer.
            transformer: Transformation description.
            metadata: File-specific metrics.

        Returns:
            Concrete DataVersion subclass instance.

        Raises:
            ValueError: If storage_type has no registered class.
            ValueError: If neither source_path nor dvc_hash provided.
        """
        ...
```

#### 4.5.4 OodcpManager (`dvc/oodcp/app/manager.py`)

```python
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from dvc.oodcp.app.factory.datafile_factory import DataFileFactory
    from dvc.oodcp.app.factory.dataset_factory import DataSetFactory
    from dvc.oodcp.app.factory.dataversion_factory import DataVersionFactory
    from dvc.oodcp.domain.entities.datarepo import DataRepo
    from dvc.oodcp.domain.services.integrity_service import (
        IntegrityService,
    )
    from dvc.oodcp.domain.services.lineage_service import LineageService
    from dvc.oodcp.infrastructure.gateways.metadata_gateway import (
        MetadataGateway,
    )
    from dvc.oodcp.infrastructure.gateways.storage_gateway import (
        StorageGateway,
    )
    from dvc.repo import Repo

class OodcpManager:
    """Facade for OOD-CP operations.

    Entry point registered on Repo as `repo.oodcp`. Wires together
    all layers: creates gateways, repositories, factories, and
    domain services. Provides simplified API for callers.

    Attributes:
        _repo: DVC Repo instance.
        _metadata_gateway: Lazy-initialized metadata gateway.
        _storage_gateway: Lazy-initialized storage gateway.
        datarepo: Lazy-initialized DataRepo aggregate root.
        dataset_factory: Lazy-initialized DataSetFactory.
        datafile_factory: Lazy-initialized DataFileFactory.
        dataversion_factory: Lazy-initialized DataVersionFactory.
        lineage_service: Lazy-initialized LineageService.
        integrity_service: Lazy-initialized IntegrityService.
    """

    def __init__(self, repo: "Repo") -> None:
        """Initialize with DVC Repo.

        Args:
            repo: Initialized DVC Repo instance.
        """
        self._repo = repo
        self._metadata_gateway: Optional["MetadataGateway"] = None
        self._storage_gateway: Optional["StorageGateway"] = None

    @property
    def metadata_gateway(self) -> "MetadataGateway":
        """Lazy-initialize SQLiteMetadataAdapter.

        Returns:
            MetadataGateway instance.
        """
        ...

    @property
    def storage_gateway(self) -> "StorageGateway":
        """Lazy-initialize DVCStorageAdapter.

        Returns:
            StorageGateway instance.
        """
        ...

    @property
    def datarepo(self) -> "DataRepo":
        """Lazy-initialize DataRepo with wired repositories.

        Returns:
            DataRepo aggregate root.
        """
        ...

    @property
    def dataset_factory(self) -> "DataSetFactory":
        """Lazy-initialize DataSetFactory.

        Returns:
            DataSetFactory with injected repositories.
        """
        ...

    @property
    def datafile_factory(self) -> "DataFileFactory":
        """Lazy-initialize DataFileFactory.

        Returns:
            DataFileFactory with injected repositories.
        """
        ...

    @property
    def dataversion_factory(self) -> "DataVersionFactory":
        """Lazy-initialize DataVersionFactory.

        Returns:
            DataVersionFactory with injected StorageGateway.
        """
        ...

    def close(self) -> None:
        """Release all held resources."""
        ...
```

---

## 5. DVC Class Mappings

| OOD-CP Concept | DVC Equivalent | DVC File |
|---|---|---|
| `DataVersion.dvc_hash + hash_algorithm` | `HashInfo(name, value)` | `dvc_data/hashfile/hash_info.py` |
| `DataVersion.storage_uri` | `Remote.path + Remote.fs` | `dvc/data_cloud.py:22` |
| `DataVersion.metadata` | `Meta(size, nfiles, isdir, version_id)` | `dvc_data/hashfile/meta.py` |
| `DataVersion.savedata()` | `build()` → `DataCloud.push()` | `dvc/data_cloud.py:168` |
| `DataVersion.getdata()` | `DataCloud.pull()` → `checkout()` | `dvc/data_cloud.py:228` |
| `DataFile` | Analogous to `Output` | `dvc/output.py:281` |
| `DataSet` | Analogous to `Datasets` | `dvc/repo/datasets.py` |
| `DataRepo` | Analogous to `Repo` aggregate | `dvc/repo/__init__.py` |
| `StorageGateway.transfer()` | `DataCloud.transfer()` | `dvc/data_cloud.py:116` |
| `StorageGateway.verify()` | `DataCloud.status()` | `dvc/data_cloud.py:212` |
| `OodcpDependency` | Extends `DatasetDependency` pattern | `dvc/dependency/dataset.py` |

---

## 6. Modules Impacted

### 6.1 New Modules

| Module | Layer | Purpose |
|--------|-------|---------|
| `dvc/oodcp/__init__.py` | — | Package root, public exports |
| `dvc/oodcp/infrastructure/gateways/storage_gateway.py` | Infrastructure | StorageGateway Protocol |
| `dvc/oodcp/infrastructure/gateways/metadata_gateway.py` | Infrastructure | MetadataGateway Protocol |
| `dvc/oodcp/infrastructure/gateways/scm_gateway.py` | Infrastructure | SCMGateway Protocol |
| `dvc/oodcp/data/adapters/dvc_storage_adapter.py` | Data | DVCStorageAdapter (wraps DataCloud) |
| `dvc/oodcp/data/adapters/sqlite_adapter.py` | Data | SQLiteMetadataAdapter |
| `dvc/oodcp/data/adapters/lakefs_adapter.py` | Data | LakeFSStorageAdapter (stub) |
| `dvc/oodcp/data/schema.py` | Data | SQLite DDL |
| `dvc/oodcp/repo/dataset_repository.py` | Repo | DataSetRepository |
| `dvc/oodcp/repo/datafile_repository.py` | Repo | DataFileRepository |
| `dvc/oodcp/repo/dataversion_repository.py` | Repo | DataVersionRepository |
| `dvc/oodcp/repo/unit_of_work.py` | Repo | UnitOfWork |
| `dvc/oodcp/domain/entities/dataset.py` | Domain | DataSet entity |
| `dvc/oodcp/domain/entities/datafile.py` | Domain | DataFile entity |
| `dvc/oodcp/domain/entities/dataversion.py` | Domain | DataVersion ABC + 4 subclasses |
| `dvc/oodcp/domain/entities/datarepo.py` | Domain | DataRepo aggregate |
| `dvc/oodcp/domain/value_objects.py` | Domain | DVCHash, StorageURI, VersionNumber |
| `dvc/oodcp/domain/enums.py` | Domain | EntityStatus, VersionStatus, StorageType |
| `dvc/oodcp/domain/exceptions.py` | Domain | OOD-CP exception hierarchy |
| `dvc/oodcp/domain/services/lineage_service.py` | Domain | LineageService |
| `dvc/oodcp/domain/services/integrity_service.py` | Domain | IntegrityService |
| `dvc/oodcp/app/factory/dataset_factory.py` | App | DataSetFactory |
| `dvc/oodcp/app/factory/datafile_factory.py` | App | DataFileFactory |
| `dvc/oodcp/app/factory/dataversion_factory.py` | App | DataVersionFactory |
| `dvc/oodcp/app/manager.py` | App | OodcpManager facade |
| `dvc/oodcp/integration/pipeline.py` | Integration | OodcpDependency |
| `dvc/oodcp/integration/experiments.py` | Integration | ExperimentVersionMapper |

### 6.2 Modified Existing Modules

| Module | Change | Layer |
|--------|--------|-------|
| `dvc/repo/__init__.py:234` | Add `self.oodcp = OodcpManager(self)` | App |
| `dvc/dependency/__init__.py:37` | Add `elif OodcpDependency.is_oodcp(p)` | Integration |
| `dvc/config_schema.py` | Add optional `[oodcp]` config section | Data |
| `dvc/commands/__init__.py` | Register `oodcp` command group | App |

---

## 7. Clarifying Questions

### Q1: Metadata Storage Scope

**Context:** The OOD-CP metadata database (datasets, datafiles, dataversions) needs a persistence location. DVC already uses `.dvc/tmp/` for transient data (like `DataIndex` at `~/.cache/dvc/index/data/db.db`) and `.dvc/config` for user configuration.

**Question:** Should the metadata database be per-repo (local to `.dvc/tmp/oodcp/metadata.db`) or shared across repos (at a configurable external URI)?

**Impact:** Per-repo means metadata is isolated per working copy, which is simpler but means metadata isn't shared across clones. Shared means multiple repos can reference the same dataset registry, but adds connection management complexity and network dependency.

**Options:**

| Option | Pros | Cons |
|--------|------|------|
| A. Per-repo only (`.dvc/tmp/oodcp/metadata.db`) | Simple; no network deps; follows DVC pattern; no auth issues | Metadata lost on clone; no cross-repo sharing; must re-register datasets per clone |
| B. Shared external DB (PostgreSQL/MySQL) | Cross-repo sharing; team collaboration; centralized registry | External dependency; connection management; auth complexity; migration burden |
| C. Per-repo with optional external override (Recommended) | Default simplicity; opt-in sharing; progressive adoption | Slight config complexity; two code paths to test |

**Recommendation:** Option C — per-repo with optional external override.

**Justification:** Matches DVC's existing pattern where defaults are local (`.dvc/cache`) but can be overridden via config (`dvc config cache.dir`). Teams that need shared registries can configure an external DB URI in `[oodcp]` config. The SQLiteMetadataAdapter works for both (SQLite file path vs `:memory:` for tests). A future PostgreSQL adapter can implement the same MetadataGateway protocol.

---

### Q2: DataVersion Creation with Data

**Context:** The spec requires "Ensure DataVersion creation is instantiated with the data and the associated DVC Hash." DataVersionFactory needs to handle two cases: (a) user provides local data that needs hashing, (b) pipeline stage completes and provides a pre-computed hash.

**Question:** Should DataVersionFactory always require `source_path` (immediate hash+push), or also accept a pre-computed `dvc_hash` for cases where DVC has already hashed the data?

**Impact:** Requiring `source_path` always means double-hashing when data comes from a DVC pipeline stage (which already computed the hash). Accepting `dvc_hash` avoids this but means the factory trusts the caller's hash without verification.

**Options:**

| Option | Pros | Cons |
|--------|------|------|
| A. Always require `source_path` | Simple API; always verified; single code path | Double-hashing from pipelines; slower for large data |
| B. Accept either `source_path` or `dvc_hash` (Recommended) | No double-hashing; flexible; supports pipeline integration | Two creation paths; caller can provide wrong hash |
| C. Require both always | Maximum safety | Redundant I/O; poor UX |

**Recommendation:** Option B — accept either `source_path` or `dvc_hash`.

**Justification:** Pipeline stages already compute hashes via `dvc_data.hashfile.build`. Requiring re-hashing wastes I/O for large datasets. The `verify()` method exists as a safety net for callers who want to validate a pre-known hash. The factory validates that at least one of `source_path` or `dvc_hash` is provided.

---

### Q3: Pipeline Dependency URI Scheme

**Context:** The spec requires "Expose storage URIs on DataVersions that users can utilize as an external dependency within their own pipeline definitions." DVC pipelines use `dvc.yaml` to define dependencies. A new dependency type needs a recognizable URI pattern.

**Question:** What URI scheme should OOD-CP dependencies use in `dvc.yaml`, and how should version pinning work?

**Impact:** The scheme must be parseable by DVC's dependency resolution, distinguishable from existing schemes (`s3://`, `gs://`, `http://`), and support optional version pinning.

**Options:**

| Option | Pros | Cons |
|--------|------|------|
| A. `oodcp://dataset/file@v3` (Recommended) | Clear namespace; version pinning; matches URL conventions | New scheme to document; longer URIs |
| B. `ds://dataset/file:3` | Shorter; clean | Conflicts with potential DataStation; colon parsing ambiguity |
| C. Special `dvc.yaml` key (not URI) | Structured YAML; no parsing | Breaks existing dep resolution; larger dvc.yaml change |

**Recommendation:** Option A — `oodcp://dataset_name/file_name@v3`.

**Justification:** Follows URL conventions (`@v3` for version pinning). Easily parsed by `urlparse`. The `oodcp://` prefix is distinctive and won't conflict with existing cloud schemes. Version is optional: `oodcp://dataset/file` resolves to latest COMMITTED version. Matches the existing `DatasetDependency.is_dataset()` pattern for detection.

---

### Q4: Experiment Linkage Strategy

**Context:** The spec requires mapping DataVersions to DVC experiment tracking. DVC experiments use Git refs (`refs/exps/`) and are managed by `dvc.repo.experiments.Experiments`.

**Question:** Should OOD-CP DataVersions be linked to experiments via metadata tagging (non-invasive) or by modifying the experiment creation flow?

**Impact:** Invasive modification risks breaking existing experiment functionality. Non-invasive tagging is safe but requires manual linking.

**Options:**

| Option | Pros | Cons |
|--------|------|------|
| A. Metadata tagging (Recommended) | Zero changes to experiment code; safe; reversible | Manual linkage; no automatic tracking |
| B. Hook into experiment creation | Automatic tracking; seamless UX | Modifies sensitive code; regression risk; tighter coupling |
| C. Experiment wrapper class | Clean separation; full control | Duplicates experiment logic; maintenance burden |

**Recommendation:** Option A — metadata tagging.

**Justification:** Experiments are a complex, Git-ref-based system. Modifying the experiment flow risks regressions. Metadata tagging stores `experiment_ref` and `experiment_name` in DataVersion.metadata, which is sufficient for querying. The `ExperimentVersionMapper` provides a clean API without touching `dvc/repo/experiments/`. If tighter integration is needed later, Option B can be pursued as a follow-up.

---

### Q5: LakeFS Integration Approach

**Context:** The spec requires mapping OOD-CP storage abstractions to LakeFS. LakeFS provides an S3-compatible API and Git-like branching for data.

**Question:** Should LakeFS be integrated as a separate StorageGateway adapter or as a DVC remote configured via fsspec?

**Impact:** Separate adapter gives full control but duplicates remote management logic. DVC remote integration reuses existing infrastructure but may not expose LakeFS-specific features (branches, commits).

**Options:**

| Option | Pros | Cons |
|--------|------|------|
| A. DVC remote via fsspec (Recommended) | Reuses DVC infrastructure; minimal new code; proven path | Limited LakeFS-specific features |
| B. Separate LakeFSStorageAdapter | Full LakeFS feature access; branching support | More code; parallel infrastructure; separate auth |
| C. Both (DVC remote + optional adapter) | Maximum flexibility | Complexity; two paths to maintain |

**Recommendation:** Option A — DVC remote via fsspec (with stub adapter for future extension).

**Justification:** LakeFS provides an S3-compatible endpoint. DVC already supports arbitrary S3-compatible remotes via `dvc remote add -d lakefs s3://repo/branch --endpointurl http://lakefs:8000`. This works with zero OOD-CP changes. The `LakeFSStorageAdapter` stub is included for future LakeFS-specific features (branch management, commit semantics). Starting with the DVC remote path means faster delivery with proven infrastructure.

---

## 8. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| SQLite locking under concurrent access | Data corruption or deadlocks | Medium | WAL mode; retry with exponential backoff; UnitOfWork isolation |
| Hash algorithm mismatch between OOD-CP and DVC | Silent data corruption | Low | Store `hash_algorithm` per version; validate in `verify()`; default to DVC's `DEFAULT_ALGORITHM` |
| Breaking existing Dataset/Artifact contracts | Regression in existing features | Low | Minimal modification (single `elif` branch); run full existing test suite; changes are additive |
| Tight coupling to DVC internals | Brittle when DVC upgrades | Medium | `StorageGateway` protocol as indirection; only `DVCStorageAdapter` knows DVC internals; adapter tests catch breakage |
| Performance at scale (large metadata DB) | Slow queries for large registries | Low | Indexes on FKs; pagination in MetadataGateway; connection pooling for external DB |
| Domain entities mutating without persistence | Stale metadata | Medium | Repository.save() after every mutation; UnitOfWork for atomic multi-entity ops |

---

## 9. Phased Implementation

### Phase 1: Core Domain, Infrastructure, and Data Layers

**Goal:** All entities creatable, stored, retrieved. No DVC storage integration.

**Steps:**
1. Create `dvc/oodcp/` full package structure (all `__init__.py` files)
2. Implement `domain/enums.py`, `domain/value_objects.py`, `domain/exceptions.py`
3. Implement `infrastructure/gateways/` — all 3 Protocol definitions
4. Implement `data/schema.py` — SQLite DDL
5. Implement `data/adapters/sqlite_adapter.py` — SQLiteMetadataAdapter
6. Implement `domain/entities/` — DataSet, DataFile, DataVersion (ABC + 4 concrete), DataRepo
7. Implement `repo/` — DataSetRepository, DataFileRepository, DataVersionRepository, UnitOfWork
8. Implement `app/factory/` — DataSetFactory, DataFileFactory, DataVersionFactory
9. Unit tests for all above (see Test Design Phase 1)

**Deliverable:** All domain entities with CRUD operations via in-memory SQLite. No external I/O.

### Phase 2: DVC Storage Integration and Manager

**Goal:** `savedata()`/`getdata()` work against real DVC remotes.

**Steps:**
1. Implement `data/adapters/dvc_storage_adapter.py` — DVCStorageAdapter
2. Implement `domain/services/lineage_service.py`, `integrity_service.py`
3. Implement `app/manager.py` — OodcpManager
4. Add `self.oodcp = OodcpManager(self)` to `dvc/repo/__init__.py`
5. Add `[oodcp]` config section to `dvc/config_schema.py`
6. Functional tests with local remote (see Test Design Phase 2)

**Deliverable:** End-to-end: create DataSet → add DataFile → create DataVersion → push → pull → verify.

### Phase 3: Pipeline and Experiment Integration

**Goal:** OOD-CP versions usable as pipeline deps, linked to experiments.

**Steps:**
1. Implement `integration/pipeline.py` — OodcpDependency
2. Register in `dvc/dependency/__init__.py`
3. Implement `integration/experiments.py` — ExperimentVersionMapper
4. Implement `data/adapters/lakefs_adapter.py` — LakeFSStorageAdapter (stub)
5. CLI commands for CRUD in `dvc/commands/oodcp.py`
6. Functional tests (see Test Design Phase 3)

**Deliverable:** Pipelines can use `oodcp://` deps; experiment metadata tagging works.

---

## 10. Test Design

### 10.1 Test Directory Structure

```
tests/unit/oodcp/
├── conftest.py                           # Shared fixtures
├── domain/
│   ├── conftest.py
│   ├── test_enums.py
│   ├── test_value_objects.py
│   ├── test_exceptions.py
│   ├── test_dataset.py
│   ├── test_datafile.py
│   ├── test_dataversion.py
│   ├── test_datarepo.py
│   ├── test_lineage_service.py
│   └── test_integrity_service.py
├── repo/
│   ├── conftest.py
│   ├── test_dataset_repository.py
│   ├── test_datafile_repository.py
│   ├── test_dataversion_repository.py
│   └── test_unit_of_work.py
├── data/
│   ├── conftest.py
│   ├── test_sqlite_adapter.py
│   └── test_dvc_storage_adapter.py
├── app/
│   ├── conftest.py
│   ├── test_dataset_factory.py
│   ├── test_datafile_factory.py
│   ├── test_dataversion_factory.py
│   └── test_manager.py
└── integration/
    ├── test_pipeline.py
    └── test_experiments.py

tests/func/oodcp/
├── conftest.py
├── test_end_to_end.py
└── test_dvc_storage.py
```

### 10.2 Shared Fixtures (`tests/unit/oodcp/conftest.py`)

```python
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from dvc.oodcp.domain.enums import EntityStatus, VersionStatus, StorageType
from dvc.oodcp.domain.entities.dataset import DataSet
from dvc.oodcp.domain.entities.datafile import DataFile
from dvc.oodcp.domain.entities.dataversion import (
    S3DataVersion,
    LocalDataVersion,
)
from dvc.oodcp.data.adapters.sqlite_adapter import SQLiteMetadataAdapter
from dvc.oodcp.repo.dataset_repository import DataSetRepository
from dvc.oodcp.repo.datafile_repository import DataFileRepository
from dvc.oodcp.repo.dataversion_repository import DataVersionRepository
from dvc.oodcp.repo.unit_of_work import UnitOfWork
from dvc.oodcp.app.factory.dataset_factory import DataSetFactory
from dvc.oodcp.app.factory.datafile_factory import DataFileFactory
from dvc.oodcp.app.factory.dataversion_factory import DataVersionFactory


# ── Gateway Fixtures ──────────────────────────────────────────

@pytest.fixture
def metadata_gateway():
    """In-memory SQLite gateway for isolated tests.

    Yields:
        SQLiteMetadataAdapter connected to ':memory:' database.
        Automatically closed after test.
    """
    adapter = SQLiteMetadataAdapter(":memory:")
    yield adapter
    adapter.close()


@pytest.fixture
def mock_storage_gateway():
    """Mock StorageGateway that returns predictable values.

    The mock's push() returns ("abc123hash", "md5").
    The mock's pull() returns "/tmp/pulled/data".
    The mock's verify() returns True.
    The mock's transfer() returns True.

    Returns:
        MagicMock conforming to StorageGateway protocol.
    """
    mock = MagicMock()
    mock.push.return_value = ("abc123hash", "md5")
    mock.pull.return_value = "/tmp/pulled/data"
    mock.verify.return_value = True
    mock.transfer.return_value = True
    return mock


@pytest.fixture
def mock_metadata_gateway():
    """Mock MetadataGateway for pure unit testing without SQLite.

    Returns:
        MagicMock conforming to MetadataGateway protocol.
    """
    return MagicMock()


# ── Repository Fixtures ───────────────────────────────────────

@pytest.fixture
def dataset_repo(metadata_gateway):
    """DataSetRepository backed by in-memory SQLite.

    Args:
        metadata_gateway: In-memory SQLiteMetadataAdapter.

    Returns:
        DataSetRepository instance.
    """
    return DataSetRepository(metadata_gateway)


@pytest.fixture
def datafile_repo(metadata_gateway):
    """DataFileRepository backed by in-memory SQLite.

    Args:
        metadata_gateway: In-memory SQLiteMetadataAdapter.

    Returns:
        DataFileRepository instance.
    """
    return DataFileRepository(metadata_gateway)


@pytest.fixture
def dataversion_repo(metadata_gateway):
    """DataVersionRepository backed by in-memory SQLite.

    Args:
        metadata_gateway: In-memory SQLiteMetadataAdapter.

    Returns:
        DataVersionRepository instance.
    """
    return DataVersionRepository(metadata_gateway)


@pytest.fixture
def unit_of_work(metadata_gateway):
    """UnitOfWork backed by in-memory SQLite.

    Args:
        metadata_gateway: In-memory SQLiteMetadataAdapter.

    Returns:
        UnitOfWork instance.
    """
    return UnitOfWork(metadata_gateway)


# ── Factory Fixtures ──────────────────────────────────────────

@pytest.fixture
def dataset_factory(dataset_repo, datafile_repo):
    """DataSetFactory with in-memory repositories.

    Returns:
        DataSetFactory instance.
    """
    return DataSetFactory(dataset_repo, datafile_repo)


@pytest.fixture
def datafile_factory(datafile_repo, dataversion_repo):
    """DataFileFactory with in-memory repositories.

    Returns:
        DataFileFactory instance.
    """
    return DataFileFactory(datafile_repo, dataversion_repo)


@pytest.fixture
def dataversion_factory(mock_storage_gateway):
    """DataVersionFactory with mock storage gateway.

    Returns:
        DataVersionFactory instance.
    """
    return DataVersionFactory(mock_storage_gateway)


# ── Sample Entity Fixtures ────────────────────────────────────

FIXED_TIME = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_dataset(dataset_repo, datafile_repo):
    """A pre-built DataSet entity with injected repos.

    Returns:
        DataSet with name='test-dataset', wired with repos.
    """
    return DataSet(
        uuid="ds-uuid-001",
        name="test-dataset",
        description="A test dataset",
        project="test-project",
        owner="test-owner",
        status=EntityStatus.ACTIVE,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
        shared_metadata={"license": "MIT"},
        _dataset_repo=dataset_repo,
        _datafile_repo=datafile_repo,
    )


@pytest.fixture
def sample_datafile(datafile_repo, dataversion_repo):
    """A pre-built DataFile entity with injected repos.

    Returns:
        DataFile with name='train.csv', wired with repos.
    """
    return DataFile(
        uuid="df-uuid-001",
        dataset_uuid="ds-uuid-001",
        name="train.csv",
        description="Training data",
        owner="test-owner",
        status=EntityStatus.ACTIVE,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
        _datafile_repo=datafile_repo,
        _dataversion_repo=dataversion_repo,
    )


@pytest.fixture
def sample_s3_version(mock_storage_gateway):
    """A pre-built S3DataVersion with mock storage.

    Returns:
        S3DataVersion with version_number=1, COMMITTED status.
    """
    return S3DataVersion(
        uuid="ver-uuid-001",
        datafile_uuid="df-uuid-001",
        version_number=1,
        dvc_hash="abc123hash",
        hash_algorithm="md5",
        storage_uri="s3://bucket/path/data",
        status=VersionStatus.COMMITTED,
        metadata={"size": 1024, "rows": 1000},
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
        _storage_gateway=mock_storage_gateway,
    )


@pytest.fixture
def sample_local_version(mock_storage_gateway):
    """A pre-built LocalDataVersion with mock storage.

    Returns:
        LocalDataVersion with version_number=1, DRAFT status.
    """
    return LocalDataVersion(
        uuid="ver-uuid-002",
        datafile_uuid="df-uuid-001",
        version_number=1,
        dvc_hash="",
        hash_algorithm="md5",
        storage_uri="/local/path/data",
        status=VersionStatus.DRAFT,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
        _storage_gateway=mock_storage_gateway,
    )
```

### 10.3 Phase 1 Tests — Domain, Repo, Data, App Layers

#### 10.3.1 Domain Enums (`tests/unit/oodcp/domain/test_enums.py`)

```python
"""Tests for OOD-CP domain enums."""
import pytest
from dvc.oodcp.domain.enums import EntityStatus, VersionStatus, StorageType


class TestEntityStatus:
    """Verify EntityStatus enum values and string behavior."""

    def test_active_value(self):
        """EntityStatus.ACTIVE has string value 'ACTIVE'."""
        assert EntityStatus.ACTIVE == "ACTIVE"
        assert EntityStatus.ACTIVE.value == "ACTIVE"

    def test_deleted_value(self):
        """EntityStatus.DELETED has string value 'DELETED'."""
        assert EntityStatus.DELETED == "DELETED"

    def test_from_string(self):
        """EntityStatus can be constructed from string."""
        assert EntityStatus("ACTIVE") is EntityStatus.ACTIVE

    def test_invalid_raises(self):
        """Invalid string raises ValueError."""
        with pytest.raises(ValueError):
            EntityStatus("INVALID")


class TestVersionStatus:
    """Verify VersionStatus enum values."""

    def test_draft_value(self):
        assert VersionStatus.DRAFT == "DRAFT"

    def test_committed_value(self):
        assert VersionStatus.COMMITTED == "COMMITTED"

    def test_deleted_value(self):
        assert VersionStatus.DELETED == "DELETED"


class TestStorageType:
    """Verify StorageType enum values."""

    @pytest.mark.parametrize(
        "member, expected",
        [
            (StorageType.S3, "S3"),
            (StorageType.GCS, "GCS"),
            (StorageType.AZURE, "AZURE"),
            (StorageType.LOCAL, "LOCAL"),
        ],
    )
    def test_values(self, member, expected):
        """Each StorageType member has correct string value."""
        assert member.value == expected
```

#### 10.3.2 Value Objects (`tests/unit/oodcp/domain/test_value_objects.py`)

```python
"""Tests for OOD-CP domain value objects."""
import pytest
from dvc.oodcp.domain.value_objects import DVCHash, StorageURI, VersionNumber


class TestDVCHash:
    """Verify DVCHash immutability and behavior."""

    def test_create_with_defaults(self):
        """DVCHash defaults to md5 algorithm."""
        h = DVCHash(value="abc123")
        assert h.value == "abc123"
        assert h.algorithm == "md5"

    def test_create_with_algorithm(self):
        """DVCHash accepts custom algorithm."""
        h = DVCHash(value="abc123", algorithm="sha256")
        assert h.algorithm == "sha256"

    def test_bool_true_when_value(self):
        """DVCHash is truthy when value is non-empty."""
        assert bool(DVCHash(value="abc123"))

    def test_bool_false_when_empty(self):
        """DVCHash is falsy when value is empty."""
        assert not bool(DVCHash(value=""))

    def test_immutable(self):
        """DVCHash attributes cannot be modified."""
        h = DVCHash(value="abc123")
        with pytest.raises(AttributeError):
            h.value = "changed"

    def test_equality(self):
        """Two DVCHash with same fields are equal."""
        a = DVCHash(value="abc", algorithm="md5")
        b = DVCHash(value="abc", algorithm="md5")
        assert a == b

    def test_inequality(self):
        """Two DVCHash with different fields are not equal."""
        a = DVCHash(value="abc", algorithm="md5")
        b = DVCHash(value="def", algorithm="md5")
        assert a != b


class TestStorageURI:
    """Verify StorageURI parsing and immutability."""

    @pytest.mark.parametrize(
        "uri, expected_scheme",
        [
            ("s3://bucket/path", "s3"),
            ("gs://bucket/path", "gs"),
            ("azure://container/path", "azure"),
            ("/local/path", ""),
        ],
    )
    def test_scheme_extraction(self, uri, expected_scheme):
        """StorageURI.scheme extracts protocol from URI."""
        s = StorageURI(uri=uri)
        assert s.scheme == expected_scheme

    def test_str(self):
        """StorageURI str() returns the URI."""
        s = StorageURI(uri="s3://bucket/path")
        assert str(s) == "s3://bucket/path"


class TestVersionNumber:
    """Verify VersionNumber validation."""

    def test_valid_version(self):
        """VersionNumber accepts positive integers."""
        v = VersionNumber(value=1)
        assert v.value == 1
        assert int(v) == 1

    def test_zero_raises(self):
        """VersionNumber rejects zero."""
        with pytest.raises(ValueError, match="must be >= 1"):
            VersionNumber(value=0)

    def test_negative_raises(self):
        """VersionNumber rejects negative numbers."""
        with pytest.raises(ValueError, match="must be >= 1"):
            VersionNumber(value=-1)
```

#### 10.3.3 DataSet Entity (`tests/unit/oodcp/domain/test_dataset.py`)

```python
"""Tests for DataSet domain entity."""
import pytest
from unittest.mock import MagicMock, call
from datetime import datetime, timezone

from dvc.oodcp.domain.entities.dataset import DataSet
from dvc.oodcp.domain.entities.datafile import DataFile
from dvc.oodcp.domain.enums import EntityStatus
from dvc.oodcp.domain.exceptions import (
    EntityNotFoundError,
    DuplicateNameError,
)


class TestDataSetCreation:
    """Verify DataSet instantiation and defaults."""

    def test_create_with_defaults(self):
        """DataSet creates with UUID, ACTIVE status, empty metadata."""
        ds = DataSet(name="test")
        assert ds.uuid  # non-empty UUID
        assert ds.name == "test"
        assert ds.status == EntityStatus.ACTIVE
        assert ds.shared_metadata == {}
        assert isinstance(ds.created_at, datetime)

    def test_create_with_all_fields(self):
        """DataSet accepts all constructor arguments."""
        ds = DataSet(
            uuid="custom-uuid",
            name="my-dataset",
            description="desc",
            project="proj",
            owner="owner",
            shared_metadata={"license": "MIT"},
        )
        assert ds.uuid == "custom-uuid"
        assert ds.description == "desc"
        assert ds.shared_metadata == {"license": "MIT"}


class TestDataSetAddFile:
    """Verify DataSet.addfile() behavior."""

    def test_addfile_creates_datafile(self, sample_dataset):
        """addfile() creates a DataFile linked to this dataset."""
        df = sample_dataset.addfile(name="train.csv", description="Training")
        assert isinstance(df, DataFile)
        assert df.dataset_uuid == sample_dataset.uuid
        assert df.name == "train.csv"

    def test_addfile_persists_via_repo(self, sample_dataset, datafile_repo):
        """addfile() calls datafile_repo.save()."""
        sample_dataset.addfile(name="train.csv")
        saved = datafile_repo.get_by_name(sample_dataset.uuid, "train.csv")
        assert saved is not None
        assert saved.name == "train.csv"

    def test_addfile_duplicate_raises(self, sample_dataset):
        """addfile() with duplicate name raises DuplicateNameError."""
        sample_dataset.addfile(name="train.csv")
        with pytest.raises(DuplicateNameError):
            sample_dataset.addfile(name="train.csv")


class TestDataSetGetFile:
    """Verify DataSet.getfile() behavior."""

    def test_getfile_by_name(self, sample_dataset):
        """getfile(name=) retrieves the correct DataFile."""
        sample_dataset.addfile(name="train.csv")
        df = sample_dataset.getfile(name="train.csv")
        assert df.name == "train.csv"

    def test_getfile_not_found_raises(self, sample_dataset):
        """getfile() raises EntityNotFoundError for missing file."""
        with pytest.raises(EntityNotFoundError):
            sample_dataset.getfile(name="nonexistent.csv")

    def test_getfile_no_args_raises(self, sample_dataset):
        """getfile() with no args raises ValueError."""
        with pytest.raises(ValueError):
            sample_dataset.getfile()


class TestDataSetListFiles:
    """Verify DataSet.listfiles() behavior."""

    def test_listfiles_returns_active(self, sample_dataset):
        """listfiles() returns only ACTIVE files by default."""
        sample_dataset.addfile(name="a.csv")
        sample_dataset.addfile(name="b.csv")
        files = sample_dataset.listfiles()
        assert len(files) == 2

    def test_listfiles_excludes_deleted(self, sample_dataset):
        """listfiles() excludes DELETED files by default."""
        sample_dataset.addfile(name="a.csv")
        sample_dataset.addfile(name="b.csv")
        sample_dataset.delfile("b.csv")
        files = sample_dataset.listfiles()
        assert len(files) == 1
        assert files[0].name == "a.csv"

    def test_listfiles_includes_deleted(self, sample_dataset):
        """listfiles(include_deleted=True) includes DELETED files."""
        sample_dataset.addfile(name="a.csv")
        sample_dataset.addfile(name="b.csv")
        sample_dataset.delfile("b.csv")
        files = sample_dataset.listfiles(include_deleted=True)
        assert len(files) == 2


class TestDataSetDelete:
    """Verify DataSet soft-delete behavior."""

    def test_delfile_sets_deleted(self, sample_dataset):
        """delfile() sets file status to DELETED."""
        sample_dataset.addfile(name="a.csv")
        sample_dataset.delfile("a.csv")
        df = sample_dataset.getfile(name="a.csv")
        assert df.status == EntityStatus.DELETED

    def test_delfile_not_found_raises(self, sample_dataset):
        """delfile() raises EntityNotFoundError for missing file."""
        with pytest.raises(EntityNotFoundError):
            sample_dataset.delfile("nonexistent.csv")

    def test_delallfiles(self, sample_dataset):
        """delallfiles() deletes all files."""
        sample_dataset.addfile(name="a.csv")
        sample_dataset.addfile(name="b.csv")
        sample_dataset.delallfiles()
        assert sample_dataset.listfiles() == []

    def test_candelete_true_when_all_deleted(self, sample_dataset):
        """candelete() returns True when all files are DELETED."""
        sample_dataset.addfile(name="a.csv")
        sample_dataset.delfile("a.csv")
        assert sample_dataset.candelete() is True

    def test_candelete_true_when_no_files(self, sample_dataset):
        """candelete() returns True when dataset has no files."""
        assert sample_dataset.candelete() is True

    def test_candelete_false_when_active_files(self, sample_dataset):
        """candelete() returns False when active files exist."""
        sample_dataset.addfile(name="a.csv")
        assert sample_dataset.candelete() is False
```

#### 10.3.4 DataVersion Entity (`tests/unit/oodcp/domain/test_dataversion.py`)

```python
"""Tests for DataVersion domain entity and subclasses."""
import pytest
from unittest.mock import MagicMock

from dvc.oodcp.domain.entities.dataversion import (
    DataVersion,
    S3DataVersion,
    GCSDataVersion,
    AzureDataVersion,
    LocalDataVersion,
)
from dvc.oodcp.domain.enums import StorageType, VersionStatus
from dvc.oodcp.domain.value_objects import DVCHash


class TestDataVersionABC:
    """Verify DataVersion cannot be instantiated directly."""

    def test_cannot_instantiate_abc(self):
        """DataVersion is abstract and cannot be instantiated."""
        with pytest.raises(TypeError, match="abstract"):
            DataVersion()


class TestDataVersionSubclasses:
    """Verify each concrete subclass returns correct storage_type."""

    @pytest.mark.parametrize(
        "cls, expected_type",
        [
            (S3DataVersion, StorageType.S3),
            (GCSDataVersion, StorageType.GCS),
            (AzureDataVersion, StorageType.AZURE),
            (LocalDataVersion, StorageType.LOCAL),
        ],
    )
    def test_storage_type(self, cls, expected_type):
        """Each subclass returns its designated StorageType."""
        version = cls(
            datafile_uuid="df-001",
            version_number=1,
        )
        assert version.storage_type == expected_type


class TestDataVersionHashInfo:
    """Verify hash_info property conversion."""

    def test_hash_info_returns_dvchash(self, sample_s3_version):
        """hash_info returns DVCHash value object."""
        hi = sample_s3_version.hash_info
        assert isinstance(hi, DVCHash)
        assert hi.value == "abc123hash"
        assert hi.algorithm == "md5"


class TestDataVersionSaveData:
    """Verify savedata() behavior with mock gateway."""

    def test_savedata_calls_push(self, sample_local_version):
        """savedata() delegates to storage_gateway.push()."""
        sample_local_version.savedata("/local/source/data.csv")
        sample_local_version._storage_gateway.push.assert_called_once()

    def test_savedata_updates_hash(self, sample_local_version):
        """savedata() updates dvc_hash from push result."""
        sample_local_version.savedata("/local/source/data.csv")
        assert sample_local_version.dvc_hash == "abc123hash"
        assert sample_local_version.hash_algorithm == "md5"

    def test_savedata_sets_committed(self, sample_local_version):
        """savedata() transitions status to COMMITTED."""
        assert sample_local_version.status == VersionStatus.DRAFT
        sample_local_version.savedata("/local/source/data.csv")
        assert sample_local_version.status == VersionStatus.COMMITTED


class TestDataVersionGetData:
    """Verify getdata() behavior with mock gateway."""

    def test_getdata_calls_pull(self, sample_s3_version):
        """getdata() delegates to storage_gateway.pull()."""
        result = sample_s3_version.getdata("/tmp/dest")
        sample_s3_version._storage_gateway.pull.assert_called_once_with(
            "abc123hash", "md5", "/tmp/dest", None, None,
        )
        assert result == "/tmp/pulled/data"


class TestDataVersionVerify:
    """Verify verify() behavior with mock gateway."""

    def test_verify_delegates_to_gateway(self, sample_s3_version):
        """verify() calls storage_gateway.verify()."""
        result = sample_s3_version.verify()
        sample_s3_version._storage_gateway.verify.assert_called_once_with(
            "abc123hash", "md5", None,
        )
        assert result is True

    def test_verify_returns_false_on_mismatch(self, sample_s3_version):
        """verify() returns False when gateway reports mismatch."""
        sample_s3_version._storage_gateway.verify.return_value = False
        assert sample_s3_version.verify() is False
```

#### 10.3.5 SQLite Adapter (`tests/unit/oodcp/data/test_sqlite_adapter.py`)

```python
"""Tests for SQLiteMetadataAdapter."""
import json
import pytest
from datetime import datetime, timezone

from dvc.oodcp.data.adapters.sqlite_adapter import SQLiteMetadataAdapter


@pytest.fixture
def adapter():
    """Fresh in-memory SQLite adapter per test."""
    a = SQLiteMetadataAdapter(":memory:")
    yield a
    a.close()


@pytest.fixture
def sample_dataset_dict():
    """Sample dataset dictionary for persistence tests."""
    return {
        "uuid": "ds-001",
        "name": "test-dataset",
        "description": "A test dataset",
        "project": "proj",
        "owner": "owner",
        "status": "ACTIVE",
        "created_at": "2025-01-15T12:00:00+00:00",
        "updated_at": "2025-01-15T12:00:00+00:00",
        "shared_metadata": json.dumps({"license": "MIT"}),
    }


@pytest.fixture
def sample_datafile_dict():
    """Sample datafile dictionary for persistence tests."""
    return {
        "uuid": "df-001",
        "dataset_uuid": "ds-001",
        "name": "train.csv",
        "description": "Training data",
        "owner": "owner",
        "status": "ACTIVE",
        "created_at": "2025-01-15T12:00:00+00:00",
        "updated_at": "2025-01-15T12:00:00+00:00",
    }


@pytest.fixture
def sample_version_dict():
    """Sample dataversion dictionary for persistence tests."""
    return {
        "uuid": "ver-001",
        "datafile_uuid": "df-001",
        "version_number": 1,
        "dvc_hash": "abc123",
        "hash_algorithm": "md5",
        "storage_uri": "s3://bucket/path",
        "storage_type": "S3",
        "status": "COMMITTED",
        "source_version_uuid": None,
        "transformer": "",
        "metadata": json.dumps({"size": 1024}),
        "created_at": "2025-01-15T12:00:00+00:00",
        "updated_at": "2025-01-15T12:00:00+00:00",
    }


class TestDatasetCRUD:
    """Verify dataset CRUD operations in SQLite."""

    def test_save_and_get(self, adapter, sample_dataset_dict):
        """save_dataset then get_dataset returns same data."""
        adapter.save_dataset(sample_dataset_dict)
        result = adapter.get_dataset("ds-001")
        assert result is not None
        assert result["name"] == "test-dataset"
        assert result["uuid"] == "ds-001"

    def test_get_by_name(self, adapter, sample_dataset_dict):
        """get_dataset_by_name retrieves by unique name."""
        adapter.save_dataset(sample_dataset_dict)
        result = adapter.get_dataset_by_name("test-dataset")
        assert result is not None
        assert result["uuid"] == "ds-001"

    def test_get_nonexistent_returns_none(self, adapter):
        """get_dataset returns None for unknown UUID."""
        assert adapter.get_dataset("nonexistent") is None

    def test_list_excludes_deleted(self, adapter, sample_dataset_dict):
        """list_datasets excludes DELETED by default."""
        adapter.save_dataset(sample_dataset_dict)
        deleted = {**sample_dataset_dict, "uuid": "ds-002",
                   "name": "deleted-ds", "status": "DELETED"}
        adapter.save_dataset(deleted)
        result = adapter.list_datasets()
        assert len(result) == 1

    def test_list_includes_deleted(self, adapter, sample_dataset_dict):
        """list_datasets(include_deleted=True) returns all."""
        adapter.save_dataset(sample_dataset_dict)
        deleted = {**sample_dataset_dict, "uuid": "ds-002",
                   "name": "deleted-ds", "status": "DELETED"}
        adapter.save_dataset(deleted)
        result = adapter.list_datasets(include_deleted=True)
        assert len(result) == 2

    def test_upsert_updates_existing(self, adapter, sample_dataset_dict):
        """save_dataset updates existing record on UUID conflict."""
        adapter.save_dataset(sample_dataset_dict)
        updated = {**sample_dataset_dict, "description": "Updated"}
        adapter.save_dataset(updated)
        result = adapter.get_dataset("ds-001")
        assert result["description"] == "Updated"

    def test_json_metadata_round_trip(self, adapter, sample_dataset_dict):
        """shared_metadata JSON survives save/load cycle."""
        adapter.save_dataset(sample_dataset_dict)
        result = adapter.get_dataset("ds-001")
        meta = json.loads(result["shared_metadata"])
        assert meta == {"license": "MIT"}


class TestDatafileCRUD:
    """Verify datafile CRUD operations in SQLite."""

    def test_save_and_get(
        self, adapter, sample_dataset_dict, sample_datafile_dict
    ):
        """save_datafile then get_datafile returns same data."""
        adapter.save_dataset(sample_dataset_dict)
        adapter.save_datafile(sample_datafile_dict)
        result = adapter.get_datafile("df-001")
        assert result is not None
        assert result["name"] == "train.csv"

    def test_get_by_name(
        self, adapter, sample_dataset_dict, sample_datafile_dict
    ):
        """get_datafile_by_name finds file within dataset."""
        adapter.save_dataset(sample_dataset_dict)
        adapter.save_datafile(sample_datafile_dict)
        result = adapter.get_datafile_by_name("ds-001", "train.csv")
        assert result is not None

    def test_unique_constraint(
        self, adapter, sample_dataset_dict, sample_datafile_dict
    ):
        """Duplicate (dataset_uuid, name) raises error."""
        adapter.save_dataset(sample_dataset_dict)
        adapter.save_datafile(sample_datafile_dict)
        dup = {**sample_datafile_dict, "uuid": "df-002"}
        with pytest.raises(Exception):  # sqlite3.IntegrityError
            adapter.save_datafile(dup)

    def test_list_for_dataset(
        self, adapter, sample_dataset_dict, sample_datafile_dict
    ):
        """list_datafiles returns files for given dataset."""
        adapter.save_dataset(sample_dataset_dict)
        adapter.save_datafile(sample_datafile_dict)
        second = {**sample_datafile_dict, "uuid": "df-002",
                  "name": "test.csv"}
        adapter.save_datafile(second)
        result = adapter.list_datafiles("ds-001")
        assert len(result) == 2


class TestDataversionCRUD:
    """Verify dataversion CRUD operations in SQLite."""

    def test_save_and_get(
        self, adapter, sample_dataset_dict, sample_datafile_dict,
        sample_version_dict,
    ):
        """save_dataversion then get_dataversion returns same data."""
        adapter.save_dataset(sample_dataset_dict)
        adapter.save_datafile(sample_datafile_dict)
        adapter.save_dataversion(sample_version_dict)
        result = adapter.get_dataversion("ver-001")
        assert result is not None
        assert result["dvc_hash"] == "abc123"

    def test_get_latest_committed(
        self, adapter, sample_dataset_dict, sample_datafile_dict,
        sample_version_dict,
    ):
        """get_latest_dataversion returns highest COMMITTED version."""
        adapter.save_dataset(sample_dataset_dict)
        adapter.save_datafile(sample_datafile_dict)
        adapter.save_dataversion(sample_version_dict)
        v2 = {**sample_version_dict, "uuid": "ver-002",
              "version_number": 2, "dvc_hash": "def456"}
        adapter.save_dataversion(v2)
        draft = {**sample_version_dict, "uuid": "ver-003",
                 "version_number": 3, "status": "DRAFT"}
        adapter.save_dataversion(draft)
        result = adapter.get_latest_dataversion("df-001")
        assert result["version_number"] == 2

    def test_next_version_number_empty(
        self, adapter, sample_dataset_dict, sample_datafile_dict,
    ):
        """get_next_version_number returns 1 when no versions exist."""
        adapter.save_dataset(sample_dataset_dict)
        adapter.save_datafile(sample_datafile_dict)
        assert adapter.get_next_version_number("df-001") == 1

    def test_next_version_number_increments(
        self, adapter, sample_dataset_dict, sample_datafile_dict,
        sample_version_dict,
    ):
        """get_next_version_number returns max + 1."""
        adapter.save_dataset(sample_dataset_dict)
        adapter.save_datafile(sample_datafile_dict)
        adapter.save_dataversion(sample_version_dict)
        assert adapter.get_next_version_number("df-001") == 2

    def test_list_ordered_by_version(
        self, adapter, sample_dataset_dict, sample_datafile_dict,
        sample_version_dict,
    ):
        """list_dataversions returns versions in order."""
        adapter.save_dataset(sample_dataset_dict)
        adapter.save_datafile(sample_datafile_dict)
        adapter.save_dataversion(sample_version_dict)
        v2 = {**sample_version_dict, "uuid": "ver-002",
              "version_number": 2}
        adapter.save_dataversion(v2)
        result = adapter.list_dataversions("df-001")
        assert [r["version_number"] for r in result] == [1, 2]


class TestLineageChain:
    """Verify lineage traversal via recursive CTE."""

    def test_lineage_single(
        self, adapter, sample_dataset_dict, sample_datafile_dict,
        sample_version_dict,
    ):
        """Single version with no parent returns chain of length 1."""
        adapter.save_dataset(sample_dataset_dict)
        adapter.save_datafile(sample_datafile_dict)
        adapter.save_dataversion(sample_version_dict)
        chain = adapter.get_lineage_chain("ver-001")
        assert len(chain) == 1

    def test_lineage_chain_of_three(
        self, adapter, sample_dataset_dict, sample_datafile_dict,
        sample_version_dict,
    ):
        """Three-version chain returns all ancestors in order."""
        adapter.save_dataset(sample_dataset_dict)
        adapter.save_datafile(sample_datafile_dict)
        adapter.save_dataversion(sample_version_dict)  # v1, no parent
        v2 = {**sample_version_dict, "uuid": "ver-002",
              "version_number": 2, "source_version_uuid": "ver-001"}
        adapter.save_dataversion(v2)
        v3 = {**sample_version_dict, "uuid": "ver-003",
              "version_number": 3, "source_version_uuid": "ver-002"}
        adapter.save_dataversion(v3)
        chain = adapter.get_lineage_chain("ver-003")
        assert len(chain) == 3
        assert [c["uuid"] for c in chain] == [
            "ver-003", "ver-002", "ver-001"
        ]

    def test_lineage_respects_depth(
        self, adapter, sample_dataset_dict, sample_datafile_dict,
        sample_version_dict,
    ):
        """max_depth limits traversal."""
        adapter.save_dataset(sample_dataset_dict)
        adapter.save_datafile(sample_datafile_dict)
        adapter.save_dataversion(sample_version_dict)
        v2 = {**sample_version_dict, "uuid": "ver-002",
              "version_number": 2, "source_version_uuid": "ver-001"}
        adapter.save_dataversion(v2)
        v3 = {**sample_version_dict, "uuid": "ver-003",
              "version_number": 3, "source_version_uuid": "ver-002"}
        adapter.save_dataversion(v3)
        chain = adapter.get_lineage_chain("ver-003", max_depth=1)
        assert len(chain) == 1
```

#### 10.3.6 Factory Tests (`tests/unit/oodcp/app/test_dataversion_factory.py`)

```python
"""Tests for DataVersionFactory."""
import pytest
from unittest.mock import MagicMock

from dvc.oodcp.app.factory.dataversion_factory import DataVersionFactory
from dvc.oodcp.domain.entities.dataversion import (
    S3DataVersion,
    GCSDataVersion,
    LocalDataVersion,
)
from dvc.oodcp.domain.enums import StorageType, VersionStatus


@pytest.fixture(autouse=True)
def register_defaults():
    """Register default storage types before each test."""
    DataVersionFactory.register(StorageType.S3, S3DataVersion)
    DataVersionFactory.register(StorageType.GCS, GCSDataVersion)
    DataVersionFactory.register(StorageType.LOCAL, LocalDataVersion)
    yield
    DataVersionFactory._registry.clear()


class TestDataVersionFactoryCreate:
    """Verify DataVersionFactory.create() behavior."""

    def test_creates_s3_version(self, dataversion_factory):
        """create() with S3 type returns S3DataVersion."""
        v = dataversion_factory.create(
            datafile_uuid="df-001",
            version_number=1,
            storage_type=StorageType.S3,
            dvc_hash="abc123",
        )
        assert isinstance(v, S3DataVersion)
        assert v.storage_type == StorageType.S3

    def test_creates_local_version(self, dataversion_factory):
        """create() with LOCAL type returns LocalDataVersion."""
        v = dataversion_factory.create(
            datafile_uuid="df-001",
            version_number=1,
            storage_type=StorageType.LOCAL,
            dvc_hash="abc123",
        )
        assert isinstance(v, LocalDataVersion)

    def test_with_source_path_calls_savedata(self, dataversion_factory):
        """create() with source_path triggers immediate push."""
        v = dataversion_factory.create(
            datafile_uuid="df-001",
            version_number=1,
            storage_type=StorageType.S3,
            source_path="/local/data.csv",
            storage_uri="s3://bucket/data",
        )
        assert v.dvc_hash == "abc123hash"
        assert v.status == VersionStatus.COMMITTED

    def test_with_dvc_hash_no_push(self, dataversion_factory):
        """create() with dvc_hash skips push, keeps DRAFT."""
        v = dataversion_factory.create(
            datafile_uuid="df-001",
            version_number=1,
            storage_type=StorageType.S3,
            dvc_hash="precomputed",
        )
        assert v.dvc_hash == "precomputed"

    def test_no_hash_or_path_raises(self, dataversion_factory):
        """create() without source_path or dvc_hash raises ValueError."""
        with pytest.raises(ValueError):
            dataversion_factory.create(
                datafile_uuid="df-001",
                version_number=1,
                storage_type=StorageType.S3,
            )

    def test_unregistered_type_raises(self, dataversion_factory):
        """create() with unregistered type raises ValueError."""
        DataVersionFactory._registry.clear()
        with pytest.raises(ValueError):
            dataversion_factory.create(
                datafile_uuid="df-001",
                version_number=1,
                storage_type=StorageType.S3,
                dvc_hash="abc",
            )

    def test_register_custom_type(self, dataversion_factory):
        """register() adds custom storage type support."""
        class CustomVersion(S3DataVersion):
            pass
        DataVersionFactory.register(StorageType.S3, CustomVersion)
        v = dataversion_factory.create(
            datafile_uuid="df-001",
            version_number=1,
            storage_type=StorageType.S3,
            dvc_hash="abc",
        )
        assert isinstance(v, CustomVersion)
```

#### 10.3.7 UnitOfWork Tests (`tests/unit/oodcp/repo/test_unit_of_work.py`)

```python
"""Tests for UnitOfWork transactional behavior."""
import pytest
from dvc.oodcp.repo.unit_of_work import UnitOfWork
from dvc.oodcp.domain.entities.dataset import DataSet
from dvc.oodcp.domain.enums import EntityStatus


class TestUnitOfWork:
    """Verify transactional commit/rollback behavior."""

    def test_commit_on_success(self, metadata_gateway):
        """Successful with-block commits changes."""
        with UnitOfWork(metadata_gateway) as uow:
            ds = DataSet(uuid="ds-001", name="test")
            uow.datasets.save(ds)
        # Verify persisted after commit
        result = metadata_gateway.get_dataset("ds-001")
        assert result is not None

    def test_rollback_on_exception(self, metadata_gateway):
        """Exception in with-block rolls back changes."""
        with pytest.raises(ValueError):
            with UnitOfWork(metadata_gateway) as uow:
                ds = DataSet(uuid="ds-001", name="test")
                uow.datasets.save(ds)
                raise ValueError("trigger rollback")
        # Verify not persisted after rollback
        result = metadata_gateway.get_dataset("ds-001")
        assert result is None

    def test_multi_entity_atomic(self, metadata_gateway):
        """Multiple saves in one UoW are atomic."""
        with UnitOfWork(metadata_gateway) as uow:
            ds = DataSet(uuid="ds-001", name="test")
            uow.datasets.save(ds)
            # DataFile and DataVersion saves would follow
        result = metadata_gateway.get_dataset("ds-001")
        assert result is not None
```

### 10.4 Phase 2 Tests — DVC Storage Integration

#### 10.4.1 DVCStorageAdapter (`tests/unit/oodcp/data/test_dvc_storage_adapter.py`)

```python
"""Tests for DVCStorageAdapter with mocked DVC internals."""
import pytest
from unittest.mock import MagicMock, patch

from dvc.oodcp.data.adapters.dvc_storage_adapter import DVCStorageAdapter


@pytest.fixture
def mock_repo():
    """Mock DVC Repo with cloud and cache attributes.

    Returns:
        MagicMock with:
        - repo.cloud.push() returning TransferResult
        - repo.cloud.pull() returning TransferResult
        - repo.cloud.status() returning CompareStatusResult
        - repo.cloud.get_remote_odb() returning mock ODB
        - repo.cache.local as mock ODB
    """
    repo = MagicMock()
    repo.cloud.push.return_value = MagicMock(
        transferred={MagicMock()}, failed=set()
    )
    repo.cloud.pull.return_value = MagicMock(
        transferred={MagicMock()}, failed=set()
    )
    repo.cloud.status.return_value = MagicMock(
        ok={MagicMock()}, missing=set()
    )
    repo.cloud.get_remote_odb.return_value = MagicMock()
    repo.cache.local = MagicMock()
    return repo


@pytest.fixture
def adapter(mock_repo):
    """DVCStorageAdapter wrapping a mock repo."""
    return DVCStorageAdapter(mock_repo)


class TestDVCStorageAdapterPush:
    """Verify push() delegates to DVC build + DataCloud.push()."""

    @patch("dvc.oodcp.data.adapters.dvc_storage_adapter.build")
    def test_push_builds_and_pushes(self, mock_build, adapter, mock_repo):
        """push() calls build() then DataCloud.push()."""
        mock_hash_info = MagicMock()
        mock_hash_info.name = "md5"
        mock_hash_info.value = "abc123"
        mock_build.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_build.return_value[2].hash_info = mock_hash_info

        result = adapter.push("/local/data", "s3://bucket/path")
        assert mock_build.called
        assert mock_repo.cloud.push.called

    @patch("dvc.oodcp.data.adapters.dvc_storage_adapter.build")
    def test_push_returns_hash_tuple(self, mock_build, adapter):
        """push() returns (hash_value, algorithm) tuple."""
        mock_obj = MagicMock()
        mock_obj.hash_info.name = "md5"
        mock_obj.hash_info.value = "abc123"
        mock_build.return_value = (MagicMock(), MagicMock(), mock_obj)

        dvc_hash, algo = adapter.push("/local/data", "s3://bucket/path")
        assert dvc_hash == "abc123"
        assert algo == "md5"


class TestDVCStorageAdapterPull:
    """Verify pull() delegates to DataCloud.pull()."""

    def test_pull_calls_cloud_pull(self, adapter, mock_repo):
        """pull() invokes DataCloud.pull() with correct HashInfo."""
        adapter.pull("abc123", "md5", "/tmp/dest")
        assert mock_repo.cloud.pull.called


class TestDVCStorageAdapterVerify:
    """Verify verify() delegates to DataCloud.status()."""

    def test_verify_calls_status(self, adapter, mock_repo):
        """verify() invokes DataCloud.status()."""
        result = adapter.verify("abc123", "md5")
        assert mock_repo.cloud.status.called
        assert result is True


class TestDVCStorageAdapterTransfer:
    """Verify transfer() between remotes."""

    def test_transfer_calls_cloud_transfer(self, adapter, mock_repo):
        """transfer() gets ODBs and calls DataCloud.transfer()."""
        mock_repo.cloud.transfer.return_value = MagicMock(failed=set())
        result = adapter.transfer("abc123", "md5", "remote1", "remote2")
        assert mock_repo.cloud.get_remote_odb.call_count == 2
```

### 10.5 Phase 3 Tests — Integration

#### 10.5.1 OodcpDependency (`tests/unit/oodcp/integration/test_pipeline.py`)

```python
"""Tests for OodcpDependency pipeline integration."""
import pytest
from unittest.mock import MagicMock

from dvc.oodcp.integration.pipeline import OodcpDependency


class TestOodcpDependencyScheme:
    """Verify URI scheme detection and parsing."""

    @pytest.mark.parametrize(
        "path, expected",
        [
            ("oodcp://dataset/file", True),
            ("oodcp://dataset/file@v3", True),
            ("s3://bucket/path", False),
            ("/local/path", False),
            ("dataset://name", False),
        ],
    )
    def test_is_oodcp(self, path, expected):
        """is_oodcp() correctly identifies oodcp:// URIs."""
        assert OodcpDependency.is_oodcp(path) is expected

    def test_parse_uri_without_version(self):
        """Parses dataset and file from URI without version."""
        dep = OodcpDependency(
            stage=MagicMock(), p="oodcp://my-dataset/train.csv", info={}
        )
        assert dep.dataset_name == "my-dataset"
        assert dep.file_name == "train.csv"
        assert dep.pinned_version is None

    def test_parse_uri_with_version(self):
        """Parses dataset, file, and version from pinned URI."""
        dep = OodcpDependency(
            stage=MagicMock(), p="oodcp://my-dataset/train.csv@v3", info={}
        )
        assert dep.dataset_name == "my-dataset"
        assert dep.file_name == "train.csv"
        assert dep.pinned_version == 3


class TestOodcpDependencyStatus:
    """Verify workspace_status detection."""

    def test_status_unchanged(self):
        """workspace_status returns empty when hash matches."""
        dep = OodcpDependency(
            stage=MagicMock(), p="oodcp://ds/file", info={}
        )
        dep.hash_info = MagicMock(value="abc123")
        dep._get_current_hash = MagicMock(return_value="abc123")
        assert dep.workspace_status() == {}

    def test_status_modified(self):
        """workspace_status returns 'modified' when hash differs."""
        dep = OodcpDependency(
            stage=MagicMock(), p="oodcp://ds/file", info={}
        )
        dep.hash_info = MagicMock(value="abc123")
        dep._get_current_hash = MagicMock(return_value="def456")
        status = dep.workspace_status()
        assert "modified" in str(status).lower()
```

### 10.6 Functional Tests (`tests/func/oodcp/`)

#### 10.6.1 End-to-End (`tests/func/oodcp/test_end_to_end.py`)

```python
"""Functional end-to-end tests for OOD-CP control plane."""
import pytest

from dvc.oodcp.app.manager import OodcpManager
from dvc.oodcp.domain.enums import EntityStatus, VersionStatus, StorageType


@pytest.fixture
def oodcp(tmp_dir, dvc):
    """OodcpManager wired to a real DVC repo with local remote.

    Uses tmp_dir and dvc fixtures from DVC's test infrastructure
    to provide a real repo with a local remote for functional tests.
    """
    manager = OodcpManager(dvc)
    yield manager
    manager.close()


class TestEndToEndWorkflow:
    """Verify complete OOD-CP workflow against real DVC repo."""

    def test_create_dataset_and_files(self, oodcp):
        """Create dataset, add files, verify retrieval."""
        ds = oodcp.dataset_factory.create(
            name="cifar10",
            description="CIFAR-10 dataset",
            project="vision",
        )
        oodcp.datarepo.savedataset(ds)

        ds.addfile(name="train.csv", description="Training split")
        ds.addfile(name="test.csv", description="Test split")

        retrieved = oodcp.datarepo.getdataset(name="cifar10")
        files = retrieved.listfiles()
        assert len(files) == 2
        names = {f.name for f in files}
        assert names == {"train.csv", "test.csv"}

    def test_version_lifecycle(self, oodcp, tmp_dir):
        """Create version, push data, verify hash."""
        ds = oodcp.dataset_factory.create(name="test-ds")
        oodcp.datarepo.savedataset(ds)
        df = ds.addfile(name="data.csv")

        # Generate test data
        tmp_dir.gen("data.csv", "col1,col2\n1,2\n3,4")

        v = df.addversion(
            source_path=str(tmp_dir / "data.csv"),
            storage_gateway=oodcp.storage_gateway,
            storage_uri="",
        )
        assert v.status == VersionStatus.COMMITTED
        assert v.dvc_hash  # non-empty hash
        assert v.version_number == 1

    def test_soft_delete_cascade(self, oodcp):
        """Soft-delete files, verify candelete logic."""
        ds = oodcp.dataset_factory.create(name="delete-test")
        oodcp.datarepo.savedataset(ds)
        ds.addfile(name="a.csv")
        ds.addfile(name="b.csv")

        assert ds.candelete() is False
        ds.delallfiles()
        assert ds.candelete() is True

    def test_lineage_query(self, oodcp, tmp_dir):
        """Verify lineage traversal across versions."""
        ds = oodcp.dataset_factory.create(name="lineage-ds")
        oodcp.datarepo.savedataset(ds)
        df = ds.addfile(name="evolving.csv")

        tmp_dir.gen("v1.csv", "version1")
        v1 = df.addversion(
            source_path=str(tmp_dir / "v1.csv"),
            storage_gateway=oodcp.storage_gateway,
        )

        tmp_dir.gen("v2.csv", "version2")
        v2 = df.addversion(
            source_path=str(tmp_dir / "v2.csv"),
            storage_gateway=oodcp.storage_gateway,
            source_version_uuid=v1.uuid,
        )

        lineage = oodcp.datarepo.querylineage(v2.uuid)
        assert len(lineage) == 2
        assert lineage[0].uuid == v2.uuid
        assert lineage[1].uuid == v1.uuid
```

### 10.7 Regression Testing

After modifying existing DVC files, run:

```bash
# Phase 1: No existing files modified — only new files
pytest tests/unit/oodcp/ -v

# Phase 2: After modifying dvc/repo/__init__.py and dvc/config_schema.py
pytest tests/unit/ -x --ignore=tests/unit/oodcp
pytest tests/func/ -x --ignore=tests/func/oodcp

# Phase 3: After modifying dvc/dependency/__init__.py
pytest tests/unit/dependency/ -v
pytest tests/func/ -x --ignore=tests/func/oodcp

# Full suite
pytest tests/unit/ tests/func/ -v
```

---

## 11. Verification

1. **Phase 1:** `pytest tests/unit/oodcp/domain/ tests/unit/oodcp/data/ tests/unit/oodcp/repo/ tests/unit/oodcp/app/ -v`
2. **Phase 2:** `pytest tests/unit/oodcp/ tests/func/oodcp/test_dvc_storage.py -v`
3. **Phase 3:** `pytest tests/unit/oodcp/ tests/func/oodcp/ -v`
4. **Regression:** `pytest tests/unit/ tests/func/ -x --ignore=tests/unit/oodcp --ignore=tests/func/oodcp`
5. **Manual workflow:** Create DataSet → Add DataFile → Create DataVersion with local data → Push → Pull → Verify hash matches
