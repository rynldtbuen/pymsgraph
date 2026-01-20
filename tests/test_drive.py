from typing import TYPE_CHECKING
import httpx
import pytest

from pymsgraph.models.drive import Drive, DriveItem
from pymsgraph.models.user import User

if TYPE_CHECKING:
    from .conftest import MakeClient


def test_path():
    drive = Drive(id="123")
    items = drive.root.items
    assert items.path == "/drives/123/root/children"
    assert drive.by_path(path="/abc/def").path == "/drives/123/root:/abc/def"
    assert drive.by_path("/abc/def").items.path == "/drives/123/root:/abc/def:/children"

    item = DriveItem(id="098", path="/drives/123/items")
    assert item.path == "/drives/123/items/098"
    assert item.items.path == "/drives/123/items/098/children"
    assert DriveItem(id="765", path="/drives/123/items").path == "/drives/123/items/765"
    assert (
        DriveItem(id="765", path="/drives/123/items").by_path("/abc/def").path
        == "/drives/123/items/765:/abc/def"
    )
    assert (
        DriveItem(id="765", path="/drives/123/items").by_path("/abc/def").items.path
        == "/drives/123/items/765:/abc/def:/children"
    )

    # DriveItemsQueryset does not support by_path chaining

    items = User(id="123").drive.root.items

    assert items.path == "/users/123/drive/root/children"
    assert (
        DriveItem(id="098", path="/users/123/drive/items").path
        == "/users/123/drive/items/098"
    )
    assert (
        DriveItem(id="098", path="/users/123/drive/items").items.path
        == "/users/123/drive/items/098/children"
    )
    assert (
        DriveItem(id="098", path="/users/123/drive/items").by_path("/abc/def").path
        == "/users/123/drive/items/098:/abc/def"
    )
    assert (
        DriveItem(id="098", path="/users/123/drive/items")
        .by_path("/abc/def")
        .items.path
        == "/users/123/drive/items/098:/abc/def:/children"
    )

    assert (
        User(id="123").drive.by_path("/abc/def").path
        == "/users/123/drive/root:/abc/def"
    )
    assert (
        User(id="123").drive.by_path("/abc/def").items.path
        == "/users/123/drive/root:/abc/def:/children"
    )

    User(id="123").drive.by_path("/123/456")


@pytest.mark.asyncio
async def test_user_drive_get_by_id(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/users/u1":
            return httpx.Response(200, json={"id": "u1"})
        if request.url.path == "/v1.0/users/u1/drive":
            return httpx.Response(
                200,
                json={
                    "id": "drive123",
                    "name": "Demo Drive",
                    "driveType": "documentLibrary",
                    "webUrl": "https://contoso.sharepoint.com/drives/drive123",
                },
            )
        return httpx.Response(404)

    client, _ = make_client(handler)

    user = await client.users.get(id="u1")
    data = await client.get(user.drive.path)
    drive = Drive.from_graph(data, client=client, path=user.drive.path)

    assert drive.id == "drive123"
    assert drive.name == "Demo Drive"


@pytest.mark.asyncio
async def test_user_driveitems_get_by_id(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/users/u1":
            return httpx.Response(200, json={"id": "u1"})
        if request.url.path == "/v1.0/users/u1/drive/items/item123":
            return httpx.Response(
                200,
                json={
                    "id": "item123",
                    "name": "Doc1",
                    "webUrl": "https://contoso.sharepoint.com/doc1",
                    "size": 1024,
                    "file": {},
                },
            )
        return httpx.Response(404)

    client, _ = make_client(handler)

    user = await client.users.get(id="u1")
    item_ref = DriveItem(id="item123", path="/users/u1/drive/items")
    data = await client.get(item_ref.path)
    item = DriveItem.from_graph(data, client=client, path=item_ref.path)

    assert item.id == "item123"
    assert item.name == "Doc1"


@pytest.mark.asyncio
async def test_user_driveitems_get_by_path(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/users/u1":
            return httpx.Response(200, json={"id": "u1"})
        if request.url.path == "/v1.0/users/u1/drive/root:/Reports/2024.xlsx":
            return httpx.Response(
                200,
                json={
                    "id": "itemXYZ",
                    "name": "2024.xlsx",
                    "webUrl": "https://contoso.sharepoint.com/reports/2024.xlsx",
                    "size": 2048,
                    "file": {},
                },
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    user = await client.users.get(id="u1")
    item_ref = user.drive.by_path("/Reports/2024.xlsx")
    data = await client.get(item_ref.path)
    item = DriveItem.from_graph(data, client=client, path=item_ref.path)

    assert item.id == "itemXYZ"
    assert item.name == "2024.xlsx"


@pytest.mark.asyncio
async def test_driveitem_children(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/users/u1":
            return httpx.Response(200, json={"id": "u1"})
        if request.url.path == "/v1.0/users/u1/drive/items/item123/children":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {"id": "child1", "name": "DocA", "file": {}},
                        {"id": "child2", "name": "DocB", "file": {}},
                    ]
                },
            )
        return httpx.Response(404)

    c, _ = make_client(handler)
    u = await c.users.get(id="u1")
    children = [c.id async for c in u.drive.root.by_id("item123").items]

    assert children == ["child1", "child2"]


@pytest.mark.asyncio
async def test_user_drive_root_items(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/users/u1":
            return httpx.Response(200, json={"id": "u1"})
        if request.url.path == "/v1.0/users/u1/drive/root/children":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {"id": "item1", "name": "Folder", "folder": {}},
                        {"id": "item2", "name": "File.docx", "file": {}},
                    ]
                },
            )
        return httpx.Response(404)

    c, _ = make_client(handler)
    u = await c.users.get(id="u1")
    items = [i.id async for i in u.drive.root.items]
    assert items == ["item1", "item2"]


@pytest.mark.asyncio
async def test_driveitem_upload(make_client: "MakeClient"):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": request.content,
                "headers": dict(request.headers),
            }
        )
        if request.url.path == "/v1.0/users/u1/drive/items/folder1:/hello.txt:/content":
            assert request.method == "PUT"
            return httpx.Response(
                201,
                json={"id": "file1", "name": "hello.txt", "size": 5, "file": {}},
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    folder = DriveItem.from_graph(
        {"id": "folder1", "name": "Folder", "folder": {"childCount": 0}},
        client=client,
        path="/users/u1/drive/items",
    )

    uploaded = await folder.upload("hello.txt", b"hello")

    assert isinstance(uploaded, DriveItem)
    assert any(
        entry["method"] == "PUT"
        and entry["path"] == "/v1.0/users/u1/drive/items/folder1:/hello.txt:/content"
        for entry in seen
    )


@pytest.mark.asyncio
async def test_driveitem_upload_from_path(make_client: "MakeClient", tmp_path):
    seen = []

    file_path = tmp_path / "hello.txt"
    file_path.write_text("hello from path", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": request.content,
            }
        )
        if request.url.path == "/v1.0/users/u1/drive/items/folder1:/hello.txt:/content":
            assert request.method == "PUT"
            assert request.content == b"hello from path"
            return httpx.Response(
                201,
                json={"id": "file1", "name": "hello.txt", "size": 15, "file": {}},
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    folder = DriveItem.from_graph(
        {"id": "folder1", "name": "Folder", "folder": {"childCount": 0}},
        client=client,
        path="/users/u1/drive/items",
    )

    uploaded = await folder.upload(file_path=str(file_path))

    assert isinstance(uploaded, DriveItem)
    assert any(
        entry["method"] == "PUT"
        and entry["path"] == "/v1.0/users/u1/drive/items/folder1:/hello.txt:/content"
        for entry in seen
    )


@pytest.mark.asyncio
async def test_driveitem_copy(make_client: "MakeClient"):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": request.content,
            }
        )
        if request.url.path == "/v1.0/users/u1/drive/items/item123/copy":
            assert request.method == "POST"
            return httpx.Response(
                200,
                json={"id": "copy123", "name": "Doc1-copy", "file": {}},
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    item = DriveItem.from_graph(
        {"id": "item123", "name": "Doc1", "file": {}},
        client=client,
        path="/users/u1/drive/items",
    )

    copied = await item.copy(name="Doc1-copy", parent_id="destFolder")

    assert isinstance(copied, DriveItem)
    assert any(
        entry["method"] == "POST"
        and entry["path"] == "/v1.0/users/u1/drive/items/item123/copy"
        for entry in seen
    )


@pytest.mark.asyncio
async def test_driveitem_copy_with_parent_item(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/users/u1/drive/items/item123/copy":
            return httpx.Response(
                200,
                json={"id": "copy123", "name": "Doc1-copy", "file": {}},
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    parent = DriveItem.from_graph(
        {"id": "parentFolder", "name": "Dest", "folder": {}},
        client=client,
        path="/users/u1/drive/items",
    )
    item = DriveItem.from_graph(
        {"id": "item123", "name": "Doc1", "file": {}},
        client=client,
        path="/users/u1/drive/items",
    )

    copied = await item.copy(parent_item=parent, drive_id="drive123")

    assert isinstance(copied, DriveItem)


@pytest.mark.asyncio
async def test_driveitem_move(make_client: "MakeClient"):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": request.content,
            }
        )
        if request.url.path == "/v1.0/users/u1/drive/items/item123":
            if request.method == "PATCH":
                return httpx.Response(
                    200, json={"id": "item123", "name": "Doc1", "file": {}}
                )
        return httpx.Response(404)

    client, _ = make_client(handler)
    dest = DriveItem.from_graph(
        {"id": "destFolder", "name": "Dest", "folder": {}},
        client=client,
        path="/users/u1/drive/items",
    )
    item = DriveItem.from_graph(
        {"id": "item123", "name": "Doc1", "file": {}},
        client=client,
        path="/users/u1/drive/items",
    )

    moved = await item.move(parent_item=dest, drive_id="drive123")

    assert isinstance(moved, DriveItem)
    assert any(
        entry["method"] == "PATCH"
        and entry["path"] == "/v1.0/users/u1/drive/items/item123"
        for entry in seen
    )


@pytest.mark.asyncio
async def test_driveitem_download(make_client: "MakeClient", tmp_path):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/v1.0/users/u1/drive/items/file1/content":
            return httpx.Response(200, content=b"hello")
        return httpx.Response(404)

    client, _ = make_client(handler)
    item = DriveItem.from_graph(
        {"id": "file1", "name": "file1.txt", "file": {}},
        client=client,
        path="/users/u1/drive/items",
    )

    dest = tmp_path / "file1.txt"
    data = await item.download(dest_path=dest)

    assert data == b"hello"
    assert dest.read_bytes() == b"hello"
    assert "/v1.0/users/u1/drive/items/file1/content" in seen


@pytest.mark.asyncio
async def test_driveitem_get_site_path(make_client: "MakeClient"):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/v1.0/sites/contoso.sharepoint.com:/sites/Test:/drive":
            return httpx.Response(
                200,
                json={
                    "id": "drive123",
                    "name": "Test Drive",
                    "driveType": "documentLibrary",
                },
            )
        if request.url.path == "/v1.0/drives/drive123/root:/Shared":
            return httpx.Response(
                200,
                json={"id": "item1", "name": "Shared", "folder": {}},
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    item = DriveItem(
        client=client,
        path="/sites/contoso.sharepoint.com:/sites/Test:/drive/root:/Shared",
    )

    resolved = await item.get()

    assert resolved.id == "item1"
    assert resolved.name == "Shared"
    assert resolved.path == "/drives/drive123/items/item1"
    assert "/v1.0/sites/contoso.sharepoint.com:/sites/Test:/drive" in seen
    assert "/v1.0/drives/drive123/root:/Shared" in seen
