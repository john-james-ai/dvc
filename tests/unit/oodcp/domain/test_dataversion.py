"""Tests for DataVersion domain entity and subclasses."""

import pytest

from dvc.oodcp.domain.entities.dataversion import (
    AzureDataVersion,
    DataVersion,
    GCSDataVersion,
    LocalDataVersion,
    S3DataVersion,
)
from dvc.oodcp.domain.enums import StorageType, VersionStatus
from dvc.oodcp.domain.value_objects import DVCHash


class TestDataVersionABC:
    """Verify DataVersion cannot be instantiated directly."""

    def test_cannot_instantiate_abc(self):
        """DataVersion is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
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
        version = cls(datafile_uuid="df-001", version_number=1)
        assert version.storage_type == expected_type

    def test_default_status_is_draft(self):
        """New DataVersion defaults to DRAFT status."""
        v = LocalDataVersion(datafile_uuid="df-001", version_number=1)
        assert v.status == VersionStatus.DRAFT

    def test_uuid_auto_generated(self):
        """DataVersion generates UUID if not provided."""
        v = LocalDataVersion(datafile_uuid="df-001", version_number=1)
        assert v.uuid  # non-empty
        assert len(v.uuid) == 36  # UUID format


class TestDataVersionHashInfo:
    """Verify hash_info property conversion."""

    def test_hash_info_returns_dvchash(self, sample_s3_version):
        """hash_info returns DVCHash value object."""
        hi = sample_s3_version.hash_info
        assert isinstance(hi, DVCHash)
        assert hi.value == "abc123hash"
        assert hi.algorithm == "md5"

    def test_hash_info_empty(self):
        """hash_info with empty hash returns falsy DVCHash."""
        v = LocalDataVersion(datafile_uuid="df-001", version_number=1)
        hi = v.hash_info
        assert not bool(hi)


class TestDataVersionSaveData:
    """Verify savedata() behavior with mock gateway."""

    def test_savedata_calls_push(self, sample_local_version):
        """savedata() delegates to storage_gateway.push()."""
        sample_local_version.savedata("/local/source/data.csv")
        sample_local_version._storage_gateway.push.assert_called_once_with(
            "/local/source/data.csv", "/local/path/data"
        )

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

    def test_savedata_updates_timestamp(self, sample_local_version):
        """savedata() updates updated_at timestamp."""
        old_time = sample_local_version.updated_at
        sample_local_version.savedata("/local/source/data.csv")
        assert sample_local_version.updated_at >= old_time


class TestDataVersionGetData:
    """Verify getdata() behavior with mock gateway."""

    def test_getdata_calls_pull(self, sample_s3_version):
        """getdata() delegates to storage_gateway.pull()."""
        result = sample_s3_version.getdata("/tmp/dest")
        sample_s3_version._storage_gateway.pull.assert_called_once_with(
            "abc123hash", "md5", "/tmp/dest"
        )
        assert result == "/tmp/pulled/data"


class TestDataVersionVerify:
    """Verify verify() behavior with mock gateway."""

    def test_verify_delegates_to_gateway(self, sample_s3_version):
        """verify() calls storage_gateway.verify()."""
        result = sample_s3_version.verify()
        sample_s3_version._storage_gateway.verify.assert_called_once_with(
            "abc123hash", "md5"
        )
        assert result is True

    def test_verify_returns_false_on_mismatch(self, sample_s3_version):
        """verify() returns False when gateway reports mismatch."""
        sample_s3_version._storage_gateway.verify.return_value = False
        assert sample_s3_version.verify() is False
