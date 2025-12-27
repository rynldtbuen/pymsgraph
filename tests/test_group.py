from __future__ import annotations
import json
from typing import TYPE_CHECKING

import httpx
import pytest

from pymsgraph.query import Q
from tests.utils import read_json

if TYPE_CHECKING:
    from .conftest import MakeClient


def test_create(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1.0/groups"

        body = read_json(request)

        # normalization
        assert body["displayName"] == "My Security Group"
        assert body["mailEnabled"] is False
        assert body["mailNickname"] == "mysecuritygroup"
        assert body["securityEnabled"] is True
        assert body["description"] == "desc"

        return httpx.Response(201, json={"id": "g_123", **body})

    c, _ = make_client(handler)
    g = c.groups.create(
        display_name="  My Security Group  ",
        mail_enabled=False,
        mail_nickname="mysecuritygroup",
        security_enabled=True,
        description="  desc  ",
    )
    assert g.id == "g_123"
    assert g.display_name == "My Security Group"


def test_update_patches_only_dirty_fields(make_client: "MakeClient"):

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/v1.0/groups/g_1"
        assert read_json(request) == expected_body
        return httpx.Response(204)

    c, _ = make_client(handler)
    g = c.groups.make_from_graph(
        {
            "id": "g_1",
            "displayName": "Old Name",
            "mailEnabled": False,
            "mailNickname": "old",
            "securityEnabled": True,
        }
    )

    g.display_name = "New Name"
    expected_body = g.to_graph(for_update=True)
    assert expected_body == {"displayName": "New Name"}
    g.save()


def test_create_missing_required_field(make_client: "MakeClient"):
    # Ensure no HTTP call occurs
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        print(request)
        raise AssertionError("HTTP should not be called")

    c, _ = make_client(handler)

    with pytest.raises(ValueError):
        c.groups.create(
            display_name="Missing flags",
            mail_nickname="x",
            # mail_enabled missing
            # security_enabled missing
        )


def test_queryset_filter(make_client: "MakeClient"):

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1.0/groups"
        assert dict(request.url.params) == expected_params_str
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "g_9",
                        "displayName": "A",
                        "mailEnabled": False,
                        "mailNickname": "a",
                        "securityEnabled": True,
                    }
                ]
            },
        )

    c, _ = make_client(handler)

    qs = (
        c.groups.filter(mail_enabled=False)
        .select("display_name", "mail_nickname")
        .order_by("display_name")
    )
    expected_params = qs._build_params()
    expected_params_str = {k: str(v) for k, v in expected_params.items()}
    objs = list(qs)
    assert len(objs) == 1
    assert objs[0].id == "g_9"
    assert objs[0].display_name == "A"


def test_queryset_q_or(make_client: "MakeClient"):

    def handler(request: httpx.Request) -> httpx.Response:
        assert dict(request.url.params) == expected_params_str
        return httpx.Response(200, json={"value": []})

    c, _ = make_client(handler)
    q = Q(display_name__startswith="A") | Q(display_name__startswith="B")
    qs = c.groups.filter(q, security_enabled=True)
    expected_params = qs._build_params()
    expected_params_str = {k: str(v) for k, v in expected_params.items()}
    list(qs)


def test_add_members_with_dup(make_client: "MakeClient"):

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/v1.0/groups/g_1"

        body = read_json(request)
        assert "members@odata.bind" in body
        binds = body["members@odata.bind"]
        assert isinstance(binds, list)

        # derive expected prefix from the request (robust to base_url differences)
        expected_prefix = str(request.url.copy_with(path="/v1.0"))

        # inputs: "u_1", User("u_2"), "u_1" (dedupe)
        assert binds == [
            f"{expected_prefix}/directoryObjects/u_1",
            f"{expected_prefix}/directoryObjects/u_2",
        ]

        calls.append(body)
        return httpx.Response(204)

    calls: list[dict] = []
    c, _ = make_client(handler)

    g = c.groups.make_from_graph(
        {
            "id": "g_1",
            "displayName": "G",
            "mailEnabled": False,
            "mailNickname": "g",
            "securityEnabled": True,
        },
    )
    u2 = c.users.make_from_graph({"id": "u_2"})

    g.members.add("u_1", u2, "u_1", "u_2")
    assert len(calls) == 1


def test_add_members_chunks_by_20(make_client: "MakeClient"):

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/v1.0/groups/g_1"

        body = read_json(request)
        binds = body["members@odata.bind"]

        expected_prefix = str(request.url.copy_with(path="/v1.0"))
        got_ids = [b.split("/directoryObjects/")[1] for b in binds]
        assert all(b.startswith(f"{expected_prefix}/directoryObjects/") for b in binds)

        seen_chunks.append(got_ids)
        return httpx.Response(204)

    c, _ = make_client(handler)

    g = c.groups.make_from_graph(
        {
            "id": "g_1",
            "displayName": "G",
            "mailEnabled": False,
            "mailNickname": "g",
            "securityEnabled": True,
        }
    )

    user_ids = [
        f"u_{i:02d}" for i in range(1, 26)
    ]  # 25 users => 2 PATCH calls (20 + 5)
    seen_chunks: list[list[str]] = []

    g.members.add(*user_ids)  # type: ignore

    assert len(seen_chunks) == 2
    assert seen_chunks[0] == user_ids[:20]
    assert seen_chunks[1] == user_ids[20:]


def test_remove_members(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1.0/$batch"

        body = read_json(request)
        received["body"] = body

        reqs = body["requests"]
        assert len(reqs) == 3

        # ids are 1..n per chunk
        assert [r["id"] for r in reqs] == ["1", "2", "3"]
        assert all(r["method"] == "DELETE" for r in reqs)

        # batch urls must be relative; should NOT include "/v1.0"
        assert [r["url"] for r in reqs] == [
            "/groups/g_1/members/u_1/$ref",
            "/groups/g_1/members/u_2/$ref",
            "/groups/g_1/members/u_3/$ref",
        ]

        # Return successful per-request statuses so raise_batch_errors() doesn't raise
        return httpx.Response(
            200,
            json={"responses": [{"id": r["id"], "status": 204} for r in reqs]},
        )

    c, _ = make_client(handler)

    g = c.groups.make_from_graph(
        {
            "id": "g_1",
            "displayName": "G",
            "mailEnabled": False,
            "mailNickname": "g",
            "securityEnabled": True,
        },
    )

    user_ids = ["u_1", "u_2", "u_3"]
    received: dict = {}

    g.members.remove(*user_ids)  # type: ignore
    assert "body" in received


def test_remove_members_raises_on_batch_error(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1.0/$batch"
        return httpx.Response(
            200,
            json={
                "responses": [
                    {"id": "1", "status": 204},
                    {
                        "id": "2",
                        "status": 404,
                        "body": {"error": {"code": "Request_ResourceNotFound"}},
                    },
                ]
            },
        )

    c, _ = make_client(handler)

    g = c.groups.make_from_graph(
        {
            "id": "g_1",
            "displayName": "G",
            "mailEnabled": False,
            "mailNickname": "g",
            "securityEnabled": True,
        },
    )

    with pytest.raises(RuntimeError, match=r"remove user/s from this groups"):
        g.members.remove("u_1", "u_2")  # type: ignore


def test_owners_add_remove(make_client: "MakeClient"):
    seen: list[list[dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1.0/$batch"
        body = json.loads(request.content.decode())
        seen.append(body.get("requests", []))
        return httpx.Response(200, json={"responses": [{"id": "1", "status": 204}]})

    c, r = make_client(handler)
    g = c.groups.make_from_graph(
        {
            "id": "g_1",
            "displayName": "G",
            "mailEnabled": False,
            "mailNickname": "g",
            "securityEnabled": True,
        },
    )

    g.owners.add("u1", "u2")  # type: ignore
    g.owners.remove("u1", "u2")  # type: ignore

    # Two batch calls: add then remove
    assert len(seen) == 2
    add_reqs, remove_reqs = seen

    # Add payload should have two POSTs to /groups/{id}/owners/$ref
    assert {r["url"] for r in add_reqs} == {
        "/groups/g_1/owners/$ref",
        "/groups/g_1/owners/$ref",
    }
    odata_ids = {r.get("body", {}).get("@odata.id") for r in add_reqs}
    assert all(r["method"] == "POST" for r in add_reqs)
    assert all(
        r.get("headers", {}).get("Content-Type") == "application/json" for r in add_reqs
    )
    assert odata_ids == {
        "https://graph.microsoft.com/v1.0/directoryObjects/u1",
        "https://graph.microsoft.com/v1.0/directoryObjects/u2",
    }

    # Remove payload should have two DELETEs to /groups/{id}/owners/{uid}/$ref
    assert {r["url"] for r in remove_reqs} == {
        "/groups/g_1/owners/u1/$ref",
        "/groups/g_1/owners/u2/$ref",
    }
    assert {r["method"] for r in remove_reqs} == {"DELETE"}

    assert len(r) == 2
