# OOD-CP (Object Oriented Data Control Plane) Design for DVC

## Context

Current DVC treats datasets as location-specific paths, forcing data scientists to work through a "file-system lens." This leads to fragmented data management where semantically identical information is scattered across different Git branches, hashes, and directory paths. There is no native way to manage the Logical Entity separately from its Physical Snapshots.

The OOD-CP adds an object-oriented layer on top of DVC around four core entities: **DataSet**, **DataFile**, **DataVersion**, and **DataRepo**. It sits as a control plane above DVC's existing infrastructure, invoking DVC commands for versioning, persistence, pipelines, and experiments rather than replacing them. All backend clients are injected (not instantiated directly), enabling pure mock-based validation.

---

## Architecture Diagram

```
+--------------------------------------------------+
|  CLI / API                                        |
|  (dvc/commands/oodcp.py, dvc/api/oodcp.py)       |
+--------------------------------------------------+
|  OOD-CP Control Plane    (dvc/oodcp/)             |
|  DataRepo -> DataSet -> DataFile -> DataVersion   |
|  Factories | MetadataStore | StorageBackend       |
+--------------------------------------------------+
|  DVC Core (invoked via injected protocols)         |
|  Repo, DataCloud, CacheManager, Experiments       |
+--------------------------------------------------+
|  dvc_data / dvc_objects / fsspec                  |
|  HashFileDB, HashInfo, Meta, Transfer             |
+--------------------------------------------------+
|  Cloud Storage (S3, GCS, Azure, Local, etc.)      |
+--------------------------------------------------+
```

Key architectural decisions:
- OOD-CP lives in `dvc/oodcp/` as a new top-level package (peer to `dvc/stage/`, `dvc/dependency/`)
- Uses **Protocols** (PEP 544) for `StorageBackend` and `MetadataStore` - enabling DI and mock-based testing
- Metadata persisted in **SQLite** at `.dvc/tmp/oodcp/metadata.db` (follows DVC's `DataIndex.open("db.db")` pattern)
- Entities are **mutable dataclasses** (not `attrs @frozen`) since they undergo status transitions

---

## Package Structure

```
dvc/oodcp/
    __init__.py                    # Public exports
    exceptions.py                  # OOD-CP exceptions
    entities/
        __init__.py
        enums.py                   # EntityStatus, VersionStatus, StorageType
        dataset.py                 # DataSet
        datafile.py                # DataFile
        dataversion.py             # DataVersion ABC + S3/GCS/Azure/Local subclasses
        datarepo.py                # DataRepo aggregate root
    factory/
        __init__.py
        dataset_factory.py         # DataSetFactory
        datafile_factory.py        # DataFileFactory
        dataversion_factory.py     # DataVersionFactory with storage registry
    storage/
        __init__.py
        protocols.py               # StorageBackend, MetadataStore Protocol defs
        dvc_storage.py             # DVCStorageBackend (wraps DataCloud + CacheManager)
    metadata/
        __init__.py
        store.py                   # SQLiteMetadataStore
        schema.py                  # DDL + migrations
    integration/
        __init__.py
        pipeline.py                # OodcpDependency for dvc.yaml deps
        experiments.py             # ExperimentVersionMapper
```

---

## Entity Design

### Enums (`dvc/oodcp/entities/enums.py`)
- `EntityStatus(str, Enum)`: ACTIVE, DELETED
- `VersionStatus(str, Enum)`: DRAFT, COMMITTED, DELETED
- `StorageType(str, Enum)`: S3, GCS, AZURE, LOCAL

### DataSet (`dvc/oodcp/entities/dataset.py`)
Mutable `@dataclass` with: `uuid`, `name`, `description`, `project`, `owner`, `status: EntityStatus`, `created_at`, `updated_at`, `shared_metadata: dict`. Injected `_metadata_store: MetadataStore`.

Methods: `addfile()`, `getfile()`, `listfiles()`, `delfile()`, `delallfiles()`, `candelete()`

### DataFile (`dvc/oodcp/entities/datafile.py`)
Mutable `@dataclass` with: `uuid`, `dataset_uuid`, `name`, `description`, `owner`, `status`, `created_at`, `updated_at`. Injected `_metadata_store`.

Methods: `getversion()`, `getlatestversion()`, `addversion()` (auto-increments version_number), `listversions()`, `delversion()`, `delallversions()`, `candelete()`

### DataVersion (`dvc/oodcp/entities/dataversion.py`)
Abstract `@dataclass` ABC with: `uuid`, `datafile_uuid`, `version_number`, `dvc_hash`, `hash_algorithm`, `storage_uri`, `status: VersionStatus`, `source_version_uuid`, `transformer`, `metadata: dict`, `created_at`, `updated_at`. Injected `_storage_backend: StorageBackend`.

Abstract property: `storage_type -> StorageType`
Property: `hash_info` (converts to/from `dvc_data.hashfile.hash_info.HashInfo`)
Methods: `getdata(dest_path)`, `savedata(source_path)`, `verify()`

Concrete subclasses: `S3DataVersion`, `GCSDataVersion`, `AzureDataVersion`, `LocalDataVersion` - each returns its `storage_type`.

### DataRepo (`dvc/oodcp/entities/datarepo.py`)
`@dataclass` with: `registry_uri`, `storage_configurations`. Injected `_metadata_store`, `_storage_backend`, `_dvc_repo`.

Class method: `from_dvc_repo(repo, metadata_store, storage_backend)`
Methods: `getdataset()`, `getdataset_by_name()`, `savedataset()`, `list_datasets()`, `querylineage(version_uuid, depth)`

### DVC Class Mappings

| OOD-CP Concept | DVC Equivalent | File |
|---|---|---|
| `DataVersion.dvc_hash + hash_algorithm` | `HashInfo(name, value)` | `dvc_data/hashfile/hash_info.py` |
| `DataVersion.storage_uri` | `Remote.path + Remote.fs` | `dvc/data_cloud.py:22` |
| `DataVersion.metadata` (size, etc.) | `Meta` | `dvc_data/hashfile/meta.py` |
| `DataVersion.savedata()` | `DataCloud.push()` | `dvc/data_cloud.py:168` |
| `DataVersion.getdata()` | `DataCloud.pull()` | `dvc/data_cloud.py:228` |
| `DataFile` | Analogous to `Output` | `dvc/output.py:281` |
| `DataSet` | Analogous to `Datasets` | `dvc/repo/datasets.py` |

---

## Protocols (`dvc/oodcp/storage/protocols.py`)

```python
@runtime_checkable
class StorageBackend(Protocol):
    def push(self, source_path, remote_name=None, jobs=None) -> HashInfo: ...
    def pull(self, hash_info, dest_path, remote_name=None, jobs=None) -> str: ...
    def verify(self, hash_info, remote_name=None) -> bool: ...
    def transfer(self, hash_info, source_remote, dest_remote, jobs=None) -> bool: ...

@runtime_checkable
class MetadataStore(Protocol):
    def save_dataset(self, dataset) -> None: ...
    def get_dataset(self, uuid) -> DataSet: ...
    def get_dataset_by_name(self, name) -> DataSet: ...
    def list_datasets(self, include_deleted=False) -> list[DataSet]: ...
    def save_datafile(self, datafile) -> None: ...
    def get_datafile(self, uuid) -> DataFile: ...
    def list_datafiles(self, dataset_uuid, include_deleted=False) -> list[DataFile]: ...
    def save_dataversion(self, version) -> None: ...
    def get_dataversion(self, uuid) -> DataVersion: ...
    def get_latest_dataversion(self, datafile_uuid) -> Optional[DataVersion]: ...
    def list_dataversions(self, datafile_uuid, include_deleted=False) -> list[DataVersion]: ...
    def close(self) -> None: ...
```

---

## DVCStorageBackend (`dvc/oodcp/storage/dvc_storage.py`)

Wraps DVC's `Repo.cache` and `Repo.cloud`:
- `push()`: Calls `dvc_data.hashfile.build.build()` → `add_update_tree()` → `repo.cloud.push()`
- `pull()`: Calls `repo.cloud.pull()` → `dvc_data.hashfile.checkout.checkout()`
- `verify()`: Calls `repo.cloud.status()`
- `transfer()`: Uses `repo.cloud.transfer()` between remote ODBs

---

## Metadata Store (`dvc/oodcp/metadata/store.py`)

SQLite schema with 3 tables: `datasets`, `datafiles`, `dataversions`. JSON TEXT columns for `shared_metadata` and `metadata`. Uses Python `sqlite3` module (not SQLAlchemy). WAL mode for concurrency. Located at `.dvc/tmp/oodcp/metadata.db`.

Key indexes: `idx_datafiles_dataset`, `idx_dataversions_datafile`, `idx_dataversions_source`.
Unique constraints: `(dataset_uuid, name)` on datafiles, `(datafile_uuid, version_number)` on dataversions.

---

## Factories (`dvc/oodcp/factory/`)

- **DataSetFactory**: Creates DataSet with injected `_metadata_store`
- **DataFileFactory**: Creates DataFile with injected `_metadata_store`
- **DataVersionFactory**: Registry-based creation. Maps `StorageType` -> concrete class. Supports `source_path` (immediate hash+push) or `dvc_hash` (pre-known). `register()` static method for extension.

---

## Integration Points

### Pipeline Integration (`dvc/oodcp/integration/pipeline.py`)
`OodcpDependency(AbstractDependency)` handles `oodcp://dataset_name/file_name@v3` URIs in `dvc.yaml` deps. Registered in `dvc/dependency/__init__.py:_get()` as a new `elif` branch (line 37).

### Experiment Integration (`dvc/oodcp/integration/experiments.py`)
`ExperimentVersionMapper` tags DataVersions with experiment refs via metadata fields. Non-invasive - does not modify experiment flow.

### Repo Integration
Add to `dvc/repo/__init__.py` line 233 (after `self.datasets = Datasets(self)`):
```python
self.oodcp: OodcpManager = OodcpManager(self)
```

---

## Modules Impacted

### New Modules (28 source files + 13 test files)
All files under `dvc/oodcp/` and `tests/unit/oodcp/`, `tests/func/oodcp/` as listed in package structure above.

### Modified Existing Modules

| Module | Change |
|--------|--------|
| `dvc/repo/__init__.py:233` | Add `self.oodcp = OodcpManager(self)` |
| `dvc/dependency/__init__.py:37` | Add `elif OodcpDependency.is_oodcp(p)` branch in `_get()` |
| `dvc/config_schema.py` | Add optional `[oodcp]` config section |
| `dvc/commands/__init__.py` | Register `oodcp` command group |

---

## Clarifying Questions / Design Decisions

1. **Metadata scope**: Per-repo (`.dvc/tmp/oodcp/metadata.db`), with config option for shared DB
2. **Version numbering**: Per-DataFile, auto-incremented by `addversion()`, starts at 1
3. **Factory with data**: Supports both `source_path` (hash immediately) and `dvc_hash` (pre-known)
4. **Pipeline deps**: `oodcp://` URI scheme in `dvc.yaml` deps, handled by `OodcpDependency`
5. **Experiment linkage**: Tagging approach (metadata fields), not modifying experiment flow
6. **Data movement**: One-shot transfer via `DataCloud.transfer()`, updates `storage_uri`
7. **Coexistence**: OOD-CP DataSets coexist with existing `dvc/repo/datasets.py` - additive, not replacing
8. **GUID format**: UUID v4 strings

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| SQLite locking under concurrent access | WAL mode + retry with exponential backoff |
| Hash algorithm mismatch | Store `hash_algorithm` per version; validate in `verify()` |
| Breaking existing Dataset/Artifact contracts | Minimal modification: single `elif` branch. Run full existing test suite. |
| Tight coupling to DVC internals | `StorageBackend` protocol as indirection; only `DVCStorageBackend` knows DVC internals |
| Performance at scale | Indexes on FKs; pagination support in MetadataStore |

---

## Phased Implementation

### Phase 1: Core Entities and Metadata Persistence
**Goal**: All entities creatable, stored, retrieved, queried. No DVC integration.

1. Create `dvc/oodcp/` package structure
2. Implement enums, exceptions
3. Implement `StorageBackend` and `MetadataStore` protocols
4. Implement `SQLiteMetadataStore` with schema DDL
5. Implement DataSet, DataFile, DataVersion (ABC + 4 concrete), DataRepo
6. Implement all 3 factories
7. **Unit tests**: All entities + store + factories with mock/in-memory SQLite

**Test coverage**: Entity CRUD, soft-delete cascading, candelete logic, version auto-numbering, lineage traversal, factory creation + DI wiring, metadata store round-trip, unique constraints.

### Phase 2: DVC Storage Integration
**Goal**: savedata/getdata work against real DVC remotes.

1. Implement `DVCStorageBackend` wrapping DataCloud + CacheManager
2. Add `self.oodcp` to `Repo.__init__`
3. Add `[oodcp]` config section
4. Wire `DataRepo.from_dvc_repo()`
5. CLI commands for basic CRUD
6. **Functional tests**: Create version → savedata → getdata with local remote; transfer between remotes

### Phase 3: Pipeline and Experiment Integration
**Goal**: OOD-CP data versions usable as pipeline deps and linked to experiments.

1. Implement `OodcpDependency` for `oodcp://` scheme
2. Register in `dvc/dependency/__init__.py`
3. Implement `ExperimentVersionMapper`
4. **Functional tests**: Pipeline with oodcp dep triggers repro on version change; experiment tagging round-trip

---

## Test Design

### Fixtures (`tests/unit/oodcp/conftest.py`)
- `mock_metadata_store` → `SQLiteMetadataStore(":memory:")`
- `mock_storage_backend` → `MagicMock()` with `push` returning `HashInfo("md5", "abc...")`
- `dataset_factory`, `datafile_factory`, `dataversion_factory` → wired with mock deps
- `datarepo` → `DataRepo` with mock store + backend

### Key Test Cases (per entity)

**DataSet**: create with defaults, addfile sets FK, listfiles excludes deleted, delfile soft-deletes, candelete logic

**DataFile**: create with defaults, addversion auto-increments, getlatestversion returns highest COMMITTED, listversions excludes deleted, candelete respects committed versions

**DataVersion**: ABC cannot instantiate, each subclass returns correct storage_type, hash_info round-trips, savedata calls backend.push + sets COMMITTED, getdata calls backend.pull, verify delegates to backend

**DataRepo**: from_dvc_repo wiring, getdataset injects store, savedataset persists, querylineage follows chain, querylineage stops at depth

**Factories**: create correct subclass from StorageType, create with source_path calls savedata, register custom type

**MetadataStore**: save/get round-trip, get_by_name, unique constraints, get_latest_version returns highest, JSON metadata round-trips

**DVCStorageBackend**: push builds hash and delegates to DataCloud (mocked), pull fetches and checks out (mocked), verify checks status (mocked)

**OodcpDependency**: recognizes scheme, parses URI with/without version, workspace_status detects modified

### Regression
- Run existing DVC test suite after modifying `repo/__init__.py`, `dependency/__init__.py`, `config_schema.py`
- Changes are additive (new branches, not altering existing ones)

---

## Verification

1. Run `pytest tests/unit/oodcp/ -v` for all unit tests
2. Run `pytest tests/func/oodcp/ -v` for functional tests
3. Run `pytest tests/unit/ tests/func/ -x --ignore=tests/unit/oodcp --ignore=tests/func/oodcp` to verify no regressions
4. Manual workflow: Create DataSet → Add DataFile → Create DataVersion with local data → Push → Pull → Verify hash matches
