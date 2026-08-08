"""Database primitives exposed to backend processes."""

from pcbknowledge.platform.database.base import Base
from pcbknowledge.platform.database.health import (
    DatabaseContractError,
    UnsafeDatabaseRoleError,
    probe_database,
    require_database_contract,
    require_restricted_database_role,
)
from pcbknowledge.platform.database.runtime import (
    DatabaseRuntime,
    get_database_runtime,
    reset_database_runtime,
)

__all__ = [
    "Base",
    "DatabaseContractError",
    "DatabaseRuntime",
    "UnsafeDatabaseRoleError",
    "get_database_runtime",
    "probe_database",
    "require_database_contract",
    "require_restricted_database_role",
    "reset_database_runtime",
]
