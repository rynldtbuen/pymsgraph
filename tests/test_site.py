from typing import TYPE_CHECKING
import httpx
import pytest

from pymsgraph.models.query import Q

if TYPE_CHECKING:
    from .conftest import MakeClient


@pytest.mark.asyncio
async def test_get_by_id(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1.0/sites/site-id"
        return httpx.Response(
            200,
            json={
                "id": "site-id",
                "displayName": "Demo Site",
                "webUrl": "https://contoso.sharepoint.com/sites/demo",
            },
        )

    c, r = make_client(handler)
    site = await c.sites.get(id="site-id")

    assert site.id == "site-id"
    assert site.display_name == "Demo Site"
    assert len(r) == 1


@pytest.mark.asyncio
async def test_get_by_path_discovers_hostname_once(make_client: "MakeClient"):
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/v1.0/sites/root":
            return httpx.Response(
                200,
                json={"siteCollection": {"hostname": "contoso.sharepoint.com"}},
            )
        assert request.url.path in {
            "/v1.0/sites/contoso.sharepoint.com:/sites/demo",
            "/v1.0/sites/contoso.sharepoint.com:/sites/other",
        }
        return httpx.Response(
            200,
            json={
                "id": "site-path",
                "displayName": "Path Site",
            },
        )

    c, r = make_client(handler)

    first = await c.sites.get(path="/sites/demo")
    second = await c.sites.get(path="sites/other")

    assert first.id == "site-path"
    assert second.id == "site-path"
    # One discovery call plus two path fetches
    assert seen_paths.count("/v1.0/sites/root") == 1
    assert len(r) == 3


@pytest.mark.asyncio
async def test_get_invalid_args(make_client: "MakeClient"):
    c, _ = make_client(lambda req: httpx.Response(200, json={}))

    with pytest.raises(ValueError):
        await c.sites.get()


def test_search(make_client: "MakeClient"):
    c, _ = make_client(lambda req: httpx.Response(200, json={"value": []}))
    qs = c.sites
    searched = qs.search(keyword="teams")

    assert searched is not qs
    assert searched._params.get("search") == "teams"
    assert searched._headers.get("ConsistencyLevel") == "eventual"


# @pytest.mark.asyncio
# async def test_site_lists_descriptor(make_client: "MakeClient"):
#     def handler(request: httpx.Request) -> httpx.Response:
#         if request.url.path.endswith("/lists"):
#             return httpx.Response(
#                 200,
#                 json={
#                     "value": [
#                         {"id": "l1", "displayName": "List 1"},
#                         {"id": "l2", "displayName": "List 2"},
#                     ]
#                 },
#             )
#         return httpx.Response(
#             200,
#             json={
#                 "id": "site-id",
#                 "displayName": "Demo Site",
#                 "webUrl": "https://contoso.sharepoint.com/sites/demo",
#             },
#         )

#     c, _ = make_client(handler)
#     s = await c.sites.get(id="site-id")

#     lists_qs = s.lists
#     assert lists_qs.path.endswith("/sites/site-id/lists")

#     names = [lst.display_name async for lst in lists_qs]
#     assert names == ["List 1", "List 2"]
