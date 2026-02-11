"""Tests for DVCStorageAdapter with mocked DVC internals."""

import os
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from dvc.oodcp.data.adapters.dvc_storage_adapter import DVCStorageAdapter


@pytest.fixture
def mock_dvc_repo():
    """Mock DVC Repo with cloud and cache attributes.

    Returns:
        MagicMock with:
        - repo.cloud.push() returning TransferResult
        - repo.cloud.pull() returning TransferResult
        - repo.cloud.status() returning CompareStatusResult
        - repo.cloud.get_remote_odb() returning mock ODB
        - repo.cloud.transfer() returning TransferResult
        - repo.cache.local as mock ODB
    """
    repo = MagicMock()
    # Push returns TransferResult with transferred items
    repo.cloud.push.return_value = MagicMock(
        transferred={MagicMock()}, failed=set()
    )
    # Pull returns TransferResult
    repo.cloud.pull.return_value = MagicMock(
        transferred={MagicMock()}, failed=set()
    )
    # Status returns CompareStatusResult
    repo.cloud.status.return_value = MagicMock(
        ok={MagicMock()}, missing=set(), new=set(), deleted=set()
    )
    # Transfer returns TransferResult
    repo.cloud.transfer.return_value = MagicMock(
        transferred={MagicMock()}, failed=set()
    )
    # Remote ODB
    repo.cloud.get_remote_odb.return_value = MagicMock()
    # Cache
    repo.cache.local = MagicMock()
    repo.cache.local.oid_to_path.return_value = "/cache/ab/c123"
    return repo


@pytest.fixture
def adapter(mock_dvc_repo):
    """DVCStorageAdapter wrapping a mock repo."""
    return DVCStorageAdapter(mock_dvc_repo)


_ADAPTER_MOD = "dvc.oodcp.data.adapters.dvc_storage_adapter"


class TestDVCStorageAdapterPush:
    """Verify push() delegates to DVC build + DataCloud.push()."""

    @patch(f"{_ADAPTER_MOD}.cache_transfer")
    @patch(f"{_ADAPTER_MOD}.build")
    def test_push_calls_build(
        self, mock_build, mock_transfer, adapter, mock_dvc_repo
    ):
        """push() calls build() to compute hash."""
        mock_obj = MagicMock()
        mock_obj.hash_info.name = "md5"
        mock_obj.hash_info.value = "abc123"
        mock_build.return_value = (MagicMock(), MagicMock(), mock_obj)

        adapter.push("/local/data", "s3://bucket/path")
        assert mock_build.called

    @patch(f"{_ADAPTER_MOD}.cache_transfer")
    @patch(f"{_ADAPTER_MOD}.build")
    def test_push_calls_cloud_push(
        self, mock_build, mock_transfer, adapter, mock_dvc_repo
    ):
        """push() calls DataCloud.push() with hash info."""
        mock_obj = MagicMock()
        mock_obj.hash_info.name = "md5"
        mock_obj.hash_info.value = "abc123"
        mock_build.return_value = (MagicMock(), MagicMock(), mock_obj)

        adapter.push("/local/data", "s3://bucket/path")
        assert mock_dvc_repo.cloud.push.called

    @patch(f"{_ADAPTER_MOD}.cache_transfer")
    @patch(f"{_ADAPTER_MOD}.build")
    def test_push_returns_hash_tuple(
        self, mock_build, mock_transfer, adapter
    ):
        """push() returns (hash_value, algorithm) tuple."""
        mock_obj = MagicMock()
        mock_obj.hash_info.name = "md5"
        mock_obj.hash_info.value = "abc123"
        mock_build.return_value = (MagicMock(), MagicMock(), mock_obj)

        dvc_hash, algo = adapter.push("/local/data", "s3://bucket/path")
        assert dvc_hash == "abc123"
        assert algo == "md5"

    @patch(f"{_ADAPTER_MOD}.cache_transfer")
    @patch(f"{_ADAPTER_MOD}.build")
    def test_push_with_remote_name(
        self, mock_build, mock_transfer, adapter, mock_dvc_repo
    ):
        """push() passes remote_name to DataCloud.push()."""
        mock_obj = MagicMock()
        mock_obj.hash_info.name = "md5"
        mock_obj.hash_info.value = "abc123"
        mock_build.return_value = (MagicMock(), MagicMock(), mock_obj)

        adapter.push("/local/data", "s3://bucket", remote_name="myremote")
        call_kwargs = mock_dvc_repo.cloud.push.call_args
        assert call_kwargs[1]["remote"] == "myremote"


class TestDVCStorageAdapterPull:
    """Verify pull() delegates to DataCloud.pull()."""

    @patch(f"{_ADAPTER_MOD}.localfs")
    def test_pull_calls_cloud_pull(self, mock_localfs, adapter, mock_dvc_repo):
        """pull() invokes DataCloud.pull() with HashInfo."""
        adapter.pull("abc123", "md5", "/tmp/dest")
        assert mock_dvc_repo.cloud.pull.called
        # Verify HashInfo was passed
        call_args = mock_dvc_repo.cloud.pull.call_args
        hash_infos = call_args[0][0]
        assert len(hash_infos) == 1

    @patch(f"{_ADAPTER_MOD}.localfs")
    def test_pull_returns_dest_path(self, mock_localfs, adapter):
        """pull() returns absolute destination path."""
        result = adapter.pull("abc123", "md5", "/tmp/dest/data.csv")
        assert result == "/tmp/dest/data.csv"

    @patch(f"{_ADAPTER_MOD}.localfs")
    def test_pull_with_remote(self, mock_localfs, adapter, mock_dvc_repo):
        """pull() passes remote_name to DataCloud.pull()."""
        adapter.pull("abc123", "md5", "/tmp/dest", remote_name="r1")
        call_kwargs = mock_dvc_repo.cloud.pull.call_args
        assert call_kwargs[1]["remote"] == "r1"


class TestDVCStorageAdapterVerify:
    """Verify verify() delegates to DataCloud.status()."""

    def test_verify_calls_status(self, adapter, mock_dvc_repo):
        """verify() invokes DataCloud.status()."""
        result = adapter.verify("abc123", "md5")
        assert mock_dvc_repo.cloud.status.called
        assert result is True

    def test_verify_returns_false_when_missing(self, adapter, mock_dvc_repo):
        """verify() returns False when object is missing."""
        mock_dvc_repo.cloud.status.return_value = MagicMock(
            ok=set(), missing={MagicMock()}
        )
        result = adapter.verify("abc123", "md5")
        assert result is False

    def test_verify_returns_false_when_empty_ok(self, adapter, mock_dvc_repo):
        """verify() returns False when ok set is empty."""
        mock_dvc_repo.cloud.status.return_value = MagicMock(
            ok=set(), missing=set()
        )
        result = adapter.verify("abc123", "md5")
        assert result is False

    def test_verify_with_remote(self, adapter, mock_dvc_repo):
        """verify() passes remote_name to DataCloud.status()."""
        adapter.verify("abc123", "md5", remote_name="r1")
        call_kwargs = mock_dvc_repo.cloud.status.call_args
        assert call_kwargs[1]["remote"] == "r1"


class TestDVCStorageAdapterTransfer:
    """Verify transfer() between remotes."""

    def test_transfer_gets_odbs(self, adapter, mock_dvc_repo):
        """transfer() gets ODBs for both remotes."""
        adapter.transfer("abc123", "md5", "remote1", "remote2")
        assert mock_dvc_repo.cloud.get_remote_odb.call_count == 2

    def test_transfer_calls_cloud_transfer(self, adapter, mock_dvc_repo):
        """transfer() calls DataCloud.transfer()."""
        adapter.transfer("abc123", "md5", "remote1", "remote2")
        assert mock_dvc_repo.cloud.transfer.called

    def test_transfer_returns_true_on_success(self, adapter, mock_dvc_repo):
        """transfer() returns True when no failures."""
        result = adapter.transfer("abc123", "md5", "remote1", "remote2")
        assert result is True

    def test_transfer_returns_false_on_failure(self, adapter, mock_dvc_repo):
        """transfer() returns False when failures exist."""
        mock_dvc_repo.cloud.transfer.return_value = MagicMock(
            failed={MagicMock()}
        )
        result = adapter.transfer("abc123", "md5", "remote1", "remote2")
        assert result is False
