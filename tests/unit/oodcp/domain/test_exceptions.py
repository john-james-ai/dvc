"""Tests for OOD-CP domain exceptions."""

from dvc.oodcp.domain.exceptions import (
    DataNotFoundError,
    DeleteConstraintError,
    DuplicateNameError,
    EntityNotFoundError,
    IntegrityError,
    InvalidStatusTransitionError,
    OodcpError,
    StorageError,
)


class TestExceptionHierarchy:
    """Verify exception inheritance chain."""

    def test_base_exception(self):
        """OodcpError is a base Exception."""
        assert issubclass(OodcpError, Exception)

    def test_entity_not_found_is_oodcp_error(self):
        assert issubclass(EntityNotFoundError, OodcpError)

    def test_duplicate_name_is_oodcp_error(self):
        assert issubclass(DuplicateNameError, OodcpError)

    def test_storage_error_is_oodcp_error(self):
        assert issubclass(StorageError, OodcpError)

    def test_data_not_found_is_storage_error(self):
        assert issubclass(DataNotFoundError, StorageError)

    def test_integrity_error_is_oodcp_error(self):
        assert issubclass(IntegrityError, OodcpError)

    def test_delete_constraint_is_oodcp_error(self):
        assert issubclass(DeleteConstraintError, OodcpError)

    def test_invalid_status_transition_is_oodcp_error(self):
        assert issubclass(InvalidStatusTransitionError, OodcpError)


class TestEntityNotFoundError:
    """Verify EntityNotFoundError attributes and message."""

    def test_attributes(self):
        err = EntityNotFoundError("DataSet", "uuid-123")
        assert err.entity_type == "DataSet"
        assert err.identifier == "uuid-123"

    def test_message(self):
        err = EntityNotFoundError("DataFile", "train.csv")
        assert "DataFile" in str(err)
        assert "train.csv" in str(err)


class TestDuplicateNameError:
    """Verify DuplicateNameError attributes and message."""

    def test_attributes(self):
        err = DuplicateNameError("DataSet", "my-dataset")
        assert err.entity_type == "DataSet"
        assert err.name == "my-dataset"

    def test_message(self):
        err = DuplicateNameError("DataFile", "train.csv")
        assert "DataFile" in str(err)
        assert "train.csv" in str(err)


class TestInvalidStatusTransitionError:
    """Verify InvalidStatusTransitionError attributes."""

    def test_attributes(self):
        err = InvalidStatusTransitionError("DRAFT", "DELETED")
        assert err.current == "DRAFT"
        assert err.target == "DELETED"

    def test_message(self):
        err = InvalidStatusTransitionError("COMMITTED", "DRAFT")
        assert "COMMITTED" in str(err)
        assert "DRAFT" in str(err)
