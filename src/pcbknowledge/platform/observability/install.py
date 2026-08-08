"""Install request metrics, correlation headers, and OpenTelemetry tracing."""

import logging
import re
import secrets
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from pcbknowledge.platform.observability.context import RequestContext, bind_request_context
from pcbknowledge.platform.observability.logging import configure_json_logging
from pcbknowledge.platform.observability.metrics import HTTP_DURATION, HTTP_REQUESTS

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_logger = logging.getLogger("pcbknowledge.http")


def install_observability(
    application: FastAPI,
    *,
    service_name: str,
    otlp_endpoint: str | None,
) -> None:
    """Install process-wide logging and per-application telemetry exactly once."""

    configure_json_logging()
    provider = _build_tracer_provider(service_name=service_name, endpoint=otlp_endpoint)
    FastAPIInstrumentor.instrument_app(
        application,
        tracer_provider=provider,
        excluded_urls="healthz,readyz,metrics",
    )

    @application.middleware("http")
    async def correlate_and_measure(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = _safe_request_id(request.headers.get("x-request-id"))
        started = time.perf_counter()
        status_code = 500
        with bind_request_context(
            RequestContext(request_id=request_id, trace_id=_current_trace_id())
        ):
            try:
                response = await call_next(request)
                status_code = response.status_code
            finally:
                route = _route_template(request)
                elapsed = time.perf_counter() - started
                HTTP_REQUESTS.labels(request.method, route, str(status_code)).inc()
                HTTP_DURATION.labels(request.method, route).observe(elapsed)
                _logger.info(
                    "request_completed method=%s route=%s status=%s duration_ms=%.3f",
                    request.method,
                    route,
                    status_code,
                    elapsed * 1000,
                )
        response.headers["x-request-id"] = request_id
        return response


def _build_tracer_provider(*, service_name: str, endpoint: str | None) -> TracerProvider:
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    if endpoint is not None:
        exporter = OTLPSpanExporter(endpoint=_trace_export_endpoint(endpoint))
        provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def _trace_export_endpoint(endpoint: str) -> str:
    return f"{endpoint.rstrip('/')}/v1/traces"


def _safe_request_id(candidate: str | None) -> str:
    if candidate is not None and _REQUEST_ID.fullmatch(candidate):
        return candidate
    return secrets.token_hex(16)


def _current_trace_id() -> str:
    span_context = trace.get_current_span().get_span_context()
    if span_context.is_valid:
        return f"{span_context.trace_id:032x}"
    return secrets.token_hex(16)


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else "unmatched"
