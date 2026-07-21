"""Coverage assertions for shared OAuth mailbox connector constants."""

from app.inbox.base import get_mailbox
from app.inbox.types import (
    OAUTH_CONFIG_BY_CONNECTOR,
    OAUTH_CONFIG_TYPES,
    OAUTH_CONNECTOR_TYPES,
)


def test_oauth_connector_constants_stay_aligned() -> None:
    """A new OAuth connector must update the shared maps together."""
    assert frozenset(OAUTH_CONFIG_BY_CONNECTOR) == OAUTH_CONNECTOR_TYPES
    assert set(OAUTH_CONFIG_BY_CONNECTOR.values()) == set(OAUTH_CONFIG_TYPES)
    for connector_type, config_cls in OAUTH_CONFIG_BY_CONNECTOR.items():
        assert connector_type in OAUTH_CONNECTOR_TYPES
        assert config_cls in OAUTH_CONFIG_TYPES
        # Registry import side-effect: every OAuth key has a mailbox adapter.
        assert get_mailbox(connector_type) is not None
