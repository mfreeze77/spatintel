from __future__ import annotations

from .audit import AuditService
from .canonical import new_uuid
from .database import Database, ProjectRow, TenantRow
from .errors import ConflictError, NotFoundError


class TenancyService:
    def __init__(self, database: Database, audit: AuditService) -> None:
        self.database = database
        self.audit = audit

    def create_tenant(self, name: str, *, tenant_id: str | None = None, actor_id: str = "system") -> str:
        identifier = tenant_id or new_uuid()
        with self.database.session() as session:
            if session.get(TenantRow, identifier):
                raise ConflictError("TENANT_EXISTS", "tenant already exists")
            session.add(TenantRow(tenant_id=identifier, name=name))
            self.audit.append(
                tenant_id=identifier,
                project_id=None,
                actor_id=actor_id,
                action="tenant:create",
                resource_type="tenant",
                resource_id=identifier,
                outcome="allowed",
                details={"name": name},
                session=session,
            )
        return identifier

    def create_project(
        self,
        tenant_id: str,
        name: str,
        *,
        vertical: str,
        classification: str,
        project_id: str | None = None,
        actor_id: str,
    ) -> str:
        identifier = project_id or new_uuid()
        with self.database.session() as session:
            if not session.get(TenantRow, tenant_id):
                raise NotFoundError("tenant", tenant_id)
            if session.get(ProjectRow, identifier):
                raise ConflictError("PROJECT_EXISTS", "project already exists")
            session.add(
                ProjectRow(
                    project_id=identifier,
                    tenant_id=tenant_id,
                    name=name,
                    vertical=vertical,
                    classification=classification,
                )
            )
            self.audit.append(
                tenant_id=tenant_id,
                project_id=identifier,
                actor_id=actor_id,
                action="project:create",
                resource_type="project",
                resource_id=identifier,
                outcome="allowed",
                details={"name": name, "vertical": vertical, "classification": classification},
                session=session,
            )
        return identifier
