"""Tests for LakeFSStorageAdapter stub."""

import pytest

from dvc.oodcp.data.adapters.lakefs_adapter import LakeFSStorageAdapter


@pytest.fixture
def adapter():
    """LakeFSStorageAdapter with sample connection params."""
    return LakeFSStorageAdapter(
        endpoint="https://lakefs.example.com",
        access_key_id="AKID",
        secret_access_key="SECRET",
        repository="my-repo",
    )


class TestLakeFSStorageAdapterInit:
    """Verify constructor stores connection parameters."""

    def test_stores_endpoint(self, adapter):
        assert adapter._endpoint == "https://lakefs.example.com"

    def test_stores_access_key(self, adapter):
        assert adapter._access_key_id == "AKID"

    def test_stores_secret_key(self, adapter):
        assert adapter._secret_access_key == "SECRET"

    def test_stores_repository(self, adapter):
        assert adapter._repository == "my-repo"


class TestLakeFSStorageAdapterStubs:
    """Verify all methods raise NotImplementedError."""

    def test_push_raises(self, adapter):
        with pytest.raises(NotImplementedError, match="LakeFS"):
            adapter.push("/local/path", "s3://bucket/path")

    def test_pull_raises(self, adapter):
        with pytest.raises(NotImplementedError, match="LakeFS"):
            adapter.pull("abc123", "md5", "/tmp/dest")

    def test_verify_raises(self, adapter):
        with pytest.raises(NotImplementedError, match="LakeFS"):
            adapter.verify("abc123", "md5")

    def test_transfer_raises(self, adapter):
        with pytest.raises(NotImplementedError, match="LakeFS"):
            adapter.transfer("abc123", "md5", "remote1", "remote2")

    def test_push_with_optional_args_raises(self, adapter):
        with pytest.raises(NotImplementedError):
            adapter.push("/path", "uri", remote_name="r", jobs=4)

    def test_pull_with_optional_args_raises(self, adapter):
        with pytest.raises(NotImplementedError):
            adapter.pull("hash", "md5", "/dest", remote_name="r", jobs=4)
