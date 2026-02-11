"""Tests for ExperimentVersionMapper metadata tagging."""

import pytest
from unittest.mock import MagicMock

from dvc.oodcp.integration.experiments import ExperimentVersionMapper


@pytest.fixture
def mock_repo():
    """Mock DVC Repo."""
    return MagicMock()


@pytest.fixture
def mock_datarepo():
    """Mock DataRepo with list/update operations."""
    return MagicMock()


@pytest.fixture
def mapper(mock_repo, mock_datarepo):
    """ExperimentVersionMapper with mocked dependencies."""
    return ExperimentVersionMapper(mock_repo, mock_datarepo)


@pytest.fixture
def mock_version():
    """A mock DataVersion with empty metadata."""
    v = MagicMock()
    v.metadata = {}
    v.uuid = "ver-001"
    v.dvc_hash = "abc123"
    return v


@pytest.fixture
def tagged_version():
    """A mock DataVersion already tagged with experiment metadata."""
    v = MagicMock()
    v.metadata = {
        "experiment_name": "exp-train-lr",
        "experiment_rev": "abc123sha",
        "experiment_ref": "refs/exps/ab/abc123sha/exp-train-lr",
        "experiment_baseline": "def456sha",
    }
    v.uuid = "ver-002"
    return v


class TestTagVersion:
    """Verify tag_version() stores metadata and persists."""

    def test_tags_experiment_name(self, mapper, mock_version, mock_datarepo):
        """tag_version() stores experiment_name in metadata."""
        mapper.tag_version(mock_version, experiment_name="my-exp")
        assert mock_version.metadata["experiment_name"] == "my-exp"
        mock_datarepo.update_dataversion.assert_called_once_with(
            mock_version
        )

    def test_tags_all_fields(self, mapper, mock_version):
        """tag_version() stores all optional fields when provided."""
        mapper.tag_version(
            mock_version,
            experiment_name="my-exp",
            experiment_rev="abc123",
            experiment_ref="refs/exps/xx/abc123/my-exp",
            experiment_baseline="def456",
        )
        assert mock_version.metadata["experiment_name"] == "my-exp"
        assert mock_version.metadata["experiment_rev"] == "abc123"
        assert mock_version.metadata["experiment_ref"] == (
            "refs/exps/xx/abc123/my-exp"
        )
        assert mock_version.metadata["experiment_baseline"] == "def456"

    def test_omits_none_fields(self, mapper, mock_version):
        """tag_version() does not store fields when None."""
        mapper.tag_version(mock_version, experiment_name="my-exp")
        assert "experiment_rev" not in mock_version.metadata
        assert "experiment_ref" not in mock_version.metadata
        assert "experiment_baseline" not in mock_version.metadata

    def test_persists_via_datarepo(self, mapper, mock_version, mock_datarepo):
        """tag_version() calls datarepo.update_dataversion()."""
        mapper.tag_version(mock_version, experiment_name="my-exp")
        mock_datarepo.update_dataversion.assert_called_once_with(
            mock_version
        )


class TestGetExperimentInfo:
    """Verify get_experiment_info() extracts metadata."""

    def test_returns_info_dict(self, mapper, tagged_version):
        """get_experiment_info() returns dict with experiment fields."""
        info = mapper.get_experiment_info(tagged_version)
        assert info is not None
        assert info["name"] == "exp-train-lr"
        assert info["rev"] == "abc123sha"
        assert info["ref"] == "refs/exps/ab/abc123sha/exp-train-lr"
        assert info["baseline"] == "def456sha"

    def test_returns_none_when_untagged(self, mapper, mock_version):
        """get_experiment_info() returns None for untagged version."""
        info = mapper.get_experiment_info(mock_version)
        assert info is None

    def test_partial_metadata(self, mapper):
        """get_experiment_info() handles partial metadata gracefully."""
        v = MagicMock()
        v.metadata = {"experiment_name": "partial-exp"}
        info = mapper.get_experiment_info(v)
        assert info["name"] == "partial-exp"
        assert info["rev"] is None
        assert info["ref"] is None
        assert info["baseline"] is None


class TestGetVersionsForExperiment:
    """Verify get_versions_for_experiment() scanning."""

    def test_finds_tagged_versions(self, mapper, mock_datarepo):
        """get_versions_for_experiment() returns matching versions."""
        ds = MagicMock(uuid="ds-001")
        df = MagicMock(uuid="df-001")
        v1 = MagicMock(metadata={"experiment_name": "target-exp"})
        v2 = MagicMock(metadata={"experiment_name": "other-exp"})
        v3 = MagicMock(metadata={})

        mock_datarepo.list_datasets.return_value = [ds]
        mock_datarepo.list_datafiles.return_value = [df]
        mock_datarepo.list_dataversions.return_value = [v1, v2, v3]

        results = mapper.get_versions_for_experiment("target-exp")
        assert len(results) == 1
        assert results[0] is v1

    def test_returns_empty_when_no_match(self, mapper, mock_datarepo):
        """get_versions_for_experiment() returns [] when no match."""
        ds = MagicMock(uuid="ds-001")
        df = MagicMock(uuid="df-001")
        v1 = MagicMock(metadata={"experiment_name": "other"})

        mock_datarepo.list_datasets.return_value = [ds]
        mock_datarepo.list_datafiles.return_value = [df]
        mock_datarepo.list_dataversions.return_value = [v1]

        results = mapper.get_versions_for_experiment("nonexistent")
        assert results == []

    def test_returns_empty_when_no_datasets(self, mapper, mock_datarepo):
        """get_versions_for_experiment() returns [] with no datasets."""
        mock_datarepo.list_datasets.return_value = []
        results = mapper.get_versions_for_experiment("any")
        assert results == []

    def test_scans_multiple_datasets(self, mapper, mock_datarepo):
        """get_versions_for_experiment() scans across datasets."""
        ds1 = MagicMock(uuid="ds-001")
        ds2 = MagicMock(uuid="ds-002")
        df1 = MagicMock(uuid="df-001")
        df2 = MagicMock(uuid="df-002")
        v1 = MagicMock(metadata={"experiment_name": "target"})
        v2 = MagicMock(metadata={"experiment_name": "target"})

        mock_datarepo.list_datasets.return_value = [ds1, ds2]
        mock_datarepo.list_datafiles.side_effect = [[df1], [df2]]
        mock_datarepo.list_dataversions.side_effect = [[v1], [v2]]

        results = mapper.get_versions_for_experiment("target")
        assert len(results) == 2


class TestListExperimentNames:
    """Verify list_experiment_names() unique collection."""

    def test_returns_sorted_unique_names(self, mapper, mock_datarepo):
        """list_experiment_names() returns sorted unique names."""
        ds = MagicMock(uuid="ds-001")
        df = MagicMock(uuid="df-001")
        v1 = MagicMock(metadata={"experiment_name": "beta-exp"})
        v2 = MagicMock(metadata={"experiment_name": "alpha-exp"})
        v3 = MagicMock(metadata={"experiment_name": "beta-exp"})
        v4 = MagicMock(metadata={})

        mock_datarepo.list_datasets.return_value = [ds]
        mock_datarepo.list_datafiles.return_value = [df]
        mock_datarepo.list_dataversions.return_value = [v1, v2, v3, v4]

        names = mapper.list_experiment_names()
        assert names == ["alpha-exp", "beta-exp"]

    def test_returns_empty_when_none_tagged(self, mapper, mock_datarepo):
        """list_experiment_names() returns [] when no versions tagged."""
        ds = MagicMock(uuid="ds-001")
        df = MagicMock(uuid="df-001")
        v1 = MagicMock(metadata={})

        mock_datarepo.list_datasets.return_value = [ds]
        mock_datarepo.list_datafiles.return_value = [df]
        mock_datarepo.list_dataversions.return_value = [v1]

        assert mapper.list_experiment_names() == []

    def test_returns_empty_with_no_datasets(self, mapper, mock_datarepo):
        """list_experiment_names() returns [] with no datasets."""
        mock_datarepo.list_datasets.return_value = []
        assert mapper.list_experiment_names() == []
