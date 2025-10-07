from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from pymsgraph import Client

import pytest

from pymsgraph.directory_objects import DirectoryObjects


@pytest.fixture
def directory_objects(client: "Client") -> DirectoryObjects:
    return client.directory_objects


def test_directory_objects(
    directory_objects: DirectoryObjects, url: str, check_request_attributes: Callable
) -> None:

    assert directory_objects.url == f"{url}/directoryObjects"

    check_request_attributes(directory_objects, _type="query_param")
    check_request_attributes(directory_objects, _type="method")


def test_directory_object(
    directory_objects: DirectoryObjects, url: str, check_request_attributes: Callable
) -> None:

    obj = directory_objects.by_id("12345")

    assert obj.url == f"{url}/directoryObjects/12345"

    check_request_attributes(obj, _type="query_param")
    check_request_attributes(obj, _type="method")


def test_directory_object_ref(
    directory_objects: DirectoryObjects, url: str, check_request_attributes: Callable
) -> None:

    obj = directory_objects.by_id("12345").ref

    assert obj.url == f"{url}/directoryObjects/12345/$ref"

    check_request_attributes(obj, _type="query_param")
    check_request_attributes(obj, _type="method")
