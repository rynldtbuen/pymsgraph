import json
import base64
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from pymsgraph.models.directory_object import DirectoryObject
from pymsgraph.models.group import Group
from pymsgraph.models.user import User, UserQuerySet
from pymsgraph.models.user.common import AssignedLicense, PasswordProfile
from pymsgraph.models.user.mail_folder import MailFolder, MailFolderQuerySet
from pymsgraph.models.user.message import (
    Attachment,
    AttachmentQuerySet,
    Message,
    MessageQuerySet,
)
from pymsgraph.models.user.query import (
    AppRoleAssignmentQuerySet,
    AssignedLicensesQuerySet,
    GroupsQuerySet,
    MemberOfQuerySet,
)
from pymsgraph.models.service_principal.common import AppRoleAssignment

if TYPE_CHECKING:
    from tests.conftest import MakeClient


def test_required_fields() -> None:
    assert User.REQUIRED_FIELDS == {
        "account_enabled",
        "display_name",
        "mail_nickname",
        "user_principal_name",
    }


@pytest.mark.asyncio
async def test_qs_create(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1.0/users"
        body = json.loads(request.content.decode())
        # basic payload expectations
        assert body["displayName"] == "Alice"
        assert body["userPrincipalName"] == "alice@example.com"
        assert body["mailNickname"] == "alice"
        assert body["accountEnabled"] == True
        assert "passwordProfile" in body
        return httpx.Response(
            201,
            json={
                "id": "123",
                "displayName": "Alice",
                "userPrincipalName": "alice@example.com",
                "mailNickname": "alice",
                "mail": "alice@example.com",
                "account_enabled": "true",
            },
        )

    c, _ = make_client(handler)
    u = await c.users.create(
        display_name="Alice",
        user_principal_name="alice@example.com",
        mail_nickname="alice",
        password="Pass@word1",
    )

    assert u.id == "123"
    assert u.display_name == "Alice"
    assert u.user_principal_name == "alice@example.com"
    assert u.mail == "alice@example.com"
    assert u.account_enabled is True
    assert u.path == "/users/123"
    assert u._dirty == set()
    assert u.password_profile is None


@pytest.mark.asyncio
async def test_qs_create_missing_required_fields(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP should not be called")

    c, _ = make_client(handler)

    with pytest.raises(ValueError):
        await c.users.create(
            display_name="Unsaved",
            user_principal_name="unsaved@example.com",
            mail_nickname="unsaved",
        )


@pytest.mark.asyncio
async def test_update(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and request.url.path.endswith("/users/123"):
            body = json.loads(request.content.decode())
            assert body == {"jobTitle": "Senior Engineer", "city": "Auckland"}
            return httpx.Response(204, json={})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, r = make_client(handler)
    user = c.users.make(id="123", display_name="Alice", job_title="Engineer")
    assert user._dirty == set()

    user.job_title = "Senior Engineer"
    user.city = "Auckland"
    assert "job_title" in user._dirty
    assert "city" in user._dirty
    saved = await user.update()
    assert saved is True
    assert user._dirty == set()
    assert user.path == "/users/123"
    assert len(r) == 1


@pytest.mark.asyncio
async def test_update_id_is_required(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP should not be called")

    c, r = make_client(handler)
    user = c.users.make(display_name="Alice")
    assert user._dirty == set()

    user.job_title = "Senior Engineer"
    user.city = "Auckland"
    assert "job_title" in user._dirty
    assert "city" in user._dirty

    with pytest.raises(AttributeError):
        await user.update()


def test_qs_select_build_params(users_qs):
    qs = users_qs._clone()
    params = qs.select("display_name", "mail_nickname")._build_params()
    assert params["$select"] == "id,displayName,mailNickname"

    params = qs._build_params()
    assert params["$select"] == "accountEnabled,displayName,id,mail,userPrincipalName"


def test_field_password_profile() -> None:
    u = User(
        password_profile={
            "password": "  a  b  ",
            "force_change_password_next_sign_in": True,
        }
    )
    assert isinstance(u.password_profile, PasswordProfile)

    payload = u.serialize()
    assert "passwordProfile" in payload
    inner = payload["passwordProfile"]
    assert inner["password"] == "a b"
    assert inner["forceChangePasswordNextSignIn"] is True


def test_field_assigned_licenses(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    c, _ = make_client(handler)
    u = c.users.make(id="u1")

    qs = u.assigned_licenses
    assert isinstance(qs, AssignedLicensesQuerySet)
    assert qs.path == "/users/u1/assignLicense"
    assert qs._model_class is AssignedLicense


def test_field_app_role_assignments(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    c, _ = make_client(handler)
    u = c.users.make(id="u1")

    qs = u.app_role_assignments
    assert isinstance(qs, AppRoleAssignmentQuerySet)
    assert qs.path == "/users/u1/appRoleAssignments"
    assert qs._model_class is AppRoleAssignment


def test_field_messages(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    c, _ = make_client(handler)
    u = c.users.make(id="u1")

    qs = u.messages
    assert isinstance(qs, MessageQuerySet)
    assert qs.path == "/users/u1/messages"
    assert qs._model_class is Message


def test_message_queryset_by_id(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP call expected")

    client, _ = make_client(handler)
    user = client.users.make(id="u1")

    message = user.messages.by_id("m1")

    assert isinstance(message, Message)
    assert message.id == "m1"
    assert message.path == "/users/u1/messages/m1"


def test_message_queryset_by_id_preserves_mail_folder_path(
    make_client: "MakeClient",
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP call expected")

    client, _ = make_client(handler)
    folder = MailFolder(id="f1", client=client, path="/users/u1/mailFolders")

    message = folder.messages.by_id("m1")

    assert isinstance(message, Message)
    assert message.id == "m1"
    assert message.path == "/users/u1/mailFolders/f1/messages/m1"


def test_message_queryset_by_id_requires_id(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP call expected")

    client, _ = make_client(handler)
    user = client.users.make(id="u1")

    with pytest.raises(ValueError, match="requires a message id"):
        user.messages.by_id("")


def test_field_mail_folders(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    c, _ = make_client(handler)
    u = c.users.make(id="u1")

    qs = u.mail_folders
    assert isinstance(qs, MailFolderQuerySet)
    assert qs.path == "/users/u1/mailFolders"
    assert qs._model_class is MailFolder


def test_field_mail_folders_upn_path(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    c, _ = make_client(handler)
    u = c.users.make(user_principal_name="alice@contoso.com")

    qs = u.mail_folders
    assert isinstance(qs, MailFolderQuerySet)
    assert qs.path == "/users/alice@contoso.com/mailFolders"
    assert qs._model_class is MailFolder


def test_mail_folder_messages(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    client, _ = make_client(handler)
    folder = MailFolder(id="f1", client=client, path="/users/u1/mailFolders")

    qs = folder.messages

    assert isinstance(qs, MessageQuerySet)
    assert qs.path == "/users/u1/mailFolders/f1/messages"
    assert qs._model_class is Message


def test_mail_folder_child_folders(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    client, _ = make_client(handler)
    folder = MailFolder(id="f1", client=client, path="/users/u1/mailFolders")

    qs = folder.child_folders

    assert isinstance(qs, MailFolderQuerySet)
    assert qs.path == "/users/u1/mailFolders/f1/childFolders"
    assert qs._model_class is MailFolder


@pytest.mark.asyncio
async def test_field_messages_list(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP call expected")

    client, _ = make_client(handler)
    user = client.users._model_class.from_graph(
        {
            "id": "u1",
            "messages": [
                {
                    "id": "m1",
                    "subject": "Hello",
                    "isRead": False,
                    "receivedDateTime": "2026-02-20T00:00:00Z",
                }
            ],
        },
        client=client,
    )

    items = [obj async for obj in user.messages]

    assert len(items) == 1
    assert isinstance(items[0], Message)
    assert items[0].id == "m1"
    assert items[0].subject == "Hello"
    assert items[0].is_read is False


@pytest.mark.asyncio
async def test_field_mail_folders_list(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP call expected")

    client, _ = make_client(handler)
    user = client.users._model_class.from_graph(
        {
            "id": "u1",
            "mailFolders": [
                {
                    "id": "f1",
                    "displayName": "Inbox",
                    "totalItemCount": 10,
                    "unreadItemCount": 3,
                }
            ],
        },
        client=client,
    )

    items = [obj async for obj in user.mail_folders]

    assert len(items) == 1
    assert isinstance(items[0], MailFolder)
    assert items[0].id == "f1"
    assert items[0].display_name == "Inbox"
    assert items[0].total_item_count == 10
    assert items[0].unread_item_count == 3


@pytest.mark.asyncio
async def test_mail_folder_messages_list(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP call expected")

    client, _ = make_client(handler)
    folder = MailFolder.from_graph(
        {
            "id": "f1",
            "displayName": "Test Folder",
            "messages": [
                {
                    "id": "m1",
                    "subject": "Nested message",
                    "isRead": True,
                    "receivedDateTime": "2026-02-20T00:00:00Z",
                }
            ],
        },
        client=client,
        path="/users/u1/mailFolders",
    )

    items = [obj async for obj in folder.messages]

    assert len(items) == 1
    assert isinstance(items[0], Message)
    assert items[0].id == "m1"
    assert items[0].subject == "Nested message"
    assert items[0].is_read is True


@pytest.mark.asyncio
async def test_mail_folder_child_folders_list(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP call expected")

    client, _ = make_client(handler)
    folder = MailFolder.from_graph(
        {
            "id": "f1",
            "displayName": "Inbox",
            "childFolders": [
                {
                    "id": "f2",
                    "displayName": "Test Folder",
                    "totalItemCount": 5,
                    "unreadItemCount": 1,
                }
            ],
        },
        client=client,
        path="/users/u1/mailFolders",
    )

    items = [obj async for obj in folder.child_folders]

    assert len(items) == 1
    assert isinstance(items[0], MailFolder)
    assert items[0].id == "f2"
    assert items[0].display_name == "Test Folder"
    assert items[0].total_item_count == 5
    assert items[0].unread_item_count == 1


def test_message_attachments_queryset(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    client, _ = make_client(handler)
    message = Message(id="m1", client=client, path="/users/u1/messages")

    qs = message.attachments

    assert isinstance(qs, AttachmentQuerySet)
    assert qs.path == "/users/u1/messages/m1/attachments"
    assert qs._model_class is Attachment


@pytest.mark.asyncio
async def test_message_attachments_list_uses_cached_data(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP call expected")

    client, _ = make_client(handler)
    message = Message.from_graph(
        {
            "id": "m1",
            "attachments": [
                {
                    "id": "a1",
                    "name": "report.txt",
                    "size": 42,
                    "contentType": "text/plain",
                }
            ],
        },
        client=client,
        path="/users/u1/messages",
    )

    items = [obj async for obj in message.attachments]

    assert len(items) == 1
    assert isinstance(items[0], Attachment)
    assert items[0].id == "a1"
    assert items[0].name == "report.txt"
    assert items[0].size == 42
    assert items[0].content_type == "text/plain"


@pytest.mark.asyncio
async def test_message_attachments_empty_list_uses_cached_data(
    make_client: "MakeClient",
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP call expected")

    client, _ = make_client(handler)
    message = Message.from_graph(
        {"id": "m1", "attachments": []},
        client=client,
        path="/users/u1/messages",
    )

    items = [obj async for obj in message.attachments]

    assert items == []


@pytest.mark.asyncio
async def test_message_attachments_download_from_content_bytes(
    make_client: "MakeClient",
) -> None:
    raw = b"hello-attachment"
    encoded = base64.b64encode(raw).decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP call expected")

    client, _ = make_client(handler)
    message = Message.from_graph(
        {
            "id": "m1",
            "attachments": [
                {
                    "id": "a1",
                    "name": "note.txt",
                    "contentBytes": encoded,
                }
            ],
        },
        client=client,
        path="/users/u1/messages",
    )

    downloaded = await message.attachments.download()

    assert downloaded == {"a1": raw}


@pytest.mark.asyncio
async def test_message_attachments_download_fetches_value_and_writes_files(
    make_client: "MakeClient", tmp_path: Path
) -> None:
    raw = b"from-value-endpoint"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users/u1/messages/m1/attachments":
            return httpx.Response(
                200,
                json={"value": [{"id": "a1", "name": "doc.txt"}]},
            )
        if request.method == "GET" and request.url.path == "/v1.0/users/u1/messages/m1/attachments/a1/$value":
            return httpx.Response(200, content=raw)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client, _ = make_client(handler)
    message = Message(id="m1", client=client, path="/users/u1/messages")

    downloaded = await message.attachments.download(tmp_path)

    assert downloaded == {"a1": raw}
    assert (tmp_path / "doc.txt").read_bytes() == raw


def test_message_attachments_requires_id(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    client, _ = make_client(handler)
    message = Message(client=client, path="/users/u1/messages")

    with pytest.raises(AttributeError):
        _ = message.attachments


@pytest.mark.asyncio
async def test_message_move(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "POST"
            and request.url.path == "/v1.0/users/u1/messages/m1/move"
        ):
            body = json.loads(request.content.decode())
            assert body == {"destinationId": "folder-archive"}
            return httpx.Response(
                201,
                json={
                    "id": "m1",
                    "subject": "Hello",
                    "parentFolderId": "folder-archive",
                },
            )

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client, _ = make_client(handler)
    message = Message(id="m1", client=client, path="/users/u1/messages")

    moved = await message.move("folder-archive")

    assert isinstance(moved, Message)
    assert moved.id == "m1"
    assert moved.subject == "Hello"
    assert moved.parent_folder_id == "folder-archive"
    assert moved.path == "/users/u1/messages/m1"


@pytest.mark.asyncio
async def test_message_download(make_client: "MakeClient") -> None:
    raw = b"From: sender@example.com\r\nSubject: Hello\r\n\r\nBody"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users/u1/messages/m1/$value":
            return httpx.Response(200, content=raw)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client, _ = make_client(handler)
    message = Message(id="m1", client=client, path="/users/u1/messages")

    data = await message.download()

    assert data == raw


@pytest.mark.asyncio
async def test_message_download_to_path(
    make_client: "MakeClient", tmp_path: Path
) -> None:
    raw = b"From: sender@example.com\r\nSubject: Hello\r\n\r\nBody"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users/u1/messages/m1/$value":
            return httpx.Response(200, content=raw)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client, _ = make_client(handler)
    message = Message(id="m1", client=client, path="/users/u1/messages")
    out = tmp_path / "message.eml"

    data = await message.download(out)

    assert data == raw
    assert out.read_bytes() == raw


@pytest.mark.asyncio
async def test_message_move_requires_destination_id(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP should not be called")

    client, _ = make_client(handler)
    message = Message(id="m1", client=client, path="/users/u1/messages")

    with pytest.raises(ValueError, match="destination_id is required"):
        await message.move("")


@pytest.mark.asyncio
async def test_assign_manager(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "PUT"
            and request.url.path == "/v1.0/users/u1/manager/$ref"
        ):
            body = json.loads(request.content.decode())
            assert body == {
                "@odata.id": "https://graph.microsoft.com/v1.0/directoryObjects/m1"
            }
            return httpx.Response(204, json={})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    user = c.users.make(id="u1")

    await user.assign_manager("m1")


@pytest.mark.asyncio
async def test_assign_manager_uses_cache(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "PUT"
            and request.url.path == "/v1.0/users/u1/manager/$ref"
        ):
            body = json.loads(request.content.decode())
            assert body == {
                "@odata.id": "https://graph.microsoft.com/v1.0/directoryObjects/m1"
            }
            return httpx.Response(204, json={})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    user = c.users.make(id="u1")
    c.users._cache.set("manager@example.com", "m1")

    await user.assign_manager("manager@example.com")


@pytest.mark.asyncio
async def test_qs_assign_manager(make_client: "MakeClient") -> None:
    batch_requests: list[list[dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users":
            return httpx.Response(200, json={"value": [{"id": "u1"}, {"id": "u2"}]})

        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            batch_requests.append(body.get("requests", []))
            return httpx.Response(200, json={"responses": [{"id": "1", "status": 204}]})

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    await c.users.assign_manager("m1")

    assert len(batch_requests) == 1
    requests = batch_requests[0]
    assert {req["method"] for req in requests} == {"PUT"}
    assert {req["url"] for req in requests} == {
        "/users/u1/manager/$ref",
        "/users/u2/manager/$ref",
    }
    for req in requests:
        assert req["body"] == {
            "@odata.id": "https://graph.microsoft.com/v1.0/directoryObjects/m1"
        }


@pytest.mark.asyncio
async def test_field_app_role_assignments_list(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP call expected")

    client, _ = make_client(handler)
    user = client.users._model_class.from_graph(
        {
            "id": "u1",
            "appRoleAssignments": [
                {
                    "appRoleId": "role1",
                    "principalDisplayName": "Ada Lovelace",
                    "principalId": "u1",
                    "principalType": "User",
                    "resourceDisplayName": "Contoso App",
                    "resourceId": "res1",
                }
            ],
        },
        client=client,
    )

    items = [obj async for obj in user.app_role_assignments]

    assert len(items) == 1
    assert isinstance(items[0], AppRoleAssignment)
    assert items[0].app_role_id == "role1"
    assert items[0].principal_display_name == "Ada Lovelace"
    assert items[0].principal_id == "u1"
    assert items[0].principal_type == "User"
    assert items[0].resource_display_name == "Contoso App"
    assert items[0].resource_id == "res1"


@pytest.mark.asyncio
async def test_field_app_role_assignments_add(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            assert body == {
                "requests": [
                    {
                        "id": "1",
                        "method": "POST",
                        "url": "/servicePrincipals/sp1/appRoleAssignedTo",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "principalId": "u1",
                            "resourceId": "sp1",
                            "appRoleId": "role1",
                        },
                    }
                ]
            }
            return httpx.Response(
                200,
                json={
                    "responses": [
                        {
                            "id": "1",
                            "status": 201,
                            "body": {
                                "id": "ara1",
                                "appRoleId": "role1",
                                "principalDisplayName": "Alice",
                                "principalId": "u1",
                                "principalType": "User",
                                "resourceDisplayName": "Contoso App",
                                "resourceId": "sp1",
                            },
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    user = c.users.make(id="u1")

    await user.app_role_assignments.add({"resource_id": "sp1", "app_role_id": "role1"})

    # assert assignment is not None
    # assert assignment.resource_id == "sp1"
    # assert assignment.principal_id == "u1"


@pytest.mark.asyncio
async def test_field_app_role_assignments_remove(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            assert body == {
                "requests": [
                    {
                        "id": "1",
                        "method": "DELETE",
                        "url": "/servicePrincipals/sp1/appRoleAssignedTo/ara1",
                    }
                ]
            }
            return httpx.Response(
                200,
                json={"responses": [{"id": "1", "status": 204}]},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    user = c.users.make(id="u1")

    await user.app_role_assignments.remove({"id": "ara1", "resource_id": "sp1"})


@pytest.mark.asyncio
async def test_field_assigned_licenses_list(
    make_client: "MakeClient",
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP call expected")

    client, _ = make_client(handler)
    qs = client.users
    user = qs._model_class.from_graph(
        {
            "id": "u1",
            "assignedLicenses": [{"disabledPlans": [], "skuId": "skuId1"}],
        },
        client=client,
    )

    qs = user.assigned_licenses
    items = [obj async for obj in qs]

    assert len(items) == 1
    assert isinstance(items[0], AssignedLicense)
    assert items[0].sku_id == "skuId1"
    assert items[0].disabled_plans == []


@pytest.mark.asyncio
async def test_field_assigned_licenses_add_remove(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/subscribedSkus":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "skuId": "sku1",
                            "consumedUnits": 0,
                            "prepaidUnits": {"enabled": 2, "warning": 0},
                        }
                    ]
                },
            )
        body = json.loads(request.content.decode())
        assert request.method == "POST"
        assert request.url.path == "/v1.0/users/123/assignLicense"
        if body["addLicenses"]:
            assert body == {
                "addLicenses": [{"skuId": "sku1", "disabledPlans": []}],
                "removeLicenses": [],
            }
        else:
            assert body == {
                "addLicenses": [],
                "removeLicenses": ["sku1"],
            }
        return httpx.Response(200, json={"responses": [{"id": "1", "status": 200}]})

    c, _ = make_client(handler)
    u = c.users.make(id="123", display_name="Alice")
    await u.assigned_licenses.add("sku1")
    await u.assigned_licenses.remove("sku1")


@pytest.mark.asyncio
async def test_field_assigned_licenses_add_checks_available(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/subscribedSkus":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "skuId": "sku1",
                            "consumedUnits": 1,
                            "prepaidUnits": {"enabled": 2, "warning": 0},
                        }
                    ]
                },
            )
        if (
            request.method == "POST"
            and request.url.path == "/v1.0/users/123/assignLicense"
        ):
            body = json.loads(request.content.decode())
            assert body == {
                "addLicenses": [{"skuId": "sku1", "disabledPlans": []}],
                "removeLicenses": [],
            }
            return httpx.Response(200, json={})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    u = c.users.make(id="123", display_name="Alice")

    await u.assigned_licenses.add("sku1")

    cached: Any | None = await c.subscribed_skus._cache.get("sku1")
    if cached is None:
        raise AssertionError("SubscribedSku not cached")
    assert cached.consumed_units == 2


@pytest.mark.asyncio
async def test_field_assigned_licenses_add_insufficient(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/subscribedSkus":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "skuId": "sku1",
                            "consumedUnits": 2,
                            "prepaidUnits": {"enabled": 2, "warning": 0},
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    u = c.users.make(id="123", display_name="Alice")

    with pytest.raises(ValueError, match="No available units"):
        await u.assigned_licenses.add("sku1")


def test_qs_filter_assigned_licenses(users_qs: UserQuerySet):

    qs = users_qs._clone()
    # params = (
    #     qs._clone()
    #     .assigned_licenses.filter(sku_id="cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46")
    #     ._build_params()
    # )
    # assert (
    #     params["$filter"]
    #     == "(assignedLicenses/any(u:u/skuId eq 'cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46'))"
    # )

    # params = (
    #     qs._clone()
    #     .assigned_licenses.filter(sku_id__exact="cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46")
    #     ._build_params()
    # )
    # assert (
    #     params["$filter"]
    #     == "(assignedLicenses/any(u:u/skuId eq 'cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46'))"
    # )

    # params = qs._clone().assigned_licenses.filter(isnull=True)._build_params()
    # assert params["$filter"] == "(assignedLicenses/$count eq 0)"

    # params = qs._clone().assigned_licenses.filter(isnull=False)._build_params()
    # assert params["$filter"] == "(assignedLicenses/$count ne 0)"

    params = (
        qs._clone()
        .filter(assigned_licenses__sku_id__exact="cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46")
        ._build_params()
    )
    assert (
        params["$filter"]
        == "(assignedLicenses/any(u:u/skuId eq 'cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46'))"
    )

    params = qs._clone().filter(assigned_licenses__isnull=True)._build_params()
    assert params["$filter"] == "(assignedLicenses/$count eq 0)"

    params = qs._clone().filter(assigned_licenses__isnull=False)._build_params()
    assert params["$filter"] == "(assignedLicenses/$count ne 0)"


def test_qs_filter_list_field(users_qs: UserQuerySet):
    params = (
        users_qs._clone()
        .filter(proxy_addresses="SMTP:admin@contoso.com")
        ._build_params()
    )
    assert params["$filter"] == "(proxyAddresses/any(i:i eq 'SMTP:admin@contoso.com'))"

    params = (
        users_qs._clone().filter(proxy_addresses__startswith="SMTP:")._build_params()
    )
    assert params["$filter"] == "(proxyAddresses/any(i:startswith(i, 'SMTP:')))"

    params = users_qs._clone().filter(proxy_addresses__isnull=True)._build_params()
    assert params["$filter"] == "(proxyAddresses/$count eq 0)"


@pytest.mark.asyncio
async def test_qs_assigned_licenses_proxy_add_remove(make_client: "MakeClient"):
    batch_requests: list[list[dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/subscribedSkus":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "skuId": "sku1",
                            "consumedUnits": 0,
                            "prepaidUnits": {"enabled": 10, "warning": 0},
                        },
                        {
                            "skuId": "sku2",
                            "consumedUnits": 0,
                            "prepaidUnits": {"enabled": 10, "warning": 0},
                        },
                    ]
                },
            )
        if request.method == "GET" and request.url.path == "/v1.0/users":
            return httpx.Response(200, json={"value": [{"id": "u1"}, {"id": "u2"}]})

        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            batch_requests.append(body.get("requests", []))
            return httpx.Response(200, json={"responses": [{"id": "1", "status": 200}]})

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    qs = c.users

    result = await qs.assigned_licenses.add("sku1")
    assert result == {"sku1": {"assigned": 2, "skipped": 0}}
    await qs.assigned_licenses.remove("sku2")

    # Two batch calls: add then remove
    assert len(batch_requests) == 2
    add_requests, remove_requests = batch_requests

    assert {req["method"] for req in add_requests} == {"POST"}
    assert {req["url"] for req in add_requests} == {
        "/users/u1/assignLicense",
        "/users/u2/assignLicense",
    }
    for req in add_requests:
        assert req.get("body") == {
            "addLicenses": [{"skuId": "sku1", "disabledPlans": []}],
            "removeLicenses": [],
        }

    assert {req["method"] for req in remove_requests} == {"POST"}
    assert {req["url"] for req in remove_requests} == {
        "/users/u1/assignLicense",
        "/users/u2/assignLicense",
    }
    for req in remove_requests:
        assert req.get("body") == {
            "addLicenses": [],
            "removeLicenses": ["sku2"],
        }


@pytest.mark.asyncio
async def test_qs_reset_password(make_client: "MakeClient", tmp_path: "Path") -> None:
    batch_requests: list[list[dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "u1",
                            "displayName": "Alice",
                            "userPrincipalName": "alice@example.com",
                            "mobilePhone": "111",
                        },
                        {
                            "id": "u2",
                            "displayName": "Bob",
                            "userPrincipalName": "bob@example.com",
                            "mobilePhone": "222",
                        },
                    ]
                },
            )

        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            batch_requests.append(body.get("requests", []))
            return httpx.Response(200, json={"responses": [{"id": "1", "status": 204}]})

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    out = tmp_path / "reset_passwords.csv"

    await c.users.reset_password(
        str(out),
        password="Pass@word1",
        force_change_password_next_sign_in=False,
    )

    assert len(batch_requests) == 1
    requests = batch_requests[0]
    assert {req["method"] for req in requests} == {"PATCH"}
    assert {req["url"] for req in requests} == {"/users/u1", "/users/u2"}
    for req in requests:
        profile = req.get("body", {}).get("passwordProfile", {})
        assert profile.get("password") == "Pass@word1"
        assert profile.get("forceChangePasswordNextSignIn") is False

    import csv

    with out.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    assert [r["id"] for r in rows] == ["u1", "u2"]
    assert [r["display_name"] for r in rows] == ["Alice", "Bob"]
    assert [r["user_principal_name"] for r in rows] == [
        "alice@example.com",
        "bob@example.com",
    ]
    assert [r["mobile_phone"] for r in rows] == ["111", "222"]
    assert all(r["password"] == "Pass@word1" for r in rows)


@pytest.mark.asyncio
async def test_qs_app_role_assignments_proxy_add(make_client: "MakeClient") -> None:
    batch_requests: list[list[dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users":
            return httpx.Response(200, json={"value": [{"id": "u1"}, {"id": "u2"}]})

        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            batch_requests.append(body.get("requests", []))
            return httpx.Response(200, json={"responses": [{"id": "1", "status": 201}]})

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    qs = c.users

    await qs.app_role_assignments.add({"resource_id": "sp1", "app_role_id": "role1"})

    assert len(batch_requests) == 1
    add_requests = batch_requests[0]
    assert {req["method"] for req in add_requests} == {"POST"}
    assert {req["url"] for req in add_requests} == {
        "/servicePrincipals/sp1/appRoleAssignedTo",
    }
    bodies = {tuple(sorted(req.get("body", {}).items())) for req in add_requests}
    assert bodies == {
        tuple(
            sorted(
                {
                    "principalId": "u1",
                    "resourceId": "sp1",
                    "appRoleId": "role1",
                }.items()
            )
        ),
        tuple(
            sorted(
                {
                    "principalId": "u2",
                    "resourceId": "sp1",
                    "appRoleId": "role1",
                }.items()
            )
        ),
    }


@pytest.mark.asyncio
async def test_qs_app_role_assignments_proxy_remove(make_client: "MakeClient") -> None:
    batch_requests: list[list[dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users":
            return httpx.Response(200, json={"value": [{"id": "u1"}, {"id": "u2"}]})

        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            batch_requests.append(body.get("requests", []))

            requests = body.get("requests", [])
            if requests and requests[0].get("method") == "GET":
                return httpx.Response(
                    200,
                    json={
                        "responses": [
                            {
                                "id": "1",
                                "status": 200,
                                "body": {
                                    "value": [
                                        {
                                            "id": "ara1",
                                            "resourceId": "sp1",
                                            "appRoleId": "role1",
                                        }
                                    ]
                                },
                            },
                            {
                                "id": "2",
                                "status": 200,
                                "body": {
                                    "value": [
                                        {
                                            "id": "ara2",
                                            "resourceId": "sp1",
                                            "appRoleId": "role1",
                                        }
                                    ]
                                },
                            },
                        ]
                    },
                )
            return httpx.Response(200, json={"responses": [{"id": "1", "status": 204}]})

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    qs = c.users

    await qs.app_role_assignments.remove({"resource_id": "sp1", "app_role_id": "role1"})

    assert len(batch_requests) == 2
    list_requests, delete_requests = batch_requests

    assert {req["method"] for req in list_requests} == {"GET"}
    assert {req["url"] for req in list_requests} == {
        "/users/u1/appRoleAssignments",
        "/users/u2/appRoleAssignments",
    }

    assert {req["method"] for req in delete_requests} == {"DELETE"}
    assert {req["url"] for req in delete_requests} == {
        "/servicePrincipals/sp1/appRoleAssignedTo/ara1",
        "/servicePrincipals/sp1/appRoleAssignedTo/ara2",
    }


@pytest.mark.asyncio
async def test_qs_bulk_update(make_client: "MakeClient") -> None:
    seen_batches: list[list[dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {"id": "u1"},
                        {"id": "u2"},
                        {"id": "u3"},
                    ]
                },
            )
        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            seen_batches.append(body.get("requests", []))
            return httpx.Response(200, json={"responses": [{"id": "1", "status": 200}]})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    updated = await c.users.update(company_name="Contoso", city="Auckland")

    assert updated == 3
    # One batch with 3 PATCH requests
    assert len(seen_batches) == 1
    requests = seen_batches[0]
    assert {req["method"] for req in requests} == {"PATCH"}
    assert {req["url"] for req in requests} == {
        "/users/u1",
        "/users/u2",
        "/users/u3",
    }
    for req in requests:
        assert req.get("headers", {}).get("Content-Type") == "application/json"
        assert req.get("body") == {
            "companyName": "Contoso",
            "city": "Auckland",
        }


@pytest.mark.asyncio
async def test_field_member_of_groups_cached_data(
    make_client: "MakeClient",
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP call expected")

    client, _ = make_client(handler)
    user = client.users.make_from_graph(
        {
            "id": "u1",
            "displayName": "User One",
            "memberOf": [
                {
                    "@odata.type": "#microsoft.graph.group",
                    "id": "g1",
                    "displayName": "Group One",
                },
                {
                    "@odata.type": "#microsoft.graph.directoryRole",
                    "id": "r1",
                    "displayName": "Role One",
                },
            ],
        },
    )

    groups = [g async for g in user.member_of.groups]
    assert len(groups) == 1
    assert isinstance(groups[0], Group)
    assert groups[0].id == "g1"


@pytest.mark.asyncio
async def test_field_member_of_polymorphic_models(
    make_client: "MakeClient",
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP call expected")

    client, _ = make_client(handler)
    user = client.users.make_from_graph(
        {
            "id": "u1",
            "displayName": "User One",
            "memberOf": [
                {
                    "@odata.type": "#microsoft.graph.group",
                    "id": "g1",
                    "displayName": "Group One",
                },
                {
                    "@odata.type": "#microsoft.graph.directoryRole",
                    "id": "r1",
                    "displayName": "Role One",
                },
            ],
        },
    )

    items = [i async for i in user.member_of]
    assert len(items) == 2
    assert isinstance(items[0], Group)
    assert isinstance(items[1], DirectoryObject)


def test_field_member_of_groups(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    c, _ = make_client(handler)
    u = c.users.make(id="u1")

    member_of_qs: MemberOfQuerySet = u.member_of
    assert isinstance(member_of_qs, MemberOfQuerySet)
    assert member_of_qs.path == "/users/u1/memberOf"
    assert member_of_qs._model_class is DirectoryObject

    groups_qs: GroupsQuerySet = u.member_of.groups
    assert isinstance(groups_qs, GroupsQuerySet)
    assert groups_qs.path == "/users/u1/memberOf/microsoft.graph.group"
    assert groups_qs._model_class is Group


@pytest.mark.asyncio
async def test_field_member_of_groups_add_remove(make_client: "MakeClient"):
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        seen.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            requests = body.get("requests", [])
            first_method = requests[0]["method"] if requests else None
            if first_method == "POST":
                assert requests == [
                    {
                        "id": "1",
                        "method": "POST",
                        "url": "/groups/g1/members/$ref",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "@odata.id": "https://graph.microsoft.com/v1.0/directoryObjects/123"
                        },
                    },
                ]
            elif first_method == "DELETE":
                assert requests == [
                    {
                        "id": "1",
                        "method": "DELETE",
                        "url": "/groups/g1/members/123/$ref",
                    }
                ]
            else:
                raise AssertionError(f"Unexpected batch payload: {requests}")
            return httpx.Response(200, json={"responses": [{"id": "1", "status": 204}]})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, r = make_client(handler)
    u = c.users.make(id="123", display_name="Alice")
    await u.member_of.groups.add("g1")
    await u.member_of.groups.remove("g1")

    assert seen == [
        ("POST", "/v1.0/$batch"),
        ("POST", "/v1.0/$batch"),
    ]
    assert len(r) == 2


@pytest.mark.asyncio
async def test_field_member_of_groups_add_remove_multiple(make_client: "MakeClient"):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            seen.append(body.get("requests", []))
            return httpx.Response(200, json={"responses": [{"id": "1", "status": 204}]})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, r = make_client(handler)
    user = c.users.make(id="123", display_name="Alice")
    await user.member_of.groups.add("g1", Group(id="g2"))
    await user.member_of.groups.remove("g1", Group(id="g2"))

    # Two batch calls: add then remove
    assert len(seen) == 2
    add_requests, remove_requests = seen

    # Add batch: two POSTs to /groups/{gid}/members/$ref with correct body
    assert {req["method"] for req in add_requests} == {"POST"}
    assert {req["url"] for req in add_requests} == {
        "/groups/g1/members/$ref",
        "/groups/g2/members/$ref",
    }
    for req in add_requests:
        assert req.get("headers", {}).get("Content-Type") == "application/json"
        assert req.get("body") == {
            "@odata.id": "https://graph.microsoft.com/v1.0/directoryObjects/123"
        }

    # Remove batch: two DELETEs to /groups/{gid}/members/{uid}/$ref
    assert {req["method"] for req in remove_requests} == {"DELETE"}
    assert {req["url"] for req in remove_requests} == {
        "/groups/g1/members/123/$ref",
        "/groups/g2/members/123/$ref",
    }

    assert len(r) == 2


@pytest.mark.asyncio
async def test_field_member_of_groups_copy_to(make_client: "MakeClient") -> None:
    seen_batches: list[list[dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and request.url.path == "/v1.0/users/u1/memberOf/microsoft.graph.group"
        ):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "g1",
                            "displayName": "Dist",
                            "mailEnabled": True,
                            "securityEnabled": False,
                        },
                        {
                            "id": "g2",
                            "displayName": "Sec",
                            "mailEnabled": False,
                            "securityEnabled": True,
                        },
                    ]
                },
            )
        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            seen_batches.append(body.get("requests", []))
            return httpx.Response(200, json={"responses": [{"id": "1", "status": 204}]})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    user = c.users.make(id="u1", display_name="User One")

    await user.member_of.groups.copy_to("u2")

    assert len(seen_batches) == 1
    requests = seen_batches[0]
    assert requests == [
        {
            "id": "1",
            "method": "POST",
            "url": "/groups/g2/members/$ref",
            "headers": {"Content-Type": "application/json"},
            "body": {
                "@odata.id": "https://graph.microsoft.com/v1.0/directoryObjects/u2"
            },
        }
    ]


@pytest.mark.asyncio
async def test_qs_get_by_id(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1.0/users/abc"
        return httpx.Response(
            200,
            json={
                "id": "abc",
                "accountEnabled": "true",
                "displayName": "Bob",
                "userPrincipalName": "bob@example.com",
                "mailNickname": "bob",
            },
        )

    c, _ = make_client(handler)
    qs = c.users
    user = await qs.get(id="abc")
    assert user is not None
    assert user.id == "abc"
    assert user.display_name == "Bob"
    assert user.user_principal_name == "bob@example.com"
    assert user.account_enabled is True


@pytest.mark.asyncio
async def test_delete_missing_id(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP should not be called")

    c, _ = make_client(handler)
    user = c.users.make(display_name="Alice")
    with pytest.raises(AttributeError):
        await user.delete(force=True)


@pytest.mark.asyncio
async def test_force_delete(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/v1.0/users/u_del"
        return httpx.Response(204)

    c, _ = make_client(handler)
    user = c.users.make_from_graph(
        {
            "id": "u_del",
            "displayName": "Del",
            "userPrincipalName": "del@example.com",
            "accountEnabled": True,
            "mailNickname": "del",
        }
    )

    await user.delete(force=True)
    assert user.id is None


@pytest.mark.asyncio
async def test_delete(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP should not be called")

    c, _ = make_client(handler)
    user = c.users._model_class.from_graph(
        {
            "id": "u_del",
            "displayName": "Del",
            "userPrincipalName": "del@example.com",
            "accountEnabled": True,
            "mailNickname": "del",
        }
    )
    with pytest.raises(RuntimeError):
        await user.delete()


# def test_select_related_prefetch_licenses(make_client: "MakeClient"):
#     def handler(request: httpx.Request) -> httpx.Response:
#         if request.url.path == "/v1.0/users":
#             return httpx.Response(
#                 200,
#                 json={
#                     "value": [
#                         {"id": "u1", "displayName": "User 1"},
#                         {"id": "u2", "displayName": "User 2"},
#                     ]
#                 },
#             )
#         if request.url.path == "/v1.0/$batch":
#             body = json.loads(request.content.decode())
#             assert len(body.get("requests", [])) == 2
#             responses = [
#                 {"id": "1", "status": 200, "body": {"value": [{"skuId": "sku1"}]}},
#                 {"id": "2", "status": 200, "body": {"value": [{"skuId": "sku2"}]}},
#             ]
#             return httpx.Response(200, json={"responses": responses})
#         return httpx.Response(404)

#     c, _ = make_client(handler)

#     users = list(c.users.select_related("licenses"))
#     assert [u.id for u in users] == ["u1", "u2"]

#     assert [l.sku_id for l in users[0].licenses] == ["sku1"]
#     assert [l.sku_id for l in users[1].licenses] == ["sku2"]
