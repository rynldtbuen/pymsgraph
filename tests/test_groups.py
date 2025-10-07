from typing import TYPE_CHECKING, Callable

import pytest

if TYPE_CHECKING:
    from pymsgraph import Client

from pymsgraph.groups import Groups


@pytest.fixture
def groups(client: "Client") -> Groups:
    return client.groups


def test_groups(groups: Groups, url: str, check_request_attributes: Callable):
    assert groups.url == f"{url}/groups"
    check_request_attributes(groups, _type="method", GET=True)
    check_request_attributes(
        groups,
        _type="query_param",
        SELECT=True,
        ORDERBY=True,
        FILTER=True,
        TOP=True,
        SEARCH=True,
        COUNT=True,
    )

    groups.search("displayName:Video OR description:prod").orderby("displayName")
    assert (
        groups.url_with_query_params
        == f'{url}/groups?$search="displayName:Video" OR "description:prod"&$orderby=displayName'
    )


def test_group(groups: Groups, url: str, check_request_attributes: Callable):
    obj = groups.by_id("12345")
    assert obj.url == f"{url}/groups/12345"
    check_request_attributes(obj, _type="method", GET=True)
    check_request_attributes(obj, _type="query_param", SELECT=True)


def test_group_members(groups: Groups, url: str, check_request_attributes: Callable):
    obj = groups.by_id("12345").members
    assert obj.url == f"{url}/groups/12345/members"
    check_request_attributes(obj, _type="method", GET=True)
    check_request_attributes(
        obj, _type="query_param", SELECT=True, FILTER=True, ORDERBY=True
    )


def test_group_members_ref(
    groups: Groups, url: str, check_request_attributes: Callable
):
    obj = groups.by_id("12345").members.ref
    assert obj.url == f"{url}/groups/12345/members/$ref"
    check_request_attributes(obj, _type="method", POST=True)
    check_request_attributes(obj, _type="query_param")


def test_group_members_by_dir_obj_id(
    groups: Groups, url: str, check_request_attributes: Callable
):
    obj = groups.by_id("12345").members.by_directory_object_id("12345")
    assert obj.url == f"{url}/groups/12345/members/12345"
    check_request_attributes(obj, _type="method")
    check_request_attributes(obj, _type="query_param")


def test_group_members_by_dir_obj_id_ref(
    groups: Groups, url: str, check_request_attributes: Callable
):
    obj = groups.by_id("12345").members.by_directory_object_id("12345").ref
    assert obj.url == f"{url}/groups/12345/members/12345/$ref"
    check_request_attributes(obj, _type="method", DELETE=True)
    check_request_attributes(obj, _type="query_param")


def test_group_members_graph_user(
    groups: Groups, url: str, check_request_attributes: Callable
):
    obj = groups.by_id("12345").members.graph_user
    assert obj.url == f"{url}/groups/12345/members/microsoft.graph.user"
    check_request_attributes(obj, _type="method", GET=True)
    check_request_attributes(
        obj,
        _type="query_param",
        FILTER=True,
        SELECT=True,
        TOP=True,
        SEARCH=True,
        COUNT=True,
        ORDERBY=True,
    )

    obj.orderby("displayName").search("displayName:Pr").select("displayName,id")
    assert (
        obj.url_with_query_params
        == f'{url}/groups/12345/members/microsoft.graph.user?$orderby=displayName&$search="displayName:Pr"&$select=displayName,id'
    )
