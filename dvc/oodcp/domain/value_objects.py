from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class DVCHash:
    """Immutable content-addressed hash produced by DVC.

    Attributes:
        value: The hex string hash value (e.g., "d41d8cd9...").
        algorithm: Hash algorithm name (e.g., "md5", "md5-dos2unix").
    """

    value: str
    algorithm: str = "md5"

    def __bool__(self) -> bool:
        """Return True if hash value is non-empty."""
        return bool(self.value)


@dataclass(frozen=True)
class StorageURI:
    """Immutable physical address of versioned data.

    Attributes:
        uri: Full URI string (e.g., "s3://bucket/path", "/local/path").
    """

    uri: str

    @property
    def scheme(self) -> str:
        """Extract scheme from URI (e.g., 's3', 'gs', 'file').

        Returns:
            URI scheme string, or empty string for local paths.
        """
        parsed = urlparse(self.uri)
        return parsed.scheme

    def __str__(self) -> str:
        return self.uri


@dataclass(frozen=True)
class VersionNumber:
    """Immutable sequential version identifier.

    Attributes:
        value: Positive integer version number (>= 1).
    """

    value: int

    def __post_init__(self) -> None:
        """Validate that version number is >= 1."""
        if self.value < 1:
            raise ValueError(f"Version number must be >= 1, got {self.value}")

    def __int__(self) -> int:
        return self.value
