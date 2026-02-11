"""Factory for creating DataVersion subclass instances.

Uses a registry mapping StorageType to concrete DataVersion class.
Supports two creation modes:
1. With source_path: hashes data immediately via StorageGateway.
2. With dvc_hash: uses a pre-known hash (no immediate I/O).
"""

from typing import TYPE_CHECKING, Optional

from dvc.oodcp.domain.entities.dataversion import (
    AzureDataVersion,
    GCSDataVersion,
    LocalDataVersion,
    S3DataVersion,
)
from dvc.oodcp.domain.enums import StorageType, VersionStatus

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.dataversion import DataVersion
    from dvc.oodcp.infrastructure.gateways.storage_gateway import (
        StorageGateway,
    )

_REGISTRY: dict[StorageType, type["DataVersion"]] = {
    StorageType.S3: S3DataVersion,
    StorageType.GCS: GCSDataVersion,
    StorageType.AZURE: AzureDataVersion,
    StorageType.LOCAL: LocalDataVersion,
}


class DataVersionFactory:
    """Factory for creating DataVersion subclass instances.

    Attributes:
        _storage_gateway: Injected gateway for push operations.
    """

    def __init__(self, storage_gateway: "StorageGateway") -> None:
        """Initialize with a StorageGateway.

        Args:
            storage_gateway: For push operations during creation.
        """
        self._storage_gateway = storage_gateway

    def create(
        self,
        datafile_uuid: str,
        version_number: int,
        storage_type: StorageType = StorageType.LOCAL,
        storage_uri: str = "",
        source_path: Optional[str] = None,
        dvc_hash: Optional[str] = None,
        hash_algorithm: str = "md5",
        source_version_uuid: Optional[str] = None,
        transformer: str = "",
        metadata: Optional[dict] = None,
    ) -> "DataVersion":
        """Create a DataVersion of the appropriate subclass.

        If source_path is provided and dvc_hash is not, data is hashed
        and pushed immediately. If dvc_hash is provided, the version is
        created with the pre-known hash (no push). Per design Q2: only
        recreate the hash if not provided one.

        Args:
            datafile_uuid: Parent DataFile UUID.
            version_number: Sequential version number.
            storage_type: Target storage backend.
            storage_uri: Physical storage address.
            source_path: Local data path (triggers push if no dvc_hash).
            dvc_hash: Pre-known hash (skips push).
            hash_algorithm: Hash algorithm name.
            source_version_uuid: Optional lineage pointer.
            transformer: Transformation description.
            metadata: File-specific metrics.

        Returns:
            Concrete DataVersion subclass instance.

        Raises:
            ValueError: If storage_type has no registered class.
            ValueError: If neither source_path nor dvc_hash provided.
        """
        if source_path is None and dvc_hash is None:
            raise ValueError(
                "Either source_path or dvc_hash must be provided"
            )

        cls = _REGISTRY.get(storage_type)
        if cls is None:
            raise ValueError(
                f"No registered DataVersion class for storage type: "
                f"{storage_type}"
            )

        version = cls(
            datafile_uuid=datafile_uuid,
            version_number=version_number,
            dvc_hash=dvc_hash or "",
            hash_algorithm=hash_algorithm,
            storage_uri=storage_uri,
            source_version_uuid=source_version_uuid,
            transformer=transformer,
            metadata=metadata or {},
            _storage_gateway=self._storage_gateway,
        )

        if dvc_hash:
            version.status = VersionStatus.COMMITTED
        elif source_path is not None:
            version.savedata(source_path)

        return version
