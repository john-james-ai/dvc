"""Stub StorageGateway implementation for LakeFS.

LakeFS provides an S3-compatible API, so the primary integration path
is via DVC's existing S3 remote support (``dvc remote add lakefs
s3://repo/branch --endpointurl http://lakefs:8000``).

This stub adapter is reserved for future LakeFS-specific features
such as branch management, commit semantics, and merge operations
that go beyond simple S3 compatibility.
"""

from typing import Optional


class LakeFSStorageAdapter:
    """Stub StorageGateway for LakeFS (Phase 3+ placeholder).

    All methods raise NotImplementedError.  The recommended
    integration path for LakeFS is via DVC's S3-compatible remote
    support rather than this adapter.

    Attributes:
        _endpoint: LakeFS server endpoint URL.
        _access_key_id: LakeFS access key.
        _secret_access_key: LakeFS secret key.
        _repository: LakeFS repository name.
    """

    def __init__(
        self,
        endpoint: str,
        access_key_id: str,
        secret_access_key: str,
        repository: str,
    ) -> None:
        self._endpoint = endpoint
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._repository = repository

    def push(
        self,
        source_path: str,
        storage_uri: str,
        remote_name: Optional[str] = None,
        jobs: Optional[int] = None,
    ) -> tuple[str, str]:
        raise NotImplementedError("LakeFS adapter not yet implemented")

    def pull(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        dest_path: str,
        remote_name: Optional[str] = None,
        jobs: Optional[int] = None,
    ) -> str:
        raise NotImplementedError("LakeFS adapter not yet implemented")

    def verify(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        remote_name: Optional[str] = None,
    ) -> bool:
        raise NotImplementedError("LakeFS adapter not yet implemented")

    def transfer(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        source_remote: str,
        dest_remote: str,
        jobs: Optional[int] = None,
    ) -> bool:
        raise NotImplementedError("LakeFS adapter not yet implemented")
