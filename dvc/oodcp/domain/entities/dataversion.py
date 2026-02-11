from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from dvc.oodcp.domain.enums import StorageType, VersionStatus
from dvc.oodcp.domain.value_objects import DVCHash

if TYPE_CHECKING:
    from dvc.oodcp.infrastructure.gateways.storage_gateway import (
        StorageGateway,
    )


@dataclass
class DataVersion(ABC):
    """Abstract base for versioned data snapshots.

    Represents an immutable snapshot of data at a specific point in
    time. Concrete subclasses (S3DataVersion, GCSDataVersion, etc.)
    handle storage-type-specific details.

    Attributes:
        uuid: Unique identifier (UUID v4 string).
        datafile_uuid: Foreign key to parent DataFile.
        version_number: Sequential integer (>= 1).
        dvc_hash: Content-addressed hash value.
        hash_algorithm: Hash algorithm name (e.g., "md5").
        storage_uri: Physical address of the data.
        status: Lifecycle status (DRAFT, COMMITTED, DELETED).
        source_version_uuid: Lineage pointer to source version.
        transformer: Process that created this version.
        metadata: File-specific metrics (row count, size, etc.).
        created_at: When this version was created.
        updated_at: When this version was last modified.
        _storage_gateway: Injected gateway for data operations.
    """

    uuid: str = field(default_factory=lambda: str(uuid4()))
    datafile_uuid: str = ""
    version_number: int = 0
    dvc_hash: str = ""
    hash_algorithm: str = "md5"
    storage_uri: str = ""
    status: VersionStatus = VersionStatus.DRAFT
    source_version_uuid: Optional[str] = None
    transformer: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    _storage_gateway: Optional["StorageGateway"] = field(
        default=None, repr=False, compare=False
    )

    @property
    @abstractmethod
    def storage_type(self) -> StorageType:
        """Return the storage backend type for this version."""

    @property
    def hash_info(self) -> DVCHash:
        """Convert to DVCHash value object."""
        return DVCHash(value=self.dvc_hash, algorithm=self.hash_algorithm)

    def getdata(self, dest_path: str) -> str:
        """Lazy-load: pull data from storage to local path.

        Args:
            dest_path: Local destination path.

        Returns:
            Absolute path to the retrieved data.

        Raises:
            StorageError: If pull operation fails.
            DataNotFoundError: If data doesn't exist on remote.
        """
        return self._storage_gateway.pull(
            self.dvc_hash,
            self.hash_algorithm,
            dest_path,
        )

    def savedata(self, source_path: str) -> None:
        """Push local data to remote storage and commit.

        Hashes the data, pushes to remote, updates dvc_hash and
        storage_uri, and sets status to COMMITTED.

        Args:
            source_path: Absolute path to local data.

        Raises:
            StorageError: If push operation fails.
        """
        dvc_hash, algorithm = self._storage_gateway.push(
            source_path, self.storage_uri
        )
        self.dvc_hash = dvc_hash
        self.hash_algorithm = algorithm
        self.status = VersionStatus.COMMITTED
        self.updated_at = datetime.now(timezone.utc)

    def verify(self) -> bool:
        """Check data integrity against stored hash.

        Returns:
            True if remote data matches dvc_hash.

        Raises:
            StorageError: If verification operation fails.
        """
        return self._storage_gateway.verify(
            self.dvc_hash, self.hash_algorithm
        )


@dataclass
class S3DataVersion(DataVersion):
    """DataVersion stored on Amazon S3."""

    @property
    def storage_type(self) -> StorageType:
        return StorageType.S3


@dataclass
class GCSDataVersion(DataVersion):
    """DataVersion stored on Google Cloud Storage."""

    @property
    def storage_type(self) -> StorageType:
        return StorageType.GCS


@dataclass
class AzureDataVersion(DataVersion):
    """DataVersion stored on Azure Blob Storage."""

    @property
    def storage_type(self) -> StorageType:
        return StorageType.AZURE


@dataclass
class LocalDataVersion(DataVersion):
    """DataVersion stored on local filesystem."""

    @property
    def storage_type(self) -> StorageType:
        return StorageType.LOCAL
