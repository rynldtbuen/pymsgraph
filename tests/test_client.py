from typing import TYPE_CHECKING

import httpx
import pytest

if TYPE_CHECKING:
    from tests.conftest import MakeClient


@pytest.mark.asyncio
async def test_client_counts_requests_for_all_http_helpers(
    make_client: "MakeClient",
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/content"):
            return httpx.Response(200, content=b"content")
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"ok": True})

    client, _ = make_client(handler)

    assert client.requests_sent == 0

    await client.get("/users")
    await client.post("/users", body={"displayName": "Alice"})
    await client.put("/users/u1", body={"displayName": "Alice"})
    await client.patch("/users/u1", body={"displayName": "Alice"})
    await client.delete("/users/u1")
    await client.get_content("/drives/d1/items/i1/content")

    assert client.requests_sent == 6


@pytest.mark.asyncio
async def test_client_request_counter_can_reset(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    client, _ = make_client(handler)

    await client.get("/users")
    assert client.requests_sent == 1

    client.reset_requests_sent()
    assert client.requests_sent == 0

    await client.get("/groups")
    assert client.requests_sent == 1


@pytest.mark.asyncio
async def test_client_counts_failed_requests(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "Bad request"}})

    client, _ = make_client(handler)

    with pytest.raises(httpx.HTTPStatusError):
        await client.get("/users")

    assert client.requests_sent == 1
