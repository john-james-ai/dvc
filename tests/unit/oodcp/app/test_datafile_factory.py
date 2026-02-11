"""Tests for DataFileFactory."""

import pytest

from dvc.oodcp.app.factory.datafile_factory import DataFileFactory
from dvc.oodcp.domain.entities.datafile import DataFile
from dvc.oodcp.domain.enums import EntityStatus


class TestDataFileFactory:
    """Verify DataFileFactory.create() behavior."""

    def test_creates_datafile(self, repo):
        """create() returns a DataFile entity."""
        factory = DataFileFactory(repo)
        df = factory.create(dataset_uuid="ds-001", name="train.csv")
        assert isinstance(df, DataFile)
        assert df.name == "train.csv"
        assert df.dataset_uuid == "ds-001"

    def test_injects_repo(self, repo):
        """create() injects DataRepo into entity."""
        factory = DataFileFactory(repo)
        df = factory.create(dataset_uuid="ds-001", name="test")
        assert df._repo is repo

    def test_default_status_active(self, repo):
        """Created DataFile defaults to ACTIVE status."""
        factory = DataFileFactory(repo)
        df = factory.create(dataset_uuid="ds-001", name="test")
        assert df.status == EntityStatus.ACTIVE

    def test_all_params(self, repo):
        """create() accepts all optional parameters."""
        factory = DataFileFactory(repo)
        df = factory.create(
            dataset_uuid="ds-001",
            name="data.csv",
            description="desc",
            owner="owner",
        )
        assert df.description == "desc"
        assert df.owner == "owner"
