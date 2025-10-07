from typing import TYPE_CHECKING, Callable
import pytest

if TYPE_CHECKING:
    from pymsgraph import Client

from pymsgraph import sites as s


@pytest.fixture
def sites(client: "Client") -> s.Sites:
    return client.sites


# @pytest.fixture
# def site_by_id(sites) -> s.SiteById:
#     return sites.by_id("12345")


# @pytest.fixture
# def site_root(sites) -> s.SiteRoot:
#     return sites.root


# @pytest.fixture
# def site_root_by_relative_path(site_root) -> s.SiteByRelativePath:
#     return site_root.by_relative_path("sites/testpath12345")


def test_sites(sites: s.Sites, url: str, check_request_attributes: Callable):
    assert sites.url == f"{url}/sites"

    check_request_attributes(sites, _type="method", GET=True)
    check_request_attributes(sites, _type="query_param", SELECT=True, SEARCH=True)


def test_site_root(sites: s.Sites, url: str, check_request_attributes: Callable):
    obj = sites.root
    assert obj.url == f"{url}/sites/root"

    check_request_attributes(obj, _type="method", GET=True)
    check_request_attributes(obj, _type="query_param", SELECT=True)


# By relative path
def test_site_root_by_relative_path(
    sites: s.Sites, url: str, check_request_attributes: Callable
):
    obj = sites.root.by_relative_path("test-site")
    assert obj.url == f"{url}/sites/root:/test-site"

    check_request_attributes(obj, _type="method", GET=True)
    check_request_attributes(obj, _type="query_param", SELECT=True)


# Default drive
def test_site_root_default_drive(
    sites: s.Sites, url: str, check_request_attributes: Callable
):
    obj = sites.root.by_relative_path("test-site").drive
    assert obj.url == f"{url}/sites/root:/test-site:/drive"

    check_request_attributes(obj, _type="method", GET=True)
    check_request_attributes(obj, _type="query_param", SELECT=True)


def test_site_by_hostname(sites: s.Sites, url: str, check_request_attributes: Callable):
    obj = sites("test.sharepoint.com")
    assert obj.url == f"{url}/sites/test.sharepoint.com"

    check_request_attributes(obj, _type="method", GET=True)
    check_request_attributes(obj, _type="query_param", SELECT=True)


# By relative path
def test_site_by_hostname_by_relative_path(
    sites: s.Sites, url: str, check_request_attributes: Callable
):
    obj = sites("test.sharepoint.com").by_relative_path("test-site")
    assert obj.url == f"{url}/sites/test.sharepoint.com:/test-site"

    check_request_attributes(obj, _type="method", GET=True)
    check_request_attributes(obj, _type="query_param", SELECT=True)


# def test_site_by_relative_path(
#     site_root_by_relative_path: s.SiteByRelativePath,
#     url: str,
#     check_request_attributes: Callable,
# ):
#     assert site_root_by_relative_path.url == f"{url}/sites/root:/sites/testpath12345"

#     check_request_attributes(site_root_by_relative_path, _type="method", GET=True)
#     check_request_attributes(
#         site_root_by_relative_path, _type="query_param", SELECT=True
#     )


def test_site_by_hostname_default_drive(
    sites: s.Sites,
    url: str,
    check_request_attributes: Callable,
):
    obj = sites("test.sharepoint.com").by_relative_path("test-site").drive
    assert obj.url == f"{url}/sites/test.sharepoint.com:/test-site:/drive"

    check_request_attributes(obj, _type="method", GET=True)
    check_request_attributes(obj, _type="query_param", SELECT=True)


# # Default drive root item
# def test_site_by_hostname_03(
#     sites: s.Sites,
#     url: str,
#     check_request_attributes: Callable,
# ):
#     obj = sites("test.sharepoint.com").by_relative_path("test-site").drive
#     assert obj.url == f"{url}/sites/test.sharepoint.com:/test-site:/drive"

#     check_request_attributes(obj, _type="method", GET=True, PATCH=True)
#     check_request_attributes(obj, _type="query_param", SELECT=True, SEARCH=True)


# def test_site_by_relative_default_drive_root_item_children(
#     site_root_by_relative_path: s.SiteByRelativePath,
#     url: str,
#     check_request_attributes: Callable,
# ):
#     obj = site_root_by_relative_path.drive.root.children
#     assert obj.url == f"{url}/sites/root:/sites/testpath12345:/drive/root/children"

#     check_request_attributes(obj, _type="method", GET=True, POST=True)
#     check_request_attributes(
#         obj, _type="query_param", SELECT=True, ORDERBY=True, TOP=True
#     )


# def test_site_by_relative_default_drive_root_item_by_relative_path(
#     site_root_by_relative_path: s.SiteByRelativePath,
#     url: str,
#     check_request_attributes: Callable,
# ):

#     obj = site_root_by_relative_path.drive.root.by_relative_path("secret/files")
#     assert obj.url == f"{url}/sites/root:/sites/testpath12345:/drive/root:/secret/files"

#     check_request_attributes(obj, _type="method", GET=True, PATCH=True)
#     check_request_attributes(obj, _type="query_param", SELECT=True, SEARCH=True)


# def test_site_by_relative_default_drive_root_item_by_path_relative_children(
#     site_root_by_relative_path: s.SiteByRelativePath,
#     url: str,
#     check_request_attributes: Callable,
# ):
#     obj = site_root_by_relative_path.drive.root.by_relative_path(
#         "secret/files"
#     ).children

#     assert (
#         obj.url
#         == f"{url}/sites/root:/sites/testpath12345:/drive/root:/secret/files:/children"
#     )

#     check_request_attributes(obj, _type="method", GET=True, POST=True)
#     check_request_attributes(
#         obj,
#         _type="query_param",
#         SELECT=True,
#         ORDERBY=True,
#         TOP=True,
#     )


def test_site_by_id(sites: s.Sites, url: str, check_request_attributes: Callable):
    obj = sites.by_id("12345")
    assert obj.url == f"{url}/sites/12345"

    check_request_attributes(obj, _type="method", GET=True)
    check_request_attributes(obj, _type="query_param", SELECT=True)


def test_site_by_id_default_drive(
    sites: s.Sites,
    url: str,
    check_request_attributes: Callable,
):
    obj = sites.by_id("12345").drive
    assert obj.url == f"{url}/sites/12345/drive"

    check_request_attributes(obj, _type="method", GET=True)
    check_request_attributes(obj, _type="query_param", SELECT=True)


def test_site_by_id_default_drive_root_item(
    sites: s.Sites,
    url: str,
    check_request_attributes: Callable,
):
    obj = sites.by_id("12345").drive.root
    assert obj.url == f"{url}/sites/12345/drive/root"

    check_request_attributes(obj, _type="method", GET=True, PATCH=True)
    check_request_attributes(obj, _type="query_param", SELECT=True, SEARCH=True)


def test_drive_root_item_children(
    sites: s.Sites,
    url: str,
    check_request_attributes: Callable,
):
    obj = sites.by_id("12345").drive.root.children
    assert obj.url == f"{url}/sites/12345/drive/root/children"

    check_request_attributes(obj, _type="method", GET=True, POST=True)
    check_request_attributes(
        obj, _type="query_param", SELECT=True, ORDERBY=True, TOP=True
    )


def test_drive_root_item_by_relative_path(
    sites: s.Sites,
    url: str,
    check_request_attributes: Callable,
):
    obj = sites.by_id("12345").drive.root.by_relative_path("test_folder/file.csv")
    assert obj.url == f"{url}/sites/12345/drive/root:/test_folder/file.csv"

    check_request_attributes(obj, _type="method", GET=True, PATCH=True)
    check_request_attributes(obj, _type="query_param", SELECT=True, SEARCH=True)


def test_drive_root_item_by_relative_path_children(
    sites: s.Sites,
    url: str,
    check_request_attributes: Callable,
):
    obj = (
        sites.by_id("12345")
        .drive.root.by_relative_path("test_folder/test_folder1")
        .children
    )
    assert (
        obj.url == f"{url}/sites/12345/drive/root:/test_folder/test_folder1:/children"
    )

    check_request_attributes(obj, _type="method", GET=True, POST=True)
    check_request_attributes(
        obj, _type="query_param", SELECT=True, ORDERBY=True, TOP=True
    )


def test_sites_by_id_lists(
    sites: s.Sites, url: str, check_request_attributes: Callable
):
    obj = sites.by_id("12345").lists
    assert obj.url == f"{url}/sites/12345/lists"

    check_request_attributes(obj, _type="method", GET=True)
    check_request_attributes(
        obj, _type="query_param", SELECT=True, ORDERBY=True, FILTER=True
    )


def test_sites_by_id_lists_by_id(
    sites: s.Sites,
    url: str,
    check_request_attributes: Callable,
):
    obj = sites.by_id("12345").lists.by_id("12345")
    assert obj.url == f"{url}/sites/12345/lists/12345"

    check_request_attributes(obj, _type="method", GET=True)
    check_request_attributes(obj, _type="query_param", SELECT=True)


def test_sites_by_id_lists_by_id_items(
    sites: s.Sites,
    url: str,
    check_request_attributes: Callable,
):
    obj = sites.by_id("12345").lists.by_id("12345").items
    assert obj.url == f"{url}/sites/12345/lists/12345/items"

    check_request_attributes(obj, _type="method", GET=True, POST=True)
    check_request_attributes(
        obj, _type="query_param", SELECT=True, FILTER=True, ORDERBY=True
    )


# def test_list_from_site_relative_path(
#     site_root_by_relative_path: s.SiteByRelativePath,
#     url: str,
#     check_request_attributes: Callable,
# ):
#     obj = site_root_by_relative_path.lists
#     assert obj.url == f"{url}/sites/root:/sites/testpath12345:/lists"

#     check_request_attributes(obj, _type="method", GET=True)
#     check_request_attributes(
#         obj, _type="query_param", SELECT=True, ORDERBY=True, FILTER=True
#     )


# def test_list_by_name_from_site_relative_path(
#     site_root_by_relative_path: s.SiteByRelativePath,
#     url: str,
#     check_request_attributes: Callable,
# ):
#     obj = site_root_by_relative_path.lists.by_name("Test list")
#     assert obj.url == f"{url}/sites/root:/sites/testpath12345:/lists/Test list"

#     check_request_attributes(obj, _type="method", GET=True)
#     check_request_attributes(obj, _type="query_param", SELECT=True)


# def test_list_by_name_items_from_site_relative_path(
#     site_root_by_relative_path: s.SiteByRelativePath,
#     url: str,
#     check_request_attributes: Callable,
# ):
#     obj = site_root_by_relative_path.lists.by_name("Test list").items
#     assert obj.url == f"{url}/sites/root:/sites/testpath12345:/lists/Test list/items"

#     check_request_attributes(obj, _type="method", GET=True, POST=True)
#     check_request_attributes(
#         obj, _type="query_param", SELECT=True, FILTER=True, ORDERBY=True
#     )


# def test_list_by_name_items_by_id_from_site_relative_path(
#     site_root_by_relative_path: s.SiteByRelativePath,
#     url: str,
#     check_request_attributes: Callable,
# ):
#     obj = site_root_by_relative_path.lists.by_name("Test list").items.by_id("12345")
#     assert (
#         obj.url == f"{url}/sites/root:/sites/testpath12345:/lists/Test list/items/12345"
#     )

#     check_request_attributes(obj, _type="method", GET=True, DELETE=True)
#     check_request_attributes(obj, _type="query_param", SELECT=True)


# def test_list_by_name_items_fields_by_id_from_site_relative_path(
#     site_root_by_relative_path: s.SiteByRelativePath,
#     url: str,
#     check_request_attributes: Callable,
# ):
#     obj = site_root_by_relative_path.lists.by_name("Test list").items.by_id("12345")
#     assert (
#         obj.url == f"{url}/sites/root:/sites/testpath12345:/lists/Test list/items/12345"
#     )

#     check_request_attributes(obj, _type="method", GET=True, DELETE=True)
#     check_request_attributes(obj, _type="query_param", SELECT=True)


# def test_list_item_fields(
#     site_root_by_relative_path: s.SiteByRelativePath,
#     url: str,
#     check_request_attributes: Callable,
# ):
#     obj = (
#         site_root_by_relative_path.lists.by_name("Test list")
#         .items.by_id("12345")
#         .fields
#     )
#     assert (
#         obj.url
#         == f"{url}/sites/root:/sites/testpath12345:/lists/Test list/items/12345/fields"
#     )

#     check_request_attributes(obj, _type="method", GET=True, PATCH=True)
#     check_request_attributes(obj, _type="query_param")
