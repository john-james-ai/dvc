"""Tests for DataRepoSQLite concrete implementation.

Tests the full round-trip: entity → dict → SQLite → dict → entity.
Uses in-memory SQLite for isolation.
"""

import json
import pytest

from dvc.oodcp.data.datarepo_sqlite import DataRepoSQLite
from dvc.oodcp.domain.entities.datafile import DataFile
from dvc.oodcp.domain.entities.dataset import DataSet
from dvc.oodcp.domain.entities.dataversion import (
    GCSDataVersion,
    LocalDataVersion,
    S3DataVersion,
)
from dvc.oodcp.domain.enums import EntityStatus, StorageType, VersionStatus


@pytest.fixture
def sqlite_repo():
    """Fresh in-memory DataRepoSQLite per test."""
    r = DataRepoSQLite(":memory:")
    yield r
    r.close()


@pytest.fixture
def persisted_dataset(sqlite_repo):
    """A DataSet persisted in the sqlite_repo."""
    ds = DataSet(
        uuid="ds-001",
        name="test-dataset",
        description="A test dataset",
        project="proj",
        owner="owner",
        shared_metadata={"license": "MIT"},
        _repo=sqlite_repo,
    )
    sqlite_repo.add_dataset(ds)
    return ds


@pytest.fixture
def persisted_datafile(sqlite_repo, persisted_dataset):
    """A DataFile persisted in the sqlite_repo."""
    df = DataFile(
        uuid="df-001",
        dataset_uuid="ds-001",
        name="train.csv",
        description="Training data",
        owner="owner",
        _repo=sqlite_repo,
    )
    sqlite_repo.add_datafile(df)
    return df


class TestDataSetCRUD:
    """Verify DataSet CRUD round-trips through SQLite."""

    def test_add_and_get(self, sqlite_repo):
        """add_dataset then get_dataset returns same entity."""
        ds = DataSet(uuid="ds-001", name="test", _repo=sqlite_repo)
        sqlite_repo.add_dataset(ds)
        result = sqlite_repo.get_dataset("ds-001")
        assert result is not None
        assert result.uuid == "ds-001"
        assert result.name == "test"

    def test_get_by_name(self, sqlite_repo):
        """get_dataset_by_name retrieves by unique name."""
        ds = DataSet(uuid="ds-001", name="unique-name", _repo=sqlite_repo)
        sqlite_repo.add_dataset(ds)
        result = sqlite_repo.get_dataset_by_name("unique-name")
        assert result is not None
        assert result.uuid == "ds-001"

    def test_get_nonexistent_returns_none(self, sqlite_repo):
        """get_dataset returns None for unknown UUID."""
        assert sqlite_repo.get_dataset("nonexistent") is None

    def test_list_excludes_deleted(self, sqlite_repo):
        """list_datasets excludes DELETED by default."""
        ds1 = DataSet(uuid="ds-001", name="active", _repo=sqlite_repo)
        ds2 = DataSet(
            uuid="ds-002", name="deleted",
            status=EntityStatus.DELETED, _repo=sqlite_repo,
        )
        sqlite_repo.add_dataset(ds1)
        sqlite_repo.add_dataset(ds2)
        result = sqlite_repo.list_datasets()
        assert len(result) == 1
        assert result[0].name == "active"

    def test_list_includes_deleted(self, sqlite_repo):
        """list_datasets(include_deleted=True) returns all."""
        ds1 = DataSet(uuid="ds-001", name="active", _repo=sqlite_repo)
        ds2 = DataSet(
            uuid="ds-002", name="deleted",
            status=EntityStatus.DELETED, _repo=sqlite_repo,
        )
        sqlite_repo.add_dataset(ds1)
        sqlite_repo.add_dataset(ds2)
        result = sqlite_repo.list_datasets(include_deleted=True)
        assert len(result) == 2

    def test_update_dataset(self, sqlite_repo):
        """update_dataset persists changed fields."""
        ds = DataSet(uuid="ds-001", name="test", description="old",
                     _repo=sqlite_repo)
        sqlite_repo.add_dataset(ds)
        ds.description = "updated"
        sqlite_repo.update_dataset(ds)
        result = sqlite_repo.get_dataset("ds-001")
        assert result.description == "updated"

    def test_shared_metadata_round_trip(self, sqlite_repo):
        """shared_metadata dict survives save/load cycle."""
        ds = DataSet(
            uuid="ds-001", name="test",
            shared_metadata={"key": "value", "nested": {"a": 1}},
            _repo=sqlite_repo,
        )
        sqlite_repo.add_dataset(ds)
        result = sqlite_repo.get_dataset("ds-001")
        assert result.shared_metadata == {"key": "value", "nested": {"a": 1}}

    def test_entity_has_repo_injected(self, sqlite_repo):
        """Retrieved DataSet has _repo injected."""
        ds = DataSet(uuid="ds-001", name="test", _repo=sqlite_repo)
        sqlite_repo.add_dataset(ds)
        result = sqlite_repo.get_dataset("ds-001")
        assert result._repo is sqlite_repo


class TestDataFileCRUD:
    """Verify DataFile CRUD round-trips through SQLite."""

    def test_add_and_get(self, sqlite_repo, persisted_dataset):
        """add_datafile then get_datafile returns same entity."""
        df = DataFile(
            uuid="df-001", dataset_uuid="ds-001",
            name="train.csv", _repo=sqlite_repo,
        )
        sqlite_repo.add_datafile(df)
        result = sqlite_repo.get_datafile("df-001")
        assert result is not None
        assert result.name == "train.csv"

    def test_get_by_name(self, sqlite_repo, persisted_dataset):
        """get_datafile_by_name finds file within dataset."""
        df = DataFile(
            uuid="df-001", dataset_uuid="ds-001",
            name="train.csv", _repo=sqlite_repo,
        )
        sqlite_repo.add_datafile(df)
        result = sqlite_repo.get_datafile_by_name("ds-001", "train.csv")
        assert result is not None

    def test_list_for_dataset(self, sqlite_repo, persisted_dataset):
        """list_datafiles returns files for given dataset."""
        for i, name in enumerate(["a.csv", "b.csv"]):
            df = DataFile(
                uuid=f"df-{i}", dataset_uuid="ds-001",
                name=name, _repo=sqlite_repo,
            )
            sqlite_repo.add_datafile(df)
        result = sqlite_repo.list_datafiles("ds-001")
        assert len(result) == 2

    def test_list_excludes_deleted(self, sqlite_repo, persisted_dataset):
        """list_datafiles excludes DELETED by default."""
        df1 = DataFile(
            uuid="df-001", dataset_uuid="ds-001",
            name="active.csv", _repo=sqlite_repo,
        )
        df2 = DataFile(
            uuid="df-002", dataset_uuid="ds-001",
            name="deleted.csv", status=EntityStatus.DELETED,
            _repo=sqlite_repo,
        )
        sqlite_repo.add_datafile(df1)
        sqlite_repo.add_datafile(df2)
        result = sqlite_repo.list_datafiles("ds-001")
        assert len(result) == 1

    def test_entity_has_repo_injected(self, sqlite_repo, persisted_dataset):
        """Retrieved DataFile has _repo injected."""
        df = DataFile(
            uuid="df-001", dataset_uuid="ds-001",
            name="train.csv", _repo=sqlite_repo,
        )
        sqlite_repo.add_datafile(df)
        result = sqlite_repo.get_datafile("df-001")
        assert result._repo is sqlite_repo


class TestDataVersionCRUD:
    """Verify DataVersion CRUD round-trips through SQLite."""

    def test_add_and_get(self, sqlite_repo, persisted_datafile):
        """add_dataversion then get_dataversion returns same entity."""
        v = S3DataVersion(
            uuid="ver-001", datafile_uuid="df-001",
            version_number=1, dvc_hash="abc123",
            storage_uri="s3://bucket/path",
            status=VersionStatus.COMMITTED,
        )
        sqlite_repo.add_dataversion(v)
        result = sqlite_repo.get_dataversion("ver-001")
        assert result is not None
        assert isinstance(result, S3DataVersion)
        assert result.dvc_hash == "abc123"

    def test_storage_type_mapping(self, sqlite_repo, persisted_datafile):
        """Retrieved DataVersion is correct subclass based on storage_type."""
        v = GCSDataVersion(
            uuid="ver-001", datafile_uuid="df-001",
            version_number=1, dvc_hash="abc123",
        )
        sqlite_repo.add_dataversion(v)
        result = sqlite_repo.get_dataversion("ver-001")
        assert isinstance(result, GCSDataVersion)
        assert result.storage_type == StorageType.GCS

    def test_get_latest_committed(self, sqlite_repo, persisted_datafile):
        """get_latest_dataversion returns highest COMMITTED version."""
        for i in range(1, 4):
            v = LocalDataVersion(
                uuid=f"ver-{i:03d}", datafile_uuid="df-001",
                version_number=i, dvc_hash=f"hash{i}",
                status=VersionStatus.COMMITTED,
            )
            sqlite_repo.add_dataversion(v)
        # Add a DRAFT version (should not be returned)
        v_draft = LocalDataVersion(
            uuid="ver-004", datafile_uuid="df-001",
            version_number=4, status=VersionStatus.DRAFT,
        )
        sqlite_repo.add_dataversion(v_draft)

        result = sqlite_repo.get_latest_dataversion("df-001")
        assert result.version_number == 3

    def test_next_version_number_empty(self, sqlite_repo, persisted_datafile):
        """get_next_version_number returns 1 when no versions exist."""
        assert sqlite_repo.get_next_version_number("df-001") == 1

    def test_next_version_number_increments(
        self, sqlite_repo, persisted_datafile
    ):
        """get_next_version_number returns max + 1."""
        v = LocalDataVersion(
            uuid="ver-001", datafile_uuid="df-001",
            version_number=1, dvc_hash="abc",
        )
        sqlite_repo.add_dataversion(v)
        assert sqlite_repo.get_next_version_number("df-001") == 2

    def test_list_ordered_by_version(self, sqlite_repo, persisted_datafile):
        """list_dataversions returns versions in order."""
        for i in [3, 1, 2]:  # insert out of order
            v = LocalDataVersion(
                uuid=f"ver-{i:03d}", datafile_uuid="df-001",
                version_number=i, dvc_hash=f"hash{i}",
                status=VersionStatus.COMMITTED,
            )
            sqlite_repo.add_dataversion(v)
        result = sqlite_repo.list_dataversions("df-001")
        numbers = [r.version_number for r in result]
        assert numbers == [1, 2, 3]

    def test_list_excludes_deleted(self, sqlite_repo, persisted_datafile):
        """list_dataversions excludes DELETED by default."""
        v1 = LocalDataVersion(
            uuid="ver-001", datafile_uuid="df-001",
            version_number=1, status=VersionStatus.COMMITTED,
        )
        v2 = LocalDataVersion(
            uuid="ver-002", datafile_uuid="df-001",
            version_number=2, status=VersionStatus.DELETED,
        )
        sqlite_repo.add_dataversion(v1)
        sqlite_repo.add_dataversion(v2)
        result = sqlite_repo.list_dataversions("df-001")
        assert len(result) == 1

    def test_metadata_round_trip(self, sqlite_repo, persisted_datafile):
        """metadata dict survives save/load cycle."""
        v = LocalDataVersion(
            uuid="ver-001", datafile_uuid="df-001",
            version_number=1, metadata={"rows": 500, "cols": 10},
        )
        sqlite_repo.add_dataversion(v)
        result = sqlite_repo.get_dataversion("ver-001")
        assert result.metadata == {"rows": 500, "cols": 10}

    def test_update_dataversion(self, sqlite_repo, persisted_datafile):
        """update_dataversion persists changed fields."""
        v = LocalDataVersion(
            uuid="ver-001", datafile_uuid="df-001",
            version_number=1, status=VersionStatus.DRAFT,
        )
        sqlite_repo.add_dataversion(v)
        v.status = VersionStatus.COMMITTED
        v.dvc_hash = "newhash"
        sqlite_repo.update_dataversion(v)
        result = sqlite_repo.get_dataversion("ver-001")
        assert result.status == VersionStatus.COMMITTED
        assert result.dvc_hash == "newhash"


class TestLineageChain:
    """Verify lineage traversal via recursive CTE."""

    def test_lineage_single(self, sqlite_repo, persisted_datafile):
        """Single version with no parent returns chain of length 1."""
        v = LocalDataVersion(
            uuid="ver-001", datafile_uuid="df-001",
            version_number=1, dvc_hash="abc",
            status=VersionStatus.COMMITTED,
        )
        sqlite_repo.add_dataversion(v)
        chain = sqlite_repo.query_lineage("ver-001")
        assert len(chain) == 1
        assert chain[0].uuid == "ver-001"

    def test_lineage_chain_of_three(self, sqlite_repo, persisted_datafile):
        """Three-version chain returns all ancestors in order."""
        v1 = LocalDataVersion(
            uuid="ver-001", datafile_uuid="df-001",
            version_number=1, dvc_hash="h1",
            status=VersionStatus.COMMITTED,
        )
        v2 = LocalDataVersion(
            uuid="ver-002", datafile_uuid="df-001",
            version_number=2, dvc_hash="h2",
            source_version_uuid="ver-001",
            status=VersionStatus.COMMITTED,
        )
        v3 = LocalDataVersion(
            uuid="ver-003", datafile_uuid="df-001",
            version_number=3, dvc_hash="h3",
            source_version_uuid="ver-002",
            status=VersionStatus.COMMITTED,
        )
        sqlite_repo.add_dataversion(v1)
        sqlite_repo.add_dataversion(v2)
        sqlite_repo.add_dataversion(v3)

        chain = sqlite_repo.query_lineage("ver-003")
        assert len(chain) == 3
        uuids = [c.uuid for c in chain]
        assert uuids == ["ver-003", "ver-002", "ver-001"]

    def test_lineage_respects_depth(self, sqlite_repo, persisted_datafile):
        """max_depth limits traversal."""
        v1 = LocalDataVersion(
            uuid="ver-001", datafile_uuid="df-001",
            version_number=1, dvc_hash="h1",
            status=VersionStatus.COMMITTED,
        )
        v2 = LocalDataVersion(
            uuid="ver-002", datafile_uuid="df-001",
            version_number=2, dvc_hash="h2",
            source_version_uuid="ver-001",
            status=VersionStatus.COMMITTED,
        )
        v3 = LocalDataVersion(
            uuid="ver-003", datafile_uuid="df-001",
            version_number=3, dvc_hash="h3",
            source_version_uuid="ver-002",
            status=VersionStatus.COMMITTED,
        )
        sqlite_repo.add_dataversion(v1)
        sqlite_repo.add_dataversion(v2)
        sqlite_repo.add_dataversion(v3)

        chain = sqlite_repo.query_lineage("ver-003", depth=1)
        assert len(chain) == 1

    def test_lineage_nonexistent_returns_empty(
        self, sqlite_repo, persisted_datafile
    ):
        """query_lineage for nonexistent UUID returns empty list."""
        chain = sqlite_repo.query_lineage("nonexistent")
        assert chain == []


class TestDataRepoSQLiteLifecycle:
    """Verify connection lifecycle."""

    def test_close_releases_connection(self):
        """close() sets connection to None."""
        r = DataRepoSQLite(":memory:")
        _ = r.conn  # trigger initialization
        r.close()
        assert r._conn is None

    def test_reopen_after_close(self):
        """Accessing conn after close() re-initializes."""
        r = DataRepoSQLite(":memory:")
        _ = r.conn
        r.close()
        _ = r.conn  # should work after re-open
        r.close()
