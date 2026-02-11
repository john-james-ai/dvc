"""Tests for OodcpManager facade."""

import os
import pytest
from unittest.mock import MagicMock, PropertyMock, patch

from dvc.oodcp.app.manager import OodcpManager


@pytest.fixture
def mock_dvc_repo():
    """Mock DVC Repo with minimal attributes for OodcpManager.

    Returns:
        MagicMock with tmp_dir returning a temp directory path.
    """
    repo = MagicMock()
    repo.tmp_dir = None  # Forces :memory: database
    repo.cloud = MagicMock()
    repo.cache = MagicMock()
    return repo


@pytest.fixture
def manager(mock_dvc_repo):
    """OodcpManager wrapping a mock DVC repo."""
    m = OodcpManager(mock_dvc_repo)
    yield m
    m.close()


class TestOodcpManagerInit:
    """Verify OodcpManager initialization."""

    def test_creates_with_repo(self, mock_dvc_repo):
        """OodcpManager initializes with DVC Repo."""
        m = OodcpManager(mock_dvc_repo)
        assert m._repo is mock_dvc_repo
        m.close()

    def test_all_properties_initially_none(self, mock_dvc_repo):
        """All lazy properties start as None."""
        m = OodcpManager(mock_dvc_repo)
        assert m._datarepo is None
        assert m._storage_gateway is None
        assert m._dataset_factory is None
        assert m._datafile_factory is None
        assert m._dataversion_factory is None
        assert m._lineage_service is None
        assert m._integrity_service is None
        m.close()


class TestOodcpManagerLazyProperties:
    """Verify lazy initialization of properties."""

    def test_datarepo_lazy_init(self, manager):
        """datarepo property initializes on first access."""
        from dvc.oodcp.data.datarepo_sqlite import DataRepoSQLite

        repo = manager.datarepo
        assert isinstance(repo, DataRepoSQLite)
        # Second access returns same instance
        assert manager.datarepo is repo

    def test_storage_gateway_lazy_init(self, manager):
        """storage_gateway property initializes on first access."""
        from dvc.oodcp.data.adapters.dvc_storage_adapter import (
            DVCStorageAdapter,
        )

        gw = manager.storage_gateway
        assert isinstance(gw, DVCStorageAdapter)
        assert manager.storage_gateway is gw

    def test_dataset_factory_lazy_init(self, manager):
        """dataset_factory property initializes on first access."""
        from dvc.oodcp.app.factory.dataset_factory import DataSetFactory

        f = manager.dataset_factory
        assert isinstance(f, DataSetFactory)
        assert manager.dataset_factory is f

    def test_datafile_factory_lazy_init(self, manager):
        """datafile_factory property initializes on first access."""
        from dvc.oodcp.app.factory.datafile_factory import DataFileFactory

        f = manager.datafile_factory
        assert isinstance(f, DataFileFactory)
        assert manager.datafile_factory is f

    def test_dataversion_factory_lazy_init(self, manager):
        """dataversion_factory property initializes on first access."""
        from dvc.oodcp.app.factory.dataversion_factory import (
            DataVersionFactory,
        )

        f = manager.dataversion_factory
        assert isinstance(f, DataVersionFactory)
        assert manager.dataversion_factory is f

    def test_lineage_service_lazy_init(self, manager):
        """lineage_service property initializes on first access."""
        from dvc.oodcp.domain.services.lineage_service import (
            LineageService,
        )

        s = manager.lineage_service
        assert isinstance(s, LineageService)
        assert manager.lineage_service is s

    def test_integrity_service_lazy_init(self, manager):
        """integrity_service property initializes on first access."""
        from dvc.oodcp.domain.services.integrity_service import (
            IntegrityService,
        )

        s = manager.integrity_service
        assert isinstance(s, IntegrityService)
        assert manager.integrity_service is s


class TestOodcpManagerDbPath:
    """Verify database path resolution."""

    def test_memory_when_no_tmp_dir(self, mock_dvc_repo):
        """Falls back to :memory: when repo has no tmp_dir."""
        mock_dvc_repo.tmp_dir = None
        m = OodcpManager(mock_dvc_repo)
        assert m._get_db_path() == ":memory:"
        m.close()

    def test_file_path_when_tmp_dir_exists(self, tmp_path, mock_dvc_repo):
        """Creates oodcp dir under tmp_dir and returns db path."""
        mock_dvc_repo.tmp_dir = str(tmp_path)
        m = OodcpManager(mock_dvc_repo)
        db_path = m._get_db_path()
        assert db_path.endswith("oodcp/metadata.db")
        assert os.path.isdir(os.path.dirname(db_path))
        m.close()


class TestOodcpManagerClose:
    """Verify close() releases resources."""

    def test_close_resets_all(self, manager):
        """close() sets all cached instances to None."""
        # Force initialization
        _ = manager.datarepo
        _ = manager.storage_gateway
        manager.close()
        assert manager._datarepo is None
        assert manager._storage_gateway is None
        assert manager._dataset_factory is None

    def test_close_idempotent(self, manager):
        """close() can be called multiple times safely."""
        manager.close()
        manager.close()  # should not raise


class TestOodcpManagerIntegration:
    """Verify OodcpManager wires layers correctly."""

    def test_factory_creates_entity_with_repo(self, manager):
        """dataset_factory creates entities wired to datarepo."""
        ds = manager.dataset_factory.create(name="test")
        assert ds._repo is manager.datarepo

    def test_round_trip_via_manager(self, manager):
        """Create dataset via factory, persist, retrieve."""
        ds = manager.dataset_factory.create(
            name="test-dataset", description="A test"
        )
        manager.datarepo.add_dataset(ds)

        retrieved = manager.datarepo.get_dataset_by_name("test-dataset")
        assert retrieved is not None
        assert retrieved.name == "test-dataset"
        assert retrieved.description == "A test"
