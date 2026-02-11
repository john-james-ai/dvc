from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class StorageGateway(Protocol):
    """Abstract gateway for data storage operations.

    Defines the contract for pushing, pulling, verifying, and
    transferring data between storage backends. Implementations
    wrap specific storage systems (DVC remotes, LakeFS, local).
    """

    def push(
        self,
        source_path: str,
        storage_uri: str,
        remote_name: Optional[str] = None,
        jobs: Optional[int] = None,
    ) -> tuple[str, str]:
        """Push local data to remote storage.

        Args:
            source_path: Absolute path to local file or directory.
            storage_uri: Target URI (e.g., "s3://bucket/path").
            remote_name: Named remote from DVC config.
            jobs: Number of parallel transfer jobs.

        Returns:
            Tuple of (dvc_hash, hash_algorithm).
        """
        ...

    def pull(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        dest_path: str,
        remote_name: Optional[str] = None,
        jobs: Optional[int] = None,
    ) -> str:
        """Pull data from remote storage to local path.

        Args:
            dvc_hash: Content-addressed hash of the data.
            hash_algorithm: Algorithm used for hashing.
            dest_path: Local destination path.
            remote_name: Named remote from DVC config.
            jobs: Number of parallel transfer jobs.

        Returns:
            Absolute path to the retrieved data.
        """
        ...

    def verify(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        remote_name: Optional[str] = None,
    ) -> bool:
        """Verify that data exists and is intact on remote storage.

        Args:
            dvc_hash: Content-addressed hash of the data.
            hash_algorithm: Algorithm used for hashing.
            remote_name: Named remote from DVC config.

        Returns:
            True if data exists and hash matches, False otherwise.
        """
        ...

    def transfer(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        source_remote: str,
        dest_remote: str,
        jobs: Optional[int] = None,
    ) -> bool:
        """Transfer data between two remote storage locations.

        Args:
            dvc_hash: Content-addressed hash of the data.
            hash_algorithm: Algorithm used for hashing.
            source_remote: Name of source remote.
            dest_remote: Name of destination remote.
            jobs: Number of parallel transfer jobs.

        Returns:
            True if transfer succeeded, False otherwise.
        """
        ...
