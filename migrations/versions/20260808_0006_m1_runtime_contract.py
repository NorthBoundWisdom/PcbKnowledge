"""Expose only the migration revision required by runtime contract probes.

Revision ID: 20260808_0006
Revises: 20260808_0005
Create Date: 2026-08-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260808_0006"
down_revision: str | None = "20260808_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        REVOKE ALL ON TABLE public.alembic_version
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker;
        GRANT USAGE ON SCHEMA public
            TO pcbknowledge_app, pcbknowledge_worker;
        GRANT SELECT ON TABLE public.alembic_version
            TO pcbknowledge_app, pcbknowledge_worker;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        REVOKE SELECT ON TABLE public.alembic_version
            FROM pcbknowledge_app, pcbknowledge_worker;
        REVOKE USAGE ON SCHEMA public
            FROM pcbknowledge_app, pcbknowledge_worker;
        """
    )
