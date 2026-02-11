from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.datafile import DataFile
    from dvc.oodcp.domain.entities.dataset import DataSet
    from dvc.oodcp.domain.entities.dataversion import DataVersion


class DataRepo(ABC):
    """Abstract repository providing persistence semantics for OOD-CP entities.

    Defines the single repository interface for all DataSet, DataFile,
    and DataVersion operations: add, get, list, delete, and lineage
    queries. Concrete implementations in the Data Layer delegate I/O
    to DAL objects that execute SQL on the underlying database.

    There is ONE DataRepo abstract (Domain Layer) and ONE concrete
    implementation (Data Layer) in the architecture.
    """

    # ── DataSet operations ────────────────────────────────────

    @abstractmethod
    def add_dataset(self, dataset: "DataSet") -> None:
        """Persist a new DataSet.

        Args:
            dataset: DataSet entity to persist.

        Raises:
            DuplicateNameError: If a dataset with the same name exists.
        """

    @abstractmethod
    def get_dataset(self, uuid: str) -> Optional["DataSet"]:
        """Retrieve a DataSet by UUID.

        Args:
            uuid: DataSet unique identifier.

        Returns:
            DataSet entity with injected _repo reference, or None.
        """

    @abstractmethod
    def get_dataset_by_name(self, name: str) -> Optional["DataSet"]:
        """Retrieve a DataSet by human-readable name.

        Args:
            name: DataSet name.

        Returns:
            DataSet entity, or None if not found.
        """

    @abstractmethod
    def list_datasets(self, include_deleted: bool = False) -> list["DataSet"]:
        """List all DataSets.

        Args:
            include_deleted: If True, include DELETED datasets.

        Returns:
            List of DataSet entities.
        """

    @abstractmethod
    def update_dataset(self, dataset: "DataSet") -> None:
        """Update an existing DataSet record.

        Args:
            dataset: DataSet entity with updated fields.
        """

    # ── DataFile operations ───────────────────────────────────

    @abstractmethod
    def add_datafile(self, datafile: "DataFile") -> None:
        """Persist a new DataFile.

        Args:
            datafile: DataFile entity to persist.

        Raises:
            DuplicateNameError: If a file with the same name exists
                                in the same dataset.
        """

    @abstractmethod
    def get_datafile(self, uuid: str) -> Optional["DataFile"]:
        """Retrieve a DataFile by UUID.

        Args:
            uuid: DataFile unique identifier.

        Returns:
            DataFile entity with injected _repo reference, or None.
        """

    @abstractmethod
    def get_datafile_by_name(
        self, dataset_uuid: str, name: str
    ) -> Optional["DataFile"]:
        """Retrieve a DataFile by name within a dataset.

        Args:
            dataset_uuid: Parent dataset UUID.
            name: Logical filename.

        Returns:
            DataFile entity, or None if not found.
        """

    @abstractmethod
    def list_datafiles(
        self, dataset_uuid: str, include_deleted: bool = False
    ) -> list["DataFile"]:
        """List all DataFiles for a dataset.

        Args:
            dataset_uuid: Parent dataset UUID.
            include_deleted: If True, include DELETED files.

        Returns:
            List of DataFile entities.
        """

    @abstractmethod
    def update_datafile(self, datafile: "DataFile") -> None:
        """Update an existing DataFile record.

        Args:
            datafile: DataFile entity with updated fields.
        """

    # ── DataVersion operations ────────────────────────────────

    @abstractmethod
    def add_dataversion(self, version: "DataVersion") -> None:
        """Persist a new DataVersion.

        Args:
            version: DataVersion entity to persist.
        """

    @abstractmethod
    def get_dataversion(self, uuid: str) -> Optional["DataVersion"]:
        """Retrieve a DataVersion by UUID.

        Args:
            uuid: DataVersion unique identifier.

        Returns:
            Correct DataVersion subclass instance, or None.
        """

    @abstractmethod
    def get_latest_dataversion(
        self, datafile_uuid: str
    ) -> Optional["DataVersion"]:
        """Retrieve the highest-numbered COMMITTED version.

        Args:
            datafile_uuid: Parent datafile UUID.

        Returns:
            DataVersion with highest version_number in COMMITTED status,
            or None if no committed version exists.
        """

    @abstractmethod
    def list_dataversions(
        self, datafile_uuid: str, include_deleted: bool = False
    ) -> list["DataVersion"]:
        """List all DataVersions for a datafile.

        Args:
            datafile_uuid: Parent datafile UUID.
            include_deleted: If True, include DELETED versions.

        Returns:
            List of DataVersion entities ordered by version_number.
        """

    @abstractmethod
    def update_dataversion(self, version: "DataVersion") -> None:
        """Update an existing DataVersion record.

        Args:
            version: DataVersion entity with updated fields.
        """

    @abstractmethod
    def get_next_version_number(self, datafile_uuid: str) -> int:
        """Get the next available version number for a datafile.

        Args:
            datafile_uuid: Parent datafile UUID.

        Returns:
            Next sequential version number (starts at 1).
        """

    # ── Lineage ───────────────────────────────────────────────

    @abstractmethod
    def query_lineage(
        self, version_uuid: str, depth: int = 100
    ) -> list["DataVersion"]:
        """Traverse source_version_uuid pointers for provenance.

        Args:
            version_uuid: Starting DataVersion UUID.
            depth: Maximum traversal depth.

        Returns:
            List from the given version back through ancestors.
        """

    # ── Lifecycle ─────────────────────────────────────────────

    @abstractmethod
    def close(self) -> None:
        """Release any held resources (connections, file handles)."""
