from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from dvc.oodcp.domain.enums import EntityStatus
from dvc.oodcp.domain.exceptions import (
    DuplicateNameError,
    EntityNotFoundError,
)

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.datafile import DataFile
    from dvc.oodcp.domain.entities.datarepo import DataRepo


@dataclass
class DataSet:
    """A logical grouping of related data entities.

    Provides the domain context and shared metadata for a collection
    of DataFiles (e.g., CIFAR-10). Does not carry a version itself;
    acts as a namespace and registry for DataFile objects.

    Attributes:
        uuid: Unique identifier (UUID v4 string).
        name: Human-readable name (e.g., "Object-Detection-Alpha").
        description: Summary of the dataset's purpose or contents.
        project: Identity of the project team responsible.
        owner: Identity of the user responsible for the collection.
        status: Lifecycle status (ACTIVE or DELETED).
        created_at: When this dataset was first created.
        updated_at: When this dataset was last modified.
        shared_metadata: Key-value pairs applying to all files
                         (e.g., License, Data Source).
        _repo: Injected DataRepo for persistence operations.
    """

    uuid: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    project: str = ""
    owner: str = ""
    status: EntityStatus = EntityStatus.ACTIVE
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    shared_metadata: dict = field(default_factory=dict)

    _repo: Optional["DataRepo"] = field(
        default=None, repr=False, compare=False
    )

    def addfile(
        self,
        name: str,
        description: str = "",
        owner: str = "",
    ) -> "DataFile":
        """Register a new DataFile within this dataset.

        Creates a DataFile linked to this DataSet's UUID and persists
        it via the injected DataRepo.

        Args:
            name: Logical filename (must be unique within this dataset).
            description: Optional summary of the file's purpose.
            owner: Optional owner identity.

        Returns:
            Newly created DataFile entity.

        Raises:
            DuplicateNameError: If name already exists in this dataset.
        """
        from dvc.oodcp.domain.entities.datafile import DataFile

        existing = self._repo.get_datafile_by_name(self.uuid, name)
        if existing is not None:
            raise DuplicateNameError("DataFile", name)

        df = DataFile(
            dataset_uuid=self.uuid,
            name=name,
            description=description,
            owner=owner or self.owner,
            _repo=self._repo,
        )
        self._repo.add_datafile(df)
        return df

    def getfile(
        self, name: Optional[str] = None, uuid: Optional[str] = None
    ) -> "DataFile":
        """Retrieve a DataFile by name or UUID.

        Args:
            name: Logical filename to look up.
            uuid: DataFile UUID to look up.

        Returns:
            The matching DataFile entity.

        Raises:
            EntityNotFoundError: If no matching DataFile exists.
            ValueError: If neither name nor uuid is provided.
        """
        if name is None and uuid is None:
            raise ValueError("Either name or uuid must be provided")

        if uuid:
            result = self._repo.get_datafile(uuid)
        else:
            result = self._repo.get_datafile_by_name(self.uuid, name)

        if result is None:
            identifier = uuid or name
            raise EntityNotFoundError("DataFile", identifier)
        return result

    def listfiles(self, include_deleted: bool = False) -> list["DataFile"]:
        """Return all DataFiles in this dataset.

        Args:
            include_deleted: If True, include DELETED files.

        Returns:
            List of DataFile entities.
        """
        return self._repo.list_datafiles(self.uuid, include_deleted)

    def delfile(self, name: str) -> None:
        """Soft-delete a DataFile by name.

        Sets the DataFile's status to DELETED. Does not remove data.

        Args:
            name: Logical filename to delete.

        Raises:
            EntityNotFoundError: If no file with this name exists.
        """
        df = self.getfile(name=name)
        df.status = EntityStatus.DELETED
        df.updated_at = datetime.now(timezone.utc)
        self._repo.update_datafile(df)

    def delallfiles(self) -> None:
        """Soft-delete all DataFiles in this dataset."""
        for df in self.listfiles():
            df.status = EntityStatus.DELETED
            df.updated_at = datetime.now(timezone.utc)
            self._repo.update_datafile(df)

    def candelete(self) -> bool:
        """Check whether this DataSet can be deleted.

        Returns:
            True if all child DataFiles are already DELETED or
            if there are no child DataFiles.
        """
        files = self.listfiles(include_deleted=True)
        return all(f.status == EntityStatus.DELETED for f in files)
