"""Non-sensitive object storage and registry errors."""


class StorageError(RuntimeError):
    """Base storage error that never embeds keys, payloads, URLs, or credentials."""


class InvalidObjectDigestError(StorageError):
    def __init__(self) -> None:
        super().__init__("object SHA-256 digest is invalid")


class ObjectIntegrityError(StorageError):
    def __init__(self) -> None:
        super().__init__("stored object does not match the claimed digest")


class ObjectDigestMismatchError(ObjectIntegrityError):
    def __init__(self) -> None:
        StorageError.__init__(self, "stored object does not match the optional client digest")


class ObjectSizeMismatchError(ObjectIntegrityError):
    def __init__(self) -> None:
        StorageError.__init__(self, "stored object does not match the reserved byte size")


class ObjectMagicMismatchError(ObjectIntegrityError):
    def __init__(self) -> None:
        StorageError.__init__(self, "stored object does not have the required file signature")


class ObjectStoreUnavailableError(StorageError):
    def __init__(self) -> None:
        super().__init__("object store operation failed")


class ObjectAssetNotFoundError(StorageError):
    def __init__(self) -> None:
        super().__init__("object asset was not found in the active scope")


class ObjectAccessDeniedError(StorageError):
    def __init__(self) -> None:
        super().__init__("object asset access is denied")


class ObjectAuditRequiredError(StorageError):
    def __init__(self) -> None:
        super().__init__("object access audit could not be recorded")


class StagingUploadNotFoundError(StorageError):
    def __init__(self) -> None:
        super().__init__("staging upload was not found in the active scope")


class StagingUploadStateError(StorageError):
    def __init__(self) -> None:
        super().__init__("staging upload is not in the required state")
