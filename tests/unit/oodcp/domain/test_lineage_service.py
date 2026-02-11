"""Tests for LineageService domain service."""

import pytest

from dvc.oodcp.data.datarepo_sqlite import DataRepoSQLite
from dvc.oodcp.domain.entities.datafile import DataFile
from dvc.oodcp.domain.entities.dataset import DataSet
from dvc.oodcp.domain.entities.dataversion import LocalDataVersion
from dvc.oodcp.domain.enums import VersionStatus
from dvc.oodcp.domain.services.lineage_service import LineageService


@pytest.fixture
def lineage_repo():
    """In-memory DataRepoSQLite with pre-populated lineage data."""
    r = DataRepoSQLite(":memory:")

    ds = DataSet(uuid="ds-001", name="test", _repo=r)
    r.add_dataset(ds)

    df = DataFile(
        uuid="df-001", dataset_uuid="ds-001", name="data.csv", _repo=r
    )
    r.add_datafile(df)

    # v1 -> no parent
    v1 = LocalDataVersion(
        uuid="ver-001", datafile_uuid="df-001",
        version_number=1, dvc_hash="h1",
        status=VersionStatus.COMMITTED,
    )
    # v2 -> parent v1
    v2 = LocalDataVersion(
        uuid="ver-002", datafile_uuid="df-001",
        version_number=2, dvc_hash="h2",
        source_version_uuid="ver-001",
        status=VersionStatus.COMMITTED,
    )
    # v3 -> parent v2
    v3 = LocalDataVersion(
        uuid="ver-003", datafile_uuid="df-001",
        version_number=3, dvc_hash="h3",
        source_version_uuid="ver-002",
        status=VersionStatus.COMMITTED,
    )
    r.add_dataversion(v1)
    r.add_dataversion(v2)
    r.add_dataversion(v3)

    yield r
    r.close()


@pytest.fixture
def service(lineage_repo):
    """LineageService backed by pre-populated repo."""
    return LineageService(lineage_repo)


class TestGetLineage:
    """Verify get_lineage() traversal."""

    def test_full_chain(self, service):
        """get_lineage() returns full ancestor chain."""
        chain = service.get_lineage("ver-003")
        assert len(chain) == 3
        uuids = [v.uuid for v in chain]
        assert uuids == ["ver-003", "ver-002", "ver-001"]

    def test_single_version(self, service):
        """get_lineage() on root version returns single item."""
        chain = service.get_lineage("ver-001")
        assert len(chain) == 1
        assert chain[0].uuid == "ver-001"

    def test_with_depth_limit(self, service):
        """get_lineage() respects max_depth."""
        chain = service.get_lineage("ver-003", max_depth=2)
        assert len(chain) == 2

    def test_nonexistent_returns_empty(self, service):
        """get_lineage() for unknown UUID returns empty list."""
        chain = service.get_lineage("nonexistent")
        assert chain == []


class TestGetDescendants:
    """Verify get_descendants() reverse lookup."""

    def test_finds_direct_children(self, service):
        """get_descendants() returns versions citing this as source."""
        descendants = service.get_descendants("ver-001")
        assert len(descendants) == 1
        assert descendants[0].uuid == "ver-002"

    def test_root_has_one_child(self, service):
        """v1 has exactly one descendant (v2)."""
        descendants = service.get_descendants("ver-001")
        assert len(descendants) == 1

    def test_leaf_has_no_descendants(self, service):
        """v3 (leaf) has no descendants."""
        descendants = service.get_descendants("ver-003")
        assert len(descendants) == 0

    def test_nonexistent_returns_empty(self, service):
        """get_descendants() for unknown UUID returns empty."""
        descendants = service.get_descendants("nonexistent")
        assert descendants == []
