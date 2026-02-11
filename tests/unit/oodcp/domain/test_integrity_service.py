"""Tests for IntegrityService domain service."""

import pytest
from unittest.mock import MagicMock

from dvc.oodcp.domain.entities.dataversion import (
    LocalDataVersion,
    S3DataVersion,
)
from dvc.oodcp.domain.enums import VersionStatus
from dvc.oodcp.domain.services.integrity_service import IntegrityService


@pytest.fixture
def mock_gateway():
    """Mock StorageGateway for integrity verification."""
    mock = MagicMock()
    mock.verify.return_value = True
    return mock


@pytest.fixture
def service(mock_gateway):
    """IntegrityService with mock gateway."""
    return IntegrityService(mock_gateway)


@pytest.fixture
def committed_version():
    """A COMMITTED version with hash."""
    return S3DataVersion(
        uuid="ver-001",
        datafile_uuid="df-001",
        version_number=1,
        dvc_hash="abc123",
        hash_algorithm="md5",
        status=VersionStatus.COMMITTED,
    )


@pytest.fixture
def empty_hash_version():
    """A DRAFT version with no hash."""
    return LocalDataVersion(
        uuid="ver-002",
        datafile_uuid="df-001",
        version_number=1,
        dvc_hash="",
        status=VersionStatus.DRAFT,
    )


class TestVerifyVersion:
    """Verify single version verification."""

    def test_verify_returns_true(self, service, committed_version):
        """verify_version() returns True when gateway confirms."""
        assert service.verify_version(committed_version) is True

    def test_verify_calls_gateway(
        self, service, committed_version, mock_gateway
    ):
        """verify_version() delegates to gateway.verify()."""
        service.verify_version(committed_version)
        mock_gateway.verify.assert_called_once_with("abc123", "md5")

    def test_verify_returns_false_on_mismatch(
        self, service, committed_version, mock_gateway
    ):
        """verify_version() returns False when gateway says no."""
        mock_gateway.verify.return_value = False
        assert service.verify_version(committed_version) is False

    def test_verify_empty_hash_returns_false(
        self, service, empty_hash_version
    ):
        """verify_version() returns False for empty hash."""
        assert service.verify_version(empty_hash_version) is False


class TestVerifyBatch:
    """Verify batch verification."""

    def test_batch_returns_all_results(self, service, committed_version):
        """verify_batch() returns dict with result for each version."""
        v2 = S3DataVersion(
            uuid="ver-002",
            datafile_uuid="df-001",
            version_number=2,
            dvc_hash="def456",
            status=VersionStatus.COMMITTED,
        )
        results = service.verify_batch([committed_version, v2])
        assert len(results) == 2
        assert results["ver-001"] is True
        assert results["ver-002"] is True

    def test_batch_mixed_results(
        self, service, committed_version, empty_hash_version
    ):
        """verify_batch() handles mixed pass/fail."""
        results = service.verify_batch(
            [committed_version, empty_hash_version]
        )
        assert results["ver-001"] is True
        assert results["ver-002"] is False

    def test_batch_empty_list(self, service):
        """verify_batch() with empty list returns empty dict."""
        results = service.verify_batch([])
        assert results == {}
