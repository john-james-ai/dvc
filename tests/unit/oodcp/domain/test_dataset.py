"""Tests for DataSet domain entity."""

import pytest

from dvc.oodcp.domain.entities.datafile import DataFile
from dvc.oodcp.domain.entities.dataset import DataSet
from dvc.oodcp.domain.enums import EntityStatus
from dvc.oodcp.domain.exceptions import (
    DuplicateNameError,
    EntityNotFoundError,
)


class TestDataSetCreation:
    """Verify DataSet instantiation and defaults."""

    def test_create_with_defaults(self):
        """DataSet creates with UUID, ACTIVE status, empty metadata."""
        ds = DataSet(name="test")
        assert ds.uuid
        assert ds.name == "test"
        assert ds.status == EntityStatus.ACTIVE
        assert ds.shared_metadata == {}

    def test_create_with_all_fields(self):
        """DataSet accepts all constructor arguments."""
        ds = DataSet(
            uuid="custom-uuid",
            name="my-dataset",
            description="desc",
            project="proj",
            owner="owner",
            shared_metadata={"license": "MIT"},
        )
        assert ds.uuid == "custom-uuid"
        assert ds.description == "desc"
        assert ds.shared_metadata == {"license": "MIT"}


class TestDataSetAddFile:
    """Verify DataSet.addfile() behavior.

    Uses sample_dataset fixture which is wired with an in-memory
    DataRepoSQLite. The dataset must be persisted first so the
    foreign key constraint is satisfied.
    """

    def test_addfile_creates_datafile(self, sample_dataset, repo):
        """addfile() creates a DataFile linked to this dataset."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="train.csv", description="Training")
        assert isinstance(df, DataFile)
        assert df.dataset_uuid == sample_dataset.uuid
        assert df.name == "train.csv"

    def test_addfile_persists_via_repo(self, sample_dataset, repo):
        """addfile() persists the DataFile in the repo."""
        repo.add_dataset(sample_dataset)
        sample_dataset.addfile(name="train.csv")
        saved = repo.get_datafile_by_name(sample_dataset.uuid, "train.csv")
        assert saved is not None
        assert saved.name == "train.csv"

    def test_addfile_duplicate_raises(self, sample_dataset, repo):
        """addfile() with duplicate name raises DuplicateNameError."""
        repo.add_dataset(sample_dataset)
        sample_dataset.addfile(name="train.csv")
        with pytest.raises(DuplicateNameError):
            sample_dataset.addfile(name="train.csv")

    def test_addfile_inherits_owner(self, sample_dataset, repo):
        """addfile() without owner inherits from dataset."""
        repo.add_dataset(sample_dataset)
        df = sample_dataset.addfile(name="data.csv")
        assert df.owner == sample_dataset.owner


class TestDataSetGetFile:
    """Verify DataSet.getfile() behavior."""

    def test_getfile_by_name(self, sample_dataset, repo):
        """getfile(name=) retrieves the correct DataFile."""
        repo.add_dataset(sample_dataset)
        sample_dataset.addfile(name="train.csv")
        df = sample_dataset.getfile(name="train.csv")
        assert df.name == "train.csv"

    def test_getfile_by_uuid(self, sample_dataset, repo):
        """getfile(uuid=) retrieves the correct DataFile."""
        repo.add_dataset(sample_dataset)
        created = sample_dataset.addfile(name="train.csv")
        df = sample_dataset.getfile(uuid=created.uuid)
        assert df.name == "train.csv"

    def test_getfile_not_found_raises(self, sample_dataset, repo):
        """getfile() raises EntityNotFoundError for missing file."""
        repo.add_dataset(sample_dataset)
        with pytest.raises(EntityNotFoundError):
            sample_dataset.getfile(name="nonexistent.csv")

    def test_getfile_no_args_raises(self, sample_dataset):
        """getfile() with no args raises ValueError."""
        with pytest.raises(ValueError):
            sample_dataset.getfile()


class TestDataSetListFiles:
    """Verify DataSet.listfiles() behavior."""

    def test_listfiles_returns_active(self, sample_dataset, repo):
        """listfiles() returns only ACTIVE files by default."""
        repo.add_dataset(sample_dataset)
        sample_dataset.addfile(name="a.csv")
        sample_dataset.addfile(name="b.csv")
        files = sample_dataset.listfiles()
        assert len(files) == 2

    def test_listfiles_excludes_deleted(self, sample_dataset, repo):
        """listfiles() excludes DELETED files by default."""
        repo.add_dataset(sample_dataset)
        sample_dataset.addfile(name="a.csv")
        sample_dataset.addfile(name="b.csv")
        sample_dataset.delfile("b.csv")
        files = sample_dataset.listfiles()
        assert len(files) == 1
        assert files[0].name == "a.csv"

    def test_listfiles_includes_deleted(self, sample_dataset, repo):
        """listfiles(include_deleted=True) includes DELETED files."""
        repo.add_dataset(sample_dataset)
        sample_dataset.addfile(name="a.csv")
        sample_dataset.addfile(name="b.csv")
        sample_dataset.delfile("b.csv")
        files = sample_dataset.listfiles(include_deleted=True)
        assert len(files) == 2


class TestDataSetDelete:
    """Verify DataSet soft-delete behavior."""

    def test_delfile_sets_deleted(self, sample_dataset, repo):
        """delfile() sets file status to DELETED."""
        repo.add_dataset(sample_dataset)
        sample_dataset.addfile(name="a.csv")
        sample_dataset.delfile("a.csv")
        df = sample_dataset.getfile(name="a.csv")
        assert df.status == EntityStatus.DELETED

    def test_delfile_not_found_raises(self, sample_dataset, repo):
        """delfile() raises EntityNotFoundError for missing file."""
        repo.add_dataset(sample_dataset)
        with pytest.raises(EntityNotFoundError):
            sample_dataset.delfile("nonexistent.csv")

    def test_delallfiles(self, sample_dataset, repo):
        """delallfiles() deletes all files."""
        repo.add_dataset(sample_dataset)
        sample_dataset.addfile(name="a.csv")
        sample_dataset.addfile(name="b.csv")
        sample_dataset.delallfiles()
        assert sample_dataset.listfiles() == []

    def test_candelete_true_when_all_deleted(self, sample_dataset, repo):
        """candelete() returns True when all files are DELETED."""
        repo.add_dataset(sample_dataset)
        sample_dataset.addfile(name="a.csv")
        sample_dataset.delfile("a.csv")
        assert sample_dataset.candelete() is True

    def test_candelete_true_when_no_files(self, sample_dataset, repo):
        """candelete() returns True when dataset has no files."""
        repo.add_dataset(sample_dataset)
        assert sample_dataset.candelete() is True

    def test_candelete_false_when_active_files(self, sample_dataset, repo):
        """candelete() returns False when active files exist."""
        repo.add_dataset(sample_dataset)
        sample_dataset.addfile(name="a.csv")
        assert sample_dataset.candelete() is False
