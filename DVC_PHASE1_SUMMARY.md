# Phase 1 Summary — Core Domain, Infrastructure, and Data Layers

## 1. Implementation Summary

Phase 1 established the complete foundational architecture for the OOD-CP (Object-Oriented Data Control Plane). All entities are creatable, persistable, and retrievable via in-memory SQLite. No DVC storage integration (push/pull/verify) is included — that is Phase 2.

**Scope delivered:**
- Full package structure with 14 `__init__.py` files across `dvc/oodcp/` and `tests/unit/oodcp/`
- Domain Layer: enums, value objects, exceptions, 4 entity classes, DataRepo ABC
- Infrastructure Layer: StorageGateway Protocol definition
- Data Layer: SQLite schema, 3 DAL classes, DataRepoSQLite concrete implementation
- App Layer: 3 factory classes (DataSetFactory, DataFileFactory, DataVersionFactory)
- 154 unit tests — all passing

---

## 2. Implementation Detail

### 2.1 Domain Layer (`dvc/oodcp/domain/`)

| File | Purpose |
|------|---------|
| `enums.py` | `EntityStatus` (ACTIVE/DELETED), `VersionStatus` (DRAFT/COMMITTED/DELETED), `StorageType` (S3/GCS/AZURE/LOCAL) — all `str, Enum` subclasses |
| `value_objects.py` | `DVCHash` (frozen, with `__bool__`), `StorageURI` (with `scheme` property via `urlparse`), `VersionNumber` (validated >= 1) |
| `exceptions.py` | 8-class hierarchy rooted at `OodcpError`: `EntityNotFoundError`, `DuplicateNameError`, `InvalidStatusTransitionError`, `StorageError`, `DataNotFoundError`, `IntegrityError`, `DeleteConstraintError` |
| `entities/datarepo.py` | `DataRepo` ABC — single repository interface defining 17 abstract methods across DataSet, DataFile, DataVersion, lineage, and lifecycle operations |
| `entities/dataset.py` | Mutable `@dataclass` with `_repo: Optional[DataRepo]`. Methods: `addfile()`, `getfile()`, `listfiles()`, `delfile()`, `delallfiles()`, `candelete()` |
| `entities/datafile.py` | Mutable `@dataclass` with `_repo: Optional[DataRepo]`. Methods: `getversion()`, `getlatestversion()`, `addversion()`, `listversions()`, `delversion()`, `delallversions()`, `candelete()` |
| `entities/dataversion.py` | `DataVersion` ABC with `_storage_gateway: Optional[StorageGateway]`. Abstract property `storage_type`. Methods: `getdata()`, `savedata()`, `verify()`, `hash_info` property. 4 concrete subclasses: `S3DataVersion`, `GCSDataVersion`, `AzureDataVersion`, `LocalDataVersion` |

### 2.2 Infrastructure Layer (`dvc/oodcp/infrastructure/`)

| File | Purpose |
|------|---------|
| `gateways/storage_gateway.py` | `StorageGateway` — PEP 544 `@runtime_checkable Protocol` with methods: `push()`, `pull()`, `verify()`, `transfer()` |

### 2.3 Data Layer (`dvc/oodcp/data/`)

| File | Purpose |
|------|---------|
| `schema.py` | SQLite DDL: 3 tables (`datasets`, `datafiles`, `dataversions`) with foreign keys, unique constraints, and 3 indexes |
| `dal/dataset_dal.py` | `DataSetDAL` — SQL UPSERT, get by UUID/name, list with status filter |
| `dal/datafile_dal.py` | `DataFileDAL` — SQL UPSERT, get by UUID/name-within-dataset, list with status filter |
| `dal/dataversion_dal.py` | `DataVersionDAL` — SQL UPSERT, get latest committed, next version number, list ordered by version_number, recursive CTE lineage traversal |
| `datarepo_sqlite.py` | `DataRepoSQLite(DataRepo)` — concrete implementation. Lazy-initializes SQLite connection with WAL mode. Delegates SQL to DALs. Handles entity↔dict serialization (JSON for metadata/shared_metadata, ISO 8601 for datetimes, enum `.value` for statuses). Maps `storage_type` string to correct `DataVersion` subclass on retrieval. |

### 2.4 App Layer (`dvc/oodcp/app/`)

| File | Purpose |
|------|---------|
| `factory/dataset_factory.py` | `DataSetFactory` — creates `DataSet` with injected `DataRepo` |
| `factory/datafile_factory.py` | `DataFileFactory` — creates `DataFile` with injected `DataRepo` |
| `factory/dataversion_factory.py` | `DataVersionFactory` — module-level `_REGISTRY` mapping `StorageType` → concrete class. Dual-mode creation: `dvc_hash` (pre-computed, sets COMMITTED) or `source_path` (triggers `savedata()` push) |

### 2.5 Test Suite (`tests/unit/oodcp/`)

| File | Tests | Coverage Focus |
|------|-------|----------------|
| `conftest.py` | — | Shared fixtures: `repo` (in-memory SQLite), `mock_storage_gateway`, `mock_repo`, sample entities |
| `domain/test_enums.py` | 9 | Enum values, string construction, invalid raises |
| `domain/test_value_objects.py` | 12 | Immutability, `__bool__`, scheme parsing, validation |
| `domain/test_exceptions.py` | 14 | Hierarchy, attributes, messages |
| `domain/test_datarepo.py` | 6 | ABC contract — cannot instantiate, all abstract methods present |
| `domain/test_dataset.py` | 14 | addfile/getfile/listfiles/delfile/candelete with real SQLite |
| `domain/test_datafile.py` | 19 | addversion (hash/source_path/auto-increment/lineage/metadata), getversion, listversions, delete lifecycle |
| `domain/test_dataversion.py` | 11 | ABC enforcement, subclass storage_type, savedata/getdata/verify with mock gateway |
| `data/test_datarepo_sqlite.py` | 24 | Full CRUD round-trip, metadata JSON, lineage CTE, status filtering, connection lifecycle |
| `app/test_dataset_factory.py` | 6 | DI injection, defaults, all params |
| `app/test_datafile_factory.py` | 4 | DI injection, defaults |
| `app/test_dataversion_factory.py` | 9 | Subclass selection, dual-mode creation, validation |

---

## 3. Design Decisions

### 3.1 Single DataRepo ABC (per user Q1)
The original V2 design had a separate Repo Layer with `DataSetRepository`, `DataFileRepository`, `DataVersionRepository`, and `UnitOfWork`. Per the user's Q1 answer, this was consolidated into **one DataRepo ABC** (Domain Layer) with **one DataRepoSQLite concrete** (Data Layer) delegating to DAL objects. This simplified dependency injection — entities carry a single `_repo` reference instead of multiple repository references.

### 3.2 DAL Pattern for SQL Isolation
Rather than putting SQL directly in `DataRepoSQLite`, SQL operations are isolated in three DAL classes (`DataSetDAL`, `DataFileDAL`, `DataVersionDAL`). `DataRepoSQLite` handles entity↔dict conversion and delegates raw SQL execution to DALs. This keeps serialization logic separate from query logic and makes it straightforward to add a PostgreSQL DAL later.

### 3.3 Dual-Mode DataVersion Creation (per user Q2)
`DataVersionFactory.create()` and `DataFile.addversion()` both accept either `source_path` (triggers hash+push via StorageGateway) **or** `dvc_hash` (pre-computed, skips push). When `dvc_hash` is provided, status is set directly to COMMITTED. This avoids double-hashing when data comes from DVC pipeline stages that already computed the hash.

### 3.4 Module-Level Registry for DataVersionFactory
`DataVersionFactory` uses a module-level `_REGISTRY` dict mapping `StorageType` to concrete `DataVersion` subclass, pre-populated with all 4 types. This avoids class-level mutable state that could leak between tests (the V2 design had `_registry` as a class variable with `register()` classmethod — changed to module-level for safety).

### 3.5 SQLite UPSERT for Save/Update Unification
Both `add_*` and `update_*` methods in `DataRepoSQLite` delegate to the same DAL `.save()` method which uses `INSERT ... ON CONFLICT(uuid) DO UPDATE`. This simplifies the code — no separate insert vs. update paths — while the domain layer distinguishes add vs. update semantically.

### 3.6 Lazy Connection Initialization
`DataRepoSQLite` lazily initializes the SQLite connection on first access via the `conn` property. Schema creation (`CREATE TABLE IF NOT EXISTS`) runs automatically. This allows the object to be instantiated without immediate I/O, and supports re-initialization after `close()`.

---

## 4. Testing

### 4.1 Modules/Classes Tested

| Module | Class Under Test | Test Strategy |
|--------|-----------------|---------------|
| `domain/enums.py` | `EntityStatus`, `VersionStatus`, `StorageType` | Direct enum value assertions, string construction, invalid value rejection |
| `domain/value_objects.py` | `DVCHash`, `StorageURI`, `VersionNumber` | Immutability (`pytest.raises(AttributeError)`), equality, `__bool__`, `scheme` parsing, validation |
| `domain/exceptions.py` | All 8 exception classes | `issubclass` hierarchy checks, attribute access, `str()` message content |
| `domain/entities/datarepo.py` | `DataRepo` ABC | `TypeError` on instantiation, `__abstractmethods__` membership |
| `domain/entities/dataset.py` | `DataSet` | Integration with real `DataRepoSQLite` — addfile creates+persists, duplicate raises `DuplicateNameError`, getfile by name/uuid, listfiles with status filter, soft-delete, candelete |
| `domain/entities/datafile.py` | `DataFile` | Integration with real `DataRepoSQLite` — addversion with hash/source_path, auto-increment, lineage, metadata, getversion by number/uuid, listversions, delete lifecycle |
| `domain/entities/dataversion.py` | `DataVersion`, `S3DataVersion`, etc. | ABC enforcement, `storage_type` property, `savedata()` mock push, `getdata()` mock pull, `verify()` mock check |
| `data/datarepo_sqlite.py` | `DataRepoSQLite` | Full CRUD round-trips for all 3 entity types, JSON metadata serialization, lineage CTE traversal with depth limit, status filtering, entity `_repo` injection, connection lifecycle |
| `app/factory/dataset_factory.py` | `DataSetFactory` | DI injection verification, defaults, all parameters |
| `app/factory/datafile_factory.py` | `DataFileFactory` | DI injection verification, defaults |
| `app/factory/dataversion_factory.py` | `DataVersionFactory` | Subclass registry selection, dual-mode creation (hash vs. source_path), validation, metadata passthrough |

### 4.2 Test Execution
```
$ pytest tests/unit/oodcp/ -v
154 passed in 0.91s
```

---

## 5. Challenges Faced

### 5.1 DataRepo Architecture Pivot
The V2 design specified a separate Repo Layer with 3 repositories + UnitOfWork. The user's Q1 answer mandated a single `DataRepo` ABC with one concrete implementation. This required rethinking entity injection (single `_repo` instead of multiple repo references) and eliminating the UnitOfWork class for Phase 1. The entity method signatures had to be adjusted — e.g., `DataSet._repo` instead of `DataSet._dataset_repo` + `DataSet._datafile_repo`.

### 5.2 Foreign Key Constraints in Tests
Domain entity tests (e.g., `TestDataSetAddFile`) that use real SQLite require the parent entity to be persisted first (`repo.add_dataset(sample_dataset)`) before adding child entities, due to SQLite foreign key enforcement. The initial fixtures didn't persist the parent, which would have caused `IntegrityError` failures. Resolved by adding explicit `repo.add_dataset()` calls in tests that create child entities.

### 5.3 DataVersion Subclass Mapping on Retrieval
When loading `DataVersion` from SQLite, the `storage_type` column determines which concrete subclass to instantiate. The `_dataversion_from_dict()` method maps `StorageType` enum to the correct class via `_VERSION_CLS_MAP`. This mapping must stay in sync with any new subclasses added in the future.

### 5.4 JSON Serialization for Dict Fields
`DataSet.shared_metadata` and `DataVersion.metadata` are Python dicts but stored as JSON TEXT in SQLite. The serialization/deserialization must handle both directions correctly. `DataRepoSQLite` uses `json.dumps()` on save and `json.loads()` on load, with a guard for cases where the value might already be a dict (e.g., when retrieved via `sqlite3.Row`).

---

## 6. Open Questions / Risks

### 6.1 UnitOfWork Deferred
The V2 design included a `UnitOfWork` class for atomic multi-entity transactions. With the single `DataRepoSQLite` pattern, each `add_*`/`update_*` call commits immediately. This means a failure mid-way through a multi-step operation (e.g., creating a DataFile then its first DataVersion) can leave the database in a partially committed state. **Risk:** Low for Phase 1 (tests use in-memory SQLite), but should be addressed before production use. A transaction context manager on `DataRepoSQLite` could wrap multi-step operations.

### 6.2 Concurrent Access Not Tested
SQLite WAL mode is enabled for concurrent reads, but no tests exercise concurrent writes. **Risk:** If multiple processes write to the same `.dvc/tmp/oodcp/metadata.db` simultaneously, locking contention could occur. Mitigation: Phase 2 will add retry logic or advisory locking if needed.

### 6.3 MetadataGateway Protocol Not Yet Defined
The V2 design included a `MetadataGateway` Protocol in the Infrastructure Layer. Phase 1 skipped this because `DataRepoSQLite` directly implements `DataRepo` ABC and encapsulates all SQLite knowledge. If a PostgreSQL backend is needed later, defining `MetadataGateway` as an additional abstraction between the DALs and external databases would be required.

### 6.4 SCMGateway Not Yet Needed
The V2 design included `SCMGateway` Protocol for Git operations. Phase 1 has no Git integration, so this was deferred to Phase 3 when pipeline dependencies need to track metadata files.

### 6.5 Domain Services Deferred to Phase 2
`LineageService` and `IntegrityService` were originally Phase 1 in the V2 design but are more logically Phase 2 deliverables since `IntegrityService` requires a working `StorageGateway` implementation, and `LineageService` duplicates functionality already present in `DataRepo.query_lineage()`.

### 6.6 DataVersion `getdata()` Signature Mismatch with StorageGateway
`DataVersion.getdata()` calls `self._storage_gateway.pull(dvc_hash, hash_algorithm, dest_path)` with 3 positional args, but `StorageGateway.pull()` defines 5 parameters (including `remote_name` and `jobs`). The current entity methods don't expose `remote_name` or `jobs` to callers. **Risk:** Minor — default `None` values work, but the entity API may need extension for advanced use cases.

---

## 7. Statistics

### 7.1 Lines of Code

| Category | LOC |
|----------|----:|
| Source code (non-test, non-`__init__`) | 1,988 |
| Test code (non-`__init__`) | 1,694 |
| Package `__init__.py` files (14 files, all empty) | 0 |
| **Total** | **3,682** |

**Source file breakdown:**

| File | LOC |
|------|----:|
| `domain/enums.py` | 25 |
| `domain/value_objects.py` | 62 |
| `domain/exceptions.py` | 60 |
| `domain/entities/datarepo.py` | 225 |
| `domain/entities/dataset.py` | 166 |
| `domain/entities/datafile.py` | 226 |
| `domain/entities/dataversion.py` | 157 |
| `infrastructure/gateways/storage_gateway.py` | 93 |
| `data/schema.py` | 55 |
| `data/dal/dataset_dal.py` | 96 |
| `data/dal/datafile_dal.py` | 103 |
| `data/dal/dataversion_dal.py` | 168 |
| `data/datarepo_sqlite.py` | 323 |
| `app/factory/dataset_factory.py` | 58 |
| `app/factory/datafile_factory.py` | 55 |
| `app/factory/dataversion_factory.py` | 116 |

### 7.2 Modules Created / Modified

| Category | Count |
|----------|------:|
| Source modules created (non-`__init__`) | 16 |
| Test modules created (non-`__init__`) | 12 |
| Package `__init__.py` files created | 14 |
| Existing modules modified | 0 |
| **Total files created** | **42** |

### 7.3 Classes Created / Modified

| Category | Count |
|----------|------:|
| Source classes created | 30 |
| Test classes created | 36 |
| Existing classes modified | 0 |
| **Total classes** | **66** |

**Source classes (30):** `EntityStatus`, `VersionStatus`, `StorageType`, `DVCHash`, `StorageURI`, `VersionNumber`, `OodcpError`, `EntityNotFoundError`, `DuplicateNameError`, `InvalidStatusTransitionError`, `StorageError`, `DataNotFoundError`, `IntegrityError`, `DeleteConstraintError`, `DataRepo`, `DataSet`, `DataFile`, `DataVersion`, `S3DataVersion`, `GCSDataVersion`, `AzureDataVersion`, `LocalDataVersion`, `StorageGateway`, `DataSetDAL`, `DataFileDAL`, `DataVersionDAL`, `DataRepoSQLite`, `DataSetFactory`, `DataFileFactory`, `DataVersionFactory`

### 7.4 Tests Completed

| Test Type | Count | Status |
|-----------|------:|--------|
| Unit tests | 154 | All passing |
| Integration tests | 0 | N/A (Phase 1 scope) |
| Regression tests | 0 | N/A (no existing modules modified) |
| **Total** | **154** | **All passing** |

```
$ pytest tests/unit/oodcp/ -v
154 passed in 0.91s
```
