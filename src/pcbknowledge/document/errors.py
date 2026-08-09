"""Non-disclosing document intake and retrieval errors."""


class DocumentError(RuntimeError):
    """Base error that never embeds tenant metadata or object identifiers."""


class DocumentAccessDeniedError(DocumentError):
    def __init__(self) -> None:
        super().__init__("document access is denied")


class DocumentNotFoundError(DocumentError):
    def __init__(self) -> None:
        super().__init__("document was not found in the active scope")


class UploadSessionNotFoundError(DocumentError):
    def __init__(self) -> None:
        super().__init__("upload session was not found in the active scope")


class UploadSessionConflictError(DocumentError):
    def __init__(self) -> None:
        super().__init__("upload session conflicts with an existing request")


class UploadSessionStateError(DocumentError):
    def __init__(self) -> None:
        super().__init__("upload session is not in the required state")


class IntakeOptionsUnavailableError(DocumentError):
    def __init__(self) -> None:
        super().__init__("no authorized intake configuration is available")


class InvalidUploadJobError(DocumentError):
    def __init__(self) -> None:
        super().__init__("upload verification job is invalid")


class UploadTooLargeError(DocumentError):
    def __init__(self) -> None:
        super().__init__("upload exceeds the qualified object storage limit")
