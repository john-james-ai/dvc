"""Non-invasive experiment-to-version metadata mapper.

Maps DVC experiment refs to OOD-CP DataVersion metadata entries
without modifying DVC's experiment system.  Stores experiment
information in DataVersion.metadata for later querying.
"""

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from dvc.oodcp.domain.entities.datarepo import DataRepo
    from dvc.oodcp.domain.entities.dataversion import DataVersion
    from dvc.repo import Repo


class ExperimentVersionMapper:
    """Maps DVC experiments to OOD-CP DataVersions via metadata tagging.

    Non-invasive: reads experiment information from Git refs and
    the DVC experiment cache, then stores mappings as entries in
    DataVersion.metadata.  Does not modify any DVC experiment code.

    Attributes:
        _repo: DVC Repo for experiment queries.
        _datarepo: OOD-CP DataRepo for version persistence.
    """

    METADATA_KEY_EXP_REF = "experiment_ref"
    METADATA_KEY_EXP_NAME = "experiment_name"
    METADATA_KEY_EXP_BASELINE = "experiment_baseline"
    METADATA_KEY_EXP_REV = "experiment_rev"

    def __init__(self, repo: "Repo", datarepo: "DataRepo") -> None:
        """Initialize with DVC Repo and OOD-CP DataRepo.

        Args:
            repo: Initialized DVC Repo for experiment queries.
            datarepo: OOD-CP DataRepo for version persistence.
        """
        self._repo = repo
        self._datarepo = datarepo

    def tag_version(
        self,
        version: "DataVersion",
        experiment_name: str,
        experiment_rev: Optional[str] = None,
        experiment_ref: Optional[str] = None,
        experiment_baseline: Optional[str] = None,
    ) -> None:
        """Tag a DataVersion with experiment metadata.

        Stores experiment information in the version's metadata dict
        and persists the change via DataRepo.

        Args:
            version: DataVersion to tag.
            experiment_name: Human-readable experiment name.
            experiment_rev: Git commit SHA of the experiment.
            experiment_ref: Full Git ref (e.g., refs/exps/XX/.../name).
            experiment_baseline: Baseline commit SHA.
        """
        version.metadata[self.METADATA_KEY_EXP_NAME] = experiment_name
        if experiment_rev:
            version.metadata[self.METADATA_KEY_EXP_REV] = experiment_rev
        if experiment_ref:
            version.metadata[self.METADATA_KEY_EXP_REF] = experiment_ref
        if experiment_baseline:
            version.metadata[self.METADATA_KEY_EXP_BASELINE] = (
                experiment_baseline
            )
        self._datarepo.update_dataversion(version)

    def get_versions_for_experiment(
        self, experiment_name: str
    ) -> list["DataVersion"]:
        """Find all DataVersions tagged with a given experiment name.

        Scans all datasets, files, and versions in the DataRepo to
        find versions whose metadata contains the experiment name.

        Args:
            experiment_name: The experiment name to search for.

        Returns:
            List of DataVersion entities tagged with this experiment.
        """
        results: list["DataVersion"] = []
        for ds in self._datarepo.list_datasets():
            for df in self._datarepo.list_datafiles(ds.uuid):
                for ver in self._datarepo.list_dataversions(
                    df.uuid, include_deleted=True
                ):
                    if (
                        ver.metadata.get(self.METADATA_KEY_EXP_NAME)
                        == experiment_name
                    ):
                        results.append(ver)
        return results

    def get_experiment_info(
        self, version: "DataVersion"
    ) -> Optional[dict[str, Any]]:
        """Extract experiment metadata from a DataVersion.

        Args:
            version: DataVersion to inspect.

        Returns:
            Dict with experiment fields, or None if not tagged.
        """
        name = version.metadata.get(self.METADATA_KEY_EXP_NAME)
        if name is None:
            return None

        return {
            "name": name,
            "rev": version.metadata.get(self.METADATA_KEY_EXP_REV),
            "ref": version.metadata.get(self.METADATA_KEY_EXP_REF),
            "baseline": version.metadata.get(
                self.METADATA_KEY_EXP_BASELINE
            ),
        }

    def list_experiment_names(self) -> list[str]:
        """List all unique experiment names tagged on DataVersions.

        Returns:
            Sorted list of unique experiment name strings.
        """
        names: set[str] = set()
        for ds in self._datarepo.list_datasets():
            for df in self._datarepo.list_datafiles(ds.uuid):
                for ver in self._datarepo.list_dataversions(
                    df.uuid, include_deleted=True
                ):
                    name = ver.metadata.get(self.METADATA_KEY_EXP_NAME)
                    if name:
                        names.add(name)
        return sorted(names)
