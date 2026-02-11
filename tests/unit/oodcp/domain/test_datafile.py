"""Tests for DataFile domain entity."""

import pytest
from unittest.mock import MagicMock

from dvc.oodcp.domain.entities.datafile import DataFile
from dvc.oodcp.domain.entities.dataset import DataSet
from dvc.oodcp.domain.entities.dataversion import LocalDataVersion
from dvc.oodcp.domain.enums import EntityStatus, VersionStatus
from dvc.oodcp.domain.exceptions import EntityNotFoundError


class TestDataFileCreation:
    """Verify DataFile instantiation and defaults."""

    def test_create_with_defaults(self):
        """DataFile creates with UUID, ACTIVE status."""
        df = DataFile(name="train.csv", dataset_uuid="ds-001")
        assert df.uuid
        assert df.name == "train.csv"
        assert df.status == EntityStatus.ACTIVE

    def test_create_with_all_fields(self):
        """DataFile accepts all constructor arguments."""
        df = DataFile(
            uuid="custom-uuid",
            dataset_uuid="ds-001",
            name="train.csv",
            description="Training data",
            owner="owner",
        )
        assert df.uuid == "custom-uuid"
        assert df.description == "Training data"


class TestDataFileGetVersion:
    """Verify DataFile.getversion() behavior."""

    def test_getversion_by_number(self, sample_dataset, repo, mock_storage_gateway):
        """getversion(version_number=) retrieves correct version."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        df.addversion(
            storage_gateway=mock_storage_gateway,
            dvc_hash="hash1",
        )
        v = df.getversion(version_number=1)
        assert v.version_number == 1
        assert v.dvc_hash == "hash1"

    def test_getversion_by_uuid(self, sample_dataset, repo, mock_storage_gateway):
        """getversion(uuid=) retrieves correct version."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        created = df.addversion(
            storage_gateway=mock_storage_gateway,
            dvc_hash="hash1",
        )
        v = df.getversion(uuid=created.uuid)
        assert v.uuid == created.uuid

    def test_getversion_not_found_raises(self, sample_dataset, repo):
        """getversion() raises EntityNotFoundError for missing version."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        with pytest.raises(EntityNotFoundError):
            df.getversion(version_number=999)

    def test_getversion_no_args_raises(self, sample_datafile):
        """getversion() with no args raises ValueError."""
        with pytest.raises(ValueError):
            sample_datafile.getversion()


class TestDataFileGetLatestVersion:
    """Verify DataFile.getlatestversion() behavior."""

    def test_getlatestversion_returns_highest(
        self, sample_dataset, repo, mock_storage_gateway
    ):
        """getlatestversion() returns highest COMMITTED version."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        df.addversion(
            storage_gateway=mock_storage_gateway,
            dvc_hash="hash1",
        )
        df.addversion(
            storage_gateway=mock_storage_gateway,
            dvc_hash="hash2",
        )
        latest = df.getlatestversion()
        assert latest.version_number == 2
        assert latest.dvc_hash == "hash2"

    def test_getlatestversion_no_versions_raises(
        self, sample_dataset, repo
    ):
        """getlatestversion() raises EntityNotFoundError when no versions."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        with pytest.raises(EntityNotFoundError):
            df.getlatestversion()


class TestDataFileAddVersion:
    """Verify DataFile.addversion() behavior."""

    def test_addversion_with_hash(
        self, sample_dataset, repo, mock_storage_gateway
    ):
        """addversion() with dvc_hash creates COMMITTED version."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        v = df.addversion(
            storage_gateway=mock_storage_gateway,
            dvc_hash="precomputed_hash",
            hash_algorithm="sha256",
        )
        assert v.dvc_hash == "precomputed_hash"
        assert v.hash_algorithm == "sha256"
        assert v.status == VersionStatus.COMMITTED
        assert v.version_number == 1

    def test_addversion_with_source_path(
        self, sample_dataset, repo, mock_storage_gateway
    ):
        """addversion() with source_path pushes data and commits."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        v = df.addversion(
            storage_gateway=mock_storage_gateway,
            source_path="/local/data.csv",
            storage_uri="s3://bucket/data",
        )
        mock_storage_gateway.push.assert_called_once()
        assert v.status == VersionStatus.COMMITTED
        assert v.dvc_hash == "abc123hash"

    def test_addversion_auto_increments(
        self, sample_dataset, repo, mock_storage_gateway
    ):
        """addversion() auto-increments version_number."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        v1 = df.addversion(
            storage_gateway=mock_storage_gateway,
            dvc_hash="hash1",
        )
        v2 = df.addversion(
            storage_gateway=mock_storage_gateway,
            dvc_hash="hash2",
        )
        assert v1.version_number == 1
        assert v2.version_number == 2

    def test_addversion_no_args_raises(
        self, sample_dataset, repo, mock_storage_gateway
    ):
        """addversion() without source_path or dvc_hash raises ValueError."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        with pytest.raises(ValueError):
            df.addversion(storage_gateway=mock_storage_gateway)

    def test_addversion_with_lineage(
        self, sample_dataset, repo, mock_storage_gateway
    ):
        """addversion() sets source_version_uuid for lineage."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        v1 = df.addversion(
            storage_gateway=mock_storage_gateway,
            dvc_hash="hash1",
        )
        v2 = df.addversion(
            storage_gateway=mock_storage_gateway,
            dvc_hash="hash2",
            source_version_uuid=v1.uuid,
        )
        assert v2.source_version_uuid == v1.uuid

    def test_addversion_with_metadata(
        self, sample_dataset, repo, mock_storage_gateway
    ):
        """addversion() stores metadata dict."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        v = df.addversion(
            storage_gateway=mock_storage_gateway,
            dvc_hash="hash1",
            metadata={"rows": 1000, "size": 2048},
        )
        assert v.metadata == {"rows": 1000, "size": 2048}


class TestDataFileListVersions:
    """Verify DataFile.listversions() behavior."""

    def test_listversions_returns_all(
        self, sample_dataset, repo, mock_storage_gateway
    ):
        """listversions() returns all non-deleted versions."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        df.addversion(
            storage_gateway=mock_storage_gateway, dvc_hash="h1"
        )
        df.addversion(
            storage_gateway=mock_storage_gateway, dvc_hash="h2"
        )
        versions = df.listversions()
        assert len(versions) == 2

    def test_listversions_excludes_deleted(
        self, sample_dataset, repo, mock_storage_gateway
    ):
        """listversions() excludes DELETED versions by default."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        df.addversion(
            storage_gateway=mock_storage_gateway, dvc_hash="h1"
        )
        df.addversion(
            storage_gateway=mock_storage_gateway, dvc_hash="h2"
        )
        df.delversion(2)
        versions = df.listversions()
        assert len(versions) == 1

    def test_listversions_includes_deleted(
        self, sample_dataset, repo, mock_storage_gateway
    ):
        """listversions(include_deleted=True) returns all."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        df.addversion(
            storage_gateway=mock_storage_gateway, dvc_hash="h1"
        )
        df.addversion(
            storage_gateway=mock_storage_gateway, dvc_hash="h2"
        )
        df.delversion(2)
        versions = df.listversions(include_deleted=True)
        assert len(versions) == 2


class TestDataFileDeleteVersions:
    """Verify DataFile version deletion behavior."""

    def test_delversion_sets_deleted(
        self, sample_dataset, repo, mock_storage_gateway
    ):
        """delversion() sets version status to DELETED."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        df.addversion(
            storage_gateway=mock_storage_gateway, dvc_hash="h1"
        )
        df.delversion(1)
        v = df.getversion(version_number=1)
        assert v.status == VersionStatus.DELETED

    def test_delallversions(
        self, sample_dataset, repo, mock_storage_gateway
    ):
        """delallversions() deletes all versions."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        df.addversion(
            storage_gateway=mock_storage_gateway, dvc_hash="h1"
        )
        df.addversion(
            storage_gateway=mock_storage_gateway, dvc_hash="h2"
        )
        df.delallversions()
        assert df.listversions() == []

    def test_candelete_true_when_all_deleted(
        self, sample_dataset, repo, mock_storage_gateway
    ):
        """candelete() returns True when all versions are DELETED."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        df.addversion(
            storage_gateway=mock_storage_gateway, dvc_hash="h1"
        )
        df.delversion(1)
        assert df.candelete() is True

    def test_candelete_true_when_no_versions(
        self, sample_dataset, repo
    ):
        """candelete() returns True when no versions exist."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        assert df.candelete() is True

    def test_candelete_false_when_active_versions(
        self, sample_dataset, repo, mock_storage_gateway
    ):
        """candelete() returns False when active versions exist."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        df.addversion(
            storage_gateway=mock_storage_gateway, dvc_hash="h1"
        )
        assert df.candelete() is False
