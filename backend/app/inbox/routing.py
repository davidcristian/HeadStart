"""Label → mailbox folder resolution for inbox routing."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.email_classifiers.labels import EMAIL_CLASSIFICATION_LABELS

DEFAULT_LABEL_FOLDERS: dict[str, str] = {
    "general": "HeadStart/General",
    "rejection": "HeadStart/Rejections",
    "follow_up": "HeadStart/General",
    "interview_request": "HeadStart/General",
    "self_ghost_archive": "HeadStart/Ghost",
}

NON_ROUTABLE_LABELS = frozenset({"out_of_scope"})


class InboxRoutingConfig(BaseModel):
    """Per-user folder targets for classified inbound mail."""

    enabled: bool = False
    auto_route_on_classify: bool = True
    label_folders: dict[str, str] = Field(default_factory=dict)


def default_routing_config() -> InboxRoutingConfig:
    """Return routing defaults with HeadStart folder names pre-populated."""
    return InboxRoutingConfig(
        enabled=False,
        auto_route_on_classify=True,
        label_folders=dict(DEFAULT_LABEL_FOLDERS),
    )


def merge_routing_config(raw: dict | None) -> InboxRoutingConfig:
    """Load stored JSON into a config, filling missing folder keys from defaults."""
    base = default_routing_config()
    if not raw:
        return base
    stored = InboxRoutingConfig.model_validate(raw)
    folders = dict(DEFAULT_LABEL_FOLDERS)
    folders.update(stored.label_folders)
    return InboxRoutingConfig(
        enabled=stored.enabled,
        auto_route_on_classify=stored.auto_route_on_classify,
        label_folders=folders,
    )


def resolve_destination(label: str, config: InboxRoutingConfig) -> str | None:
    """Return the IMAP mailbox folder for `label`, or None when routing is skipped."""
    if label in NON_ROUTABLE_LABELS or not config.enabled:
        return None
    if label not in EMAIL_CLASSIFICATION_LABELS:
        return None
    folder = config.label_folders.get(label) or DEFAULT_LABEL_FOLDERS.get(label)
    if not folder or not folder.strip():
        return None
    return folder.strip()
