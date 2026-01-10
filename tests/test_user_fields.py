from __future__ import annotations
from typing import TYPE_CHECKING

import httpx
import pytest

from pymsgraph.models.user import User
from pymsgraph.models.user.model_fields import (
    AssignedLicense,
    AssignedLicensesQuerySet,
    PasswordProfile,
)

if TYPE_CHECKING:
    from tests.conftest import MakeClient


# def test_user_fields_registered() -> None:
#     expected = {
#         "id",
#         "display_name",
#         "account_enabled",
#         "mail_nickname",
#         "user_principal_name",
#         "password_profile",
#     }
#     print(User.FIELDS)
#     assert expected.issubset(set(User.FIELDS))


def test_user_required_fields() -> None:
    assert User.REQUIRED_FIELDS == {
        "account_enabled",
        "display_name",
        "mail_nickname",
        "user_principal_name",
    }


# def test_password_profile_fields_registered() -> None:
#     expected = {
#         "password",
#         "force_change_password_next_sign_in",
#         "force_change_password_next_sign_in_with_mfa",
#     }
#     assert expected.issubset(set(PasswordProfile.FIELDS))


def test_user_password_profile() -> None:
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


def test_user_assigned_licenses(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    c, _ = make_client(handler)
    u = c.users.make(
        id="u1",
        display_name="Alice",
        account_enabled=True,
        mail_nickname="alice",
        user_principal_name="alice@example.com",
    )

    qs = u.assigned_licenses
    assert isinstance(qs, AssignedLicensesQuerySet)
    assert qs._endpoint == "/users/u1/assignedLicense"
    assert qs._model_class is AssignedLicense


@pytest.mark.asyncio
async def test_user_assigned_licenses_from_graph_returns_models(
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


def test_user_assigned_licenses_field_builds_queryset(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    client, _ = make_client(handler)
    user = User(
        id="u1",
        client=client,
        endpoint="/users",
        display_name="Alice",
        account_enabled=True,
        mail_nickname="alice",
        user_principal_name="alice@example.com",
    )

    qs = user.assigned_licenses
    assert isinstance(qs, AssignedLicensesQuerySet)
    assert qs._endpoint == "/users/u1/assignedLicense"
    assert qs._model_class is AssignedLicense
