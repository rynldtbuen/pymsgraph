import json
from typing import TYPE_CHECKING

import httpx
import pytest


if TYPE_CHECKING:
    from tests.conftest import MakeClient


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
        assert body["accountEnabled"] == "true"
        assert "passwordProfile" in body
        return httpx.Response(
            201,
            json={
                "id": "123",
                "displayName": "Alice",
                "userPrincipalName": "alice@example.com",
                "mailNickname": "alice",
                "mail": "alice@example.com",
            },
        )

    c, r = make_client(handler)
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
    assert u._endpoint == "/users/123"
    assert u._dirty == set()
    assert u.password_profile is None


# @pytest.mark.asyncio
# async def test_user_create(make_client: "MakeClient"):
#     def handler(request: httpx.Request) -> httpx.Response:
#         assert request.method == "POST"
#         assert request.url.path == "/v1.0/users"
#         body = json.loads(request.content.decode())
#         # basic payload expectations
#         assert body["displayName"] == "Alice"
#         assert body["userPrincipalName"] == "alice@example.com"
#         assert body["mailNickname"] == "alice"
#         assert "passwordProfile" in body
#         return httpx.Response(
#             201,
#             json={
#                 "id": "123",
#                 "displayName": "Alice",
#                 "userPrincipalName": "alice@example.com",
#                 "mailNickname": "alice",
#             },
#         )

#     c, r = make_client(handler)
#     queryset = c.users
#     user = User(
#         display_name="Alice",
#         user_principal_name="alice@example.com",
#         mail_nickname="alice",
#         password_profile=dict(
#             password="Pass@word1",
#             force_change_password_next_sign_in=True,
#         ),
#         client=queryset._client,
#         endpoint=queryset._endpoint,
#     )

#     saved = await user.save()
#     assert saved is True
#     assert user.id == "123"
#     assert user.display_name == "Alice"
#     assert user.user_principal_name == "alice@example.com"
#     assert user._dirty == set()
#     assert len(r) == 1
#     assert user.password_profile is None
#     assert user._endpoint == "/users/123"


# @pytest.mark.asyncio
# async def test_user_save_patches_dirty_fields(make_client: "MakeClient"):
#     def handler(request: httpx.Request) -> httpx.Response:
#         if request.method == "PATCH" and request.url.path.endswith("/users/123"):
#             body = json.loads(request.content.decode())
#             assert body == {"jobTitle": "Engineer"}
#             return httpx.Response(204, json={})
#         raise AssertionError(f"Unexpected request: {request.method} {request.url}")

#     c, r = make_client(handler)
#     queryset = c.users
#     user = queryset._model_class.from_graph(
#         {"id": "123", "displayName": "Alice"},
#         client=queryset._client,
#         endpoint=queryset._endpoint,
#     )
#     assert user._dirty == set()

#     user.job_title = "Engineer"
#     assert "job_title" in user._dirty

#     saved = await user.save()
#     assert saved is True
#     assert user._dirty == set()
#     assert len(r) == 1
#     assert user._endpoint == "/users/123"


# def test_user_queryset_select_builds_select(user_qs):
#     qs = user_qs.select("display_name", "mail_nickname")
#     params = qs._build_params()
#     assert params["$select"] == "displayName,mailNickname,id"


# def test_user_queryset_order_by(user_qs):
#     qs = user_qs.order_by("-display_name", "mail_nickname")
#     params = qs._build_params()
#     assert params["$orderby"] == "displayName desc,mailNickname"


# def test_user_queryset_filter_builds_filter_param(user_qs):
#     qs = user_qs.filter(display_name__startswith="A", account_enabled=True)
#     params = qs._build_params()
#     assert (
#         params["$filter"]
#         == "(startswith(displayName, 'A')) and (accountEnabled eq true)"
#     )


# def test_user_queryset_filter_with_q_object(user_qs):
#     from pymsgraph.models.query import Q

#     qs = user_qs.filter(
#         Q(display_name__startswith="A") | Q(display_name__startswith="Z")
#     )
#     params = qs._build_params()
#     assert (
#         params["$filter"]
#         == "((startswith(displayName, 'A')) or (startswith(displayName, 'Z')))"
#     )


# def test_user_queryset_rejects_unsupported_lookup(user_qs):
#     with pytest.raises(ValueError):
#         user_qs.filter(display_name__contains="x")._build_params()


# def test_user_queryset_top_sets_limit(user_qs):
#     qs = user_qs.top(5)
#     params = qs._build_params()
#     assert params["$top"] == "5"


# @pytest.mark.asyncio
# async def test_user_queryset_count(make_client: "MakeClient"):
#     def handler(request: httpx.Request) -> httpx.Response:
#         assert request.method == "GET"
#         assert request.url.path == "/v1.0/users"
#         return httpx.Response(
#             200,
#             json={
#                 "@odata.count": 42,
#                 "value": [{"id": "1"}, {"id": "2"}],
#             },
#         )

#     c, _ = make_client(handler)
#     qs = c.users.with_count()
#     async for item in qs:
#         ...
#     count = await qs.count()
#     assert count == 42
#     p = qs.iterator()
#     assert p._cached_count == 42
#     assert p is qs.iterator()


# def test_select_related_invalid_field(make_client: "MakeClient"):
#     c, _ = make_client(lambda req: httpx.Response(200, json={"value": []}))
#     qs = c.users

#     with pytest.raises(ValueError):
#         qs.select_related("does_not_exist")


# # def test_select_related_prefetch_licenses(make_client: "MakeClient"):
# #     def handler(request: httpx.Request) -> httpx.Response:
# #         if request.url.path == "/v1.0/users":
# #             return httpx.Response(
# #                 200,
# #                 json={
# #                     "value": [
# #                         {"id": "u1", "displayName": "User 1"},
# #                         {"id": "u2", "displayName": "User 2"},
# #                     ]
# #                 },
# #             )
# #         if request.url.path == "/v1.0/$batch":
# #             body = json.loads(request.content.decode())
# #             assert len(body.get("requests", [])) == 2
# #             responses = [
# #                 {"id": "1", "status": 200, "body": {"value": [{"skuId": "sku1"}]}},
# #                 {"id": "2", "status": 200, "body": {"value": [{"skuId": "sku2"}]}},
# #             ]
# #             return httpx.Response(200, json={"responses": responses})
# #         return httpx.Response(404)

# #     c, _ = make_client(handler)

# #     users = list(c.users.select_related("licenses"))
# #     assert [u.id for u in users] == ["u1", "u2"]

# #     assert [l.sku_id for l in users[0].licenses] == ["sku1"]
# #     assert [l.sku_id for l in users[1].licenses] == ["sku2"]


# def test_queryset_set_attr_and_save(make_client: "MakeClient"):
#     def handler(request: httpx.Request) -> httpx.Response:
#         if request.url.path == "/v1.0/users":
#             return httpx.Response(
#                 200,
#                 json={
#                     "value": [
#                         {"id": "u1", "displayName": "User 1", "city": "Old"},
#                         {"id": "u2", "displayName": "User 2", "city": "Old"},
#                     ]
#                 },
#             )
#         if request.url.path == "/v1.0/$batch":
#             body = json.loads(request.content.decode())
#             assert len(body.get("requests", [])) == 2
#             for req in body.get("requests", []):
#                 assert req["method"] == "PATCH"
#                 assert req["body"]["city"] == "Auckland"
#                 assert req["body"]["department"] == "IT"
#             return httpx.Response(
#                 200,
#                 json={
#                     "responses": [
#                         {"id": "1", "status": 204},
#                         {"id": "2", "status": 204},
#                     ]
#                 },
#             )
#         return httpx.Response(404)

#     c, _ = make_client(handler)
#     qs = c.users

#     updated = qs.set_attr("city", "Auckland").set_attr("department", "IT").save()

#     assert updated == 2


# def test_queryset_set_attr_rejects_unknown_field(make_client: "MakeClient"):
#     c, _ = make_client(lambda req: httpx.Response(200, json={"value": []}))

#     with pytest.raises(ValueError):
#         c.users.set_attr("not_a_field", "x")


# @pytest.mark.asyncio
# async def test_user_queryset_get_by_id(make_client: "MakeClient"):
#     def handler(request: httpx.Request) -> httpx.Response:
#         assert request.method == "GET"
#         assert request.url.path == "/v1.0/users/abc"
#         return httpx.Response(
#             200,
#             json={
#                 "id": "abc",
#                 "displayName": "Bob",
#                 "userPrincipalName": "bob@example.com",
#                 "mailNickname": "bob",
#             },
#         )

#     c, _ = make_client(handler)
#     qs = c.users
#     user = await qs.get(id="abc")
#     assert user is not None
#     assert user.id == "abc"
#     assert user.display_name == "Bob"
#     assert user.user_principal_name == "bob@example.com"


# def test_user_groups_add_remove(make_client: "MakeClient"):
#     seen: list[tuple[str, str]] = []

#     def handler(request: httpx.Request) -> httpx.Response:
#         assert request.method == "POST"
#         seen.append((request.method, request.url.path))
#         if request.method == "POST" and request.url.path == "/v1.0/$batch":
#             body = json.loads(request.content.decode())
#             requests = body.get("requests", [])
#             first_method = requests[0]["method"] if requests else None
#             if first_method == "POST":
#                 assert requests == [
#                     {
#                         "id": "1",
#                         "method": "POST",
#                         "url": "/groups/g1/members/$ref",
#                         "headers": {"Content-Type": "application/json"},
#                         "body": {
#                             "@odata.id": "https://graph.microsoft.com/v1.0/directoryObjects/123"
#                         },
#                     }
#                 ]
#             elif first_method == "DELETE":
#                 assert requests == [
#                     {
#                         "id": "1",
#                         "method": "DELETE",
#                         "url": "/groups/g1/members/123/$ref",
#                     }
#                 ]
#             else:
#                 raise AssertionError(f"Unexpected batch payload: {requests}")
#             return httpx.Response(200, json={"responses": [{"id": "1", "status": 204}]})
#         raise AssertionError(f"Unexpected request: {request.method} {request.url}")

#     c, r = make_client(handler)
#     user = c.users.make_from_graph({"id": "123", "displayName": "Alice"})
#     user.groups.add("g1")
#     user.groups.remove("g1")

#     assert seen == [
#         ("POST", "/v1.0/$batch"),
#         ("POST", "/v1.0/$batch"),
#     ]
#     assert len(r) == 2


# def test_user_groups_add_remove_multiple(make_client: "MakeClient"):
#     seen: list[list[dict[str, Any]]] = []

#     def handler(request: httpx.Request) -> httpx.Response:
#         if request.method == "POST" and request.url.path == "/v1.0/$batch":
#             body = json.loads(request.content.decode())
#             seen.append(body.get("requests", []))
#             return httpx.Response(200, json={"responses": [{"id": "1", "status": 204}]})
#         raise AssertionError(f"Unexpected request: {request.method} {request.url}")

#     c, r = make_client(handler)
#     user = c.users.make_from_graph({"id": "123", "displayName": "Alice"})
#     user.groups.add("g1", "g2")
#     user.groups.remove("g1", "g2")

#     # Two batch calls: add then remove
#     assert len(seen) == 2
#     add_requests, remove_requests = seen

#     # Add batch: two POSTs to /groups/{gid}/members/$ref with correct body
#     assert {req["method"] for req in add_requests} == {"POST"}
#     assert {req["url"] for req in add_requests} == {
#         "/groups/g1/members/$ref",
#         "/groups/g2/members/$ref",
#     }
#     for req in add_requests:
#         assert req.get("headers", {}).get("Content-Type") == "application/json"
#         assert req.get("body") == {
#             "@odata.id": "https://graph.microsoft.com/v1.0/directoryObjects/123"
#         }

#     # Remove batch: two DELETEs to /groups/{gid}/members/{uid}/$ref
#     assert {req["method"] for req in remove_requests} == {"DELETE"}
#     assert {req["url"] for req in remove_requests} == {
#         "/groups/g1/members/123/$ref",
#         "/groups/g2/members/123/$ref",
#     }

#     assert len(r) == 2


# def test_user_licenses_add_remove(make_client: "MakeClient"):
#     def handler(request: httpx.Request) -> httpx.Response:
#         body = json.loads(request.content.decode())
#         assert request.method == "POST"
#         assert request.url.path == "/v1.0/users/123/assignLicense"
#         if body["addLicenses"]:
#             assert body == {
#                 "addLicenses": [{"skuId": "sku1", "disabledPlans": []}],
#                 "removeLicenses": [],
#             }
#         else:
#             assert body == {
#                 "addLicenses": [],
#                 "removeLicenses": ["sku1"],
#             }
#         return httpx.Response(200, json={"responses": [{"id": "1", "status": 200}]})

#     c, _ = make_client(handler)
#     user = c.users.make_from_graph({"id": "123", "displayName": "Alice"})
#     user.assigned_licenses.add("sku1")
#     user.assigned_licenses.remove("sku1")


# def test_user_groups_descriptor(make_client: "MakeClient"):
#     def handler(request: httpx.Request) -> httpx.Response:
#         assert request.method == "GET"
#         assert request.url.path == "/v1.0/users/123/memberOf"
#         if request.method == "GET" and request.url.path == "/v1.0/users/123/memberOf":
#             return httpx.Response(
#                 200,
#                 json={
#                     "value": [
#                         {
#                             "id": "g1",
#                             "displayName": "Group One",
#                             "mailNickname": "g1",
#                         }
#                     ]
#                 },
#             )
#         raise AssertionError(f"Unexpected request: {request.method} {request.url}")

#     c, r = make_client(handler)
#     # qs = UserQuerySet(client)
#     user = c.users.make_from_graph({"id": "123", "displayName": "Alice"})
#     user_groups_qs = user.groups
#     groups = list(user_groups_qs)
#     assert len(groups) == 1
#     g = groups[0]
#     assert g.id == "g1"
#     assert g.display_name == "Group One"
#     assert len(r) == 1


# def test_user_queryset_filter_licenses_sku_id(user_qs):
#     qs = user_qs.filter(
#         assigned_licenses__sku_id="cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46"
#     )
#     params = qs._build_params()
#     assert (
#         params["$filter"]
#         == "(assignedLicenses/any(u:u/skuId eq 'cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46'))"
#     )


# def test_user_queryset_filter_licenses_sku_id_with_lookup(user_qs):
#     qs = user_qs.filter(
#         assigned_licenses__sku_id__exact="cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46"
#     )
#     params = qs._build_params()
#     assert (
#         params["$filter"]
#         == "(assignedLicenses/any(u:u/skuId eq 'cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46'))"
#     )


# def test_user_queryset_filter_licenses_isnull(user_qs):
#     qs = user_qs.filter(assigned_licenses__isnull=True)
#     params = qs._build_params()
#     assert params["$filter"] == "(assignedLicenses/$count eq 0)"


# def test_user_queryset_filter_licenses_is_not_null(user_qs):
#     qs = user_qs.filter(assigned_licenses__isnull=False)
#     params = qs._build_params()
#     assert params["$filter"] == "(assignedLicenses/$count ne 0)"


# @pytest.mark.asyncio
# async def test_user_delete_requires_id(make_client: "MakeClient"):
#     # Ensure no HTTP call occurs
#     def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
#         raise AssertionError("HTTP should not be called")

#     c, _ = make_client(handler)
#     user = c.users._model_class(
#         display_name="Unsaved",
#         # user_principal_name="unsaved@example.com",
#         mail_nickname="unsaved",
#     )
#     with pytest.raises(AttributeError):
#         await user.delete(force=True)


# @pytest.mark.asyncio
# async def test_user_delete_force_calls_delete(make_client: "MakeClient"):
#     def handler(request: httpx.Request) -> httpx.Response:
#         assert request.method == "DELETE"
#         assert request.url.path == "/v1.0/users/u_del"
#         return httpx.Response(204)

#     c, _ = make_client(handler)
#     user = c.users._model_class.from_graph(
#         {
#             "id": "u_del",
#             "displayName": "Del",
#             "userPrincipalName": "del@example.com",
#             "accountEnabled": True,
#             "mailNickname": "del",
#         },
#         client=c,
#     )

#     await user.delete(force=True)
#     # after local cleanup, id should no longer be present
#     assert user.id is None


# @pytest.mark.asyncio
# async def test_user_delete_requires_force(make_client: "MakeClient"):
#     # Ensure no HTTP call occurs
#     def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
#         raise AssertionError("HTTP should not be called")

#     c, _ = make_client(handler)
#     user = c.users._model_class.from_graph(
#         {
#             "id": "u_del",
#             "displayName": "Del",
#             "userPrincipalName": "del@example.com",
#             "accountEnabled": True,
#             "mailNickname": "del",
#         }
#     )
#     with pytest.raises(RuntimeError):
#         await user.delete()


# @pytest.mark.asyncio
# async def test_user_reset_password_requires_id(make_client: "MakeClient"):
#     # Ensure no HTTP call occurs
#     def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
#         raise AssertionError("HTTP should not be called")

#     c, _ = make_client(handler)

#     with pytest.raises(ValueError):
#         await c.users.create(
#             display_name="Unsaved",
#             user_principal_name="unsaved@example.com",
#             mail_nickname="unsaved",
#         )
