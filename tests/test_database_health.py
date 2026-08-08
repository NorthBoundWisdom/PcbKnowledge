from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import pytest
from sqlalchemy import Connection

from pcbknowledge.platform.database.health import (
    UnsafeDatabaseRoleError,
    require_restricted_database_role,
)

_SAFE_ROLE_ATTRIBUTES = {
    "rolsuper": False,
    "rolinherit": False,
    "rolcreaterole": False,
    "rolcreatedb": False,
    "rolreplication": False,
    "rolbypassrls": False,
    "has_role_membership": False,
    "has_role_assumers": False,
    "owns_protected_schema": False,
    "owns_protected_relation": False,
    "owns_protected_function": False,
}


def _connection_with_role(**role_attributes: bool) -> Connection:
    result: Any = Mock()
    result.one_or_none.return_value = SimpleNamespace(**role_attributes)
    connection: Any = Mock()
    connection.execute.return_value = result
    return cast(Connection, connection)


def test_restricted_database_role_has_no_bypass_or_role_membership() -> None:
    require_restricted_database_role(_connection_with_role(**_SAFE_ROLE_ATTRIBUTES))


@pytest.mark.parametrize(
    "dangerous_attribute",
    [
        "rolsuper",
        "rolinherit",
        "rolcreaterole",
        "rolcreatedb",
        "rolreplication",
        "rolbypassrls",
        "has_role_membership",
        "has_role_assumers",
    ],
)
def test_restricted_database_role_rejects_privilege_and_set_role_edges(
    dangerous_attribute: str,
) -> None:
    role_attributes = _SAFE_ROLE_ATTRIBUTES | {dangerous_attribute: True}

    with pytest.raises(UnsafeDatabaseRoleError):
        require_restricted_database_role(_connection_with_role(**role_attributes))


@pytest.mark.parametrize(
    "owned_object",
    [
        "owns_protected_schema",
        "owns_protected_relation",
        "owns_protected_function",
    ],
)
def test_restricted_database_role_rejects_custom_non_super_owner(
    owned_object: str,
) -> None:
    role_attributes = _SAFE_ROLE_ATTRIBUTES | {owned_object: True}

    with pytest.raises(UnsafeDatabaseRoleError):
        require_restricted_database_role(_connection_with_role(**role_attributes))


def test_restricted_database_role_rejects_unknown_current_role() -> None:
    result: Any = Mock()
    result.one_or_none.return_value = None
    connection: Any = Mock()
    connection.execute.return_value = result

    with pytest.raises(UnsafeDatabaseRoleError):
        require_restricted_database_role(cast(Connection, connection))
