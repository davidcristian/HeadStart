"""Move classified inbound mail into configured IMAP folders."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.inbox.base import get_mailbox
from app.inbox.routing import InboxRoutingConfig, merge_routing_config, resolve_destination
from app.inbox.types import MoveResult
from app.models.inbox_classification import InboxClassification
from app.repositories.inbox_classifications import InboxClassificationRepository
from app.repositories.mailbox_credentials import MailboxCredentialRepository
from app.schemas.inbox_routing import (
    InboxRouteRequest,
    InboxRouteResponse,
    InboxRoutingConfigRead,
    InboxRoutingConfigUpdate,
)
from app.services.inbox import InboxService


class InboxRoutingService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.inbox = InboxService(session)
        self.credentials = MailboxCredentialRepository(session)
        self.classifications = InboxClassificationRepository(session)

    def get_config(self, user_id: int) -> InboxRoutingConfigRead:
        """Return the user's routing config with default folder names filled in."""
        self.inbox.require_enabled()
        credential = self.credentials.get_for_user(user_id)
        raw = credential.routing_config if credential is not None else None
        return self._as_read(merge_routing_config(raw))

    def update_config(self, user_id: int, data: InboxRoutingConfigUpdate) -> InboxRoutingConfigRead:
        """Persist routing settings on the user's mailbox credential."""
        self.inbox.require_enabled()
        credential = self.credentials.get_for_user(user_id)
        if credential is None:
            raise ValidationError("Mailbox credentials are not configured")
        current = merge_routing_config(credential.routing_config)
        updates = data.model_dump(exclude_unset=True)
        if "label_folders" in updates and updates["label_folders"] is not None:
            folders = dict(current.label_folders)
            folders.update(updates.pop("label_folders"))
            updates["label_folders"] = folders
        merged = current.model_copy(update=updates)
        credential.routing_config = merged.model_dump()
        self.session.flush()
        return self._as_read(merged)

    def route_classification(
        self,
        user_id: int,
        row: InboxClassification,
        *,
        force: bool = False,
    ) -> InboxRouteResponse:
        """Move one classified message when routing is enabled for its label."""
        self.inbox.require_enabled()
        if row.routing_status == "moved" and not force:
            return self._to_response(row)

        config = self.get_config(user_id)
        destination = resolve_destination(row.label, config)
        if destination is None:
            row.routing_status = "skipped"
            row.routed_to = None
            row.routing_error = None
            self.session.flush()
            return self._to_response(row)

        ctx = self.inbox.resolve_context(user_id)
        if ctx is None:
            raise ValidationError("No mailbox credentials configured")

        result = get_mailbox(ctx.connector_type).move_message(
            ctx,
            uid=row.message_uid,
            destination=destination,
            provider_message_id=_provider_message_id_from_classification(row),
        )
        self._apply_move_result(row, result)
        self.session.flush()
        return self._to_response(row)

    def route_after_classify(self, user_id: int, row: InboxClassification) -> InboxClassification:
        """Auto-route when enabled and the user opted into classify-time routing."""
        config = self.get_config(user_id)
        if not config.enabled or not config.auto_route_on_classify:
            return row
        self.route_classification(user_id, row)
        return row

    def route_by_request(self, user_id: int, data: InboxRouteRequest) -> InboxRouteResponse:
        """Route one message by classification id or mailbox UID."""
        if data.classification_id is None and data.message_uid is None:
            raise ValidationError("Provide classification_id or message_uid")
        row = self._resolve_row(user_id, data)
        return self.route_classification(user_id, row, force=True)

    def _resolve_row(self, user_id: int, data: InboxRouteRequest) -> InboxClassification:
        if data.classification_id is not None:
            row = self.classifications.get_by_id_for_user(user_id, data.classification_id)
            if row is None:
                raise NotFoundError(f"Classification {data.classification_id} not found")
            return row
        assert data.message_uid is not None
        row = self.classifications.get_by_user_and_uid(user_id, data.message_uid)
        if row is None:
            raise NotFoundError(f"Classification for message uid {data.message_uid} not found")
        return row

    @staticmethod
    def _apply_move_result(row: InboxClassification, result: MoveResult) -> None:
        row.routing_status = result.status
        row.routed_to = result.destination
        row.routing_error = result.error

    @staticmethod
    def _as_read(config: InboxRoutingConfig) -> InboxRoutingConfigRead:
        return InboxRoutingConfigRead.model_validate(config.model_dump())

    @staticmethod
    def _to_response(row: InboxClassification) -> InboxRouteResponse:
        return InboxRouteResponse(
            classification_id=row.id,
            message_uid=row.message_uid,
            label=row.label,
            routing_status=row.routing_status or "skipped",
            routed_to=row.routed_to,
            routing_error=row.routing_error,
        )


def _provider_message_id_from_classification(row: InboxClassification) -> str | None:
    if not row.payload or not isinstance(row.payload, dict):
        return None
    for key in ("graph_message_id", "jmap_email_id"):
        value = row.payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None
