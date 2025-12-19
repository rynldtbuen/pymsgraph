from __future__ import annotations

import json

import httpx
import pytest

from pymsgraph.models.user import User
from pymsgraph.queryset import Q

from .utils import read_json


def test_user_create_with_explicit_password_posts_and_hydrates(make_graph):
    u = User(
        display_name="  Test User  ",
        user_principal_name="TEST@EXAMPLE.COM ",
        account_enabled=True,
        mail_nickname="testuser",
    )

    expected_password = "P@ssw0rd!1234"
    expected_body = u.to_graph(for_update=False)
    expected_body["passwordProfile"] = {
        "password": expected_password,
        "forceChangePasswordNextSignIn": True,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1.0/users"

        body = read_json(request)
        assert body == expected_body

        # sanity checks for field normalization
        assert body["displayName"] == "Test User"
        assert body["userPrincipalName"] == "TEST@example.com"  # domain normalized
        assert body["mailNickname"] == "testuser"
        assert body["accountEnabled"] is True

        return httpx.Response(201, json={"id": "u_123", **body})

    make_graph(handler)

    u.save(password=expected_password)
    assert u.id == "u_123"
    assert u.display_name == "Test User"
    assert u.user_principal_name == "TEST@example.com"
    # explicit password should not be stored
    assert u.get_generated_password() is None


def test_user_create_auto_generate_password_and_pop(make_graph, monkeypatch):
    # Make generation deterministic for the test
    monkeypatch.setattr("pymsgraph.utils.generate_password", lambda n: "Gen3rated!Pwd")

    u = User(
        display_name="Auto User",
        user_principal_name="auto@example.com",
        mail_nickname="auto",
        account_enabled=True,
    )

    expected_body = u.to_graph(for_update=False)
    expected_body["passwordProfile"] = {
        "password": "Gen3rated!Pwd",
        "forceChangePasswordNextSignIn": True,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1.0/users"
        assert read_json(request) == expected_body
        return httpx.Response(201, json={"id": "u_auto", **expected_body})

    make_graph(handler)

    u.save(auto_generate_password=True)
    assert u.id == "u_auto"
    pwd = u.get_generated_password()
    assert pwd == "Gen3rated!Pwd"
    # second read should be cleared
    assert u.get_generated_password() is None


def test_user_update_patches_only_dirty_fields(make_graph):
    u = User.from_graph(
        {
            "id": "u_1",
            "displayName": "Old Name",
            "userPrincipalName": "old@example.com",
            "accountEnabled": True,
            "mailNickname": "oldnick",
        }
    )

    u.display_name = "New Name"
    expected_body = u.to_graph(for_update=True)
    assert expected_body == {"displayName": "New Name"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/v1.0/users/u_1"
        assert read_json(request) == expected_body
        return httpx.Response(204)

    make_graph(handler)
    u.save()


def test_user_create_missing_password_raises(make_graph):
    # Ensure no HTTP call occurs
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP should not be called")

    make_graph(handler)

    u = User(
        display_name="X",
        user_principal_name="x@example.com",
        mail_nickname="x",
    )
    with pytest.raises(ValueError):
        u.save()  # no password and auto_generate_password=False


def test_user_create_missing_required_field_raises(make_graph):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP should not be called")

    make_graph(handler)

    u = User(
        display_name="X",
        user_principal_name="x@example.com",
        # mail_nickname missing
    )
    with pytest.raises(ValueError):
        u.save(password="P@ssw0rd!1234")


def test_user_queryset_compiles_params_and_iterates(make_graph):
    qs = (
        User.objects.filter(account_enabled=True)
        .only("display_name", "user_principal_name")
        .order_by("display_name")[:2]
    )

    expected_params = qs._build_params()
    expected_params_str = {k: str(v) for k, v in expected_params.items()}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1.0/users"
        assert dict(request.url.params) == expected_params_str

        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "u_1",
                        "displayName": "A",
                        "userPrincipalName": "a@example.com",
                        "accountEnabled": True,
                        "mailNickname": "a",
                    }
                ]
            },
        )

    make_graph(handler)

    objs = list(qs)
    assert len(objs) == 1
    assert objs[0].id == "u_1"
    assert objs[0].display_name == "A"


def test_user_queryset_q_or(make_graph):
    q = Q(display_name__startswith="A") | Q(display_name__startswith="B")
    qs = User.objects.filter(q, account_enabled=True)

    expected_params = qs._build_params()
    expected_params_str = {k: str(v) for k, v in expected_params.items()}

    def handler(request: httpx.Request) -> httpx.Response:
        assert dict(request.url.params) == expected_params_str
        return httpx.Response(200, json={"value": []})

    make_graph(handler)
    list(qs)


def test_user_reset_password_patches_password_profile(make_graph):
    u = User.from_graph(
        {
            "id": "u_9",
            "displayName": "Reset Me",
            "userPrincipalName": "reset@example.com",
            "accountEnabled": True,
            "mailNickname": "reset",
        }
    )

    new_pw = "NewP@ssw0rd!1234"
    expected_body = {
        "passwordProfile": {
            "password": new_pw,
            "forceChangePasswordNextSignIn": True,
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/v1.0/users/u_9"
        assert read_json(request) == expected_body
        return httpx.Response(204)

    make_graph(handler)

    u.reset_password(password=new_pw)
    # explicit reset should not be stored as "generated"
    assert u.get_generated_password() is None


def test_user_reset_password_auto_generate_and_pop(make_graph, monkeypatch):
    monkeypatch.setattr("pymsgraph.utils.generate_password", lambda n: "R3set!GenPwd")

    u = User.from_graph(
        {
            "id": "u_10",
            "displayName": "Reset Me",
            "userPrincipalName": "reset2@example.com",
            "accountEnabled": True,
            "mailNickname": "reset2",
        }
    )

    expected_body = {
        "passwordProfile": {
            "password": "R3set!GenPwd",
            "forceChangePasswordNextSignIn": True,
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/v1.0/users/u_10"
        assert read_json(request) == expected_body
        return httpx.Response(204)

    make_graph(handler)

    u.reset_password(auto_generate_password=True)
    assert u.get_generated_password() == "R3set!GenPwd"
    assert u.get_generated_password() is None


def test_user_reset_password_requires_id(make_graph):
    # Ensure no HTTP call occurs
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP should not be called")

    make_graph(handler)

    u = User(
        display_name="Unsaved",
        user_principal_name="unsaved@example.com",
        mail_nickname="unsaved",
    )
    with pytest.raises(ValueError):
        u.reset_password(password="Whatever1!234")


def test_user_delete_requires_force(make_graph):
    u = User.from_graph(
        {
            "id": "u_del",
            "displayName": "Del",
            "userPrincipalName": "del@example.com",
            "accountEnabled": True,
            "mailNickname": "del",
        }
    )

    # Ensure no HTTP call occurs
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP should not be called")

    make_graph(handler)

    with pytest.raises(RuntimeError):
        u.delete()


def test_user_delete_force_calls_delete(make_graph):
    u = User.from_graph(
        {
            "id": "u_del",
            "displayName": "Del",
            "userPrincipalName": "del@example.com",
            "accountEnabled": True,
            "mailNickname": "del",
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/v1.0/users/u_del"
        return httpx.Response(204)

    make_graph(handler)

    u.delete(force=True)
    # after local cleanup, id should no longer be present
    assert u.id is None


def test_user_delete_requires_id(make_graph):
    # Ensure no HTTP call occurs
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP should not be called")

    make_graph(handler)

    u = User(
        display_name="Unsaved",
        # user_principal_name="unsaved@example.com",
        mail_nickname="unsaved",
    )
    with pytest.raises(ValueError):
        u.delete(force=True)


def test_user_get_by_id_short_circuits(make_graph):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1.0/users/u_1"
        assert "$filter" not in dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "id": "u_1",
                "displayName": "A",
                "userPrincipalName": "a@example.com",
                "accountEnabled": True,
                "mailNickname": "a",
            },
        )

    make_graph(handler)

    u = User.objects.get(id="u_1")
    assert u.id == "u_1"
    assert u.display_name == "A"


def test_user_groups_member_of_returns_groups_only(make_graph):
    from pymsgraph.models.group import Group

    # Build a hydrated user (simulates fetching from Graph)
    u = User.from_graph(
        {
            "id": "u_123",
            "displayName": "Has Groups",
            "userPrincipalName": "hasgroups@example.com",
            "accountEnabled": True,
            "mailNickname": "hasgroups",
        }
    )

    # Calling u.groups returns a *manager* bound to Group and configured with
    # the related endpoint: /users/{id}/memberOf
    qs = u.groups.only("display_name", "mail_nickname").order_by(  # type: ignore
        "display_name"
    )[:2]

    # The QuerySet compiles params lazily; compute the expected dict once so
    # we can verify what GraphClient sends on the wire.
    expected_params = qs._build_params()
    expected_params_str = {k: str(v) for k, v in expected_params.items()}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"

        # Ensure endpoint chaining worked: GET /users/{id}/memberOf
        assert request.url.path == "/v1.0/users/u_123/memberOf"

        # Ensure QuerySet params were compiled and passed through.
        assert dict(request.url.params) == expected_params_str

        # /memberOf can return mixed directoryObjects (groups, roles, etc.).
        # Include one non-group object to verify our queryset filters it out.
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "@odata.type": "#microsoft.graph.group",
                        "id": "g_1",
                        "displayName": "A",
                        "mailEnabled": False,
                        "mailNickname": "a",
                        "securityEnabled": True,
                    },
                    {
                        "@odata.type": "#microsoft.graph.directoryRole",
                        "id": "r_1",
                        "displayName": "Some Role",
                    },
                ]
            },
        )

    make_graph(handler)

    groups = list(qs)
    # Only Group objects should be returned from /memberOf.
    assert len(groups) == 1
    assert isinstance(groups[0], Group)
    assert groups[0].id == "g_1"
    assert groups[0].display_name == "A"


def _make_user_with_id(uid: str = "u_1") -> User:
    return User.from_graph(
        {
            "id": uid,
            "displayName": "Test User",
            "userPrincipalName": "test.user@example.com",
            "accountEnabled": True,
            "mailNickname": "testuser",
        }
    )


def test_user_memberof_add_posts_batch_patch_groups_with_members_bind_and_dedupes(
    make_graph,
):
    u = _make_user_with_id("u_1")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1.0/$batch"

        expected_prefix = str(request.url.copy_with(path="/v1.0"))

        body = read_json(request)
        reqs = body["requests"]

        # input includes duplicate group id -> should dedupe
        assert len(reqs) == 2
        assert [r["id"] for r in reqs] == ["1", "2"]

        assert reqs[0]["method"] == "PATCH"
        assert reqs[0]["url"] == "/groups/g_1"
        assert reqs[0]["body"]["members@odata.bind"] == [
            f"{expected_prefix}/directoryObjects/u_1"
        ]

        assert reqs[1]["method"] == "PATCH"
        assert reqs[1]["url"] == "/groups/g_2"
        assert reqs[1]["body"]["members@odata.bind"] == [
            f"{expected_prefix}/directoryObjects/u_1"
        ]

        return httpx.Response(
            200,
            json={
                "responses": [{"id": "1", "status": 204}, {"id": "2", "status": 204}]
            },
        )

    make_graph(handler)

    u.groups.add("g_1", "g_2", "g_1")  # type: ignore


def test_user_memberof_add_chunks_by_20(make_graph):
    u = _make_user_with_id("u_1")
    group_ids = [f"g_{i:02d}" for i in range(1, 26)]  # 25 groups => 2 batch calls

    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1.0/$batch"

        body = read_json(request)
        reqs = body["requests"]
        seen.append(len(reqs))

        # respond success for each subrequest
        return httpx.Response(
            200,
            json={"responses": [{"id": r["id"], "status": 204} for r in reqs]},
        )

    make_graph(handler)

    u.groups.add(*group_ids)  # type: ignore

    assert seen == [20, 5]


def test_user_memberof_remove_posts_batch_delete_refs(make_graph):
    u = _make_user_with_id("u_1")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1.0/$batch"

        body = read_json(request)
        reqs = body["requests"]

        assert len(reqs) == 3
        assert [r["id"] for r in reqs] == ["1", "2", "3"]
        assert all(r["method"] == "DELETE" for r in reqs)

        # batch urls must be relative; should NOT include "/v1.0"
        assert [r["url"] for r in reqs] == [
            "/groups/g_1/members/u_1/$ref",
            "/groups/g_2/members/u_1/$ref",
            "/groups/g_3/members/u_1/$ref",
        ]

        return httpx.Response(
            200,
            json={"responses": [{"id": r["id"], "status": 204} for r in reqs]},
        )

    make_graph(handler)

    u.groups.remove("g_1", "g_2", "g_3")  # type: ignore


def test_user_memberof_remove_chunks_by_20(make_graph):
    u = _make_user_with_id("u_1")
    group_ids = [f"g_{i:02d}" for i in range(1, 26)]  # 25 groups => 2 batch calls

    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1.0/$batch"

        body = read_json(request)
        reqs = body["requests"]
        seen.append(len(reqs))

        return httpx.Response(
            200,
            json={"responses": [{"id": r["id"], "status": 204} for r in reqs]},
        )

    make_graph(handler)

    u.groups.remove(*group_ids)  # type: ignore

    assert seen == [20, 5]


def test_user_memberof_add_raises_on_batch_error(make_graph):
    u = _make_user_with_id("u_1")

    def handler(request: httpx.Request) -> httpx.Response:
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

    with pytest.raises(RuntimeError, match=r"Batch add memberOf failed"):
        u.groups.add("g_1", "g_2")  # type: ignore


def test_user_memberof_remove_raises_on_batch_error(make_graph):
    u = _make_user_with_id("u_1")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1.0/$batch"
        return httpx.Response(
            200,
            json={
                "responses": [
                    {"id": "1", "status": 204},
                    {
                        "id": "2",
                        "status": 403,
                        "body": {"error": {"code": "Authorization_RequestDenied"}},
                    },
                ]
            },
        )

    make_graph(handler)

    with pytest.raises(RuntimeError, match=r"Batch remove memberOf failed"):
        u.groups.remove("g_1", "g_2")  # type: ignore


def test_user_queryset_licenses_add_posts_batch_assign_license(make_graph):
    # Any queryset works; we just need it to resolve user ids via GET /users first.
    qs = User.objects.filter(account_enabled=True)

    sku_ids = ["SKU_1", "SKU_2", "SKU_1"]  # dup should be deduped by coerce_values()

    seen_batch_bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        # 1) Resolve users (QuerySetBulkOperation.get_ids() will trigger this)
        if request.method == "GET" and request.url.path == "/v1.0/users":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "u_1",
                            "displayName": "U1",
                            "userPrincipalName": "u1@example.com",
                            "accountEnabled": True,
                            "mailNickname": "u1",
                        },
                        {
                            "id": "u_2",
                            "displayName": "U2",
                            "userPrincipalName": "u2@example.com",
                            "accountEnabled": True,
                            "mailNickname": "u2",
                        },
                        {
                            "id": "u_3",
                            "displayName": "U3",
                            "userPrincipalName": "u3@example.com",
                            "accountEnabled": True,
                            "mailNickname": "u3",
                        },
                    ]
                },
            )

        # 2) Batch assignLicense per user
        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = read_json(request)
            seen_batch_bodies.append(body)

            reqs = body["requests"]
            assert len(reqs) == 3
            assert [r["id"] for r in reqs] == ["1", "2", "3"]
            assert all(r["method"] == "POST" for r in reqs)
            assert [r["url"] for r in reqs] == [
                "/users/u_1/assignLicense",
                "/users/u_2/assignLicense",
                "/users/u_3/assignLicense",
            ]

            # dedupe SKU_1
            expected_add = [
                {"skuId": "SKU_1", "disabledPlans": []},
                {"skuId": "SKU_2", "disabledPlans": []},
            ]

            for r in reqs:
                assert r["headers"]["Content-Type"] == "application/json"
                assert r["body"]["addLicenses"] == expected_add
                assert r["body"]["removeLicenses"] == []

            return httpx.Response(
                200,
                json={"responses": [{"id": r["id"], "status": 200} for r in reqs]},
            )

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    make_graph(handler)

    qs.licenses.add(*sku_ids)
    assert len(seen_batch_bodies) == 1


def test_user_queryset_licenses_remove_posts_batch_assign_license(make_graph):
    qs = User.objects.filter(account_enabled=True)

    seen_batch_bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "u_1",
                            "displayName": "U1",
                            "userPrincipalName": "u1@example.com",
                            "accountEnabled": True,
                            "mailNickname": "u1",
                        },
                        {
                            "id": "u_2",
                            "displayName": "U2",
                            "userPrincipalName": "u2@example.com",
                            "accountEnabled": True,
                            "mailNickname": "u2",
                        },
                    ]
                },
            )

        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = read_json(request)
            seen_batch_bodies.append(body)

            reqs = body["requests"]
            assert len(reqs) == 2
            assert [r["id"] for r in reqs] == ["1", "2"]
            assert [r["url"] for r in reqs] == [
                "/users/u_1/assignLicense",
                "/users/u_2/assignLicense",
            ]

            # remove dedupes too
            assert reqs[0]["body"]["addLicenses"] == []
            assert reqs[0]["body"]["removeLicenses"] == ["SKU_1", "SKU_2"]
            assert reqs[1]["body"]["addLicenses"] == []
            assert reqs[1]["body"]["removeLicenses"] == ["SKU_1", "SKU_2"]

            return httpx.Response(
                200,
                json={"responses": [{"id": r["id"], "status": 200} for r in reqs]},
            )

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    make_graph(handler)

    qs.licenses.remove("SKU_1", "SKU_2", "SKU_1")
    assert len(seen_batch_bodies) == 1


def test_user_queryset_licenses_add_chunks_by_20(make_graph):
    qs = User.objects.filter(account_enabled=True)

    users = []
    for i in range(1, 26):
        users.append(
            {
                "id": f"u_{i:02d}",
                "displayName": f"U{i}",
                "userPrincipalName": f"u{i}@example.com",
                "accountEnabled": True,
                "mailNickname": f"u{i}",
            }
        )

    batch_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users":
            return httpx.Response(200, json={"value": users})

        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = read_json(request)
            reqs = body["requests"]
            batch_sizes.append(len(reqs))
            return httpx.Response(
                200,
                json={"responses": [{"id": r["id"], "status": 200} for r in reqs]},
            )

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    make_graph(handler)

    qs.licenses.add("SKU_1")
    assert batch_sizes == [20, 5]


def test_user_queryset_licenses_remove_raises_on_batch_error(make_graph):
    qs = User.objects.filter(account_enabled=True)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/users":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "u_1",
                            "displayName": "U1",
                            "userPrincipalName": "u1@example.com",
                            "accountEnabled": True,
                            "mailNickname": "u1",
                        },
                        {
                            "id": "u_2",
                            "displayName": "U2",
                            "userPrincipalName": "u2@example.com",
                            "accountEnabled": True,
                            "mailNickname": "u2",
                        },
                    ]
                },
            )

        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            body = read_json(request)
            reqs = body["requests"]
            return httpx.Response(
                200,
                json={
                    "responses": [
                        {"id": reqs[0]["id"], "status": 200},
                        {
                            "id": reqs[1]["id"],
                            "status": 403,
                            "body": {"error": {"code": "Authorization_RequestDenied"}},
                        },
                    ]
                },
            )

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    make_graph(handler)

    with pytest.raises(RuntimeError, match=r"Batch remove licenses failed"):
        qs.licenses.remove("SKU_1")
