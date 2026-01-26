import json
from typing import TYPE_CHECKING

import httpx
import pytest

from pymsgraph.models.query import Q
from pymsgraph.models.user import User

if TYPE_CHECKING:
    from tests.conftest import MakeClient


def test_filter_single(users_qs) -> None:
    qs = users_qs.filter(display_name="Alice")
    params = qs._build_params()
    assert params["$filter"] == "(displayName eq 'Alice')"


def test_filter_multiple(users_qs) -> None:
    qs = users_qs.filter(display_name="Alice", mail="a@x.com")
    params = qs._build_params()
    filt = params["$filter"]
    assert "displayName eq 'Alice'" in filt
    assert "mail eq 'a@x.com'" in filt
    assert " and " in filt


def test_filter_dup(users_qs) -> None:
    qs = users_qs.filter(display_name="Alice", mail="a@x.com").filter(mail="a@x.com")
    params = qs._build_params()
    filt = params["$filter"]
    assert "displayName eq 'Alice'" in filt
    assert "mail eq 'a@x.com'" in filt
    assert " and " in filt
    assert len(qs._params["$filter"]) == 2


def test_filter_q_or_with_kwargs(users_qs) -> None:
    qs = users_qs.filter(Q(display_name="A") | Q(mail="a@x.com"), account_enabled=True)
    params = qs._build_params()
    filt = params["$filter"]
    assert "displayName eq 'A'" in filt
    assert "mail eq 'a@x.com'" in filt
    assert " or " in filt
    assert "accountEnabled eq true" in filt
    assert " and " in filt
    assert (
        filt
        == "((displayName eq 'A') or (mail eq 'a@x.com')) and (accountEnabled eq true)"
    )


def test_filter_q_not(users_qs) -> None:
    qs = users_qs.filter(~Q(display_name="A"))
    params = qs._build_params()
    assert params["$filter"] == "(not (displayName eq 'A'))"


def test_select_collects_fields(users_qs) -> None:
    qs = users_qs.select("display_name", "mail")
    params = qs._build_params()
    assert params["$select"] == "id,displayName,mail"


def test_select_dedupes_fields(users_qs) -> None:
    qs = users_qs.select("display_name", "mail").select("display_name")
    params = qs._build_params()
    assert params["$select"] == "id,displayName,mail"


def test_order_by_single(users_qs) -> None:
    qs = users_qs.order_by("display_name")
    params = qs._build_params()
    assert params["$orderby"] == "displayName"


def test_order_by_desc(users_qs) -> None:
    qs = users_qs.order_by("-display_name")
    params = qs._build_params()
    assert params["$orderby"] == "displayName desc"


def test_order_by_multiple(users_qs) -> None:
    qs = users_qs.order_by("display_name", "-user_principal_name")
    params = qs._build_params()
    assert params["$orderby"] == "displayName,userPrincipalName desc"


def test_expand_single(users_qs) -> None:
    qs = users_qs.expand("manager", "display_name", "department")
    params = qs._build_params()
    assert params["$expand"] == "manager($select=department,displayName,id)"


def test_expand_multiple(users_qs) -> None:
    qs = users_qs.expand("manager", "display_name", "department").expand(
        "member_of", "display_name", "mail"
    )
    params = qs._build_params()
    assert params["$expand"] == (
        "manager($select=department,displayName,id),memberOf($select=displayName,id,mail)"
    )


def test_expand_defaults_to_related_select_fields(users_qs) -> None:
    qs = users_qs.expand("manager")
    params = qs._build_params()
    assert (
        params["$expand"]
        == "manager($select=accountEnabled,displayName,id,mail,userPrincipalName)"
    )


def test_search_with_q_and_kwargs(users_qs) -> None:
    params = users_qs.search(display_name="A")._build_params()
    assert params["$search"] == '"displayName:A"'

    params = users_qs.search(display_name="A", description="B")._build_params()
    assert params["$search"] == '"displayName:A" AND "description:B"'

    params = users_qs.search(
        Q(display_name="A") | Q(display_name="B"), description="C"
    )._build_params()
    assert (
        params["$search"] == '("displayName:A" OR "displayName:B") AND "description:C"'
    )


def test_exclude_simple(users_qs) -> None:
    params = users_qs._clone().exclude(display_name="Alice")._build_params()
    assert params["$filter"] == "(not (displayName eq 'Alice'))"


def test_exclude_list_field(users_qs) -> None:
    params = (
        users_qs._clone()
        .exclude(proxy_addresses="SMTP:admin@contoso.com")
        ._build_params()
    )
    assert (
        params["$filter"]
        == "(not (proxyAddresses/any(i:i eq 'SMTP:admin@contoso.com')))"
    )


def test_exclude_q_object(users_qs) -> None:
    params = (
        users_qs._clone()
        .exclude(Q(display_name="A") | Q(mail="a@x.com"))
        ._build_params()
    )
    assert params["$filter"] == "(not ((displayName eq 'A') or (mail eq 'a@x.com')))"


@pytest.mark.asyncio
async def test_with_objects_clean_params(users_qs) -> None:
    seeded = users_qs.filter(display_name="Alice").with_objects(
        User(id="u1", display_name="User One"),
        "u2",
    )

    assert seeded._params == {}
    items = [u async for u in seeded]
    assert [u.id for u in items] == ["u1", "u2"]


@pytest.mark.asyncio
async def test_prefetch_members_populates_cache(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/groups":
            return httpx.Response(200, json={"value": [{"id": "g1"}]})
        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            assert body.get("requests") == [
                {"id": "1", "method": "GET", "url": "/groups/g1/members"}
            ]
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
                                        "@odata.type": "#microsoft.graph.user",
                                        "id": "u1",
                                    }
                                ],
                                "@odata.nextLink": "https://graph.microsoft.com/v1.0/groups/g1/members?$skip=1",
                                "@odata.count": 2,
                            },
                        }
                    ]
                },
            )

        if request.method == "GET" and request.url.path == "/v1.0/groups/g1/members":
            raise AssertionError("members should be served from cache")
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    groups = [g async for g in c.groups.prefetch("members")]
    assert len(groups) == 1
    group = groups[0]

    members_qs = group.members
    paginator = members_qs.iterator()
    assert (
        paginator._next_link
        == "https://graph.microsoft.com/v1.0/groups/g1/members?$skip=1"
    )
    assert paginator._cached_count == 2

    members = [m async for m in members_qs]
    assert [m.id for m in members] == ["u1"]


@pytest.mark.asyncio
async def test_union_queryset_all_pages(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users":
            url_text = str(request.url)
            top = request.url.params.get("$top")
            if "skip=1" in url_text:
                return httpx.Response(200, json={"value": [{"id": "u3"}]})
            if top == "1":
                return httpx.Response(
                    200,
                    json={
                        "value": [{"id": "u1"}],
                        "@odata.nextLink": "https://graph.microsoft.com/v1.0/users?$top=1&$skip=1",
                    },
                )
            if top == "2":
                return httpx.Response(200, json={"value": [{"id": "u2"}]})

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    qs1 = c.users.top(1)
    qs2 = c.users.top(2)

    combined = qs1.union(qs2)
    items = [u async for u in combined.all()]

    assert [u.id for u in items] == ["u1", "u3", "u2"]


@pytest.mark.asyncio
async def test_values_with_callable_fields(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users":
            return httpx.Response(
                200,
                json={
                    "value": [{"id": "u1", "displayName": "Ada", "surname": "Lovelace"}]
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    rows = await c.users.values(
        "display_name",
        "surname",
        lambda u: {"full_name": f"{u.display_name} {u.surname}"},
    )

    assert rows == [
        {"display_name": "Ada", "surname": "Lovelace", "full_name": "Ada Lovelace"}
    ]


@pytest.mark.asyncio
async def test_values_uses_existing_select(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users":
            return httpx.Response(
                200,
                json={"value": [{"id": "u1", "displayName": "Ada", "surname": "L"}]},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, requests = make_client(handler)
    qs = c.users.select("display_name", "surname")
    rows = await qs.values("display_name", "surname")

    assert rows == [{"display_name": "Ada", "surname": "L"}]
    assert len(requests) == 1
    assert "displayName" in requests[0]["url"]
    assert "surname" in requests[0]["url"]


@pytest.mark.asyncio
async def test_values_overrides_select_when_missing_fields(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users":
            url = str(request.url)
            assert "surname" in url
            return httpx.Response(
                200,
                json={"value": [{"id": "u1", "displayName": "Ada", "surname": "L"}]},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, requests = make_client(handler)
    qs = c.users.select("display_name")
    rows = await qs.values("display_name", "surname")

    assert rows == [{"display_name": "Ada", "surname": "L"}]
    assert len(requests) == 1
    assert "surname" in requests[0]["url"]


@pytest.mark.asyncio
async def test_values_uses_cached_objects_when_selected(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users":
            return httpx.Response(
                200,
                json={"value": [{"id": "u1", "displayName": "Ada"}]},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, requests = make_client(handler)
    qs = c.users.select("display_name")

    # Prime paginator cache
    _ = [u async for u in qs]

    rows = await qs.values("display_name")
    assert rows == [{"display_name": "Ada"}]
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_to_csv_writes_headers_and_rows(make_client: "MakeClient", tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users":
            return httpx.Response(
                200,
                json={"value": [{"id": "u1", "displayName": "Ada", "mail": "a@x.com"}]},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    out_path = tmp_path / "users.csv"

    await c.users.to_csv(out_path, fieldnames=("display_name", "mail"))

    content = out_path.read_text(encoding="utf-8").splitlines()
    assert content[0] == "display_name,mail"
    assert content[1] == "Ada,a@x.com"


@pytest.mark.asyncio
async def test_to_csv_with_callable_fieldnames(make_client: "MakeClient", tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users":
            return httpx.Response(
                200,
                json={"value": [{"id": "u1", "display_name": "Ada", "surname": "L"}]},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    c, _ = make_client(handler)
    out_path = tmp_path / "users_callable.csv"

    await c.users.to_csv(
        out_path,
        fieldnames=(lambda u: {"full_name": f"{u.display_name} {u.surname}"},),
    )

    content = out_path.read_text(encoding="utf-8").splitlines()
    assert content[0] == "full_name"
    assert content[1] == "Ada L"
