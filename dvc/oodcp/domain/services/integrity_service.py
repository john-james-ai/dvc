"""Domain service for verifying data integrity.

Provides single and batch verification of DataVersion hashes
against remote storage via the injected StorageGateway.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.dataversion import DataVersion
    from dvc.oodcp.infrastructure.gateways.storage_gateway import (
        StorageGateway,
    )


class IntegrityService:
    """Domain service for verifying data integrity.

    Attributes:
        _storage_gateway: Injected StorageGateway for verification.
    """

    def __init__(self, storage_gateway: "StorageGateway") -> None:
        """Initialize with a StorageGateway.

        Args:
            storage_gateway: Gateway for remote verification calls.
        """
        self._storage_gateway = storage_gateway

    def verify_version(self, version: "DataVersion") -> bool:
        """Verify a single DataVersion's integrity.

        Args:
            version: DataVersion to verify.

        Returns:
            True if hash matches remote data.
        """
        if not version.dvc_hash:
            return False
        return self._storage_gateway.verify(
            version.dvc_hash, version.hash_algorithm
        )

    def verify_batch(
        self, versions: list["DataVersion"]
    ) -> dict[str, bool]:
        """Verify multiple DataVersions.

        Args:
            versions: List of DataVersions to verify.

        Returns:
            Dict mapping version UUID to verification result.
        """
        results = {}
        for version in versions:
            results[version.uuid] = self.verify_version(version)
        return results
