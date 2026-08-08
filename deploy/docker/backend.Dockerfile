ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.3
ARG PYTHON_IMAGE=python:3.14-slim-bookworm

FROM ${UV_IMAGE} AS uv_binary
FROM ${PYTHON_IMAGE} AS runtime

COPY --from=uv_binary /uv /uvx /usr/local/bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/workspace/.venv/bin:$PATH

WORKDIR /workspace

RUN groupadd --system pcbknowledge \
    && useradd --system --gid pcbknowledge --home-dir /workspace pcbknowledge

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY apps/api ./apps/api
COPY apps/worker ./apps/worker
COPY migrations ./migrations
COPY deploy/docker/backend-entrypoint.sh ./deploy/docker/backend-entrypoint.sh

RUN uv sync --frozen --no-dev \
    && chown -R pcbknowledge:pcbknowledge /workspace

USER pcbknowledge
ENTRYPOINT ["/bin/sh", "/workspace/deploy/docker/backend-entrypoint.sh"]
CMD ["uvicorn", "pcbknowledge.api:app", "--host", "0.0.0.0", "--port", "8000"]
