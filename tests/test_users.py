from typing import Callable, TYPE_CHECKING
import pytest

if TYPE_CHECKING:
    from pymsgraph import Client

from pymsgraph.users import Users


@pytest.fixture
def users(client: "Client") -> Users:
    return client.users


def test_users(users: Users, url: str, check_request_attributes: Callable):
    assert users.url == f"{url}/users"
    check_request_attributes(users, _type="method", GET=True)
    check_request_attributes(
        users,
        _type="query_param",
        SELECT=True,
        ORDERBY=True,
        FILTER=True,
        TOP=True,
        SEARCH=True,
        COUNT=True,
    )

    users.filter("endswith(mail,'a@contoso.com')").orderby("userPrincipalName").count()
    assert (
        users.url_with_query_params
        == f"{url}/users?$filter=endswith(mail,'a@contoso.com')&$orderby=userPrincipalName&$count=true"
    )


def test_user(users: Users, url: str, check_request_attributes: Callable):
    obj = users.by_id("12345")
    assert obj.url == f"{url}/users/12345"
    check_request_attributes(obj, _type="method", GET=True, PATCH=True, DELETE=True)
    check_request_attributes(obj, _type="query_param", SELECT=True)

    # users.filter("endswith(mail,'a@contoso.com')").orderby("userPrincipalName").count()
    # assert (
    #     users.url_with_query_params
    #     == f"{url}/users?$filter=endswith(mail,'a@contoso.com')&$orderby=userPrincipalName&$count=true"
    # )


def test_user_member_of(users: Users, url: str, check_request_attributes: Callable):
    obj = users.by_id("12345").member_of
    assert obj.url == f"{url}/users/12345/memberOf"
    check_request_attributes(obj, _type="method", GET=True)
    check_request_attributes(
        obj, _type="query_param", SELECT=True, FILTER=True, ORDERBY=True
    )


def test_user_default_drive(users: Users, url: str, check_request_attributes: Callable):
    obj = users.by_id("12345").drive
    assert obj.url == f"{url}/users/12345/drive"
    check_request_attributes(obj, _type="method", GET=True)
    check_request_attributes(obj, _type="query_param", SELECT=True)


def test_user_default_drive_root_drive_item(
    users: Users, url: str, check_request_attributes: Callable
):
    obj = users.by_id("12345").drive.root
    assert obj.url == f"{url}/users/12345/drive/root"
    check_request_attributes(obj, _type="method", GET=True, PATCH=True)
    check_request_attributes(obj, _type="query_param", SELECT=True, SEARCH=True)
