"""Concrete StorageGateway implementation wrapping DVC DataCloud.

Delegates push/pull/verify/transfer operations to DVC's DataCloud
and CacheManager. Bridges OOD-CP's hash/URI model with DVC's
HashInfo-based object storage.

This is the only class that imports from dvc.data_cloud and
dvc.cachemgr, keeping all DVC-specific knowledge in the Data Layer.
"""

import os
from typing import TYPE_CHECKING, Optional

from dvc_data.hashfile.build import build
from dvc_data.hashfile.hash import DEFAULT_ALGORITHM
from dvc_data.hashfile.hash_info import HashInfo
from dvc_data.hashfile.transfer import transfer as cache_transfer

from dvc.fs import localfs

if TYPE_CHECKING:
    from dvc.repo import Repo


class DVCStorageAdapter:
    """Concrete StorageGateway wrapping DVC DataCloud.

    Attributes:
        _repo: Reference to the DVC Repo instance.
    """

    def __init__(self, repo: "Repo") -> None:
        """Initialize with a DVC Repo instance.

        Args:
            repo: Initialized DVC Repo providing cloud and cache access.
        """
        self._repo = repo

    def push(
        self,
        source_path: str,
        storage_uri: str,
        remote_name: Optional[str] = None,
        jobs: Optional[int] = None,
    ) -> tuple[str, str]:
        """Push local data to remote via DVC.

        Builds a content hash using dvc_data.hashfile.build, stages
        to local cache, then pushes to remote via DataCloud.push().

        Args:
            source_path: Absolute path to local file or directory.
            storage_uri: Target URI (currently informational).
            remote_name: DVC remote name override.
            jobs: Parallel transfer jobs.

        Returns:
            Tuple of (dvc_hash, hash_algorithm).
        """
        odb = self._repo.cache.local
        hash_name = DEFAULT_ALGORITHM

        _, meta, obj = build(odb, source_path, localfs, hash_name)
        hash_info = obj.hash_info

        # Stage to local cache
        cache_transfer(None, odb, [hash_info], shallow=False, hardlink=False)

        # Push to remote
        self._repo.cloud.push(
            [hash_info], jobs=jobs, remote=remote_name
        )

        return hash_info.value, hash_info.name

    def pull(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        dest_path: str,
        remote_name: Optional[str] = None,
        jobs: Optional[int] = None,
    ) -> str:
        """Pull data from remote via DVC.

        Converts (dvc_hash, hash_algorithm) to HashInfo, pulls from
        remote to local cache via DataCloud.pull(), then checks out
        to dest_path.

        Args:
            dvc_hash: Content hash value.
            hash_algorithm: Hash algorithm name.
            dest_path: Local destination path.
            remote_name: DVC remote name override.
            jobs: Parallel transfer jobs.

        Returns:
            Absolute path to retrieved data.
        """
        hash_info = HashInfo(hash_algorithm, dvc_hash)

        # Pull from remote to local cache
        self._repo.cloud.pull(
            [hash_info], jobs=jobs, remote=remote_name
        )

        # Checkout from cache to dest_path
        odb = self._repo.cache.local
        cache_path = odb.oid_to_path(dvc_hash)
        dest_path = os.path.abspath(dest_path)

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        localfs.copy(cache_path, dest_path)

        return dest_path

    def verify(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        remote_name: Optional[str] = None,
    ) -> bool:
        """Verify data integrity on remote via DVC.

        Converts to HashInfo and calls DataCloud.status() to check
        whether the object exists on the remote.

        Args:
            dvc_hash: Content hash value.
            hash_algorithm: Hash algorithm name.
            remote_name: DVC remote name override.

        Returns:
            True if data exists and is intact.
        """
        hash_info = HashInfo(hash_algorithm, dvc_hash)
        status = self._repo.cloud.status(
            [hash_info], remote=remote_name
        )
        return len(status.ok) > 0 and len(status.missing) == 0

    def transfer(
        self,
        dvc_hash: str,
        hash_algorithm: str,
        source_remote: str,
        dest_remote: str,
        jobs: Optional[int] = None,
    ) -> bool:
        """Transfer data between two remote storage locations.

        Gets ODB instances for both remotes and calls
        DataCloud.transfer().

        Args:
            dvc_hash: Content hash value.
            hash_algorithm: Hash algorithm name.
            source_remote: Source remote name.
            dest_remote: Destination remote name.
            jobs: Parallel transfer jobs.

        Returns:
            True if transfer succeeded.
        """
        hash_info = HashInfo(hash_algorithm, dvc_hash)
        src_odb = self._repo.cloud.get_remote_odb(
            source_remote, "transfer"
        )
        dest_odb = self._repo.cloud.get_remote_odb(
            dest_remote, "transfer"
        )
        result = self._repo.cloud.transfer(
            src_odb, dest_odb, [hash_info], jobs=jobs
        )
        return len(result.failed) == 0
