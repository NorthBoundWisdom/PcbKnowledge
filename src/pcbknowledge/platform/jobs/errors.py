"""Fail-closed job queue errors with non-sensitive messages."""


class JobQueueError(RuntimeError):
    """Base error for safe job queue failures."""


class InvalidJobPayloadError(JobQueueError):
    """Raised when a job payload violates the small-metadata policy."""

    def __init__(self) -> None:
        super().__init__("job payload must contain only small JSON metadata")


class InvalidJobTransitionError(JobQueueError):
    """Raised when a worker or operator attempts an invalid transition."""

    def __init__(self) -> None:
        super().__init__("job state transition is not permitted")


class JobLeaseLostError(JobQueueError):
    """Raised after a lease expires or belongs to a different worker."""

    def __init__(self) -> None:
        super().__init__("job lease is no longer owned by this worker")


class JobPayloadIntegrityError(JobQueueError):
    """Raised when persisted job metadata no longer matches its canonical digest."""

    def __init__(self) -> None:
        super().__init__("job payload integrity verification failed")


class JobEffectProvenanceUnknownError(JobQueueError):
    """Raised when a legacy effect receipt lacks verifiable lease provenance."""

    def __init__(self) -> None:
        super().__init__("job effect receipt lease provenance is unknown")


class JobNotFoundError(JobQueueError):
    """Raised when a scoped job is unavailable."""

    def __init__(self) -> None:
        super().__init__("job was not found in the active scope")


class JobIdempotencyConflictError(JobQueueError):
    """Raised when an idempotency key is reused for different input/effect."""

    def __init__(self) -> None:
        super().__init__("idempotency key was already used for different content")
