"""OodcpDependency for using OOD-CP versions as pipeline dependencies.

Enables ``oodcp://dataset_name/file_name@v3`` URIs in ``dvc.yaml``
dependency lists.  Detects the ``oodcp://`` scheme, parses dataset,
file, and optional version pin, and delegates hash comparison to the
OOD-CP metadata database.
"""

from typing import TYPE_CHECKING, Any, ClassVar, Optional
from urllib.parse import urlparse

from funcy import compact

from dvc_data.hashfile.hash_info import HashInfo

from dvc.dependency.db import AbstractDependency

if TYPE_CHECKING:
    from dvc.stage import Stage


class OodcpDependency(AbstractDependency):
    """Pipeline dependency backed by an OOD-CP DataVersion.

    Parses ``oodcp://dataset/file@v3`` URIs and tracks the
    corresponding DataVersion hash as the dependency hash.

    Attributes:
        dataset_name: Parsed dataset name from URI.
        file_name: Parsed file name from URI.
        pinned_version: Optional pinned version number.
    """

    PARAM_OODCP = "oodcp"
    OODCP_SCHEMA: ClassVar[dict] = {PARAM_OODCP: dict}

    def __init__(
        self, stage: "Stage", p: str, info: dict[str, Any], *args, **kwargs
    ):
        super().__init__(stage, info, *args, **kwargs)
        self.def_path = p
        self.dataset_name, self.file_name, self.pinned_version = (
            self._parse_uri(p)
        )
        oodcp_info = info.get(self.PARAM_OODCP) or {}
        self.hash_info = HashInfo(self.PARAM_OODCP, oodcp_info)
        self.hash_name = self.PARAM_OODCP

    @staticmethod
    def _parse_uri(uri: str) -> tuple[str, str, Optional[int]]:
        """Parse ``oodcp://dataset/file@v3`` into components.

        Args:
            uri: Full oodcp URI string.

        Returns:
            Tuple of (dataset_name, file_name, pinned_version).
            pinned_version is None when no ``@vN`` suffix is present.
        """
        parsed = urlparse(uri)
        dataset_name = parsed.netloc
        path = parsed.path.lstrip("/")

        pinned_version: Optional[int] = None
        if "@v" in path:
            path, version_str = path.rsplit("@v", 1)
            pinned_version = int(version_str)

        return dataset_name, path, pinned_version

    @classmethod
    def is_oodcp(cls, p: str) -> bool:
        """Check whether a path string is an oodcp:// URI.

        Args:
            p: Dependency path string.

        Returns:
            True if the scheme is ``oodcp``.
        """
        return urlparse(p).scheme == "oodcp"

    def __repr__(self):
        return f"{self.__class__.__name__}({self.def_path!r})"

    def __str__(self):
        return self.def_path

    @property
    def protocol(self):
        return None

    def _resolve_version(self):
        """Resolve the target DataVersion from the OOD-CP database.

        Returns:
            DataVersion entity, or None if not found.
        """
        oodcp = self.repo.oodcp
        ds = oodcp.datarepo.get_dataset_by_name(self.dataset_name)
        if ds is None:
            return None

        df = oodcp.datarepo.get_datafile_by_name(
            ds.uuid, self.file_name
        )
        if df is None:
            return None

        if self.pinned_version is not None:
            versions = oodcp.datarepo.list_dataversions(df.uuid)
            for v in versions:
                if v.version_number == self.pinned_version:
                    return v
            return None

        return oodcp.datarepo.get_latest_dataversion(df.uuid)

    def _get_current_hash(self) -> Optional[str]:
        """Get the current DVC hash from the OOD-CP database.

        Returns:
            Hash string, or None if the version cannot be resolved.
        """
        version = self._resolve_version()
        if version is None:
            return None
        return version.dvc_hash

    def workspace_status(self) -> dict[str, str]:
        """Compare stored hash with current OOD-CP version hash.

        Returns:
            Empty dict if unchanged, or ``{str(self): status}``
            where status is "new", "modified", or "deleted".
        """
        current_hash = self._get_current_hash()
        stored = self.hash_info.value if self.hash_info else {}
        stored_hash = stored.get("dvc_hash") if isinstance(stored, dict) else None

        if current_hash is None:
            if stored_hash:
                return {str(self): "deleted"}
            return {str(self): "new"}

        if stored_hash is None:
            return {str(self): "new"}

        if current_hash != stored_hash:
            return {str(self): "modified"}

        return {}

    def status(self):
        return self.workspace_status()

    def get_hash(self):
        """Compute hash info from the current OOD-CP version.

        Returns:
            HashInfo with oodcp info dict containing version metadata.
        """
        version = self._resolve_version()
        if version is None:
            return HashInfo(self.PARAM_OODCP, {})

        info = {
            "dvc_hash": version.dvc_hash,
            "hash_algorithm": version.hash_algorithm,
            "version_number": version.version_number,
            "dataset": self.dataset_name,
            "file": self.file_name,
        }
        return HashInfo(self.PARAM_OODCP, info)

    def save(self):
        self.hash_info = self.get_hash()

    def dumpd(self, **kwargs):
        return compact(
            {self.PARAM_PATH: self.def_path, **self.hash_info.to_dict()}
        )

    def download(self, to, jobs=None):
        """Download the versioned data to an output path.

        Args:
            to: Output to download to.
            jobs: Number of parallel jobs.
        """
        version = self._resolve_version()
        if version is None:
            from dvc.exceptions import DvcException

            raise DvcException(
                f"OOD-CP version not found: {self.def_path}"
            )
        version.getdata(to.fs_path)

    def update(self, rev=None):
        """Re-resolve the version and update hash info."""
        self.save()
