"""Tests for DataRepo ABC contract verification."""

import pytest
from abc import ABC

from dvc.oodcp.domain.entities.datarepo import DataRepo


class TestDataRepoABC:
    """Verify DataRepo is abstract and defines all required methods."""

    def test_cannot_instantiate(self):
        """DataRepo cannot be instantiated directly."""
        with pytest.raises(TypeError):
            DataRepo()

    def test_is_abstract(self):
        """DataRepo is an ABC."""
        assert issubclass(DataRepo, ABC)

    def test_has_dataset_operations(self):
        """DataRepo defines all dataset abstract methods."""
        abstract_methods = DataRepo.__abstractmethods__
        for method in [
            "add_dataset", "get_dataset", "get_dataset_by_name",
            "list_datasets", "update_dataset",
        ]:
            assert method in abstract_methods, f"Missing: {method}"

    def test_has_datafile_operations(self):
        """DataRepo defines all datafile abstract methods."""
        abstract_methods = DataRepo.__abstractmethods__
        for method in [
            "add_datafile", "get_datafile", "get_datafile_by_name",
            "list_datafiles", "update_datafile",
        ]:
            assert method in abstract_methods, f"Missing: {method}"

    def test_has_dataversion_operations(self):
        """DataRepo defines all dataversion abstract methods."""
        abstract_methods = DataRepo.__abstractmethods__
        for method in [
            "add_dataversion", "get_dataversion",
            "get_latest_dataversion", "list_dataversions",
            "update_dataversion", "get_next_version_number",
        ]:
            assert method in abstract_methods, f"Missing: {method}"

    def test_has_lineage_and_lifecycle(self):
        """DataRepo defines lineage and lifecycle methods."""
        abstract_methods = DataRepo.__abstractmethods__
        assert "query_lineage" in abstract_methods
        assert "close" in abstract_methods
