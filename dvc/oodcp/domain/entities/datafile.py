from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from dvc.oodcp.domain.enums import EntityStatus, VersionStatus
from dvc.oodcp.domain.exceptions import EntityNotFoundError

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.datarepo import DataRepo
    from dvc.oodcp.domain.entities.dataversion import DataVersion
    from dvc.oodcp.infrastructure.gateways.storage_gateway import (
        StorageGateway,
    )


@dataclass
class DataFile:
    """Logical abstraction of physical data with one or more versions.

    Represents a specific named data entity within a DataSet
    (e.g., CIFAR-10DEVTRAIN). Each DataFile may have multiple
    DataVersion snapshots.

    Attributes:
        uuid: Unique identifier (UUID v4 string).
        dataset_uuid: Foreign key to parent DataSet.
        name: Logical filename (unique within parent DataSet).
        description: Summary of the file's purpose or contents.
        owner: Identity of the user responsible.
        status: Lifecycle status (ACTIVE or DELETED).
        created_at: When this file identity was first established.
        updated_at: When this file was last modified.
        _repo: Injected DataRepo for persistence operations.
    """

    uuid: str = field(default_factory=lambda: str(uuid4()))
    dataset_uuid: str = ""
    name: str = ""
    description: str = ""
    owner: str = ""
    status: EntityStatus = EntityStatus.ACTIVE
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    _repo: Optional["DataRepo"] = field(
        default=None, repr=False, compare=False
    )

    def getversion(
        self,
        version_number: Optional[int] = None,
        uuid: Optional[str] = None,
    ) -> "DataVersion":
        """Retrieve a specific DataVersion by number or UUID.

        Args:
            version_number: Sequential version number.
            uuid: DataVersion UUID.

        Returns:
            The matching DataVersion entity.

        Raises:
            EntityNotFoundError: If no matching version exists.
            ValueError: If neither version_number nor uuid is provided.
        """
        if version_number is None and uuid is None:
            raise ValueError("Either version_number or uuid must be provided")

        if uuid:
            result = self._repo.get_dataversion(uuid)
        else:
            versions = self._repo.list_dataversions(
                self.uuid, include_deleted=True
            )
            result = next(
                (v for v in versions if v.version_number == version_number),
                None,
            )

        if result is None:
            identifier = uuid or str(version_number)
            raise EntityNotFoundError("DataVersion", identifier)
        return result

    def getlatestversion(self) -> "DataVersion":
        """Return the highest-numbered COMMITTED DataVersion.

        Returns:
            DataVersion with the highest version_number in COMMITTED status.

        Raises:
            EntityNotFoundError: If no COMMITTED version exists.
        """
        result = self._repo.get_latest_dataversion(self.uuid)
        if result is None:
            raise EntityNotFoundError("DataVersion", f"latest for {self.uuid}")
        return result

    def addversion(
        self,
        storage_gateway: "StorageGateway",
        source_path: Optional[str] = None,
        dvc_hash: Optional[str] = None,
        hash_algorithm: str = "md5",
        storage_uri: str = "",
        storage_type: str = "LOCAL",
        source_version_uuid: Optional[str] = None,
        transformer: str = "",
        metadata: Optional[dict] = None,
    ) -> "DataVersion":
        """Create and persist a new DataVersion.

        Auto-increments version_number. If source_path is provided,
        hashes and pushes data via storage_gateway. If dvc_hash is
        provided, uses the pre-computed hash (no push).

        Args:
            storage_gateway: Injected StorageGateway for push.
            source_path: Local path to data (triggers hash+push).
            dvc_hash: Pre-computed hash (skips push).
            hash_algorithm: Hash algorithm name.
            storage_uri: Target storage URI.
            storage_type: Storage backend type string.
            source_version_uuid: Optional lineage pointer.
            transformer: Description of transformation process.
            metadata: File-specific metrics (row count, size, etc.).

        Returns:
            Newly created DataVersion.

        Raises:
            ValueError: If neither source_path nor dvc_hash is provided.
        """
        from dvc.oodcp.domain.entities.dataversion import (
            AzureDataVersion,
            GCSDataVersion,
            LocalDataVersion,
            S3DataVersion,
        )
        from dvc.oodcp.domain.enums import StorageType

        if source_path is None and dvc_hash is None:
            raise ValueError("Either source_path or dvc_hash must be provided")

        version_number = self._repo.get_next_version_number(self.uuid)

        cls_map = {
            StorageType.S3: S3DataVersion,
            StorageType.GCS: GCSDataVersion,
            StorageType.AZURE: AzureDataVersion,
            StorageType.LOCAL: LocalDataVersion,
        }
        st = StorageType(storage_type) if isinstance(storage_type, str) else storage_type
        version_cls = cls_map.get(st, LocalDataVersion)

        version = version_cls(
            datafile_uuid=self.uuid,
            version_number=version_number,
            dvc_hash=dvc_hash or "",
            hash_algorithm=hash_algorithm,
            storage_uri=storage_uri,
            source_version_uuid=source_version_uuid,
            transformer=transformer,
            metadata=metadata or {},
            _storage_gateway=storage_gateway,
        )

        if source_path is not None:
            version.savedata(source_path)
        elif dvc_hash:
            version.status = VersionStatus.COMMITTED
            version.updated_at = datetime.now(timezone.utc)

        self._repo.add_dataversion(version)
        return version

    def listversions(
        self, include_deleted: bool = False
    ) -> list["DataVersion"]:
        """Return all DataVersions for this file.

        Args:
            include_deleted: If True, include DELETED versions.

        Returns:
            List of DataVersion entities ordered by version_number.
        """
        return self._repo.list_dataversions(self.uuid, include_deleted)

    def delversion(self, version_number: int) -> None:
        """Soft-delete a DataVersion by version number.

        Sets the version's status to DELETED.

        Args:
            version_number: Version to delete.

        Raises:
            EntityNotFoundError: If no version with this number exists.
        """
        v = self.getversion(version_number=version_number)
        v.status = VersionStatus.DELETED
        v.updated_at = datetime.now(timezone.utc)
        self._repo.update_dataversion(v)

    def delallversions(self) -> None:
        """Soft-delete all DataVersions for this file."""
        for v in self.listversions():
            v.status = VersionStatus.DELETED
            v.updated_at = datetime.now(timezone.utc)
            self._repo.update_dataversion(v)

    def candelete(self) -> bool:
        """Check whether this DataFile can be deleted.

        Returns:
            True if all child DataVersions are DELETED or none exist.
        """
        versions = self.listversions(include_deleted=True)
        return all(v.status == VersionStatus.DELETED for v in versions)
