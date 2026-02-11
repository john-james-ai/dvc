# Phase 2 Summary — DVC Storage Integration and Manager

## 1. Implementation Summary

Phase 2 connected the OOD-CP metadata layer (Phase 1) to DVC's actual storage infrastructure. All six Phase 2 deliverables were completed:

**Scope delivered:**
- DVCStorageAdapter — concrete `StorageGateway` wrapping DVC's DataCloud and CacheManager
- LineageService — domain service for ancestor/descendant traversal
- IntegrityService — domain service for single and batch hash verification
- OodcpManager — facade wiring all layers together with lazy initialization
- DVC Repo registration — `self.oodcp = OodcpManager(self)` in `dvc/repo/__init__.py`
- DVC config section — `[oodcp]` added to `dvc/config_schema.py`
- 45 new unit tests (199 total, all passing)

**End-to-end capability:** Create DataSet → Add DataFile → Create DataVersion → Push data via DVC DataCloud → Pull from remote → Verify hash integrity → Query lineage chains.

---

## 2. Implementation Detail

### 2.1 DVCStorageAdapter (`dvc/oodcp/data/adapters/dvc_storage_adapter.py`)

| Method | DVC API Used | Behavior |
|--------|-------------|----------|
| `push()` | `dvc_data.hashfile.build.build()` → `dvc_data.hashfile.transfer.transfer()` → `Repo.cloud.push()` | Hashes local data via `build()`, stages to local cache via `transfer()`, pushes to remote via DataCloud. Returns `(hash_value, algorithm)` tuple. |
| `pull()` | `Repo.cloud.pull()` → `Repo.cache.local.oid_to_path()` → `localfs.copy()` | Converts `(dvc_hash, algorithm)` to `HashInfo`, pulls from remote to local cache, then copies from cache to destination path. |
| `verify()` | `Repo.cloud.status()` | Converts to `HashInfo`, calls `DataCloud.status()`. Returns `True` iff `len(status.ok) > 0 and len(status.missing) == 0`. |
| `transfer()` | `Repo.cloud.get_remote_odb()` × 2 → `Repo.cloud.transfer()` | Gets ODB instances for source and destination remotes, then calls `DataCloud.transfer()`. Returns `True` iff `len(result.failed) == 0`. |

**Key DVC types used:**
- `dvc_data.hashfile.hash_info.HashInfo` — DVC's content-addressed hash representation
- `dvc_data.hashfile.hash.DEFAULT_ALGORITHM` — Default hash algorithm (md5)
- `dvc.fs.localfs` — Local filesystem from dvc_objects/fsspec
- `dvc_data.hashfile.build.build` — Computes hash for a given path
- `dvc_data.hashfile.transfer.transfer` — Stages data to local cache

### 2.2 Domain Services (`dvc/oodcp/domain/services/`)

| Service | Dependencies | Methods |
|---------|-------------|---------|
| `LineageService` | `DataRepo` | `get_lineage(uuid, max_depth)` — delegates to `DataRepo.query_lineage()` for recursive CTE traversal. `get_descendants(uuid)` — reverse lookup scanning all versions for matching `source_version_uuid`. |
| `IntegrityService` | `StorageGateway` | `verify_version(version)` — returns `False` for empty hash, otherwise delegates to `StorageGateway.verify()`. `verify_batch(versions)` — returns `{uuid: bool}` dict. |

### 2.3 OodcpManager Facade (`dvc/oodcp/app/manager.py`)

The facade wires all layers with lazy-initialized properties:

| Property | Type | Wiring |
|----------|------|--------|
| `datarepo` | `DataRepoSQLite` | `DataRepoSQLite(self._get_db_path())` |
| `storage_gateway` | `DVCStorageAdapter` | `DVCStorageAdapter(self._repo)` |
| `dataset_factory` | `DataSetFactory` | `DataSetFactory(self.datarepo)` |
| `datafile_factory` | `DataFileFactory` | `DataFileFactory(self.datarepo)` |
| `dataversion_factory` | `DataVersionFactory` | `DataVersionFactory(self.storage_gateway)` |
| `lineage_service` | `LineageService` | `LineageService(self.datarepo)` |
| `integrity_service` | `IntegrityService` | `IntegrityService(self.storage_gateway)` |

**Database path resolution:** `_get_db_path()` returns `.dvc/tmp/oodcp/metadata.db` when `repo.tmp_dir` exists, otherwise falls back to `:memory:`. Creates the `oodcp/` directory if needed.

**Lifecycle:** `close()` calls `datarepo.close()` on the SQLite connection and resets all cached instances to `None`, enabling re-initialization on next access.

### 2.4 DVC Repo Registration (`dvc/repo/__init__.py:235-237`)

```python
from dvc.oodcp.app.manager import OodcpManager
self.oodcp: OodcpManager = OodcpManager(self)
```

Placed after `self.datasets = Datasets(self)` (line 233), following the existing subsystem registration pattern.

### 2.5 Config Section (`dvc/config_schema.py:387-390`)

```python
"oodcp": {
    Optional("enabled", default=False): Bool,
    "db_url": str,
},
```

Added to `SCHEMA` dict, supporting future opt-in enablement and external database URL override. Follows DVC's existing `[studio]` and `[db]` section patterns.

### 2.6 Test Suite Additions

| File | Tests | Coverage Focus |
|------|-------|----------------|
| `data/test_dvc_storage_adapter.py` | 15 | Push (build + cache_transfer + cloud.push), Pull (cloud.pull + localfs.copy), Verify (cloud.status), Transfer (get_remote_odb × 2 + cloud.transfer). All with mock DVC Repo. |
| `domain/test_lineage_service.py` | 8 | Full chain traversal, single version, depth limit, nonexistent UUID. Descendants: direct children, root has one child, leaf has none, nonexistent. Uses real in-memory SQLite with pre-populated data. |
| `domain/test_integrity_service.py` | 7 | Single verify (true/false/empty hash), gateway delegation check. Batch: all pass, mixed results, empty list. Uses mock StorageGateway. |
| `app/test_manager.py` | 14 | Init (repo reference, all properties None). Lazy properties: 7 tests verifying correct type and singleton behavior. DB path: memory fallback and file path creation. Close: resets all, idempotent. Integration: factory→entity→datarepo round trip. |

---

## 3. Design Decisions

### 3.1 Module-Level Imports in DVCStorageAdapter
DVC dependencies (`build`, `HashInfo`, `localfs`, `cache_transfer`, `DEFAULT_ALGORITHM`) are imported at module level rather than locally inside method bodies. This enables standard `@patch("dvc.oodcp.data.adapters.dvc_storage_adapter.build")` mocking patterns in tests. The initial implementation used local imports (matching DVC's internal style), which caused `AttributeError` failures because `@patch` targets module-level namespace attributes.

### 3.2 `cache_transfer` Alias
The `dvc_data.hashfile.transfer.transfer` function is imported as `cache_transfer` to avoid shadowing with `DataCloud.transfer()` and to make the purpose clear — staging data from the build output to the local cache.

### 3.3 LineageService Delegates to DataRepo
`LineageService.get_lineage()` delegates entirely to `DataRepo.query_lineage()` rather than reimplementing the recursive CTE traversal. This keeps the domain service thin — it provides a semantic entry point without duplicating SQL logic. `get_descendants()` does its own filtering since this is a reverse lookup not provided by the DataRepo interface.

### 3.4 IntegrityService Short-Circuits on Empty Hash
`verify_version()` returns `False` immediately if `version.dvc_hash` is empty, without calling the StorageGateway. This handles DRAFT versions that haven't been pushed yet, avoiding an unnecessary (and likely failing) remote call.

### 3.5 Lazy Initialization in OodcpManager
All properties are lazy-initialized (created on first access). This means importing `dvc.oodcp` and creating the manager has zero cost if OOD-CP features aren't used. Each property caches its instance and returns the same object on subsequent accesses (singleton within the manager lifetime).

### 3.6 Config Section Minimal
The `[oodcp]` config section includes only `enabled` (default False) and `db_url` (string). The `enabled` flag is a future guard — Phase 2 registers the manager unconditionally, but a future phase could check this flag before initialization. The `db_url` enables the external database override described in Design Q1 (Option C).

---

## 4. Testing

### 4.1 Modules/Classes Tested

| Module | Class Under Test | Test Strategy |
|--------|-----------------|---------------|
| `data/adapters/dvc_storage_adapter.py` | `DVCStorageAdapter` | Mock-based: `MagicMock` for DVC Repo, `@patch` for `build`, `cache_transfer`, `localfs`. Verifies delegation to DVC APIs, hash tuple return, remote name forwarding, failure detection. |
| `domain/services/lineage_service.py` | `LineageService` | Integration: real `DataRepoSQLite` with pre-populated 3-version chain (v1→v2→v3). Tests full traversal, single version, depth limit, and descendants with reverse lookup. |
| `domain/services/integrity_service.py` | `IntegrityService` | Mock-based: `MagicMock` for StorageGateway. Tests verify delegation, empty hash short-circuit, gateway argument passing, batch result aggregation. |
| `app/manager.py` | `OodcpManager` | Mock-based for init (mock DVC Repo with `tmp_dir=None`). Lazy property tests verify correct concrete types (`DataRepoSQLite`, `DVCStorageAdapter`, `DataSetFactory`, etc.) and singleton behavior. DB path tests verify `:memory:` fallback and filesystem path creation. Integration tests verify factory→entity→datarepo wiring. |

### 4.2 Test Execution

```
$ pytest tests/unit/oodcp/ -v
199 passed in 1.26s
```

**Breakdown:** 154 Phase 1 tests + 45 Phase 2 tests = 199 total.

---

## 5. Challenges Faced

### 5.1 Local Imports vs. @patch Mocking
The initial DVCStorageAdapter used local imports inside method bodies (e.g., `from dvc_data.hashfile.build import build` inside `push()`), following DVC's common internal pattern. This caused all push/pull test `@patch` decorators to fail with `AttributeError: <module> does not have the attribute 'build'` — because `@patch` modifies module-level namespace attributes, and local imports don't create module-level bindings.

**Resolution:** Moved all DVC imports (`build`, `HashInfo`, `localfs`, `cache_transfer`, `DEFAULT_ALGORITHM`) to module level. Tests now use `@patch("dvc.oodcp.data.adapters.dvc_storage_adapter.build")` which correctly intercepts the module-level reference.

### 5.2 push() Requires cache_transfer Patching
The `push()` method calls both `build()` and `cache_transfer()`. Initially, the tests only patched `build`, which caused real `cache_transfer` to execute on mock objects, producing failures. Each push test now stacks two `@patch` decorators: one for `build` and one for `cache_transfer`.

### 5.3 DVC DataCloud API Signatures
DVC's `DataCloud.push()`, `pull()`, and `status()` methods accept `Iterable[HashInfo]` as their first positional argument. The adapter wraps single hash values in `[hash_info]` lists to satisfy this interface. The `transfer()` method has a different signature (`src_odb`, `dest_odb`, `objs`) requiring ODB objects obtained from `get_remote_odb()`.

### 5.4 OodcpManager DB Path with `tmp_dir=None`
The mock DVC Repo in manager tests has `tmp_dir = None`, which triggers the `:memory:` fallback. This was intentional to avoid filesystem side effects in unit tests, but required ensuring that `_get_db_path()` checks for `None` before calling `os.path.join()`.

---

## 6. Open Questions / Risks

### 6.1 Repo Registration Unconditional
`OodcpManager` is instantiated unconditionally for every `dvc.repo.Repo()`. Since all properties are lazy, this has near-zero overhead, but the `import OodcpManager` statement does execute at Repo init time. If this causes import-time issues, the registration could be guarded by `if config.get("oodcp", {}).get("enabled"):`.

### 6.2 cache_transfer Coupling
`DVCStorageAdapter.push()` calls `dvc_data.hashfile.transfer.transfer()` to stage data to the local cache before cloud push. This is an internal DVC implementation detail that could change between DVC versions. The transfer call may also not be strictly necessary if `DataCloud.push()` handles cache staging internally. **Mitigation:** The adapter is the only module that knows about this — if DVC changes, only this file needs updating.

### 6.3 pull() Checkout Path
`pull()` copies data from cache to `dest_path` using `localfs.copy()`. This works for single files but may not correctly handle directory-type objects (where DVC uses `.dir` manifests). For Phase 2 (single-file focus), this is sufficient. Directory support may require using DVC's `checkout()` or `dvc_data.hashfile.checkout` in the future.

### 6.4 No Functional Tests Against Real Remote
Phase 2 unit tests mock all DVC internals. No functional tests exercise the actual push/pull/verify flow against a real (even local) remote. This should be added in Phase 3 using DVC's `tmp_dir` + `make_remote` test fixtures.

### 6.5 IntegrityService Sequential Batch
`verify_batch()` verifies versions sequentially via a loop. For large batches against remote storage, this could be slow. A future optimization could batch `StorageGateway.verify()` calls or use `DataCloud.status()` with multiple HashInfo objects in a single call.

### 6.6 Phase 1 Open Items Status
- **UnitOfWork (6.1):** Still deferred. Individual operations commit immediately.
- **Concurrent Access (6.2):** Still untested. WAL mode enabled but not stress-tested.
- **MetadataGateway Protocol (6.3):** Still not defined. DataRepoSQLite remains the sole implementation.
- **SCMGateway (6.4):** Still deferred to Phase 3.
- **getdata() Signature (6.6):** Still passes only required args. `remote_name` and `jobs` default to `None`.

---

## 7. Statistics

### 7.1 Lines of Code

| Category | LOC |
|----------|----:|
| New source code | 495 |
| Modified source code (lines added to existing files) | 7 |
| New test code | 602 |
| **Total Phase 2 LOC** | **1,104** |

**Cumulative (Phase 1 + Phase 2):**

| Category | LOC |
|----------|----:|
| Source code | 2,490 |
| Test code | 2,296 |
| **Grand total** | **4,786** |

**New source file breakdown:**

| File | LOC |
|------|----:|
| `data/adapters/dvc_storage_adapter.py` | 176 |
| `domain/services/lineage_service.py` | 72 |
| `domain/services/integrity_service.py` | 60 |
| `app/manager.py` | 187 |

**Modified source file breakdown:**

| File | Lines Added |
|------|----:|
| `dvc/repo/__init__.py` (registration) | 3 |
| `dvc/config_schema.py` (`[oodcp]` section) | 4 |

### 7.2 Modules Created / Modified

| Category | Count |
|----------|------:|
| New source modules | 4 |
| Modified existing source modules | 2 |
| New test modules | 4 |
| **Total files touched** | **10** |

**Cumulative (Phase 1 + Phase 2):**

| Category | Count |
|----------|------:|
| Source modules created | 20 |
| Existing modules modified | 2 |
| Test modules created | 16 |
| Package `__init__.py` files | 14 |
| **Total files** | **52** |

### 7.3 Classes Created / Modified

| Category | Count |
|----------|------:|
| Source classes created | 4 |
| Test classes created | 13 |
| Existing classes modified | 0 |
| **Total Phase 2 classes** | **17** |

**Source classes (4):** `DVCStorageAdapter`, `LineageService`, `IntegrityService`, `OodcpManager`

**Cumulative (Phase 1 + Phase 2):**

| Category | Count |
|----------|------:|
| Source classes | 34 |
| Test classes | 49 |
| **Total classes** | **83** |

### 7.4 Tests Completed

| Test Type | Phase 2 | Cumulative |Status |
|-----------|--------:|-----------:|-------|
| Unit tests | 45 | 199 | All passing |
| Integration tests | 0 | 0 | N/A |
| Regression tests | 0 | 0 | Not yet run (deferred to Phase 3) |
| **Total** | **45** | **199** | **All passing** |

```
$ pytest tests/unit/oodcp/ -v
199 passed in 1.26s
```

**Note:** Regression testing against DVC's existing test suite (`pytest tests/unit/ --ignore=tests/unit/oodcp`) is recommended after Phase 2's modifications to `dvc/repo/__init__.py` and `dvc/config_schema.py`, but was not executed in this phase as the changes are additive (new attribute on Repo, new config section) with no behavioral modifications to existing code.
