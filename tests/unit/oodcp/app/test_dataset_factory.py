"""Tests for DataSetFactory."""

import pytest

from dvc.oodcp.app.factory.dataset_factory import DataSetFactory
from dvc.oodcp.domain.entities.dataset import DataSet
from dvc.oodcp.domain.enums import EntityStatus


class TestDataSetFactory:
    """Verify DataSetFactory.create() behavior."""

    def test_creates_dataset(self, repo):
        """create() returns a DataSet entity."""
        factory = DataSetFactory(repo)
        ds = factory.create(name="test-dataset")
        assert isinstance(ds, DataSet)
        assert ds.name == "test-dataset"

    def test_injects_repo(self, repo):
        """create() injects DataRepo into entity."""
        factory = DataSetFactory(repo)
        ds = factory.create(name="test")
        assert ds._repo is repo

    def test_default_status_active(self, repo):
        """Created DataSet defaults to ACTIVE status."""
        factory = DataSetFactory(repo)
        ds = factory.create(name="test")
        assert ds.status == EntityStatus.ACTIVE

    def test_generates_uuid(self, repo):
        """Created DataSet has auto-generated UUID."""
        factory = DataSetFactory(repo)
        ds = factory.create(name="test")
        assert ds.uuid
        assert len(ds.uuid) == 36

    def test_all_params(self, repo):
        """create() accepts all optional parameters."""
        factory = DataSetFactory(repo)
        ds = factory.create(
            name="full",
            description="desc",
            project="proj",
            owner="owner",
            shared_metadata={"key": "val"},
        )
        assert ds.description == "desc"
        assert ds.project == "proj"
        assert ds.owner == "owner"
        assert ds.shared_metadata == {"key": "val"}

    def test_empty_metadata_default(self, repo):
        """create() defaults shared_metadata to empty dict."""
        factory = DataSetFactory(repo)
        ds = factory.create(name="test")
        assert ds.shared_metadata == {}
