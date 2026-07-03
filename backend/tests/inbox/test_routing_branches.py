"""Branch coverage for label->folder routing resolution and config merge."""

from app.inbox.routing import (
    InboxRoutingConfig,
    merge_routing_config,
    resolve_destination,
)


def test_merge_routing_config_returns_base_when_raw_empty() -> None:
    merged = merge_routing_config(None)
    assert merged.enabled is False
    assert merged.label_folders["rejection"] == "HeadStart/Rejections"
    # An empty dict is also falsy -> base defaults.
    assert merge_routing_config({}).label_folders["general"] == "HeadStart/General"


def test_resolve_destination_returns_none_for_unknown_label() -> None:
    config = InboxRoutingConfig(enabled=True)
    assert resolve_destination("not-a-real-label", config) is None


def test_resolve_destination_returns_none_for_whitespace_only_folder() -> None:
    # A whitespace override is truthy for .get() but strips to empty -> None.
    config = InboxRoutingConfig(enabled=True, label_folders={"general": "   "})
    assert resolve_destination("general", config) is None
