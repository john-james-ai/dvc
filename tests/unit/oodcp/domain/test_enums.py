"""Tests for OOD-CP domain enums."""

import pytest

from dvc.oodcp.domain.enums import EntityStatus, StorageType, VersionStatus


class TestEntityStatus:
    """Verify EntityStatus enum values and string behavior."""

    def test_active_value(self):
        """EntityStatus.ACTIVE has string value 'ACTIVE'."""
        assert EntityStatus.ACTIVE == "ACTIVE"
        assert EntityStatus.ACTIVE.value == "ACTIVE"

    def test_deleted_value(self):
        """EntityStatus.DELETED has string value 'DELETED'."""
        assert EntityStatus.DELETED == "DELETED"

    def test_from_string(self):
        """EntityStatus can be constructed from string."""
        assert EntityStatus("ACTIVE") is EntityStatus.ACTIVE

    def test_invalid_raises(self):
        """Invalid string raises ValueError."""
        with pytest.raises(ValueError):
            EntityStatus("INVALID")


class TestVersionStatus:
    """Verify VersionStatus enum values."""

    def test_draft_value(self):
        assert VersionStatus.DRAFT == "DRAFT"

    def test_committed_value(self):
        assert VersionStatus.COMMITTED == "COMMITTED"

    def test_deleted_value(self):
        assert VersionStatus.DELETED == "DELETED"

    def test_from_string(self):
        assert VersionStatus("COMMITTED") is VersionStatus.COMMITTED


class TestStorageType:
    """Verify StorageType enum values."""

    @pytest.mark.parametrize(
        "member, expected",
        [
            (StorageType.S3, "S3"),
            (StorageType.GCS, "GCS"),
            (StorageType.AZURE, "AZURE"),
            (StorageType.LOCAL, "LOCAL"),
        ],
    )
    def test_values(self, member, expected):
        """Each StorageType member has correct string value."""
        assert member.value == expected

    def test_from_string(self):
        assert StorageType("S3") is StorageType.S3
