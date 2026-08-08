"""Bounded-cardinality Prometheus metrics for the M1 platform boundary."""

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

HTTP_REQUESTS = Counter(
    "pcbknowledge_http_requests_total",
    "Completed HTTP requests.",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "pcbknowledge_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "route"),
)
AUTHENTICATION_FAILURES = Counter(
    "pcbknowledge_authentication_failures_total",
    "Bearer authentication failures by credential-safe reason.",
    ("reason",),
)
AUTHORIZATION_DENIALS = Counter(
    "pcbknowledge_authorization_denials_total",
    "Requests rejected by the application authorization boundary.",
    ("action",),
)
OBJECT_STORE_ERRORS = Counter(
    "pcbknowledge_object_store_errors_total",
    "Object-store operations that failed without exposing object names.",
    ("operation",),
)
JOB_QUEUE_DEPTH = Gauge(
    "pcbknowledge_job_queue_depth",
    "Current jobs by state.",
    ("state",),
)
JOB_QUEUE_OLDEST_AGE = Gauge(
    "pcbknowledge_job_queue_oldest_age_seconds",
    "Age of the oldest ready job.",
)


def prometheus_response() -> Response:
    """Render the process registry for the internal Prometheus scraper."""

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
