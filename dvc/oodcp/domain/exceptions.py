class OodcpError(Exception):
    """Base exception for all OOD-CP errors."""


class EntityNotFoundError(OodcpError):
    """Raised when a requested entity does not exist.

    Attributes:
        entity_type: Type name (e.g., "DataSet", "DataFile").
        identifier: UUID or name used in the lookup.
    """

    def __init__(self, entity_type: str, identifier: str) -> None:
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} not found: {identifier}")


class DuplicateNameError(OodcpError):
    """Raised when an entity name conflicts with an existing one.

    Attributes:
        entity_type: Type name.
        name: The conflicting name.
    """

    def __init__(self, entity_type: str, name: str) -> None:
        self.entity_type = entity_type
        self.name = name
        super().__init__(f"{entity_type} already exists: {name}")


class InvalidStatusTransitionError(OodcpError):
    """Raised when an entity status change violates lifecycle rules.

    Attributes:
        current: Current status value.
        target: Attempted target status.
    """

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition from {current} to {target}")


class StorageError(OodcpError):
    """Raised when a storage operation fails."""


class DataNotFoundError(StorageError):
    """Raised when requested data does not exist on remote."""


class IntegrityError(OodcpError):
    """Raised when data hash verification fails."""


class DeleteConstraintError(OodcpError):
    """Raised when deletion is blocked by active children."""
