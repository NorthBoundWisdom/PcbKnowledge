"""Declarative metadata root used by all future domain modules."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Single SQLAlchemy declarative base for Alembic metadata discovery."""
