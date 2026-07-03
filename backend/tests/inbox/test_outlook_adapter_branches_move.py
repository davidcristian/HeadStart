"""Branch coverage for the Outlook adapter: move / folder resolution."""

import respx
from httpx import Response

from app.inbox.adapters.outlook import OutlookMailbox
from app.inbox.types import (
    MailboxContext,
    OutlookMailboxConfig,
)

CONFIG = OutlookMailboxConfig(
    email_address="user@outlook.test", access_token="access-token", refresh_token="refresh-token"
)
CTX = MailboxContext(connector_type="outlook", config=CONFIG, user_id=1)
GRAPH = "https://graph.microsoft.com/v1.0"


# --------------------------------------------------------------------------- #
# move / folder resolution
# --------------------------------------------------------------------------- #


def test_move_without_provider_id_fails() -> None:
    result = OutlookMailbox().move_message(CTX, uid=1, destination="HeadStart/General")
    assert result.status == "failed"
    assert "graph_message_id" in (result.error or "")


@respx.mock
def test_move_creates_nested_folders() -> None:
    gid = "AAA-move"
    # Root list has no HeadStart -> create it; child list empty -> create General.
    respx.get(f"{GRAPH}/me/mailFolders").mock(
        return_value=Response(200, json={"value": [{"id": "other", "displayName": "Other"}]})
    )
    respx.post(f"{GRAPH}/me/mailFolders").mock(return_value=Response(200, json={"id": "hs-id"}))
    respx.get(f"{GRAPH}/me/mailFolders/hs-id/childFolders").mock(
        return_value=Response(200, json={"value": []})
    )
    respx.post(f"{GRAPH}/me/mailFolders/hs-id/childFolders").mock(
        return_value=Response(200, json={"id": "gen-id"})
    )
    respx.post(f"{GRAPH}/me/messages/{gid}/move").mock(return_value=Response(200, json={"id": gid}))
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="HeadStart/General", provider_message_id=gid
    )
    assert result.status == "moved"


@respx.mock
def test_move_empty_destination_fails() -> None:
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="   /  ", provider_message_id="g1"
    )
    assert result.status == "failed"
    assert "Could not create Outlook folder" in (result.error or "")


@respx.mock
def test_move_folder_create_failure_fails() -> None:
    respx.get(f"{GRAPH}/me/mailFolders").mock(return_value=Response(200, json={"value": []}))
    respx.post(f"{GRAPH}/me/mailFolders").mock(return_value=Response(400))
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="HeadStart", provider_message_id="g1"
    )
    assert result.status == "failed"
    assert "Could not create Outlook folder" in (result.error or "")


@respx.mock
def test_move_folder_create_non_str_id_fails() -> None:
    respx.get(f"{GRAPH}/me/mailFolders").mock(return_value=Response(200, json={"value": []}))
    respx.post(f"{GRAPH}/me/mailFolders").mock(return_value=Response(200, json={"id": 123}))
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="HeadStart", provider_message_id="g1"
    )
    assert result.status == "failed"


@respx.mock
def test_move_list_folders_error_and_non_list() -> None:
    # First-level list returns 400 -> [] folders -> create; created id used to move.
    gid = "AAA-listerr"
    respx.get(f"{GRAPH}/me/mailFolders").mock(return_value=Response(400))
    respx.post(f"{GRAPH}/me/mailFolders").mock(return_value=Response(200, json={"id": "hs2"}))
    respx.post(f"{GRAPH}/me/messages/{gid}/move").mock(return_value=Response(200, json={"id": gid}))
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="HeadStart", provider_message_id=gid
    )
    assert result.status == "moved"


@respx.mock
def test_move_list_folders_non_list_payload() -> None:
    gid = "AAA-nonlist"
    respx.get(f"{GRAPH}/me/mailFolders").mock(return_value=Response(200, json={"value": "nope"}))
    respx.post(f"{GRAPH}/me/mailFolders").mock(return_value=Response(200, json={"id": "hs3"}))
    respx.post(f"{GRAPH}/me/messages/{gid}/move").mock(return_value=Response(200, json={"id": gid}))
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="HeadStart", provider_message_id=gid
    )
    assert result.status == "moved"


@respx.mock
def test_move_folders_with_non_dict_entries_and_existing_match() -> None:
    gid = "AAA-existing"
    respx.get(f"{GRAPH}/me/mailFolders").mock(
        return_value=Response(
            200,
            json={"value": ["not-a-dict", {"id": "hs-existing", "displayName": "HeadStart"}]},
        )
    )
    respx.post(f"{GRAPH}/me/messages/{gid}/move").mock(return_value=Response(200, json={"id": gid}))
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="HeadStart", provider_message_id=gid
    )
    assert result.status == "moved"


@respx.mock
def test_move_graph_http_error_returns_failed() -> None:
    gid = "AAA-moveerr"
    respx.get(f"{GRAPH}/me/mailFolders").mock(
        return_value=Response(200, json={"value": [{"id": "hs", "displayName": "HeadStart"}]})
    )
    respx.post(f"{GRAPH}/me/messages/{gid}/move").mock(return_value=Response(500))
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="HeadStart", provider_message_id=gid
    )
    assert result.status == "failed"
    assert result.error
