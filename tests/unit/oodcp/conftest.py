"""Shared fixtures for OOD-CP unit tests."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from dvc.oodcp.data.datarepo_sqlite import DataRepoSQLite
from dvc.oodcp.domain.entities.datafile import DataFile
from dvc.oodcp.domain.entities.dataset import DataSet
from dvc.oodcp.domain.entities.dataversion import (
    LocalDataVersion,
    S3DataVersion,
)
from dvc.oodcp.domain.enums import EntityStatus, VersionStatus

FIXED_TIME = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


# ── DataRepo Fixtures ─────────────────────────────────────────


@pytest.fixture
def repo():
    """In-memory DataRepoSQLite for isolated tests.

    Yields:
        DataRepoSQLite connected to ':memory:' database.
        Automatically closed after test.
    """
    r = DataRepoSQLite(":memory:")
    yield r
    r.close()


# ── Mock Fixtures ─────────────────────────────────────────────


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
def mock_repo():
    """Mock DataRepo for pure unit testing without SQLite.

    Returns:
        MagicMock conforming to DataRepo protocol.
    """
    return MagicMock()


# ── Sample Entity Fixtures ────────────────────────────────────


@pytest.fixture
def sample_dataset(repo):
    """A pre-built DataSet entity with injected repo.

    Returns:
        DataSet with name='test-dataset', wired with repo.
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
        _repo=repo,
    )


@pytest.fixture
def sample_datafile(repo):
    """A pre-built DataFile entity with injected repo.

    Returns:
        DataFile with name='train.csv', wired with repo.
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
        _repo=repo,
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
