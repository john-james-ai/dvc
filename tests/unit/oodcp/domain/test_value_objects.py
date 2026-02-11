"""Tests for OOD-CP domain value objects."""

import pytest

from dvc.oodcp.domain.value_objects import DVCHash, StorageURI, VersionNumber


class TestDVCHash:
    """Verify DVCHash immutability and behavior."""

    def test_create_with_defaults(self):
        """DVCHash defaults to md5 algorithm."""
        h = DVCHash(value="abc123")
        assert h.value == "abc123"
        assert h.algorithm == "md5"

    def test_create_with_algorithm(self):
        """DVCHash accepts custom algorithm."""
        h = DVCHash(value="abc123", algorithm="sha256")
        assert h.algorithm == "sha256"

    def test_bool_true_when_value(self):
        """DVCHash is truthy when value is non-empty."""
        assert bool(DVCHash(value="abc123"))

    def test_bool_false_when_empty(self):
        """DVCHash is falsy when value is empty."""
        assert not bool(DVCHash(value=""))

    def test_immutable(self):
        """DVCHash attributes cannot be modified."""
        h = DVCHash(value="abc123")
        with pytest.raises(AttributeError):
            h.value = "changed"

    def test_equality(self):
        """Two DVCHash with same fields are equal."""
        a = DVCHash(value="abc", algorithm="md5")
        b = DVCHash(value="abc", algorithm="md5")
        assert a == b

    def test_inequality(self):
        """Two DVCHash with different fields are not equal."""
        a = DVCHash(value="abc", algorithm="md5")
        b = DVCHash(value="def", algorithm="md5")
        assert a != b


class TestStorageURI:
    """Verify StorageURI parsing and immutability."""

    @pytest.mark.parametrize(
        "uri, expected_scheme",
        [
            ("s3://bucket/path", "s3"),
            ("gs://bucket/path", "gs"),
            ("azure://container/path", "azure"),
            ("/local/path", ""),
        ],
    )
    def test_scheme_extraction(self, uri, expected_scheme):
        """StorageURI.scheme extracts protocol from URI."""
        s = StorageURI(uri=uri)
        assert s.scheme == expected_scheme

    def test_str(self):
        """StorageURI str() returns the URI."""
        s = StorageURI(uri="s3://bucket/path")
        assert str(s) == "s3://bucket/path"

    def test_immutable(self):
        """StorageURI attributes cannot be modified."""
        s = StorageURI(uri="s3://bucket/path")
        with pytest.raises(AttributeError):
            s.uri = "changed"


class TestVersionNumber:
    """Verify VersionNumber validation."""

    def test_valid_version(self):
        """VersionNumber accepts positive integers."""
        v = VersionNumber(value=1)
        assert v.value == 1
        assert int(v) == 1

    def test_zero_raises(self):
        """VersionNumber rejects zero."""
        with pytest.raises(ValueError, match="must be >= 1"):
            VersionNumber(value=0)

    def test_negative_raises(self):
        """VersionNumber rejects negative numbers."""
        with pytest.raises(ValueError, match="must be >= 1"):
            VersionNumber(value=-1)

    def test_large_version(self):
        """VersionNumber accepts large numbers."""
        v = VersionNumber(value=9999)
        assert int(v) == 9999
