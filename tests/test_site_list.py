from typing import TYPE_CHECKING
import json
import httpx
import pytest


if TYPE_CHECKING:
    from tests.conftest import MakeClient


@pytest.mark.asyncio
async def test_qs(make_client: "MakeClient"):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path.endswith("/sites/site-123"):
            return httpx.Response(
                200,
                json={"id": "site-123", "displayName": "Demo Site"},
            )
        if request.url.path.endswith("/sites/site-123/lists"):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {"id": "l1", "displayName": "List 1"},
                        {"id": "l2", "displayName": "List 2"},
                    ]
                },
            )
        return httpx.Response(404)

    c, _ = make_client(handler)

    site = await c.sites.get(id="site-123")
    lists = [l async for l in site.lists]  # triggers iteration/fetch

    assert [lst.display_name for lst in lists] == ["List 1", "List 2"]
    assert "/v1.0/sites/site-123" in seen
    assert "/v1.0/sites/site-123/lists" in seen


@pytest.mark.asyncio
async def test_qs_field_items(make_client: "MakeClient"):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/v1.0/sites/s123":
            return httpx.Response(200, json={"id": "s123", "displayName": "Site"})
        if request.url.path == "/v1.0/sites/s123/lists":
            return httpx.Response(
                200, json={"value": [{"id": "l1", "displayName": "List 1"}]}
            )
        if request.url.path == "/v1.0/sites/s123/lists/l1/items":
            return httpx.Response(
                200, json={"value": [{"id": "i1", "fields": {"Title": "Item 1"}}]}
            )
        return httpx.Response(404)

    c, _ = make_client(handler)
    site = await c.sites.get(id="s123")
    lists = [l async for l in site.lists]
    assert lists[0].id == "l1"
    items = lists[0].items
    assert items.path == "/sites/s123/lists/l1/items"
    assert [it.id async for it in items] == ["i1"]
    assert "/v1.0/sites/s123" in seen
    assert "/v1.0/sites/s123/lists" in seen
    assert "/v1.0/sites/s123/lists/l1/items" in seen


@pytest.mark.asyncio
async def test_qs_filter(make_client: "MakeClient"):
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url))
        if request.url.path == "/v1.0/sites/s123":
            return httpx.Response(200, json={"id": "s123", "displayName": "Site"})
        if request.url.path == "/v1.0/sites/s123/lists":
            # Should receive $filter query (encoded as %24filter)
            q = request.url.query
            if isinstance(q, bytes):
                q = q.decode()
                assert "%24filter" in q
                # decode percent-encoding to inspect the filter clause
                from urllib.parse import unquote_plus

                decoded = unquote_plus(q)
                assert "displayName eq 'Target'" in decoded
            return httpx.Response(
                200,
                json={"value": [{"id": "l1", "displayName": "Target"}]},
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    site = await client.sites.get(id="s123")

    qs = site.lists.filter(display_name="Target")
    results = [it async for it in qs]

    assert [lst.display_name for lst in results] == ["Target"]
    assert any("/v1.0/sites/s123/lists" in u for u in captured)


@pytest.mark.asyncio
async def test_field_items(make_client: "MakeClient"):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/v1.0/sites/s123":
            return httpx.Response(200, json={"id": "s123", "displayName": "Site"})
        if request.url.path == "/v1.0/sites/s123/lists":
            return httpx.Response(
                200, json={"value": [{"id": "l1", "displayName": "List 1"}]}
            )
        if request.url.path == "/v1.0/sites/s123/lists/l1/items":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {"id": "i1", "fields": {"Title": "Item 1"}},
                        {"id": "i2", "fields": {"Title": "Item 2"}},
                    ]
                },
            )
        if request.url.path == "/v1.0/sites/s123/lists/l1/items/i2":
            return httpx.Response(200, json={"id": "i2", "fields": {"Title": "Item 2"}})
        return httpx.Response(404)

    client, _ = make_client(handler)
    site = await client.sites.get(id="s123")
    lst = await anext(aiter(site.lists))

    # Iterate items
    items = [it async for it in lst.items]
    assert [it.id for it in items] == ["i1", "i2"]

    # Use queryset.get on items
    item = await lst.items.get(id="i2")
    print(item._graph_data)
    assert item.id == "i2"
    assert item.fields["Title"] == "Item 2"

    # Test dirty fields
    item.fields["Title"] = "Title Item 2"
    assert "Title" in item.fields._dirty

    assert "/v1.0/sites/s123/lists/l1/items/i2" in seen
    assert "/v1.0/sites/s123/lists/l1/items" in seen


@pytest.mark.asyncio
async def test_field_items_fieldvalueset_update(make_client: "MakeClient"):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": request.content,
            }
        )
        if request.method == "GET":
            if request.url.path == "/v1.0/sites/s123":
                return httpx.Response(200, json={"id": "s123", "displayName": "Site"})
            if request.url.path == "/v1.0/sites/s123/lists":
                return httpx.Response(
                    200, json={"value": [{"id": "list1", "displayName": "List 1"}]}
                )
            if request.url.path == "/v1.0/sites/s123/lists/list1/items/item1":
                return httpx.Response(
                    200,
                    json={"id": "item1", "fields": {"Title": "Old", "Number": 1}},
                )
        if request.method == "PATCH":
            assert request.url.path == "/v1.0/sites/s123/lists/list1/items/item1/fields"
            return httpx.Response(204)
        return httpx.Response(404)

    client, _ = make_client(handler)
    site = await client.sites.get(id="s123")
    lst = await anext(aiter(site.lists))
    item = await lst.items.get(id="item1")

    item.fields["Title"] = "New Title"
    item.fields["Number"] = 2
    await item.fields.update()

    # Expect multiple GETs (site, lists, item) then a PATCH
    assert any(entry["method"] == "PATCH" for entry in seen)
    patch_entry = next(e for e in seen if e["method"] == "PATCH")
    assert patch_entry["path"] == "/v1.0/sites/s123/lists/list1/items/item1/fields"
    body = patch_entry["body"]
    if isinstance(body, bytes):
        import json as _json

        payload = _json.loads(body)
    else:
        payload = body
    assert payload["Title"] == "New Title"
    assert payload["Number"] == 2


@pytest.mark.asyncio
async def test_field_items_qs_create(make_client: "MakeClient"):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": request.content,
            }
        )
        if request.method == "GET":
            if request.url.path == "/v1.0/sites/s123":
                return httpx.Response(200, json={"id": "s123", "displayName": "Site"})
            if request.url.path == "/v1.0/sites/s123/lists":
                return httpx.Response(
                    200, json={"value": [{"id": "list1", "displayName": "List 1"}]}
                )
        if request.method == "POST":
            assert request.url.path == "/v1.0/sites/s123/lists/list1/items"
            return httpx.Response(
                201,
                json={"id": "new-item", "fields": {"Title": "Created", "Number": 10}},
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    site = await client.sites.get(id="s123")
    lst = await anext(aiter(site.lists))

    item = await lst.items.create(fields={"Title": "Created", "Number": 10})

    assert item.id == "new-item"
    # Expect POST captured
    assert any(e["method"] == "POST" and e["path"].endswith("/items") for e in seen)


@pytest.mark.asyncio
async def test_field_items_qs_create_many(make_client: "MakeClient"):
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": request.content,
            }
        )
        if request.method == "GET":
            if request.url.path == "/v1.0/sites/s123":
                return httpx.Response(200, json={"id": "s123"})
            if request.url.path == "/v1.0/sites/s123/lists":
                return httpx.Response(
                    200, json={"value": [{"id": "list1", "displayName": "List 1"}]}
                )
        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            payload = json.loads(request.content.decode())
            reqs = payload.get("requests") or []
            assert len(reqs) == 2
            assert reqs[0]["method"] == "POST"
            assert reqs[0]["url"] == "/sites/s123/lists/list1/items"
            assert reqs[0]["body"] == {"fields": {"Title": "Created A"}}
            assert reqs[1]["method"] == "POST"
            assert reqs[1]["url"] == "/sites/s123/lists/list1/items"
            assert reqs[1]["body"] == {
                "fields": {"Title": "Created B", "Number": 2}
            }
            return httpx.Response(
                200,
                json={
                    "responses": [
                        {
                            "id": "1",
                            "status": 201,
                            "body": {"id": "i1", "fields": {"Title": "Created A"}},
                        },
                        {
                            "id": "2",
                            "status": 201,
                            "body": {
                                "id": "i2",
                                "fields": {"Title": "Created B", "Number": 2},
                            },
                        },
                    ]
                },
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    site = await client.sites.get(id="s123")
    lst = await anext(aiter(site.lists))

    created_qs = await lst.items.create_many(
        {"Title": "Created A"},
        {"fields": {"Title": "Created B", "Number": 2}},
    )
    created = [i async for i in created_qs]

    assert [item.id for item in created] == ["i1", "i2"]
    assert any(
        e["method"] == "POST" and e["path"] == "/v1.0/$batch" for e in captured
    )


@pytest.mark.asyncio
async def test_field_items_qs_update_dirty_fields(make_client: "MakeClient"):
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": request.content,
            }
        )
        if request.method == "GET":
            if request.url.path == "/v1.0/sites/s123":
                return httpx.Response(200, json={"id": "s123"})
            if request.url.path == "/v1.0/sites/s123/lists":
                return httpx.Response(
                    200, json={"value": [{"id": "list1", "displayName": "List 1"}]}
                )
            if request.url.path == "/v1.0/sites/s123/lists/list1/items":
                return httpx.Response(
                    200,
                    json={
                        "value": [
                            {"id": "i1", "fields": {"Title": "Item 1"}},
                            {"id": "i2", "fields": {"Number": 1}},
                        ]
                    },
                )
        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            payload = json.loads(request.content.decode())
            reqs = payload.get("requests") or []
            assert len(reqs) == 2
            assert reqs[0]["method"] == "PATCH"
            assert reqs[0]["url"] == "/sites/s123/lists/list1/items/i1/fields"
            assert reqs[0]["body"] == {"Title": "Updated 1"}
            assert reqs[1]["method"] == "PATCH"
            assert reqs[1]["url"] == "/sites/s123/lists/list1/items/i2/fields"
            assert reqs[1]["body"] == {"Number": 2}
            return httpx.Response(
                200,
                json={
                    "responses": [
                        {"id": "1", "status": 204},
                        {"id": "2", "status": 204},
                    ]
                },
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    site = await client.sites.get(id="s123")
    lst = await anext(aiter(site.lists))
    items_qs = lst.items

    items = [it async for it in items_qs]
    items[0].fields["Title"] = "Updated 1"
    items[1].fields["Number"] = 2

    updated = await items_qs.update()

    assert updated == 2
    assert any(
        e["method"] == "POST" and e["path"] == "/v1.0/$batch" for e in captured
    )


@pytest.mark.asyncio
async def test_field_items_qs_update_with_fields(make_client: "MakeClient"):
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": request.content,
            }
        )
        if request.method == "GET":
            if request.url.path == "/v1.0/sites/s123":
                return httpx.Response(200, json={"id": "s123"})
            if request.url.path == "/v1.0/sites/s123/lists":
                return httpx.Response(
                    200, json={"value": [{"id": "list1", "displayName": "List 1"}]}
                )
            if request.url.path == "/v1.0/sites/s123/lists/list1/items":
                return httpx.Response(
                    200,
                    json={
                        "value": [
                            {"id": "i1", "fields": {"Title": "Item 1"}},
                            {"id": "i2", "fields": {"Title": "Item 2"}},
                        ]
                    },
                )
        if request.method == "POST" and request.url.path == "/v1.0/$batch":
            payload = json.loads(request.content.decode())
            reqs = payload.get("requests") or []
            assert len(reqs) == 2
            assert reqs[0]["method"] == "PATCH"
            assert reqs[0]["url"] == "/sites/s123/lists/list1/items/i1/fields"
            assert reqs[0]["body"] == {"Title": "Bulk Updated"}
            assert reqs[1]["method"] == "PATCH"
            assert reqs[1]["url"] == "/sites/s123/lists/list1/items/i2/fields"
            assert reqs[1]["body"] == {"Title": "Bulk Updated"}
            return httpx.Response(
                200,
                json={
                    "responses": [
                        {"id": "1", "status": 204},
                        {"id": "2", "status": 204},
                    ]
                },
            )
        return httpx.Response(404)

    client, _ = make_client(handler)
    site = await client.sites.get(id="s123")
    lst = await anext(aiter(site.lists))
    items_qs = lst.items

    updated = await items_qs.update(fields={"Title": "Bulk Updated"})

    assert updated == 2
    assert any(
        e["method"] == "POST" and e["path"] == "/v1.0/$batch" for e in captured
    )

@pytest.mark.asyncio
async def test_site_by_path_list_by_name(make_client: "MakeClient"):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/v1.0/sites/root":
            return httpx.Response(
                200,
                json={"siteCollection": {"hostname": "contoso.sharepoint.com"}},
            )
        return httpx.Response(
            200,
            json={"value": [{"id": "i1"}, {"id": "i2"}]},
        )

    client, _ = make_client(handler)

    items = client.sites.by_path("/sites/TestSite").lists.by_name("Test List").items
    async for it in items:
        ...
    assert (
        items.path
        == "/sites/contoso.sharepoint.com:/sites/TestSite:/lists/Test%20List/items"
    )
    assert [i.id async for i in items] == ["i1", "i2"]
    assert seen == [
        "/v1.0/sites/root",
        "/v1.0/sites/contoso.sharepoint.com:/sites/TestSite:/lists/Test List",
        "/v1.0/sites/contoso.sharepoint.com:/sites/TestSite:/lists/Test List/items",
    ]


@pytest.mark.asyncio
async def test_list_get_rewrites_name_path(make_client: "MakeClient"):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/v1.0/sites/root":
            return httpx.Response(
                200,
                json={"siteCollection": {"hostname": "contoso.sharepoint.com"}},
            )
        if (
            request.url.path
            == "/v1.0/sites/contoso.sharepoint.com:/sites/TestSite:/lists/Test List"
        ):
            return httpx.Response(
                200,
                json={"id": "list1", "displayName": "Test List"},
            )
        return httpx.Response(404)

    client, _ = make_client(handler)

    lst = await client.sites.by_path("/sites/TestSite").lists.by_name("Test List").get()

    assert lst.id == "list1"
    assert lst.path == "/sites/contoso.sharepoint.com:/sites/TestSite:/lists/list1"
    assert seen == [
        "/v1.0/sites/root",
        "/v1.0/sites/contoso.sharepoint.com:/sites/TestSite:/lists/Test List",
    ]


@pytest.mark.asyncio
async def test_list_items_resolve_list_id_first(make_client: "MakeClient"):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/v1.0/sites/root":
            return httpx.Response(
                200,
                json={"siteCollection": {"hostname": "contoso.sharepoint.com"}},
            )
        if (
            request.url.path
            == "/v1.0/sites/contoso.sharepoint.com:/sites/TestSite:/lists/Test List"
        ):
            return httpx.Response(200, json={"id": "list1"})
        if (
            request.url.path
            == "/v1.0/sites/contoso.sharepoint.com:/sites/TestSite:/lists/list1/items"
        ):
            return httpx.Response(200, json={"value": [{"id": "i1"}]})
        return httpx.Response(404)

    client, _ = make_client(handler)

    items = (
        client.sites.by_path("/sites/TestSite").lists.by_name("Test List").items
    )
    assert [i.id async for i in items] == ["i1"]
    assert seen == [
        "/v1.0/sites/root",
        "/v1.0/sites/contoso.sharepoint.com:/sites/TestSite:/lists/Test List",
        "/v1.0/sites/contoso.sharepoint.com:/sites/TestSite:/lists/list1/items",
    ]


# @pytest.mark.asyncio
# async def test_list_item_delete_requires_force(make_client: "MakeClient"):
#     def handler(request: httpx.Request) -> httpx.Response:
#         if request.method == "GET":
#             if request.url.path == "/v1.0/sites/s123":
#                 return httpx.Response(200, json={"id": "s123", "displayName": "Site"})
#             if request.url.path == "/v1.0/sites/s123/lists":
#                 return httpx.Response(
#                     200, json={"value": [{"id": "list1", "displayName": "List 1"}]}
#                 )
#             if request.url.path == "/v1.0/sites/s123/lists/list1/items/item1":
#                 return httpx.Response(
#                     200, json={"id": "item1", "fields": {"Title": "Old"}}
#                 )
#         if request.method == "DELETE":
#             return httpx.Response(204)
#         return httpx.Response(404)

#     client, _ = make_client(handler)
#     site = await client.sites.get(id="s123")
#     lst = await anext(aiter(site.lists))
#     item = await lst.items.get(id="item1")

#     with pytest.raises(RuntimeError):
#         await item.delete()

#     # with force=True it should delete
#     await item.delete(force=True)
