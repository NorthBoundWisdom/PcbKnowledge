"""Trusted identity and membership value types."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pcbknowledge.platform.ids import UUID7


class PrincipalKind(StrEnum):
    """Authentication actor class stored in the trusted subject mapping."""

    HUMAN = "HUMAN"
    SERVICE_ACCOUNT = "SERVICE_ACCOUNT"


class Role(StrEnum):
    """The complete M1 role vocabulary; token-provided roles are ignored."""

    DATA_CURATOR = "DATA_CURATOR"
    DOMAIN_REVIEWER = "DOMAIN_REVIEWER"
    KNOWLEDGE_ADMIN = "KNOWLEDGE_ADMIN"
    AUDITOR = "AUDITOR"
    AGENT_SERVICE = "AGENT_SERVICE"


class Principal(BaseModel):
    """Authenticated actor built only from verified claims plus trusted DB grants."""

    model_config = ConfigDict(frozen=True)

    subject_id: UUID7
    issuer: str = Field(min_length=1, max_length=2048)
    subject: str = Field(min_length=1, max_length=512)
    kind: PrincipalKind
    client_id: str | None = Field(default=None, min_length=1, max_length=255)
    organization_id: UUID7
    organization_roles: frozenset[Role] = frozenset()
    project_roles: dict[UUID7, frozenset[Role]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_human_service_boundary(self) -> Self:
        all_roles = set(self.organization_roles)
        for roles in self.project_roles.values():
            if not roles:
                raise ValueError("project membership must contain at least one trusted role")
            all_roles.update(roles)
        if not all_roles:
            raise ValueError("principal must have at least one trusted membership role")
        if self.kind is PrincipalKind.HUMAN:
            if self.client_id is not None:
                raise ValueError("human principals cannot have a service client_id")
            if Role.AGENT_SERVICE in all_roles:
                raise ValueError("human principals cannot hold AGENT_SERVICE")
        if self.kind is PrincipalKind.SERVICE_ACCOUNT:
            if self.client_id is None:
                raise ValueError("service-account principals require a trusted client_id")
            if all_roles != {Role.AGENT_SERVICE}:
                raise ValueError("service accounts may only hold AGENT_SERVICE")
        return self

    @property
    def project_ids(self) -> frozenset[UUID7]:
        """Projects explicitly granted to this principal."""

        return frozenset(self.project_roles)

    def roles_for_project(self, project_id: UUID7 | None) -> frozenset[Role]:
        """Return effective roles, requiring explicit membership for project scope."""

        if project_id is None:
            return self.organization_roles
        project_roles = self.project_roles.get(project_id)
        if project_roles is None:
            return frozenset()
        return self.organization_roles.union(project_roles)
