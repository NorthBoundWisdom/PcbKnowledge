"""Establish the migration chain without inventing M1 domain tables.

Revision ID: 20260808_0001
Revises:
Create Date: 2026-08-08
"""

from collections.abc import Sequence

revision: str = "20260808_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """M0 has no persistent business schema."""


def downgrade() -> None:
    """M0 has no persistent business schema."""
