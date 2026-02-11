from enum import Enum


class EntityStatus(str, Enum):
    """Lifecycle status for DataSet and DataFile entities."""

    ACTIVE = "ACTIVE"
    DELETED = "DELETED"


class VersionStatus(str, Enum):
    """Lifecycle status for DataVersion entities."""

    DRAFT = "DRAFT"
    COMMITTED = "COMMITTED"
    DELETED = "DELETED"


class StorageType(str, Enum):
    """Supported storage backend types for DataVersion."""

    S3 = "S3"
    GCS = "GCS"
    AZURE = "AZURE"
    LOCAL = "LOCAL"
