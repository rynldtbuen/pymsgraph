from __future__ import annotations

import httpx
import pytest

from pymsgraph.models.group import Group
from pymsgraph.queryset import Q

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
        .top(1)
        .select("display_name", "mail_nickname")
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
