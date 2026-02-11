"""Tests for OodcpDependency pipeline integration."""

import pytest
from unittest.mock import MagicMock, PropertyMock

from dvc.oodcp.integration.pipeline import OodcpDependency
from dvc.oodcp.domain.entities.dataversion import S3DataVersion
from dvc.oodcp.domain.enums import VersionStatus


@pytest.fixture
def mock_stage():
    """Mock DVC Stage with repo.oodcp wired."""
    stage = MagicMock()
    stage.repo.oodcp = MagicMock()
    return stage


@pytest.fixture
def mock_version():
    """A mock DataVersion with known hash."""
    v = MagicMock()
    v.dvc_hash = "abc123"
    v.hash_algorithm = "md5"
    v.version_number = 3
    v.storage_type.value = "S3"
    return v


class TestOodcpDependencyScheme:
    """Verify URI scheme detection and parsing."""

    @pytest.mark.parametrize(
        "path, expected",
        [
            ("oodcp://dataset/file", True),
            ("oodcp://dataset/file@v3", True),
            ("oodcp://my-ds/train.csv", True),
            ("s3://bucket/path", False),
            ("/local/path", False),
            ("ds://name", False),
            ("dataset://name", False),
        ],
    )
    def test_is_oodcp(self, path, expected):
        """is_oodcp() correctly identifies oodcp:// URIs."""
        assert OodcpDependency.is_oodcp(path) is expected

    def test_parse_uri_without_version(self, mock_stage):
        """Parses dataset and file from URI without version pin."""
        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://my-dataset/train.csv",
            info={},
        )
        assert dep.dataset_name == "my-dataset"
        assert dep.file_name == "train.csv"
        assert dep.pinned_version is None

    def test_parse_uri_with_version(self, mock_stage):
        """Parses dataset, file, and version from pinned URI."""
        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://my-dataset/train.csv@v3",
            info={},
        )
        assert dep.dataset_name == "my-dataset"
        assert dep.file_name == "train.csv"
        assert dep.pinned_version == 3

    def test_parse_uri_version_1(self, mock_stage):
        """Parses version 1 pin correctly."""
        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://ds/file@v1",
            info={},
        )
        assert dep.pinned_version == 1

    def test_repr(self, mock_stage):
        """__repr__ includes the full URI."""
        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://ds/file@v1",
            info={},
        )
        assert "oodcp://ds/file@v1" in repr(dep)

    def test_str(self, mock_stage):
        """__str__ returns the full URI."""
        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://ds/file@v1",
            info={},
        )
        assert str(dep) == "oodcp://ds/file@v1"


class TestOodcpDependencyStatus:
    """Verify workspace_status detection."""

    def test_status_unchanged(self, mock_stage, mock_version):
        """workspace_status returns empty when hash matches."""
        mock_stage.repo.oodcp.datarepo.get_dataset_by_name.return_value = (
            MagicMock(uuid="ds-001")
        )
        mock_stage.repo.oodcp.datarepo.get_datafile_by_name.return_value = (
            MagicMock(uuid="df-001")
        )
        mock_stage.repo.oodcp.datarepo.get_latest_dataversion.return_value = (
            mock_version
        )

        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://ds/file",
            info={"oodcp": {"dvc_hash": "abc123"}},
        )
        assert dep.workspace_status() == {}

    def test_status_modified(self, mock_stage, mock_version):
        """workspace_status returns 'modified' when hash differs."""
        mock_stage.repo.oodcp.datarepo.get_dataset_by_name.return_value = (
            MagicMock(uuid="ds-001")
        )
        mock_stage.repo.oodcp.datarepo.get_datafile_by_name.return_value = (
            MagicMock(uuid="df-001")
        )
        mock_stage.repo.oodcp.datarepo.get_latest_dataversion.return_value = (
            mock_version
        )

        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://ds/file",
            info={"oodcp": {"dvc_hash": "old_hash"}},
        )
        status = dep.workspace_status()
        assert status == {str(dep): "modified"}

    def test_status_new_no_stored_hash(self, mock_stage, mock_version):
        """workspace_status returns 'new' when no stored hash."""
        mock_stage.repo.oodcp.datarepo.get_dataset_by_name.return_value = (
            MagicMock(uuid="ds-001")
        )
        mock_stage.repo.oodcp.datarepo.get_datafile_by_name.return_value = (
            MagicMock(uuid="df-001")
        )
        mock_stage.repo.oodcp.datarepo.get_latest_dataversion.return_value = (
            mock_version
        )

        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://ds/file",
            info={},
        )
        status = dep.workspace_status()
        assert status == {str(dep): "new"}

    def test_status_deleted(self, mock_stage):
        """workspace_status returns 'deleted' when version gone."""
        mock_stage.repo.oodcp.datarepo.get_dataset_by_name.return_value = None

        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://ds/file",
            info={"oodcp": {"dvc_hash": "abc123"}},
        )
        status = dep.workspace_status()
        assert status == {str(dep): "deleted"}


class TestOodcpDependencySave:
    """Verify save() computes hash info."""

    def test_save_captures_version_info(self, mock_stage, mock_version):
        """save() stores version hash and metadata in hash_info."""
        mock_stage.repo.oodcp.datarepo.get_dataset_by_name.return_value = (
            MagicMock(uuid="ds-001")
        )
        mock_stage.repo.oodcp.datarepo.get_datafile_by_name.return_value = (
            MagicMock(uuid="df-001")
        )
        mock_stage.repo.oodcp.datarepo.get_latest_dataversion.return_value = (
            mock_version
        )

        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://my-ds/train.csv",
            info={},
        )
        dep.save()

        assert dep.hash_info.value["dvc_hash"] == "abc123"
        assert dep.hash_info.value["hash_algorithm"] == "md5"
        assert dep.hash_info.value["version_number"] == 3
        assert dep.hash_info.value["dataset"] == "my-ds"
        assert dep.hash_info.value["file"] == "train.csv"

    def test_save_empty_when_not_found(self, mock_stage):
        """save() stores empty hash when version not found."""
        mock_stage.repo.oodcp.datarepo.get_dataset_by_name.return_value = None

        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://nonexistent/file",
            info={},
        )
        dep.save()
        assert dep.hash_info.value == {}


class TestOodcpDependencyDumpd:
    """Verify dumpd() serialization."""

    def test_dumpd_includes_path(self, mock_stage):
        """dumpd() includes the PARAM_PATH key."""
        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://ds/file@v1",
            info={"oodcp": {"dvc_hash": "abc"}},
        )
        d = dep.dumpd()
        assert d["path"] == "oodcp://ds/file@v1"


class TestOodcpDependencyResolve:
    """Verify version resolution logic."""

    def test_resolve_pinned_version(self, mock_stage):
        """Pinned version resolves by version_number match."""
        v2 = MagicMock(version_number=2, dvc_hash="hash2")
        v3 = MagicMock(version_number=3, dvc_hash="hash3")
        mock_stage.repo.oodcp.datarepo.get_dataset_by_name.return_value = (
            MagicMock(uuid="ds-001")
        )
        mock_stage.repo.oodcp.datarepo.get_datafile_by_name.return_value = (
            MagicMock(uuid="df-001")
        )
        mock_stage.repo.oodcp.datarepo.list_dataversions.return_value = [
            v2, v3
        ]

        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://ds/file@v3",
            info={},
        )
        version = dep._resolve_version()
        assert version is v3

    def test_resolve_latest_when_unpinned(self, mock_stage, mock_version):
        """Unpinned URI resolves to latest committed version."""
        mock_stage.repo.oodcp.datarepo.get_dataset_by_name.return_value = (
            MagicMock(uuid="ds-001")
        )
        mock_stage.repo.oodcp.datarepo.get_datafile_by_name.return_value = (
            MagicMock(uuid="df-001")
        )
        mock_stage.repo.oodcp.datarepo.get_latest_dataversion.return_value = (
            mock_version
        )

        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://ds/file",
            info={},
        )
        version = dep._resolve_version()
        assert version is mock_version

    def test_resolve_returns_none_missing_dataset(self, mock_stage):
        """Returns None when dataset not found."""
        mock_stage.repo.oodcp.datarepo.get_dataset_by_name.return_value = None

        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://missing/file",
            info={},
        )
        assert dep._resolve_version() is None

    def test_resolve_returns_none_missing_file(self, mock_stage):
        """Returns None when datafile not found."""
        mock_stage.repo.oodcp.datarepo.get_dataset_by_name.return_value = (
            MagicMock(uuid="ds-001")
        )
        mock_stage.repo.oodcp.datarepo.get_datafile_by_name.return_value = None

        dep = OodcpDependency(
            stage=mock_stage,
            p="oodcp://ds/missing",
            info={},
        )
        assert dep._resolve_version() is None
