"""Factory for creating DataSet entities with injected dependencies.

Ensures every DataSet is created with a proper DataRepo reference
so its methods (addfile, getfile, etc.) are functional.
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.datarepo import DataRepo
    from dvc.oodcp.domain.entities.dataset import DataSet


class DataSetFactory:
    """Factory for creating DataSet entities with injected DataRepo.

    Attributes:
        _repo: DataRepo instance injected into every created DataSet.
    """

    def __init__(self, repo: "DataRepo") -> None:
        """Initialize with a DataRepo.

        Args:
            repo: DataRepo for persistence operations.
        """
        self._repo = repo

    def create(
        self,
        name: str,
        description: str = "",
        project: str = "",
        owner: str = "",
        shared_metadata: Optional[dict] = None,
    ) -> "DataSet":
        """Create a new DataSet with injected DataRepo.

        Args:
            name: Human-readable dataset name.
            description: Optional dataset description.
            project: Optional project identity.
            owner: Optional owner identity.
            shared_metadata: Optional key-value pairs.

        Returns:
            New DataSet entity wired with DataRepo.
        """
        from dvc.oodcp.domain.entities.dataset import DataSet

        return DataSet(
            name=name,
            description=description,
            project=project,
            owner=owner,
            shared_metadata=shared_metadata or {},
            _repo=self._repo,
        )
