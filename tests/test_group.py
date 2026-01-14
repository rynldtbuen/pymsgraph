import json
from typing import TYPE_CHECKING

import httpx
import pytest

from pymsgraph.models.group import Group
from pymsgraph.models.group.query_fields import UsersQuerySet
from pymsgraph.models.user import User

if TYPE_CHECKING:
    from tests.conftest import MakeClient


def test_group_type() -> None:
    g = Group(group_types=["Unified"], mail_enabled=True, security_enabled=False)
    assert g.group_type == Group.MICROSOFT365

    g = Group(mail_enabled=True, security_enabled=True)
    assert g.group_type == Group.SECURITY_MAIL_ENABLED

    g = Group(mail_enabled=False, security_enabled=True)
    assert g.group_type == Group.SECURITY

    g = Group(mail_enabled=True, security_enabled=False)
    assert g.group_type == Group.DISTRIBUTION

    g = Group(mail_enabled=False, security_enabled=False)
    assert g.group_type == "unknown"


def test_qs_select_build_params(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    c, _ = make_client(handler)
    params = c.groups._clone()._build_params()
    assert (
        params["$select"]
        == "displayName,groupTypes,id,mail,mailEnabled,securityEnabled"
    )


@pytest.mark.asyncio
async def test_qs_create_security_group(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1.0/groups"
        body = json.loads(request.content.decode())
        assert body == {
            "displayName": "Group One",
            "mailEnabled": False,
            "mailNickname": "group-one",
            "securityEnabled": True,
        }
        return httpx.Response(201, json={"id": "g1", "displayName": "Group One"})

    c, _ = make_client(handler)
    g = await c.groups.create_security_group(
        display_name="Group One",
        mail_nickname="group-one",
    )

    assert g.id == "g1"
    assert g.display_name == "Group One"
    assert g.path == "/groups/g1"


@pytest.mark.asyncio
async def test_qs_create_m365_group(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1.0/groups"
        body = json.loads(request.content.decode())
        assert body == {
            "displayName": "Group Two",
            "groupTypes": ["Unified"],
            "mailEnabled": True,
            "mailNickname": "group-two",
            "securityEnabled": False,
            "visibility": "Private",
        }
        return httpx.Response(201, json={"id": "g2", "displayName": "Group Two"})

    c, _ = make_client(handler)
    g = await c.groups.create_m365_group(
        display_name="Group Two",
        mail_nickname="group-two",
        visibility="Private",
    )

    assert g.id == "g2"
    assert g.display_name == "Group Two"
    assert g.path == "/groups/g2"


@pytest.mark.asyncio
async def test_field_members_add_remove(make_client: "MakeClient") -> None:
    seen: list[list[dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            seen.append(body.get("requests", []))
            return httpx.Response(200, json={"responses": [{"id": "1", "status": 204}]})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    group = c.groups.make(id="g1", display_name="Group One")

    await group.members.add("u1")
    await group.members.remove("u1")

    assert len(seen) == 2
    add_requests, remove_requests = seen

    assert add_requests == [
        {
            "id": "1",
            "method": "POST",
            "url": "/groups/g1/members/$ref",
            "headers": {"Content-Type": "application/json"},
            "body": {
                "@odata.id": "https://graph.microsoft.com/v1.0/directoryObjects/u1"
            },
        }
    ]

    assert remove_requests == [
        {
            "id": "1",
            "method": "DELETE",
            "url": "/groups/g1/members/u1/$ref",
        }
    ]


@pytest.mark.asyncio
async def test_field_members_copy_to(make_client: "MakeClient") -> None:
    seen_batches: list[list[dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/groups/g1/members":
            return httpx.Response(200, json={"value": [{"id": "u1"}, {"id": "u2"}]})
        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            seen_batches.append(body.get("requests", []))
            return httpx.Response(200, json={"responses": [{"id": "1", "status": 204}]})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    group = c.groups.make(id="g1", display_name="Group One")

    await group.members.copy_to("g2")

    assert len(seen_batches) == 1
    requests = seen_batches[0]
    assert {r["url"] for r in requests} == {
        "/groups/g2/members/$ref",
    }
    assert {r["method"] for r in requests} == {"POST"}
    assert requests[0]["body"] == {
        "@odata.id": "https://graph.microsoft.com/v1.0/directoryObjects/u1"
    }
    assert requests[1]["body"] == {
        "@odata.id": "https://graph.microsoft.com/v1.0/directoryObjects/u2"
    }


def test_field_members_users(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    c, _ = make_client(handler)
    group = c.groups.make(id="g1", display_name="Group One")

    users_qs = group.members.users
    assert isinstance(users_qs, UsersQuerySet)
    assert users_qs.path == "/groups/g1/members/microsoft.graph.user"
    assert users_qs._model_class is User


@pytest.mark.asyncio
async def test_field_members_users_cached_data(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP call expected")

    c, _ = make_client(handler)
    group = c.groups.make_from_graph(
        {
            "id": "g1",
            "displayName": "Group One",
            "members": [
                {
                    "@odata.type": "#microsoft.graph.user",
                    "id": "u1",
                    "displayName": "User One",
                },
                {
                    "@odata.type": "#microsoft.graph.group",
                    "id": "g2",
                    "displayName": "Group Two",
                },
            ],
        }
    )

    items = [u async for u in group.members.users]
    assert len(items) == 1
    assert isinstance(items[0], User)
    assert items[0].id == "u1"
