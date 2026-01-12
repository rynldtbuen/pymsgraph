import json
from typing import TYPE_CHECKING

import httpx
import pytest

from pymsgraph.models.directory_object import DirectoryObject
from pymsgraph.models.group import Group
from pymsgraph.models.user import User, UserQuerySet
from pymsgraph.models.user.model_fields import AssignedLicense, PasswordProfile
from pymsgraph.models.user.query_fields import (
    AssignedLicensesQuerySet,
    GroupsQuerySet,
    MemberOfQuerySet,
)

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
    assert u._endpoint == "/users/123"
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
    assert user._endpoint == "/users/123"
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

    with pytest.raises(ValueError):
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
    assert qs._endpoint == "/users/u1/assignLicense"
    assert qs._model_class is AssignedLicense


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


def test_qs_filter_assigned_licenses(users_qs: UserQuerySet):

    qs = users_qs._clone()
    params = (
        qs._clone()
        .assigned_licenses.filter(sku_id="cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46")
        ._build_params()
    )
    assert (
        params["$filter"]
        == "(assignedLicenses/any(u:u/skuId eq 'cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46'))"
    )

    params = (
        qs._clone()
        .assigned_licenses.filter(sku_id__exact="cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46")
        ._build_params()
    )
    assert (
        params["$filter"]
        == "(assignedLicenses/any(u:u/skuId eq 'cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46'))"
    )

    params = qs._clone().assigned_licenses.filter(isnull=True)._build_params()
    assert params["$filter"] == "(assignedLicenses/$count eq 0)"

    params = qs._clone().assigned_licenses.filter(isnull=False)._build_params()
    assert params["$filter"] == "(assignedLicenses/$count ne 0)"


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
    assert member_of_qs._endpoint == "/users/u1/memberOf"
    assert member_of_qs._model_class is DirectoryObject

    groups_qs: GroupsQuerySet = u.member_of.groups
    assert isinstance(groups_qs, GroupsQuerySet)
    assert groups_qs._endpoint == "/users/u1/memberOf/microsoft.graph.group"
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
