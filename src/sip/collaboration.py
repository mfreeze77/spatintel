from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from .canonical import canonical_sha256, new_uuid
from .database import CollaborationCommentRow, CollaborationTaskRow, Database, NotificationRow
from .errors import ConflictError, NotFoundError, ValidationError
from .temporal import db_now


class CollaborationService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def comment(
        self,
        *,
        tenant_id: str,
        project_id: str,
        body: str,
        author_id: str,
        scene_commit_id: str | None = None,
        entity_id: str | None = None,
        anchor: dict[str, Any] | None = None,
        supersedes_comment_id: str | None = None,
    ) -> str:
        if not body.strip():
            raise ValidationError("COMMENT_EMPTY", "comment body cannot be empty")
        if not any([scene_commit_id, entity_id, anchor]):
            raise ValidationError("COMMENT_SCOPE_REQUIRED", "comment must bind to a commit, entity, or spatial anchor")
        comment_id = new_uuid()
        with self.database.session() as session:
            if supersedes_comment_id:
                prior = session.get(CollaborationCommentRow, supersedes_comment_id)
                if not prior or prior.tenant_id != tenant_id or prior.project_id != project_id:
                    raise NotFoundError("comment", supersedes_comment_id)
            session.add(
                CollaborationCommentRow(
                    comment_id=comment_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    scene_commit_id=scene_commit_id,
                    entity_id=entity_id,
                    anchor_json=anchor,
                    body=body,
                    body_hash=canonical_sha256({"body": body, "author_id": author_id, "supersedes": supersedes_comment_id}),
                    author_id=author_id,
                    supersedes_comment_id=supersedes_comment_id,
                )
            )
        return comment_id

    def create_task(
        self,
        *,
        tenant_id: str,
        project_id: str,
        title: str,
        description: str,
        created_by: str,
        entity_id: str | None = None,
        assignee_id: str | None = None,
        priority: str = "normal",
        due_at: datetime | None = None,
    ) -> str:
        if priority not in {"low", "normal", "high", "urgent"}:
            raise ValidationError("TASK_PRIORITY", "unsupported task priority")
        task_id = new_uuid()
        with self.database.session() as session:
            session.add(
                CollaborationTaskRow(
                    task_id=task_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    entity_id=entity_id,
                    state="open",
                    priority=priority,
                    title=title,
                    description=description,
                    assignee_id=assignee_id,
                    due_at=due_at,
                    created_by=created_by,
                )
            )
        return task_id

    def transition_task(self, task_id: str, *, new_state: str, actor_id: str) -> dict[str, Any]:
        allowed = {"open": {"in_progress", "cancelled"}, "in_progress": {"blocked", "done", "cancelled"}, "blocked": {"in_progress", "cancelled"}, "done": set(), "cancelled": set()}
        with self.database.session() as session:
            row = session.get(CollaborationTaskRow, task_id)
            if not row:
                raise NotFoundError("task", task_id)
            if new_state not in allowed.get(row.state, set()):
                raise ConflictError("TASK_TRANSITION_INVALID", "task state transition is invalid", {"from": row.state, "to": new_state})
            previous = row.state
            row.state = new_state
            return {"task_id": task_id, "from": previous, "to": new_state, "actor_id": actor_id}


class NotificationService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def queue(
        self,
        *,
        tenant_id: str,
        project_id: str,
        recipient_id: str,
        channel: str,
        template_id: str,
        payload: dict[str, Any],
        sensitive: bool,
    ) -> str:
        if channel not in {"in_app", "email", "sms", "push"}:
            raise ValidationError("NOTIFICATION_CHANNEL", "unsupported notification channel")
        external_payload = payload
        if sensitive and channel != "in_app":
            external_payload = {
                "message": "A restricted SIP item requires your attention. Sign in to review it.",
                "resource_id": payload.get("resource_id"),
                "contains_sensitive_details": False,
            }
        notification_id = new_uuid()
        with self.database.session() as session:
            session.add(
                NotificationRow(
                    notification_id=notification_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    recipient_id=recipient_id,
                    channel=channel,
                    template_id=template_id,
                    payload_json=external_payload,
                    sensitive=sensitive,
                )
            )
        return notification_id

    def deliverable(self, notification_id: str, *, quiet_hours: bool, urgent: bool = False) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(NotificationRow, notification_id)
            if not row:
                raise NotFoundError("notification", notification_id)
            if quiet_hours and not urgent:
                row.state = "deferred_quiet_hours"
                return {"deliver": False, "state": row.state}
            row.state = "ready"
            return {"deliver": True, "state": row.state, "channel": row.channel, "payload": row.payload_json}
