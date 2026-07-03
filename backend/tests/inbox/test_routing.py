"""Unit tests for label→folder routing resolution."""

from app.inbox.routing import (
    InboxRoutingConfig,
    merge_routing_config,
    resolve_destination,
)


def test_resolve_destination_returns_none_when_disabled() -> None:
    config = InboxRoutingConfig(enabled=False, label_folders={"general": "HeadStart/General"})
    assert resolve_destination("general", config) is None


def test_resolve_destination_skips_out_of_scope() -> None:
    config = InboxRoutingConfig(enabled=True)
    assert resolve_destination("out_of_scope", config) is None


def test_resolve_destination_uses_defaults_when_enabled() -> None:
    config = InboxRoutingConfig(enabled=True)
    assert resolve_destination("rejection", config) == "HeadStart/Rejections"
    assert resolve_destination("self_ghost_archive", config) == "HeadStart/Ghost"


def test_merge_routing_config_fills_missing_folder_keys() -> None:
    merged = merge_routing_config({"enabled": True, "label_folders": {"general": "Custom/General"}})
    assert merged.enabled is True
    assert merged.label_folders["general"] == "Custom/General"
    assert merged.label_folders["rejection"] == "HeadStart/Rejections"
