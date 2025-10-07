import json
from typing import Any, Callable

import pytest

from pymsgraph import Client
from pymsgraph.drives import Drive, Drives


@pytest.fixture
def drive_data():
    data = """
    {
       	"createdDateTime": "2017-07-27T02:41:36Z",
       	"description": "",
       	"id": "b!-RIj2DuyvEyV1T4NlOaMHk8XkS_I8MdFlUCq1BlcjgmhRfAj3-Z8RY2VpuvV_tpd",
       	"lastModifiedDateTime": "2018-03-27T07:34:38Z",
       	"name": "OneDrive",
       	"webUrl": "https://m365x214355-my.sharepoint.com/personal/meganb_m365x214355_onmicrosoft_com/Documents",
       	"driveType": "business",
       	"createdBy": {
       		"user": {
       			"displayName": "System Account"
       		}
       	},
       	"lastModifiedBy": {
       		"user": {
       			"email": "MeganB@contoso.com",
       			"id": "48d31887-5fad-4d73-a9f5-3c356e68a038",
       			"displayName": "Megan Bowen"
       		}
       	},
       	"owner": {
       		"user": {
       			"email": "MeganB@contoso.com",
       			"id": "48d31887-5fad-4d73-a9f5-3c356e68a038",
       			"displayName": "Megan Bowen"
       		}
       	},
       	"quota": {
       		"deleted": 0,
       		"remaining": 1099217021300,
       		"state": "normal",
       		"total": 1099511627776,
       		"used": 294606476
       	}
    }
    """
    return json.loads(data)


@pytest.fixture
def drives(client: Client) -> Drives:
    return client.drives


@pytest.fixture
def drive(drives: Drives) -> Drive:
    return drives.by_id(
        "b!-RIj2DuyvEyV1T4NlOaMHk8XkS_I8MdFlUCq1BlcjgmhRfAj3-Z8RY2VpuvV_tpd"
    )


def test_drives(drives: Drives, url: str, check_request_attributes: Callable):
    assert drives.url == f"{url}/drives"

    check_request_attributes(drives, _type="method")
    check_request_attributes(drives, _type="query_param")


def test_drive(drive: Drive, url: str, check_request_attributes: Callable):
    assert (
        drive.id == "b!-RIj2DuyvEyV1T4NlOaMHk8XkS_I8MdFlUCq1BlcjgmhRfAj3-Z8RY2VpuvV_tpd"
    )
    assert (
        drive._drive_id
        == "b!-RIj2DuyvEyV1T4NlOaMHk8XkS_I8MdFlUCq1BlcjgmhRfAj3-Z8RY2VpuvV_tpd"
    )
    assert (
        drive.url
        == f"{url}/drives/b!-RIj2DuyvEyV1T4NlOaMHk8XkS_I8MdFlUCq1BlcjgmhRfAj3-Z8RY2VpuvV_tpd"
    )

    check_request_attributes(drive, _type="method", GET=True)
    check_request_attributes(drive, _type="query_param", SELECT=True)


def test_drive_items(drive: Drive, url: str, check_request_attributes: Callable):
    obj = drive.items
    assert (
        obj.url
        == f"{url}/drives/b!-RIj2DuyvEyV1T4NlOaMHk8XkS_I8MdFlUCq1BlcjgmhRfAj3-Z8RY2VpuvV_tpd/items"
    )

    check_request_attributes(obj, _type="method")
    check_request_attributes(obj, _type="query_param")


def test_drive_item_by_id(drive: Drive, url: str, check_request_attributes: Callable):
    obj = drive.items.by_id("12345")
    assert (
        obj.url
        == f"{url}/drives/b!-RIj2DuyvEyV1T4NlOaMHk8XkS_I8MdFlUCq1BlcjgmhRfAj3-Z8RY2VpuvV_tpd/items/12345"
    )
    check_request_attributes(obj, _type="method", GET=True, PATCH=True)
    check_request_attributes(obj, _type="query_param", SELECT=True, SEARCH=True)


def test_drive_item_by_id_children(
    drive: Drive, url: str, check_request_attributes: Callable
):
    obj = drive.items.by_id("12345").children
    assert (
        obj.url
        == f"{url}/drives/b!-RIj2DuyvEyV1T4NlOaMHk8XkS_I8MdFlUCq1BlcjgmhRfAj3-Z8RY2VpuvV_tpd/items/12345/children"
    )

    check_request_attributes(obj, _type="method", GET=True, POST=True)
    check_request_attributes(
        obj, _type="query_param", SELECT=True, ORDERBY=True, TOP=True
    )


def test_drive_item_by_relative_path(
    drive: Drive, url: str, check_request_attributes: Callable
):
    obj = drive.items.by_id("12345").by_relative_path("test_sample/files")
    assert (
        obj.url
        == f"{url}/drives/b!-RIj2DuyvEyV1T4NlOaMHk8XkS_I8MdFlUCq1BlcjgmhRfAj3-Z8RY2VpuvV_tpd/items/12345:/test_sample/files"
    )

    check_request_attributes(obj, _type="method", GET=True, PATCH=True)
    check_request_attributes(obj, _type="query_param", SELECT=True, SEARCH=True)


def test_drive_item_by_relative_path_children(
    drive: Drive, url: str, check_request_attributes: Callable
):
    obj = drive.items.by_id("12345").by_relative_path("test_sample/files").children

    assert (
        obj.url
        == f"{url}/drives/b!-RIj2DuyvEyV1T4NlOaMHk8XkS_I8MdFlUCq1BlcjgmhRfAj3-Z8RY2VpuvV_tpd/items/12345:/test_sample/files:/children"
    )

    check_request_attributes(obj, _type="method", GET=True, POST=True)
    check_request_attributes(
        obj, _type="query_param", SELECT=True, ORDERBY=True, TOP=True
    )
