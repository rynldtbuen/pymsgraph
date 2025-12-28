from typing import TYPE_CHECKING
import httpx
import pytest

from pymsgraph.models.drive import Drive, DriveItem

if TYPE_CHECKING:
    from .conftest import MakeClient


def test_client_drives_get_by_id(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/drives/drive123":
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

    drive = client.drives.get(id="drive123")
    assert isinstance(drive, Drive)
    assert drive.id == "drive123"
    assert drive.name == "Demo Drive"


def test_client_driveitems_get_by_id(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/drives/drive123":
            return httpx.Response(
                200,
                json={
                    "id": "drive123",
                    "name": "Demo Drive",
                    "driveType": "documentLibrary",
                },
            )
        if request.url.path == "/v1.0/drives/drive123/items/item123":
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

    drive = client.drives.get(id="drive123")
    item = drive.items.get(id="item123")  # type: ignore[attr-defined]
    assert isinstance(item, DriveItem)
    assert item.id == "item123"
    assert item.name == "Doc1"


def test_client_driveitems_get_by_path(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/drives/drive123":
            return httpx.Response(
                200,
                json={
                    "id": "drive123",
                    "name": "Demo Drive",
                    "driveType": "documentLibrary",
                },
            )
        if request.url.path == "/v1.0/drives/drive123/root:/Reports/2024.xlsx":
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
    drive = client.drives.get(id="drive123")
    item = drive.items.get(path="/Reports/2024.xlsx")  # type: ignore[attr-defined]

    assert isinstance(item, DriveItem)
    assert item.id == "itemXYZ"
    assert item.name == "2024.xlsx"


def test_driveitem_children(make_client: "MakeClient"):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/v1.0/drives/drive123":
            return httpx.Response(
                200,
                json={
                    "id": "drive123",
                    "name": "Demo Drive",
                    "driveType": "documentLibrary",
                },
            )
        if request.url.path == "/v1.0/drives/drive123/items/item123":
            return httpx.Response(
                200,
                json={
                    "id": "item123",
                    "name": "Folder",
                    "folder": {},
                    "webUrl": "https://contoso.sharepoint.com/folder",
                },
            )
        if request.url.path == "/v1.0/drives/drive123/items/item123/children":
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

    client, _ = make_client(handler)
    drive = client.drives.get(id="drive123")
    item = drive.items.get(id="item123")  # type: ignore[attr-defined]

    children = item.children
    assert children._parent is item

    assert [c.id for c in children] == ["child1", "child2"]
    assert "/v1.0/drives/drive123/items/item123/children" in seen


def test_site_drive_items(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/sites/s123":
            return httpx.Response(200, json={"id": "s123", "displayName": "Site"})
        if request.url.path == "/v1.0/sites/s123/drive":
            return httpx.Response(
                200,
                json={
                    "id": "drive-site",
                    "name": "Site Drive",
                    "driveType": "documentLibrary",
                },
            )
        if request.url.path == "/v1.0/sites/s123/drive/items/itemX":
            return httpx.Response(
                200,
                json={
                    "id": "itemX",
                    "name": "Welcome.docx",
                    "webUrl": "https://contoso.sharepoint.com/sites/s123/welcome.docx",
                    "file": {},
                },
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    site = client.sites.get(id="s123")
    item = site.drive.items.get(id="itemX")  # type: ignore[attr-defined]

    assert isinstance(item, DriveItem)
    assert item.id == "itemX"
    assert item.name == "Welcome.docx"


def test_driveitem_children_create_folder(make_client: "MakeClient"):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": request.content,
            }
        )
        if request.url.path == "/v1.0/drives/drive123":
            return httpx.Response(
                200,
                json={
                    "id": "drive123",
                    "name": "Demo Drive",
                    "driveType": "documentLibrary",
                },
            )
        if request.url.path == "/v1.0/drives/drive123/items/folder1":
            return httpx.Response(
                200,
                json={
                    "id": "folder1",
                    "name": "Folder",
                    "folder": {"childCount": 1024},
                    "webUrl": "https://contoso.sharepoint.com/folder",
                },
            )
        if request.url.path == "/v1.0/drives/drive123/items/folder1/children":
            assert request.method == "POST"
            return httpx.Response(
                201,
                json={
                    "id": "childFolder",
                    "name": "SubFolder",
                    "folder": {},
                },
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    drive = client.drives.get(id="drive123")
    folder = drive.items.get(id="folder1")  # type: ignore[attr-defined]

    child = folder.children.create_folder("SubFolder")  # type: ignore[attr-defined]

    assert isinstance(child, DriveItem)
    assert child.id == "childFolder"
    assert child.name == "SubFolder"
    assert any(
        entry["method"] == "POST" and entry["path"].endswith("/children")
        for entry in seen
    )


def test_driveitem_upload(make_client: "MakeClient"):
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
        if request.url.path == "/v1.0/drives/drive123":
            return httpx.Response(
                200,
                json={
                    "id": "drive123",
                    "name": "Demo Drive",
                    "driveType": "documentLibrary",
                },
            )
        if request.url.path == "/v1.0/drives/drive123/items/folder1":
            return httpx.Response(
                200,
                json={
                    "id": "folder1",
                    "name": "Folder",
                    "folder": {"childCount": 0},
                },
            )
        if (
            request.url.path
            == "/v1.0/drives/drive123/items/folder1:/hello.txt:/content"
        ):
            assert request.method == "PUT"
            return httpx.Response(
                201,
                json={"id": "file1", "name": "hello.txt", "size": 5, "file": {}},
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    drive = client.drives.get(id="drive123")
    folder = drive.items.get(id="folder1")  # type: ignore[attr-defined]

    uploaded = folder.upload("hello.txt", b"hello")  # type: ignore[attr-defined]

    assert uploaded.id == "file1"
    assert uploaded.name == "hello.txt"
    assert any(
        entry["method"] == "PUT"
        and entry["path"] == "/v1.0/drives/drive123/items/folder1:/hello.txt:/content"
        for entry in seen
    )


def test_driveitem_upload_from_path(make_client: "MakeClient", tmp_path):
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
        if request.url.path == "/v1.0/drives/drive123":
            return httpx.Response(
                200,
                json={
                    "id": "drive123",
                    "name": "Demo Drive",
                    "driveType": "documentLibrary",
                },
            )
        if request.url.path == "/v1.0/drives/drive123/items/folder1":
            return httpx.Response(
                200,
                json={
                    "id": "folder1",
                    "name": "Folder",
                    "folder": {"childCount": 0},
                },
            )
        if (
            request.url.path
            == "/v1.0/drives/drive123/items/folder1:/hello.txt:/content"
        ):
            assert request.method == "PUT"
            # body should contain file content
            assert request.content == b"hello from path"
            return httpx.Response(
                201,
                json={"id": "file1", "name": "hello.txt", "size": 15, "file": {}},
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    drive = client.drives.get(id="drive123")
    folder = drive.items.get(id="folder1")

    uploaded = folder.upload(file_path=str(file_path))

    assert uploaded.id == "file1"
    assert uploaded.name == "hello.txt"
    assert any(
        entry["method"] == "PUT"
        and entry["path"] == "/v1.0/drives/drive123/items/folder1:/hello.txt:/content"
        for entry in seen
    )


def test_driveitem_copy(make_client: "MakeClient"):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": request.content,
            }
        )
        if request.url.path == "/v1.0/drives/drive123":
            return httpx.Response(
                200,
                json={
                    "id": "drive123",
                    "name": "Demo Drive",
                    "driveType": "documentLibrary",
                },
            )
        if request.url.path == "/v1.0/drives/drive123/items/item123":
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
        if request.url.path == "/v1.0/drives/drive123/items/item123/copy":
            assert request.method == "POST"
            return httpx.Response(
                200,
                json={"id": "copy123", "name": "Doc1-copy", "file": {}},
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    drive = client.drives.get(id="drive123")
    item = drive.items.get(id="item123")

    copied = item.copy(name="Doc1-copy", parent_id="destFolder")

    assert copied.id == "copy123"
    assert copied.name == "Doc1-copy"
    assert any(
        entry["method"] == "POST" and entry["path"].endswith("/copy") for entry in seen
    )


def test_driveitem_copy_with_parent_item(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/drives/drive123":
            return httpx.Response(
                200,
                json={
                    "id": "drive123",
                    "name": "Demo Drive",
                    "driveType": "documentLibrary",
                },
            )
        if request.url.path == "/v1.0/drives/drive123/items/parentFolder":
            return httpx.Response(
                200,
                json={
                    "id": "parentFolder",
                    "name": "Dest",
                    "folder": {},
                    "parentReference": {"driveId": "drive123"},
                },
            )
        if request.url.path == "/v1.0/drives/drive123/items/item123":
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
        if request.url.path == "/v1.0/drives/drive123/items/item123/copy":
            return httpx.Response(
                200,
                json={"id": "copy123", "name": "Doc1-copy", "file": {}},
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    drive = client.drives.get(id="drive123")
    parent = drive.items.get(id="parentFolder")
    item = drive.items.get(id="item123")

    copied = item.copy(parent_item=parent)

    assert copied.id == "copy123"
    assert copied.name == "Doc1-copy"


def test_driveitem_move(make_client: "MakeClient"):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": request.content,
            }
        )
        if request.url.path == "/v1.0/drives/drive123":
            return httpx.Response(
                200,
                json={
                    "id": "drive123",
                    "name": "Demo Drive",
                    "driveType": "documentLibrary",
                },
            )
        if request.url.path == "/v1.0/drives/drive123/items/item123":
            if request.method == "GET":
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
            if request.method == "PATCH":
                return httpx.Response(
                    200, json={"id": "item123", "name": "Doc1", "file": {}}
                )
        if request.url.path == "/v1.0/drives/drive123/items/destFolder":
            return httpx.Response(
                200,
                json={
                    "id": "destFolder",
                    "name": "Dest",
                    "folder": {},
                    "parentReference": {"driveId": "drive123"},
                },
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    drive = client.drives.get(id="drive123")
    dest = drive.items.get(id="destFolder")
    item = drive.items.get(id="item123")

    moved = item.move(parent_item=dest)

    assert moved.id == "item123"
    assert any(
        entry["method"] == "PATCH" and entry["path"].endswith("item123")
        for entry in seen
    )


def test_driveitem_download(make_client: "MakeClient", tmp_path):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/v1.0/drives/drive123":
            return httpx.Response(
                200,
                json={
                    "id": "drive123",
                    "name": "Demo Drive",
                    "driveType": "documentLibrary",
                },
            )
        if request.url.path == "/v1.0/drives/drive123/items/file1":
            return httpx.Response(
                200,
                json={
                    "id": "file1",
                    "name": "file1.txt",
                    "size": 5,
                    "file": {},
                },
            )
        if request.url.path == "/v1.0/drives/drive123/items/file1/content":
            return httpx.Response(200, content=b"hello")
        return httpx.Response(404)

    client, _ = make_client(handler)
    drive = client.drives.get(id="drive123")
    item = drive.items.get(id="file1")

    dest = tmp_path / "file1.txt"
    data = item.download(dest_path=dest)

    assert data == b"hello"
    assert dest.read_bytes() == b"hello"
    assert "/v1.0/drives/drive123/items/file1/content" in seen


# 6507149
# 6507264,
# 6507306,
# 6507104,
# 6507148,
# 6507168,
# 6507172,
# 6507181,
# 6507202,
# 6507205,
# 6507215,
# 6507219,
# 6507227,
# 6507258,
# 6507273,
# 6507279,
# 6507283,
# 6507287,
# 6507292,
# 6507299,
# 6507303,
# 6507313,
# 6507332,
# 6507337,
# 6507341,
# 6507346,
# 6507088,
# 6507103,
# 6507125,
# 6507147,
# 6507175,
# 6507184,
# 6507192,
# 6507208,
# 6507222,
# 6507231,
# 6507238,
# 6507246,
# 6507252,
# 6507316,
# 6507327,
# 6507353,
# 6507102,
# 6507146,
# 6507101,
# 6507124,
# 6507145,
# 6507100,
# 6507144,
# 6507196,
# 6507123,
# 6507143,
# 6507099,
# 6507142,
# 6507263,
# 6507305,
# 6507098,
# 6507122,
# 6507141,
# 6507167,
# 6507201,
# 6507214,
# 6507226,
# 6507257,
# 6507272,
# 6507278,
# 6507282,
# 6507286,
# 6507291,
# 6507298,
# 6507331,
# 6507336,
# 6507340,
# 6507345,
# 6507087,
# 6507097,
# 6507140,
# 6507174,
# 6507183,
# 6507191,
# 6507207,
# 6507221,
# 6507230,
# 6507237,
# 6507245,
# 6507251,
# 6507315,
# 6507326,
# 6507352,
# 6507096,
# 6507121,
# 6507139,
# 6507095,
# 6507138,
# 6507094,
# 6507120,
# 6507137,
# 6507195,
# 6507136,
# 6507093,
# 6507119,
# 6507135,
# 6507262,
# 6507304,
# 6507092,
# 6507134,
# 6507084,
# 6507085,
# 6507086,
# 6507091,
# 6507118,
# 6507133,
# 6507164,
# 6507165,
# 6507166,
# 6507170,
# 6507171,
# 6507173,
# 6507178,
# 6507179,
# 6507180,
# 6507182,
# 6507187,
# 6507188,
# 6507189,
# 6507190,
# 6507199,
# 6507200,
# 6507204,
# 6507206,
# 6507211,
# 6507212,
# 6507213,
# 6507217,
# 6507218,
# 6507220,
# 6507225,
# 6507229,
# 6507234,
# 6507235,
# 6507236,
# 6507241,
# 6507242,
# 6507243,
# 6507244,
# 6507249,
# 6507250,
# 6507255,
# 6507256,
# 6507260,
# 6507261,
# 6507267,
# 6507268,
# 6507269,
# 6507270,
# 6507271,
# 6507275,
# 6507276,
# 6507277,
# 6507281,
# 6507285,
# 6507289,
# 6507290,
# 6507294,
# 6507295,
# 6507296,
# 6507297,
# 6507301,
# 6507302,
# 6507309,
# 6507310,
# 6507311,
# 6507312,
# 6507314,
# 6507319,
# 6507320,
# 6507321,
# 6507322,
# 6507323,
# 6507324,
# 6507325,
# 6507330,
# 6507334,
# 6507335,
# 6507339,
# 6507343,
# 6507344,
# 6507348,
# 6507349,
# 6507350,
# 6507351,
# 6507356,
# 6507357
