import json
import httpx
import pytest

from pymsgraph.models.user import User, UserQuerySet


def test_user_queryset_create(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1.0/users"
        body = json.loads(request.content.decode())
        # basic payload expectations
        assert body["displayName"] == "Alice"
        assert body["userPrincipalName"] == "alice@example.com"
        assert body["mailNickname"] == "alice"
        assert "passwordProfile" in body
        return httpx.Response(
            201,
            json={
                "id": "123",
                "displayName": "Alice",
                "userPrincipalName": "alice@example.com",
                "mailNickname": "alice",
            },
        )

    client, requests = make_client(handler)
    qs = UserQuerySet(client=client, model=User, endpoint="/users")

    user = qs.create(
        display_name="Alice",
        user_principal_name="alice@example.com",
        mail_nickname="alice",
        password="Pass@word1",
    )

    assert user.id == "123"
    assert user.display_name == "Alice"
    assert user.user_principal_name == "alice@example.com"
    assert user._dirty == set()
    assert len(requests) == 1


def test_user_save_patches_dirty_fields(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and request.url.path.endswith("/users/123"):
            body = json.loads(request.content.decode())
            assert body == {"jobTitle": "Engineer"}
            return httpx.Response(204, json={})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client, requests = make_client(handler)
    qs = UserQuerySet(client=client, model=User, endpoint="/users")

    user = User(qs=qs, graph_data={"id": "123", "displayName": "Alice"})
    assert user._dirty == set()

    user.job_title = "Engineer"
    assert "job_title" in user._dirty

    saved = user.save()
    assert saved is True
    assert user._dirty == set()
    assert len(requests) == 1


def test_user_queryset_select_builds_select(user_qs):
    qs = user_qs.select("display_name", "mail_nickname")
    params = qs._build_params()
    assert params["$select"] == "displayName,mailNickname"


def test_user_queryset_order_by(user_qs):
    qs = user_qs.order_by("-display_name", "mail_nickname")
    params = qs._build_params()
    assert params["$orderby"] == "displayName desc,mailNickname"


def test_user_queryset_filter_builds_filter_param(user_qs):
    qs = user_qs.filter(display_name__startswith="A", account_enabled=True)
    params = qs._build_params()
    assert (
        params["$filter"] == "(startswith(displayName, 'A') and accountEnabled eq true)"
    )


def test_user_queryset_filter_with_q_object(user_qs):
    from pymsgraph.query import Q

    qs = user_qs.filter(
        Q(display_name__startswith="A") | Q(display_name__startswith="Z")
    )
    params = qs._build_params()
    assert (
        params["$filter"]
        == "((startswith(displayName, 'A')) or (startswith(displayName, 'Z')))"
    )


def test_user_queryset_rejects_unsupported_lookup(user_qs):
    with pytest.raises(ValueError):
        user_qs.filter(display_name__contains="x")._build_params()


def test_user_queryset_top_sets_limit(user_qs):
    qs = user_qs.top(5)
    params = qs._build_params()
    assert params["$top"] == 5


def test_user_queryset_count_uses_odata_count(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1.0/users"
        return httpx.Response(
            200,
            json={
                "@odata.count": 42,
                "value": [{"id": "1"}, {"id": "2"}],
            },
        )

    client, _ = make_client(handler)
    qs = UserQuerySet(client=client, model=User, endpoint="/users")
    assert qs.count() == 42
    # Cached objects should also be hydrated
    assert len(list(qs)) == 2


def test_user_queryset_get_by_id(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1.0/users/abc"
        return httpx.Response(
            200,
            json={
                "id": "abc",
                "displayName": "Bob",
                "userPrincipalName": "bob@example.com",
                "mailNickname": "bob",
            },
        )

    client, _ = make_client(handler)
    qs = UserQuerySet(client=client, model=User, endpoint="/users")
    user = qs.get(id="abc")
    assert user is not None
    assert user.id == "abc"
    assert user.display_name == "Bob"
    assert user.user_principal_name == "bob@example.com"


def test_user_groups_add_remove(make_client):
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            requests = body.get("requests", [])
            first_method = requests[0]["method"] if requests else None
            if first_method == "PATCH":
                assert requests == [
                    {
                        "id": "1",
                        "method": "PATCH",
                        "url": "/groups/g1",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "members@odata.bind": [
                                "https://graph.microsoft.com/v1.0/directoryObjects/123"
                            ]
                        },
                    }
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

    client, requests = make_client(handler)
    qs = UserQuerySet(client=client, model=User, endpoint="/users")
    user = User(qs=qs, graph_data={"id": "123", "displayName": "Alice"})

    user.groups.add("g1")
    user.groups.remove("g1")

    assert seen == [
        ("POST", "/v1.0/$batch"),
        ("POST", "/v1.0/$batch"),
    ]
    assert len(requests) == 2


def test_user_licenses_add_remove(make_client):
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = json.loads(request.content.decode())
            requests = body.get("requests", [])
            assert len(requests) == 1
            req = requests[0]
            assert req["url"] == "/users/123/assignLicense"
            if req["body"]["addLicenses"]:
                assert req["body"] == {
                    "addLicenses": [{"skuId": "sku1", "disabledPlans": []}],
                    "removeLicenses": [],
                }
            else:
                assert req["body"] == {
                    "addLicenses": [],
                    "removeLicenses": ["sku1"],
                }
            return httpx.Response(200, json={"responses": [{"id": "1", "status": 200}]})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client, requests = make_client(handler)
    qs = UserQuerySet(client=client, model=User, endpoint="/users")
    user = User(qs=qs, graph_data={"id": "123", "displayName": "Alice"})

    user.licenses.add("sku1")
    user.licenses.remove("sku1")

    assert seen == [
        ("POST", "/v1.0/$batch"),
        ("POST", "/v1.0/$batch"),
    ]
    assert len(requests) == 2


def test_user_groups_descriptor(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users/123/memberOf":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "g1",
                            "displayName": "Group One",
                            "mailNickname": "g1",
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client, requests = make_client(handler)
    qs = UserQuerySet(client=client, model=User, endpoint="/users")
    user = User(qs=qs, graph_data={"id": "123", "displayName": "Alice"})

    groups_qs = user.groups
    groups = list(groups_qs)
    assert len(groups) == 1
    g = groups[0]
    assert g.id == "g1"
    assert g.display_name == "Group One"
    assert len(requests) == 1


def test_user_queryset_filter_licenses_sku_id(user_qs):
    qs = user_qs.filter(licenses__sku_id="cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46")
    params = qs._build_params()
    assert (
        params["$filter"]
        == "(assignedLicenses/any(u:u/skuId eq 'cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46'))"
    )


def test_user_queryset_filter_licenses_sku_id_with_lookup(user_qs):
    qs = user_qs.filter(licenses__sku_id__exact="cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46")
    params = qs._build_params()
    assert (
        params["$filter"]
        == "(assignedLicenses/any(u:u/skuId eq 'cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46'))"
    )


def test_user_queryset_filter_licenses_isnull(user_qs):
    qs = user_qs.filter(licenses__isnull=True)
    params = qs._build_params()
    assert params["$filter"] == "(assignedLicenses/$count eq 0)"


def test_user_queryset_filter_licenses_is_not_null(user_qs):
    qs = user_qs.filter(licenses__isnull=False)
    params = qs._build_params()
    assert params["$filter"] == "(assignedLicenses/$count ne 0)"
