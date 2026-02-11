"""Domain service for data lineage and provenance queries.

Traverses source_version_uuid chains to build lineage graphs
and provenance reports. Delegates to DataRepo.query_lineage()
for the actual traversal.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.datarepo import DataRepo
    from dvc.oodcp.domain.entities.dataversion import DataVersion


class LineageService:
    """Domain service for data lineage and provenance queries.

    Attributes:
        _repo: Injected DataRepo for version retrieval and lineage.
    """

    def __init__(self, repo: "DataRepo") -> None:
        """Initialize with a DataRepo.

        Args:
            repo: DataRepo providing lineage query capability.
        """
        self._repo = repo

    def get_lineage(
        self, version_uuid: str, max_depth: int = 100
    ) -> list["DataVersion"]:
        """Build lineage chain for a version.

        Traverses source_version_uuid pointers from the given version
        back through its ancestors.

        Args:
            version_uuid: Starting version UUID.
            max_depth: Maximum chain depth.

        Returns:
            Ordered list from given version to oldest ancestor.
        """
        return self._repo.query_lineage(version_uuid, max_depth)

    def get_descendants(
        self, version_uuid: str
    ) -> list["DataVersion"]:
        """Find all versions derived from the given version.

        Scans all versions to find those citing this version as
        source_version_uuid. This is a reverse lineage query.

        Args:
            version_uuid: Ancestor version UUID.

        Returns:
            List of DataVersion entities that cite this version as source.
        """
        version = self._repo.get_dataversion(version_uuid)
        if version is None:
            return []

        # Get all versions for the same datafile
        all_versions = self._repo.list_dataversions(
            version.datafile_uuid, include_deleted=True
        )
        return [
            v for v in all_versions
            if v.source_version_uuid == version_uuid
        ]
