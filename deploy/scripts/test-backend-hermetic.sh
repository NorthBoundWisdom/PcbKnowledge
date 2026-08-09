#!/bin/sh
set -eu

ruff format --check .
ruff check .
mypy src apps tests configs
pytest \
  --ignore=tests/document/test_document_postgres.py \
  --ignore=tests/document/test_document_seaweedfs.py \
  --ignore=tests/test_m1_postgres_security.py \
  --ignore=tests/test_m1_security_repair_postgres.py \
  --ignore=tests/test_database_contract_postgres.py \
  --ignore=tests/platform_jobs/test_jobs_postgres.py \
  --ignore=tests/platform_outbox/test_outbox_postgres.py \
  --ignore=tests/platform_outbox/test_storage_cleanup_worker_integration.py \
  --ignore=tests/platform_storage/test_storage_postgres.py \
  --ignore=tests/platform_storage/test_storage_seaweedfs.py
pcbknowledge-openapi --check
