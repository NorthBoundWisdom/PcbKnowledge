"""Safe transactional outbox errors."""


class OutboxError(RuntimeError):
    """Base outbox error without event payload details."""


class OutboxTransitionError(OutboxError):
    def __init__(self) -> None:
        super().__init__("outbox event state transition is not permitted")


class OutboxLeaseLostError(OutboxError):
    def __init__(self) -> None:
        super().__init__("outbox lease is no longer owned by this worker")


class OutboxPayloadIntegrityError(OutboxError):
    """Raised before dispatch when persisted metadata fails canonical verification."""

    def __init__(self) -> None:
        super().__init__("outbox payload integrity verification failed")


class OutboxIdempotencyConflictError(OutboxError):
    def __init__(self) -> None:
        super().__init__("outbox idempotency key was reused for different content")
