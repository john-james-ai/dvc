"""Tests for DataVersionFactory."""

import pytest
from unittest.mock import MagicMock

from dvc.oodcp.app.factory.dataversion_factory import DataVersionFactory
from dvc.oodcp.domain.entities.dataversion import (
    GCSDataVersion,
    LocalDataVersion,
    S3DataVersion,
)
from dvc.oodcp.domain.enums import StorageType, VersionStatus


class TestDataVersionFactoryCreate:
    """Verify DataVersionFactory.create() behavior."""

    def test_creates_s3_version(self, mock_storage_gateway):
        """create() with S3 type returns S3DataVersion."""
        factory = DataVersionFactory(mock_storage_gateway)
        v = factory.create(
            datafile_uuid="df-001",
            version_number=1,
            storage_type=StorageType.S3,
            dvc_hash="abc123",
        )
        assert isinstance(v, S3DataVersion)
        assert v.storage_type == StorageType.S3

    def test_creates_local_version(self, mock_storage_gateway):
        """create() with LOCAL type returns LocalDataVersion."""
        factory = DataVersionFactory(mock_storage_gateway)
        v = factory.create(
            datafile_uuid="df-001",
            version_number=1,
            storage_type=StorageType.LOCAL,
            dvc_hash="abc123",
        )
        assert isinstance(v, LocalDataVersion)

    def test_creates_gcs_version(self, mock_storage_gateway):
        """create() with GCS type returns GCSDataVersion."""
        factory = DataVersionFactory(mock_storage_gateway)
        v = factory.create(
            datafile_uuid="df-001",
            version_number=1,
            storage_type=StorageType.GCS,
            dvc_hash="abc123",
        )
        assert isinstance(v, GCSDataVersion)

    def test_with_dvc_hash_sets_committed(self, mock_storage_gateway):
        """create() with dvc_hash sets status to COMMITTED."""
        factory = DataVersionFactory(mock_storage_gateway)
        v = factory.create(
            datafile_uuid="df-001",
            version_number=1,
            storage_type=StorageType.S3,
            dvc_hash="precomputed",
        )
        assert v.dvc_hash == "precomputed"
        assert v.status == VersionStatus.COMMITTED

    def test_with_source_path_calls_savedata(self, mock_storage_gateway):
        """create() with source_path triggers immediate push."""
        factory = DataVersionFactory(mock_storage_gateway)
        v = factory.create(
            datafile_uuid="df-001",
            version_number=1,
            storage_type=StorageType.S3,
            source_path="/local/data.csv",
            storage_uri="s3://bucket/data",
        )
        mock_storage_gateway.push.assert_called_once()
        assert v.dvc_hash == "abc123hash"
        assert v.status == VersionStatus.COMMITTED

    def test_no_hash_or_path_raises(self, mock_storage_gateway):
        """create() without source_path or dvc_hash raises ValueError."""
        factory = DataVersionFactory(mock_storage_gateway)
        with pytest.raises(ValueError, match="source_path or dvc_hash"):
            factory.create(
                datafile_uuid="df-001",
                version_number=1,
                storage_type=StorageType.S3,
            )

    def test_metadata_passed_through(self, mock_storage_gateway):
        """create() passes metadata to version."""
        factory = DataVersionFactory(mock_storage_gateway)
        v = factory.create(
            datafile_uuid="df-001",
            version_number=1,
            storage_type=StorageType.LOCAL,
            dvc_hash="abc",
            metadata={"rows": 100},
        )
        assert v.metadata == {"rows": 100}

    def test_lineage_pointer(self, mock_storage_gateway):
        """create() sets source_version_uuid."""
        factory = DataVersionFactory(mock_storage_gateway)
        v = factory.create(
            datafile_uuid="df-001",
            version_number=2,
            storage_type=StorageType.S3,
            dvc_hash="abc",
            source_version_uuid="ver-001",
        )
        assert v.source_version_uuid == "ver-001"

    def test_default_storage_type_is_local(self, mock_storage_gateway):
        """create() defaults to LOCAL storage type."""
        factory = DataVersionFactory(mock_storage_gateway)
        v = factory.create(
            datafile_uuid="df-001",
            version_number=1,
            dvc_hash="abc",
        )
        assert isinstance(v, LocalDataVersion)
        assert v.storage_type == StorageType.LOCAL
