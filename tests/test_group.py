from __future__ import annotations

import httpx
import pytest

from pymsgraph.models.group import Group
from pymsgraph.models.user import User

from pymsgraph.query import Q
from tests.utils import read_json


def test_group_create_posts_and_hydrates(make_graph):
    g = Group(
        display_name="  My Security Group  ",
        mail_enabled=False,
        mail_nickname="mysecuritygroup",
        security_enabled=True,
        description="  desc  ",
    )

    expected_body = g.to_graph(for_update=False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1.0/groups"

        body = read_json(request)
        assert body == expected_body

        # normalization
        assert body["displayName"] == "My Security Group"
        assert body["mailEnabled"] is False
        assert body["mailNickname"] == "mysecuritygroup"
        assert body["securityEnabled"] is True
        assert body["description"] == "desc"

        return httpx.Response(201, json={"id": "g_123", **body})

    make_graph(handler)

    g.save()
    assert g.id == "g_123"
    assert g.display_name == "My Security Group"


def test_group_update_patches_only_dirty_fields(make_graph):
    g = Group.from_graph(
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

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/v1.0/groups/g_1"
        assert read_json(request) == expected_body
        return httpx.Response(204)

    make_graph(handler)
    g.save()


def test_group_create_missing_required_field_raises(make_graph):
    # Ensure no HTTP call occurs
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP should not be called")

    make_graph(handler)
    g = Group(
        display_name="Missing flags",
        mail_nickname="x",
        # mail_enabled missing
        # security_enabled missing
    )
    with pytest.raises(ValueError):
        g.save()


def test_group_queryset_compiles_params_and_iterates(make_graph):
    qs = (
        Group.objects.filter(mail_enabled=False)
        .only("display_name", "mail_nickname")
        .order_by("display_name")
    )

    expected_params = qs._build_params()
    expected_params_str = {k: str(v) for k, v in expected_params.items()}

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

    make_graph(handler)
    objs = list(qs)
    assert len(objs) == 1
    assert objs[0].id == "g_9"
    assert objs[0].display_name == "A"


def test_group_queryset_q_or(make_graph):
    q = Q(display_name__startswith="A") | Q(display_name__startswith="B")
    qs = Group.objects.filter(q, security_enabled=True)

    expected_params = qs._build_params()
    expected_params_str = {k: str(v) for k, v in expected_params.items()}

    def handler(request: httpx.Request) -> httpx.Response:
        assert dict(request.url.params) == expected_params_str
        return httpx.Response(200, json={"value": []})

    make_graph(handler)
    list(qs)


def test_group_members_add_patches_members_bind_and_dedupes(make_graph):
    g = Group.from_graph(
        {
            "id": "g_1",
            "displayName": "G",
            "mailEnabled": False,
            "mailNickname": "g",
            "securityEnabled": True,
        }
    )
    u2 = User.from_graph({"id": "u_2"})

    calls: list[dict] = []

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

    make_graph(handler)

    g.members.add("u_1", u2, "u_1")  # type: ignore
    assert len(calls) == 1


def test_group_members_add_chunks_by_20(make_graph):
    g = Group.from_graph(
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

    make_graph(handler)

    g.members.add(*user_ids)  # type: ignore

    assert len(seen_chunks) == 2
    assert seen_chunks[0] == user_ids[:20]
    assert seen_chunks[1] == user_ids[20:]


def test_group_members_remove_posts_batch_delete_refs(make_graph):
    g = Group.from_graph(
        {
            "id": "g_1",
            "displayName": "G",
            "mailEnabled": False,
            "mailNickname": "g",
            "securityEnabled": True,
        }
    )

    user_ids = ["u_1", "u_2", "u_3"]
    received: dict = {}

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

    make_graph(handler)

    g.members.remove(*user_ids)  # type: ignore
    assert "body" in received


def test_group_members_remove_raises_on_batch_error(make_graph):
    g = Group.from_graph(
        {
            "id": "g_1",
            "displayName": "G",
            "mailEnabled": False,
            "mailNickname": "g",
            "securityEnabled": True,
        }
    )

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

    make_graph(handler)

    with pytest.raises(RuntimeError, match=r"Batch remove members failed"):
        g.members.remove("u_1", "u_2")  # type: ignore
