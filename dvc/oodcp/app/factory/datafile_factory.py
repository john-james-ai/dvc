"""Factory for creating DataFile entities with injected dependencies.

Ensures every DataFile is created with a proper DataRepo reference
so its methods (addversion, getversion, etc.) are functional.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.datafile import DataFile
    from dvc.oodcp.domain.entities.datarepo import DataRepo


class DataFileFactory:
    """Factory for creating DataFile entities with injected DataRepo.

    Attributes:
        _repo: DataRepo instance injected into every created DataFile.
    """

    def __init__(self, repo: "DataRepo") -> None:
        """Initialize with a DataRepo.

        Args:
            repo: DataRepo for persistence operations.
        """
        self._repo = repo

    def create(
        self,
        dataset_uuid: str,
        name: str,
        description: str = "",
        owner: str = "",
    ) -> "DataFile":
        """Create a new DataFile with injected DataRepo.

        Args:
            dataset_uuid: Parent DataSet UUID.
            name: Logical filename.
            description: Optional file description.
            owner: Optional owner identity.

        Returns:
            New DataFile entity wired with DataRepo.
        """
        from dvc.oodcp.domain.entities.datafile import DataFile

        return DataFile(
            dataset_uuid=dataset_uuid,
            name=name,
            description=description,
            owner=owner,
            _repo=self._repo,
        )
