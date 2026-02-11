"""Facade for OOD-CP operations.

Entry point registered on Repo as `repo.oodcp`. Wires together
all layers: creates DataRepoSQLite, DVCStorageAdapter, factories,
and domain services. Provides lazy-initialized properties.
"""

import os
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from dvc.oodcp.app.factory.datafile_factory import DataFileFactory
    from dvc.oodcp.app.factory.dataset_factory import DataSetFactory
    from dvc.oodcp.app.factory.dataversion_factory import (
        DataVersionFactory,
    )
    from dvc.oodcp.data.adapters.dvc_storage_adapter import (
        DVCStorageAdapter,
    )
    from dvc.oodcp.data.datarepo_sqlite import DataRepoSQLite
    from dvc.oodcp.domain.services.integrity_service import (
        IntegrityService,
    )
    from dvc.oodcp.domain.services.lineage_service import LineageService
    from dvc.repo import Repo


class OodcpManager:
    """Facade for OOD-CP operations.

    Entry point registered on Repo as `repo.oodcp`. Wires together
    all layers: creates gateways, repositories, factories, and
    domain services. All properties are lazy-initialized.

    Attributes:
        _repo: DVC Repo instance.
    """

    def __init__(self, repo: "Repo") -> None:
        """Initialize with DVC Repo.

        Args:
            repo: Initialized DVC Repo instance.
        """
        self._repo = repo
        self._datarepo: Optional["DataRepoSQLite"] = None
        self._storage_gateway: Optional["DVCStorageAdapter"] = None
        self._dataset_factory: Optional["DataSetFactory"] = None
        self._datafile_factory: Optional["DataFileFactory"] = None
        self._dataversion_factory: Optional["DataVersionFactory"] = None
        self._lineage_service: Optional["LineageService"] = None
        self._integrity_service: Optional["IntegrityService"] = None

    def _get_db_path(self) -> str:
        """Resolve the metadata database path.

        Uses .dvc/tmp/oodcp/metadata.db by default.
        Falls back to :memory: if no tmp_dir is available.

        Returns:
            Path to SQLite database file.
        """
        tmp_dir = self._repo.tmp_dir
        if tmp_dir is None:
            return ":memory:"
        oodcp_dir = os.path.join(tmp_dir, "oodcp")
        os.makedirs(oodcp_dir, exist_ok=True)
        return os.path.join(oodcp_dir, "metadata.db")

    @property
    def datarepo(self) -> "DataRepoSQLite":
        """Lazy-initialize DataRepoSQLite.

        Returns:
            DataRepoSQLite connected to metadata database.
        """
        if self._datarepo is None:
            from dvc.oodcp.data.datarepo_sqlite import DataRepoSQLite

            self._datarepo = DataRepoSQLite(self._get_db_path())
        return self._datarepo

    @property
    def storage_gateway(self) -> "DVCStorageAdapter":
        """Lazy-initialize DVCStorageAdapter.

        Returns:
            DVCStorageAdapter wrapping DVC DataCloud.
        """
        if self._storage_gateway is None:
            from dvc.oodcp.data.adapters.dvc_storage_adapter import (
                DVCStorageAdapter,
            )

            self._storage_gateway = DVCStorageAdapter(self._repo)
        return self._storage_gateway

    @property
    def dataset_factory(self) -> "DataSetFactory":
        """Lazy-initialize DataSetFactory.

        Returns:
            DataSetFactory with injected DataRepo.
        """
        if self._dataset_factory is None:
            from dvc.oodcp.app.factory.dataset_factory import (
                DataSetFactory,
            )

            self._dataset_factory = DataSetFactory(self.datarepo)
        return self._dataset_factory

    @property
    def datafile_factory(self) -> "DataFileFactory":
        """Lazy-initialize DataFileFactory.

        Returns:
            DataFileFactory with injected DataRepo.
        """
        if self._datafile_factory is None:
            from dvc.oodcp.app.factory.datafile_factory import (
                DataFileFactory,
            )

            self._datafile_factory = DataFileFactory(self.datarepo)
        return self._datafile_factory

    @property
    def dataversion_factory(self) -> "DataVersionFactory":
        """Lazy-initialize DataVersionFactory.

        Returns:
            DataVersionFactory with injected StorageGateway.
        """
        if self._dataversion_factory is None:
            from dvc.oodcp.app.factory.dataversion_factory import (
                DataVersionFactory,
            )

            self._dataversion_factory = DataVersionFactory(
                self.storage_gateway
            )
        return self._dataversion_factory

    @property
    def lineage_service(self) -> "LineageService":
        """Lazy-initialize LineageService.

        Returns:
            LineageService with injected DataRepo.
        """
        if self._lineage_service is None:
            from dvc.oodcp.domain.services.lineage_service import (
                LineageService,
            )

            self._lineage_service = LineageService(self.datarepo)
        return self._lineage_service

    @property
    def integrity_service(self) -> "IntegrityService":
        """Lazy-initialize IntegrityService.

        Returns:
            IntegrityService with injected StorageGateway.
        """
        if self._integrity_service is None:
            from dvc.oodcp.domain.services.integrity_service import (
                IntegrityService,
            )

            self._integrity_service = IntegrityService(
                self.storage_gateway
            )
        return self._integrity_service

    def close(self) -> None:
        """Release all held resources."""
        if self._datarepo is not None:
            self._datarepo.close()
            self._datarepo = None
        self._storage_gateway = None
        self._dataset_factory = None
        self._datafile_factory = None
        self._dataversion_factory = None
        self._lineage_service = None
        self._integrity_service = None
