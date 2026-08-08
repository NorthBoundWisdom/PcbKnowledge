# M1 observability operations

The local stack collects application metrics and traces through an internal-only OpenTelemetry/Prometheus plane and provisions a read-only Grafana baseline dashboard. This is an operational signal path, not an audit authority.

## Data flow and exposure

```text
API / Worker --OTLP--> OTel Collector --Prometheus endpoint--> Prometheus --> Grafana
API /metrics ------------------------------^                  ^
Keycloak /metrics -------------------------------------------|
```

OTLP, collector health, collector metrics, and Keycloak management port remain on the Compose backend network. Prometheus, Grafana, and the Keycloak browser port bind to host loopback. Caddy does not publish management metrics.

The collector currently exports metrics to its Prometheus endpoint and sends traces to a no-op exporter after redaction. This deliberately avoids dumping span payloads to stdout before a reviewed trace backend exists. Adding a trace backend requires a retention/access ADR or deployment decision.

## Redaction and logging rules

Collector processors remove authorization/cookie response headers, database statements, prompt/completion fields, and document body attributes before trace export. Instrumentation and structured application logging must still avoid creating those attributes in the first place.

Never log or label metrics with:

- access, refresh, or ID tokens;
- client secret, API key, cookie, or authorization header;
- original-document full text or quote bodies;
- project-confidential payloads;
- model prompts or completions;
- unbounded MPN, document, user, or request values.

Logs may contain bounded correlation identifiers such as `trace_id`, `request_id`, authorized external subject ID, organization/project ID, job ID, and document revision ID. Audit events remain append-only PostgreSQL records; Prometheus and logs do not replace them.

## Baseline signals

Prometheus scrapes the API's internal-only `/metrics`, Keycloak management metrics, and the collector with per-target sample limits. The `M1 Platform Baseline` dashboard shows scrape availability, API request rate, API p95 latency, and telemetry export failures. The API target must be `UP` after `dev-up.sh` completes; an empty graph must not be treated as zero errors.

Initial alert rules cover API, identity, collector availability, and metric export failures. They have no notification receiver in local development. Production operators must route alerts through an approved channel without embedding source payloads or credentials.

## Validation

```bash
docker compose config --quiet
docker run --rm \
  --entrypoint /bin/promtool \
  --volume "$PWD/deploy/observability/prometheus.yml:/etc/prometheus/prometheus.yml:ro" \
  --volume "$PWD/deploy/observability/rules:/etc/prometheus/rules:ro" \
  prom/prometheus:v3.7.3 \
  check config /etc/prometheus/prometheus.yml

docker run --rm \
  --volume "$PWD/deploy/observability/otel-collector.yaml:/etc/otelcol-contrib/config.yaml:ro" \
  otel/opentelemetry-collector-contrib:0.139.0 \
  validate --config=/etc/otelcol-contrib/config.yaml
```

Also verify Grafana provisioning logs, `up` series for every target, dashboard presence, alert rule loading, and loopback-only published ports. Record missing backend metrics as a failed integration check rather than silently accepting an empty dashboard.
